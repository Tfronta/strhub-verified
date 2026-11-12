"""Read a verification log and say what it establishes: nothing more.

Scans the stdout+stderr captured from a build or a run and matches known error
patterns. Each match becomes a structured entry the report embeds: an id, a
severity, a title quoting the line, how often it occurred, examples, and one
sentence on what the log establishes and whose side the class falls on.

That sentence is an observation, not a recipe. STRhub verifies whether a
tool runs as its repository documents it; a diagnostic that told the reader
which flag to add, which pin to relax or which package to install would be
the harness proposing a change to the procedure under test, which is the one
thing it must not do. What the author does with a finding is theirs; what
the log shows is ours to state faithfully. (The JSON key is still
`suggestion`, the name the web reads; its content is the observation.)

Usage (standalone):
  python harness/diagnose_log.py work/log_own.txt [--json diag.json]

As a library:
  from diagnose_log import diagnose
  issues = diagnose(log_text)
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re

# Each rule: (compiled regex, severity, short id, human title, observation).
# The observation is what the matched line establishes, and no more: never an
# instruction to change the command, the recipe or the image.
# Regexes are matched against each line OR the full text (for multi-line).
_RULES: list[tuple[re.Pattern, str, str, str, str]] = []


def _rule(pattern: str, severity: str, rid: str, title: str, observation: str,
          flags: int = re.IGNORECASE):
    _RULES.append((re.compile(pattern, flags), severity, rid, title, observation))


# --- Unrecognized / invalid options -----------------------------------------
_rule(
    r"(?:^|error\b[^\n]{0,40}?|:\s*)unrecognized option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Unrecognized command-line option: --{0}",
    "The program rejected '--{0}' as an option it does not know. The option is "
    "part of the command as cited; nothing was substituted for it.",
)

_rule(
    r"(?:^|error\b[^\n]{0,40}?|:\s*)unknown option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Unknown option: --{0}",
    "The program rejected '--{0}' as an option it does not know. The option is "
    "part of the command as cited.",
)

_rule(
    r"(?:^|error\b[^\n]{0,40}?|:\s*)invalid option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Invalid option: --{0}",
    "The program rejected '--{0}' as an invalid option. The option is part of "
    "the command as cited.",
)

# --- File not found ---------------------------------------------------------
_rule(
    r"(?:file|path)\s+(?:for\s+)?['\"]?(/data/\S+)['\"]?\s+(?:does not exist|not found|doesn'?t exist)",
    "error", "file_not_found",
    "File not found: {0}",
    "The program looked for '{0}' and the container held no such file. Paths "
    "under /data are what STRhub mounts, under names it chooses; any other "
    "path is the command's own.",
)

_rule(
    r"No such file or directory:\s*['\"]?(/data/[^'\"\s]+)",
    "error", "file_not_found",
    "File not found: {0}",
    "The program looked for '{0}' and the container held no such file. Paths "
    "under /data are what STRhub mounts; any other path is the command's own.",
)

_rule(
    r"(?:cannot open|failed to open|unable to open)\s+['\"]?(/\S+)",
    "error", "cannot_open",
    "Cannot open file: {0}",
    "The program could not open '{0}'. This line does not say whether the path, "
    "the permissions or the format was the cause.",
)

# --- BAM/CRAM issues -------------------------------------------------------
_rule(
    r"(?:BAM|CRAM) files? (?:don'?t|do not) contain read groups",
    "error", "no_read_groups",
    "BAM/CRAM missing read groups (@RG)",
    "The program requires read-group (@RG) headers and the input BAM/CRAM carries "
    "none. STRhub's reference slices are mounted as they are; nothing was added "
    "to their headers.",
)

_rule(
    r"(?:not? |in)valid BAM|truncated file|EOF marker is absent",
    "error", "bad_bam",
    "Invalid or truncated BAM file",
    "The program reported the BAM as invalid or truncated. Whether the file or "
    "the reader is at fault is not established by this line; the mounted file's "
    "digest is in the record.",
)

# --- VCF output issues ------------------------------------------------------
_rule(
    r"(?:path|output)\s+.*(?:must end|should end)\s+(?:in|with)\s+\.gz",
    "error", "vcf_gz_required",
    "Output path must end in .gz",
    "The program requires its VCF output path to end in .gz (bgzipped), and the "
    "command as cited names one that does not.",
)

# --- Too few reads / loci skipped ------------------------------------------
_rule(
    r"[Ss]kipp(?:ed|ing)\s+(?:(\d+)\s+)?loci\s+with\s+too\s+few\s+reads|[Ss]kipping\s+(?:region|locus)\s+(?:\S+\s+)?with\s+too\s+few\s+reads",
    "warning", "too_few_reads",
    "Loci skipped (too few reads)",
    "Loci were skipped for having too few reads after the program's own "
    "filtering, at the program's own thresholds. On STRhub's reference slice "
    "this can reflect the sample's coverage at those loci.",
)

_rule(
    r"[Ss]kipping\s+(?:region|locus).*(?:allele\s+)?length\s+exceeds.*(?:threshold|maximum)\s*\((\d+)\s+vs\s+(\d+)\)",
    "warning", "str_too_long",
    "Locus skipped: reference allele too long ({0} vs max {1})",
    "Loci were skipped because their reference allele exceeds the program's "
    "maximum length. The threshold is the program's own and was not changed.",
)

# --- Low base quality filtering (HipSTR specific) --------------------------
_rule(
    r"(\d+)\s+(?:reads\s+)?had low base quality scores",
    "info", "low_bq_reads",
    "Reads filtered by base quality",
    "Reads were removed by the program's base-quality filter, at the program's "
    "own threshold.",
)

# --- No mate pair (BAM slice issue) ----------------------------------------
_rule(
    r"(\d+)\s+(?:reads\s+)?did not have a mate pair",
    "info", "unpaired_reads",
    "Reads filtered (no mate pair)",
    "Reads without a mate pair were filtered by the program. The mates of a "
    "slice's reads can fall outside the sliced region; the slice was mounted "
    "as it is.",
)

# --- Genotyping summary ---------------------------------------------------
_rule(
    r"[Gg]enotyping succeeded for (\d+)/(\d+) loci",
    "info", "genotyping_summary",
    "Genotyping: {0}/{1} loci succeeded",
    "",
)

# --- Permission / segfault / OOM ------------------------------------------
# Word-bounded: apt lists `libsigsegv2` while installing a toolchain, and that
# used to count as a crash in every build log that pulled in autoconf.
_rule(
    r"[Ss]egmentation fault|(?<![\w-])SIGSEGV(?![\w-])|core dump",
    "error", "segfault",
    "Tool crashed (segmentation fault)",
    "The program crashed with a segmentation fault. This line does not establish "
    "whether the input, the build or the program is the cause.",
)

_rule(
    # Written by harness/run_container.sh, not by the tool: the only way a
    # run that hit its limit says so. Nobody's fault by class — a tool that
    # hangs and a limit set too low look the same from here.
    r"STRhub: the run was stopped at the time limit of (\d+) minutes",
    "error", "run_timeout",
    "The run did not finish within its time limit ({0} minutes)",
    "The container was stopped at the run's time limit, the one the recipe "
    "declares (run.timeout_minutes, at most 120). Whether the program hangs or "
    "needs longer on this data is not established here.",
)

_rule(
    r"[Oo]ut of memory|Cannot allocate memory|MemoryError|std::bad_alloc",
    "error", "oom",
    "Out of memory",
    "The program exceeded the automated runner's memory ceiling. That is a limit "
    "of the free environment, not a finding about the program.",
)

_rule(
    r"No space left on device|[Dd]isk quota exceeded",
    "error", "disk_full",
    "Ran out of disk space",
    "The run filled the CI runner's disk. Public runners cap disk space, so a "
    "tool with large intermediate files may not fit the automated environment.",
)

# --- Environment ceilings nobody lifts from a repository --------------------
# These separate "the cited procedure stopped" from "the automated path
# structurally cannot express this tool". See HARNESS_INCOMPATIBLE.

_rule(
    r"[Tt]emporary failure in name resolution|[Cc]ould not resolve host"
    r"|[Nn]ame or service not known|[Nn]etwork is unreachable"
    r"|Failed to establish a new connection|getaddrinfo failed",
    "error", "runtime_network",
    "Network access attempted during the run",
    "The program tried to reach the network while running, with none available. "
    "A pinned verification cannot record or reproduce what would be fetched; a "
    "manual verification can cover it.",
)

_rule(
    r"cannot connect to X server|[Nn]o display name and no \$DISPLAY"
    r"|QXcbConnection|[Cc]annot open display|GtkWindow|TclError: no display",
    "error", "requires_gui",
    "Tool requires a graphical display",
    "The program tried to open a graphical display. The automated runner is "
    "headless, so an interactive step cannot be executed or evidenced here; a "
    "manual verification can cover it.",
)

_rule(
    r"no CUDA-capable device|libcuda\.so.*(?:cannot open|not found)"
    r"|CUDA driver version is insufficient|nvidia-smi.*not found"
    r"|torch\.cuda\.is_available\(\) *(?:is |== *)?False|Found no NVIDIA driver",
    "error", "requires_gpu",
    "Tool requires a GPU",
    "The program needs CUDA hardware. Public CI runners are CPU-only, so this "
    "cannot run on the automated path; a manual verification can cover it.",
)

_rule(
    r"[Ll]icense (?:file )?(?:not found|is invalid|has expired|expired)"
    r"|[Nn]o valid license|FLEXlm|FlexNet|LM_LICENSE_FILE",
    "error", "requires_license",
    "Tool requires a license or licensed data",
    "The program needs a license or licensed reference data that a public "
    "verification run cannot hold; a manual verification can cover it.",
)

_rule(
    r"[Pp]ermission denied",
    "error", "permission_denied",
    "Permission denied",
    "A file or directory could not be accessed. The container runs with every "
    "capability dropped and can write only under /data/out; a write anywhere "
    "else fails this way.",
)

# --- Command not found ------------------------------------------------------
_rule(
    # The shell's own message, and only that. `X: not found` on its own also
    # matched "usage: ... --bams: not found" and "Processing complete: not found
    # any errors", each of which turned a clean run's badge yellow.
    r"(\S+):\s+command not found|exec: ['\"]?([^'\"\s]+)['\"]?: executable file not found|(?:^|/)sh:\s+\d+:\s+(\S+):\s+not found",
    "error", "cmd_not_found",
    "Command not found: {0}",
    "No '{0}' executable was found on the container's PATH. The image is the "
    "one the review admits; nothing was added to it.",
)
# The docker form of cmd_not_found captures in group 2; fold it into group 1 so
# the title, observation and examples read the same either way.
_CMD_NOT_FOUND_FOLD = "cmd_not_found"

# --- Python/runtime errors --------------------------------------------------
_rule(
    r"ModuleNotFoundError:\s+No module named ['\"](\S+)['\"]",
    "error", "missing_module",
    "Python module not found: {0}",
    "The Python module '{0}' is not installed in the image. The image is the one "
    "the review admits; nothing was added to it.",
)

_rule(
    r"ImportError:\s+.*['\"](\S+)['\"]",
    "error", "import_error",
    "Import error: {0}",
    "A library failed to import inside the image. The image is the one the "
    "review admits; nothing was added to it.",
)

_rule(
    # The last line of a Python traceback: what the tool itself raised.
    # NanoRepeat's run ended at its time limit with a numpy TypeError in its
    # log that the report never named: "only 0-dimensional arrays can be
    # converted to Python scalars", a dependency newer than the code.
    # ModuleNotFoundError and ImportError have rules of their own above.
    r"^(?:[\w.]+\.)?((?!ModuleNotFound|Import)\w+(?:Error|Exception)):\s+(.{3,200})$",
    "error", "python_exception",
    "The tool raised {0}: {1}",
    "The traceback before this line in the log shows where in the program it was raised.",
)

# --- Empty output -----------------------------------------------------------
_rule(
    r"Genotyping succeeded for 0/0 loci",
    "error", "zero_genotyped",
    "No loci were genotyped",
    "The program reported no genotyped loci: every locus was filtered out by its "
    "own thresholds, on STRhub's reference slice. Whether coverage or the "
    "program is the cause is not established here.",
)


# --- Build failures (the Installs gate) -------------------------------------
# The build log used to be thrown away, so a tool that failed to build was
# published as "Installs — did not pass" and nothing else: no cause, no side.
# A reader could not tell a dependency that no longer resolves from a base image
# we chose badly, and neither could its author.
#
# These patterns are specific to package managers and compilers, so they do not
# fire on a normal execution log; the same diagnoser reads both.

_rule(
    r"(?:No matching distribution found for|Could not find a version that "
    r"satisfies the requirement)\s+(\S+)",
    "error", "pip_unresolvable",
    "pip cannot resolve a pinned dependency: {0}",
    "pip could not resolve '{0}' as pinned: that version is not on PyPI, or is "
    "incompatible with the base image's Python. The pin is the build's as cited.",
)

_rule(
    r"E: Unable to locate package (\S+)",
    "error", "apt_no_package",
    "apt cannot find a package: {0}",
    "apt found no package '{0}' in the base image's repositories. The name is "
    "the build's as cited.",
)

_rule(
    r"(?:ResolvePackageNotFound|PackagesNotFoundError|UnsatisfiableError)",
    "error", "conda_unsatisfiable",
    "conda could not solve the environment",
    "The declared conda dependencies cannot be satisfied together on this base "
    "image. Bioconda builds trail the newest Python by months, so an environment "
    "that solved when it was written may not solve now.",
)

_rule(
    r"configure(?:\.ac)?: error: required file '([\w./-]+)' not found",
    "error", "autotools_aux_missing",
    "An autotools build is missing its auxiliary file: {0}",
    "configure needs '{0}', which `autoreconf -i` (or `automake --add-missing`) "
    "copies in from the automake package; the build as cited runs autoconf "
    "without installing those files, and was run that way.",
)

_rule(
    r"fatal error:\s+(\S+\.h(?:pp)?):\s+No such file or directory",
    "error", "missing_header",
    "A C/C++ header is missing at build time: {0}",
    "The build needs the development package that provides '{0}', and the image "
    "does not hold it. The build steps were run as cited.",
)

_rule(
    r"(?:COPY failed|ADD failed)[^\n]*|failed to compute cache key[^\n]*not found",
    "error", "build_file_missing",
    "The build referenced a file that is not in the build context",
    "A COPY/ADD line names a file the build context does not hold. The context "
    "is the repository checkout at the pinned commit; a file from the author's "
    "own machine is not in it.",
)

_rule(
    r"unzip:\s+cannot find or open (\S+?),",
    "error", "repo_file_missing",
    "A file the build reads is not in the repository at this commit: {0}",
    "The build reads '{0}' from the checkout, and this commit does not hold it. "
    "Either a documented step that generates or downloads it did not run first, "
    "or the file was added to the repository after this commit.",
)

_rule(
    # `toolimg:ci` is the image the build was meant to produce, not one to pull.
    r"(?:manifest for \S+ not found|manifest unknown|pull access denied for (?!toolimg))",
    "error", "base_image_missing",
    "The base image could not be pulled",
    "The base image named by the Dockerfile could not be pulled from the "
    "registry. A pull that fails says nothing about the program; the run has "
    "to be repeated.",
)

_rule(
    # BuildKit's own line for a RUN step that downloads and fails: STRsearch's
    # Dockerfile fetches USEARCH with a 2019 licence link the server no longer
    # honours (wget exit 8). Nobody's fault by class: a dead link in the
    # repository's build, or a server that was down, look the same here.
    r"process \"/bin/sh -c [^\"]*?\b(?:wget|curl)\b[^\"]*?(https?://[^\s\"]+)[^\"]*\" did not complete successfully",
    "error", "build_download_failed",
    "A download in the build failed: {0}",
    "The build fetches that address and did not get the file. A dead link, a "
    "licence wall and a server that was down look the same here; the address is "
    "the build's as cited.",
)

_rule(
    r"CMake Error: Problem extracting tar:\s*(\S+)",
    "error", "build_download_failed",
    "A download in the build failed: {0}",
    "CMake fetched an external dependency archive that could not be extracted: "
    "the download URL in CMakeLists.txt did not yield an archive.",
)

_rule(
    # Docker Hub's anonymous pull quota is shared by every job on a runner IP.
    # Hitting it says nothing about the image or the tool.
    r"(?:toomanyrequests|You have reached your (?:unauthenticated )?pull rate limit)",
    "error", "registry_rate_limited",
    "The container registry refused the pull (rate limit)",
    "The registry throttled STRhub's runner. This is ours, not the program's: "
    "the run has to be repeated.",
)

_rule(
    r"fatal: (?:reference is not a tree|couldn't find remote ref|"
    r"repository '[^']+' not found)[^\n]*",
    "error", "checkout_failed",
    "The pinned commit could not be checked out",
    "The clone of the public repository at the pinned ref failed: the commit, "
    "tag or repository was not reachable. A force-push or a deleted branch can "
    "strand a ref that once resolved.",
)

#: How many distinct examples to keep per rule. Enough to show the scale and the
#: pattern (e.g. which loci broke) without pasting a whole log into the report.
MAX_EXAMPLES = 12


def _clean(value: str) -> str:
    """Trim quoting/punctuation a greedy `\\S+` capture drags in.

    Tools quote paths inconsistently ('file "x.bam":' vs "file 'x.bam'"), so the
    same path can be captured as several distinct strings and show up as separate
    examples — inflating the list while hiding real ones.
    """
    return value.strip().strip("\"'`").rstrip(":;,.").strip("\"'`")


#: A line that is quoting the tool's own help, not reporting a failure. "An
#: invalid option --x will be rejected" in a usage block is documentation.
_HELP_LINE = re.compile(r"^(?:usage:|options?:|arguments?:|-{1,2}[a-z])", re.IGNORECASE)
#: A line the tool itself labels as a warning. Its content can still match an
#: error rule ("WARNING: file /data/in/x does not exist (optional)"), but the
#: tool has already said how serious it is, and a warning never turns the badge.
_WARN_LINE = re.compile(r"^\W*warn(?:ing)?\b", re.IGNORECASE)


def diagnose(log_text: str) -> list[dict]:
    """Return a list of diagnostic issues found in the log text.

    One entry per rule, but carrying `count` and `examples`: an earlier version
    kept only the FIRST match per rule and dropped the rest, which under-reported
    badly — a run where nine loci each failed to open their alignment file looked
    like a single stray file error. The scale of a failure is part of the finding.
    """
    order: list[str] = []
    by_rule: dict[str, dict] = {}

    for line in log_text.splitlines():
        line = line.strip()
        if not line or _HELP_LINE.match(line):
            continue
        warned = bool(_WARN_LINE.match(line))
        for pattern, severity, rid, title_tmpl, observation_tmpl in _RULES:
            m = pattern.search(line)
            if not m:
                continue
            groups = tuple(_clean(g) if isinstance(g, str) else g for g in m.groups())
            if rid == _CMD_NOT_FOUND_FOLD:
                groups = (next((g for g in groups if g), ""),)
            sev = "warning" if warned and severity == "error" else severity
            entry = by_rule.get(rid)
            if entry is None:
                title = title_tmpl.format(*groups) if groups else title_tmpl
                observation = observation_tmpl.format(*groups) if groups else observation_tmpl
                entry = {
                    "id": rid,
                    "severity": sev,
                    "title": title,
                    "count": 0,
                    "examples": [],
                }
                if observation:
                    # `suggestion` is the key the web and older reports read.
                    entry["suggestion"] = observation
                by_rule[rid] = entry
                order.append(rid)
            elif sev == "error" and entry["severity"] == "warning":
                # One real error among warnings makes it an error.
                entry["severity"] = "error"
            entry["count"] += 1
            # Distinct captured values (the file, the option, ...) are what make
            # the scale legible; a bare repeat count would not say WHAT repeated.
            if groups:
                sample = groups[0]
                if sample and sample not in entry["examples"] and len(entry["examples"]) < MAX_EXAMPLES:
                    entry["examples"].append(sample)

    return [by_rule[rid] for rid in order]


def diagnose_file(path: str | pathlib.Path) -> list[dict]:
    p = pathlib.Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    return diagnose(p.read_text(errors="replace"))


def _common_suffix(values: list[str]) -> str:
    if len(values) < 2:
        return ""
    first = values[0]
    for i in range(len(first)):
        suffix = first[i:]
        if all(v.endswith(suffix) for v in values):
            return suffix
    return ""


def short_items(examples: list[str]) -> list[str]:
    """Reduce captured paths to the part that actually varies between them.

    Diagnostics capture whole container paths, which say nothing to the forensic
    reviewer this report is for. Taking the basename and dropping the suffix every
    example shares leaves only the distinguishing token — for a tool that names
    per-locus files, that is the locus:

        /data/out/IntersectMappedReads/vWA_input.bam_alignment.sorted.bam  ->  vWA

    Pure string work, no assumption about any tool's naming convention: if the
    examples share no suffix the basenames are returned untouched.
    """
    if not examples:
        return []
    bases = [pathlib.PurePosixPath(e).name or e for e in examples]
    suffix = _common_suffix(bases)
    if suffix:
        trimmed = [b[: -len(suffix)] for b in bases]
        if all(t.strip() for t in trimmed):
            bases = trimmed
    return sorted(dict.fromkeys(bases))


#: Review-facing phrasing, one short clause per rule. The stored title carries the
#: captured path ("Cannot open file: /data/out/.../vWA_input.bam..."), which is
#: noise to the forensic reviewer the report is written for: the affected items are
#: listed separately, so this column only needs to say what kind of failure it was.
REVIEW_LABELS = {
    "bad_option": "Unrecognized command-line option",
    "file_not_found": "Expected file not found",
    "cannot_open": "Could not open expected files",
    "no_read_groups": "Input BAM/CRAM missing read groups (@RG)",
    "bad_bam": "Invalid or truncated BAM file",
    "vcf_gz_required": "Output path must end in .gz",
    "segfault": "Tool crashed (segmentation fault)",
    "oom": "Ran out of memory",
    "run_timeout": "Did not finish in time",
    "build_download_failed": "A download in the build failed",
    "python_exception": "The tool raised a Python exception",
    "permission_denied": "Permission denied",
    "cmd_not_found": "Command not found",
    "missing_module": "Required Python module not found",
    "import_error": "Import error",
    "zero_genotyped": "No loci were genotyped",
    "disk_full": "Ran out of disk space",
    "runtime_network": "Network access attempted during the run",
    "requires_gui": "Requires a graphical display",
    "requires_gpu": "Requires a GPU",
    "requires_license": "Requires a license or licensed data",
}


# Error classes a coverage-limited reference slice could plausibly cause: the tool
# ran but the sample was too thin to call, or STRhub's own slicing left the BAM
# short. For these we hedge — we cannot prove it was the sample rather than the tool.
SAMPLE_ATTRIBUTABLE = {"zero_genotyped", "bad_bam", "no_read_groups"}

# Structural failures: read depth has no bearing on whether a file opens, a flag is
# recognized, or a build is complete. A slice cannot cause these, so attributing
# them to the sample would hand the tool an alibi it has not earned — we say plainly
# they are not ours. Ids in NEITHER set are genuinely ambiguous (could be STRhub's
# staging, could be the tool) and get no note: the error table stands on its own.
STRUCTURAL = {"cannot_open", "bad_option", "vcf_gz_required",
              "cmd_not_found", "missing_module", "import_error"}


# --------------------------------------------------------------------------
# Manual-verification eligibility (STRhub Verified level 2)
# --------------------------------------------------------------------------
# Level 2 is a PAID, human-run verification, so who qualifies for it must never
# be a judgement call. The rule is therefore mechanical: eligibility is a code
# emitted by this module from the run's own evidence, and the web can only offer
# level 2 on a report that carries one. Two sets do the separating.

# Classes that sit in the cited procedure itself: its pins, package names, build
# steps or command. The automated path can express these tools; what stopped is
# what the repository states, and the author is the one who can change that and
# have it verified again, for free. Routing them to a paid tier would be
# monetising the repository's own friction, so they are named here explicitly
# and can never trigger level 2.
AUTHOR_FIXABLE = {"bad_option", "cmd_not_found", "missing_module", "import_error",
                  "vcf_gz_required", "file_not_found",
                  # Build failures that live in what the submission declared:
                  # its pins, its package names, its own Dockerfile lines.
                  "pip_unresolvable", "apt_no_package", "conda_unsatisfiable",
                  "missing_header", "build_file_missing", "checkout_failed",
                  # The build the repository itself declares runs autoconf
                  # without `-i` (GangSTR's CMakeLists does this to htslib), so
                  # the failure is in those steps and the fix is one flag.
                  "autotools_aux_missing",
                  # A build step that reads a file the commit does not have
                  # (STRspy's database zip, added six weeks after v2.0).
                  "repo_file_missing"}

# Ours. Not a fault of the tool or of the submission, and never something to ask
# its author to fix — STRhub picks the base image for a generated container, so
# an image that cannot be pulled is a fault in our pipeline. This set exists
# because the report has to be able to say "this one is on us": every other set
# here answers a different question (can they fix it? is it a ceiling?), and
# without this one a fault of ours reads as a finding about their software.
STRHUB_FIXABLE = {"base_image_missing", "registry_rate_limited"}

# Ceilings of the free automated environment. No amount of care with the form
# lifts these: a public runner has no GPU, no display, a fixed memory and disk
# budget, and a pinned snapshot cannot depend on a network fetch at run time.
# A tool that hits one of these is not failing verification — verification, as
# designed, cannot express it. That is what level 2 exists for.
HARNESS_INCOMPATIBLE = {"oom", "disk_full", "runtime_network",
                        "requires_gui", "requires_gpu", "requires_license"}

# The whole guarantee rests on an id never being both, so state it as an invariant
# rather than trusting two hand-maintained sets to stay apart.
assert not (AUTHOR_FIXABLE & HARNESS_INCOMPATIBLE), \
    "an error class cannot be both author-fixable and harness-incompatible"
assert not (STRHUB_FIXABLE & (AUTHOR_FIXABLE | HARNESS_INCOMPATIBLE)), \
    "a fault of ours cannot also be theirs, or a ceiling of the environment"


def install_fault_sentence(faults: list[str]) -> str:
    """One sentence naming whose side a failed build falls on.

    Ours is said first and unhedged wherever it applies: a reader who has just
    been told a tool did not build will otherwise take it as a fact about the
    software, and the one thing worse than no explanation is the wrong one.

    The "author" side is phrased as the run's configuration, never as a fault
    in the software or a claim about who wrote that configuration. A
    verification is the same fact whoever triggered it, and the recipe is most
    often STRhub's own reading of the repository; "corrections to the
    submission" would publish our configuration mistake as a finding about
    their code, on a page with a red badge.
    """
    if "strhub" in faults:
        return ("At least one cause is STRhub's, not the tool's: the container "
                "recipe for a generated environment is ours. Nothing here is a "
                "finding about the software, and nothing needs fixing on the "
                "author's side.")
    if "harness" in faults:
        return ("At least one cause is a ceiling of the free automated "
                "environment rather than a fault in the tool.")
    if "author" in faults:
        return ("Every cause identified sits in this run's configuration: the "
                "pinned versions, package names or build steps it declared. They "
                "are faults in how the tool was set up here rather than in the "
                "software. Re-verifying after correcting them is free.")
    return ("The cause could not be classified automatically. The full build "
            "output is linked below.")


def configuration_fault_sentence() -> str:
    """What the rows above are about: the configuration, not the software.

    Never "corrections to the submission": a reader takes that to mean the
    software's authors sent something wrong, and the configuration is most
    often STRhub's own reading of the repository. That would publish our
    mistake as a finding about their code, under their name.

    The asymmetry is what makes this urgent rather than pedantic: a bad
    configuration produces false negatives, almost never false positives. A green
    result is sound whoever configured it; a red one is not.
    """
    return ("These rows describe the configuration this run used, not the "
            "software: a result that stops for one of them says less about "
            "the tool than about the setup. Re-verifying after it changes "
            "is free. Each row above says what the log establishes.")


def fault_of(issue_id: str) -> str | None:
    """Whose side an error class falls on: 'author', 'strhub', 'harness', or None.

    None is a real answer and the most common one — plenty of failures are
    genuinely ambiguous from a log alone, and guessing a side there would put a
    name to something we do not know.
    """
    if issue_id in STRHUB_FIXABLE:
        return "strhub"
    if issue_id in AUTHOR_FIXABLE:
        return "author"
    if issue_id in HARNESS_INCOMPATIBLE:
        return "harness"
    return None

# Author-declared incompatibilities (the pre-flight, "trigger A"). Same ceilings,
# stated up front so a tool that plainly cannot run is not made to burn a CI run
# to discover it. Keys mirror the manifest's `compatibility` block.
DECLARED_INCOMPAT = {
    "requires_gui":
        "The tool declares an interactive or graphical step. The automated "
        "runner is headless and cannot execute or evidence it.",
    "requires_gpu":
        "The tool declares it needs GPU hardware. Public CI runners are CPU-only.",
    "requires_runtime_network":
        "The tool declares it fetches data over the network while running. A "
        "pinned snapshot cannot record or reproduce what was fetched.",
    "requires_licensed_reference":
        "The tool declares it needs licensed or restricted reference data that "
        "cannot be published in a public verification run.",
    "requires_unsupported_os":
        "The tool declares it needs an OS the automated runner does not provide.",
    "opaque_output_format":
        "The tool declares a binary or proprietary output with no text or tabular "
        "export, so the IO and content gates cannot inspect it.",
}

_DETECTED_REASONS = {
    "oom": "The run exhausted the CI runner's memory. The automated environment "
           "has a fixed memory budget the author cannot raise.",
    "disk_full": "The run filled the CI runner's disk. The automated environment "
                 "has a fixed disk budget the author cannot raise.",
    "runtime_network": "The tool reached for the network while running. A pinned "
                       "snapshot cannot record or reproduce what was fetched.",
    "requires_gui": "The tool tried to open a graphical display. The automated "
                    "runner is headless.",
    "requires_gpu": "The tool needs CUDA hardware. Public CI runners are CPU-only.",
    "requires_license": "The tool needs a license or licensed data that cannot be "
                        "published in a public verification run.",
}


def manual_eligibility(diagnostics: dict[str, list[dict]],
                       gates: dict[str, bool],
                       declared: dict | None = None) -> dict:
    """Decide, mechanically, whether this run may be offered manual verification.

    Returns a record that always states the outcome, so a report can distinguish
    "checked, not eligible" from an older report that never checked at all:

        {"eligible": bool, "basis": "declared"|"detected"|None,
         "reason_code": str|None, "reason": str|None}

    The order of the checks is the policy:

    1. A run that produced its expected output has nothing to escalate. Level 2
       cannot be offered over a working free path, whatever the tool declared —
       this is what stops the paid tier from becoming a queue-jump.
    2. A declared ceiling (trigger A) qualifies even without a run: a GUI tool
       should not have to burn CI to be told the runner is headless.
    3. A detected ceiling (trigger B) qualifies on the evidence of the log.
    4. Everything else does not. In particular a run that failed only on
       AUTHOR_FIXABLE errors stays on the free path: those sit in the cited
       procedure, and a changed repository is verified again at no cost.
    """
    none = {"eligible": False, "basis": None, "reason_code": None, "reason": None}

    # 1. The free path delivered: gates through IO cleared, so a file in the
    #    declared format actually came out. Nothing here needs a human.
    if gates.get("io") or gates.get("content"):
        return none

    # 2. Declared (trigger A) — checked before the log so a tool that never got
    #    to run is still routed correctly.
    for flag, reason in DECLARED_INCOMPAT.items():
        if (declared or {}).get(flag):
            return {"eligible": True, "basis": "declared",
                    "reason_code": f"declared_incompat:{flag}", "reason": reason}

    # 3. Detected (trigger B) — an environment ceiling the log proves we hit.
    #    Scanned in HARNESS_INCOMPATIBLE order so the reason is stable across
    #    runs rather than dependent on which leg happened to log first.
    hit_ids = {issue["id"] for issues in diagnostics.values() for issue in issues
               if issue.get("severity") == "error"}
    for rid in sorted(HARNESS_INCOMPATIBLE & hit_ids):
        return {"eligible": True, "basis": "detected",
                "reason_code": f"detected_incompat:{rid}",
                "reason": _DETECTED_REASONS.get(rid, REVIEW_LABELS.get(rid, rid))}

    # 4. Failed on something that sits in the cited procedure itself.
    return none


def _is_strhub_staged(path: str) -> bool:
    """True for the inputs STRhub puts in the container, not the author.

    `/data/in` and `/data/ref` are populated by harness/prepare.py under names the
    harness chooses (input.bam, sample.fastq, regions.bed, the reference genome).
    The author names none of them, so when one is missing the fault is ours.
    """
    p = path.strip().strip("'\"")
    return p.startswith("/data/ref/") or p in {
        "/data/in/regions.bed", "/data/in/input.bam", "/data/in/input.bam.bai",
        "/data/in/sample.fastq",
    }


def author_fixable_ids(diagnostics: dict[str, list[dict]]) -> list[str]:
    """Error classes in this run that sit in the cited procedure itself.

    The counterpart to `manual_eligibility`: when a run fails on these, the
    honest answer is that the repository's own steps stopped here and a changed
    repository is verified again at no cost, and the report should say so
    plainly rather than leaving a dead end that reads like a reason to pay for
    help.

    A missing file is the one class that can belong to either side. Everything
    under `/data/in` and `/data/ref` is staged by us under names we choose, so a
    file error there is OURS and must not be dressed as a correction the author
    can make — telling someone to fix a path they never wrote sends them to edit
    something that was already right.
    """
    hit: set[str] = set()
    for issues in diagnostics.values():
        for issue in issues:
            if issue.get("severity") != "error":
                continue
            examples = issue.get("examples") or []
            if (issue["id"] in {"file_not_found", "cannot_open"}
                    and examples and all(_is_strhub_staged(e) for e in examples)):
                continue
            hit.add(issue["id"])
    return sorted(AUTHOR_FIXABLE & hit)


def external_leg_notes(diagnostics: dict[str, list[dict]]) -> list[str]:
    """Review notes to append, scoped to what STRhub's reference slice can explain.

    The 'external' leg runs STRhub's reference sample, which is a SLICE. Whether an
    error there reflects the slice depends on the KIND of error: a coverage-limited
    sample yields fewer reads, but it cannot make a file fail to open or a build be
    incomplete. So we split the errors — hedging on the ones a slice could cause,
    stating plainly that the structural ones are not ours — instead of blanketing
    every failure with a coverage excuse. The closing line names what would let a
    verification run on the author's own sample as well: shipped test data.
    """
    external = diagnostics.get("external", [])
    error_ids = {i["id"] for i in external if i.get("severity") == "error"}
    if not error_ids:
        return []

    notes: list[str] = []
    if error_ids & SAMPLE_ATTRIBUTABLE:
        notes.append(
            "Some of these errors occurred on STRhub's reference sample, which is a "
            "slice around the panel loci rather than a whole genome, so they may "
            "reflect the sample's coverage rather than the tool."
        )
    if error_ids & STRUCTURAL:
        notes.append(
            "Structural errors, such as a file that will not open, an unrecognized "
            "command-line flag, or an incomplete build, do not depend on the sample: "
            "a coverage-limited slice yields fewer reads, but it cannot cause them. "
            "These are not attributable to STRhub's reference sample."
        )
    if notes:
        notes.append(
            "A small test file in the tool's own repository lets a new user run it "
            "on their first day and see it working before trusting it with their own "
            "data, and it lets a verification run against the author's sample as well "
            "as STRhub's slice. Publishing the output that file should produce helps "
            "just as much: it shows what the results are meant to look like, which is "
            "what a reader needs to tell a correct run from one that merely finished."
        )
    return notes


def summarize(diagnostics: dict[str, list[dict]]) -> list[dict]:
    """Flatten per-leg diagnostics into one review-facing list of error entries.

    Both legs run the same tool on comparable data, so the same fault shows up
    twice; reporting it once with the wider evidence is what a reviewer needs.
    Errors only — warnings are normal tool chatter and would bury the signal.
    """
    merged: dict[str, dict] = {}
    for issues in diagnostics.values():
        for issue in issues:
            if issue.get("severity") != "error":
                continue
            entry = merged.setdefault(issue["id"], {
                "id": issue["id"],
                "title": REVIEW_LABELS.get(
                    issue["id"], issue.get("title", issue["id"]).split(":")[0]
                ),
                "count": 0,
                "examples": [],
            })
            entry["count"] += issue.get("count", 1)
            for ex in issue.get("examples", []):
                if ex not in entry["examples"]:
                    entry["examples"].append(ex)
    out = []
    for entry in merged.values():
        entry["items"] = short_items(entry["examples"])
        out.append(entry)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="path to captured log file")
    ap.add_argument("--json", default="", help="write JSON output to file")
    args = ap.parse_args()

    issues = diagnose_file(args.log)
    out = json.dumps(issues, indent=2)
    print(out)
    if args.json:
        pathlib.Path(args.json).write_text(out)
    return 1 if any(i["severity"] == "error" for i in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
