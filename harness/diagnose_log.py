"""Auto-diagnose tool execution logs to suggest fixes for common failures.

Scans stdout+stderr captured from a verification run and matches known error
patterns. Returns structured diagnostics that the report embeds and the web
dashboard renders as actionable suggestions.

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

# Each rule: (compiled regex, severity, short id, human title, suggestion).
# Regexes are matched against each line OR the full text (for multi-line).
_RULES: list[tuple[re.Pattern, str, str, str, str]] = []


def _rule(pattern: str, severity: str, rid: str, title: str, suggestion: str,
          flags: int = re.IGNORECASE):
    _RULES.append((re.compile(pattern, flags), severity, rid, title, suggestion))


# --- Unrecognized / invalid options -----------------------------------------
_rule(
    r"unrecognized option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Unrecognized command-line option: --{0}",
    "The flag '--{0}' does not exist in this tool version. "
    "Check the tool's --help or README for the correct option name.",
)

_rule(
    r"unknown option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Unknown option: --{0}",
    "The flag '--{0}' is not recognized. Check --help for valid options.",
)

_rule(
    r"invalid option ['\"]?--([\w-]+)",
    "error", "bad_option",
    "Invalid option: --{0}",
    "The flag '--{0}' is not valid. Check --help for valid options.",
)

# --- File not found ---------------------------------------------------------
_rule(
    r"(?:file|path)\s+(?:for\s+)?['\"]?(/data/\S+)['\"]?\s+(?:does not exist|not found|doesn'?t exist)",
    "error", "file_not_found",
    "File not found: {0}",
    "The tool expected a file at '{0}' but it was not staged. "
    "Check the manifest inputs, fixture path, and output path.",
)

_rule(
    r"No such file or directory:\s*['\"]?(/data/[^'\"\s]+)",
    "error", "file_not_found",
    "File not found: {0}",
    "Check that the input path '{0}' matches the manifest and that the fixture was staged correctly.",
)

_rule(
    r"(?:cannot open|failed to open|unable to open)\s+['\"]?(/\S+)",
    "error", "cannot_open",
    "Cannot open file: {0}",
    "The tool could not open '{0}'. Verify the path exists and the file format is correct.",
)

# --- BAM/CRAM issues -------------------------------------------------------
_rule(
    r"(?:BAM|CRAM) files? (?:don'?t|do not) contain read groups",
    "error", "no_read_groups",
    "BAM/CRAM missing read groups (@RG)",
    "Add read groups with: samtools addreplacerg -r '@RG\\tID:sample\\tSM:sample\\tLB:lib\\tPL:ILLUMINA' input.bam -o output.bam",
)

_rule(
    r"(?:not? |in)valid BAM|truncated file|EOF marker is absent",
    "error", "bad_bam",
    "Invalid or truncated BAM file",
    "The BAM file may be corrupted or incomplete. Re-download or re-index it. "
    "If it was sliced, ensure the slice command completed successfully.",
)

# --- VCF output issues ------------------------------------------------------
_rule(
    r"(?:path|output)\s+.*(?:must end|should end)\s+(?:in|with)\s+\.gz",
    "error", "vcf_gz_required",
    "Output path must end in .gz",
    "This tool requires the VCF output path to end in .gz (bgzipped). "
    "Change the output path in the manifest to e.g. result.vcf.gz",
)

# --- Too few reads / loci skipped ------------------------------------------
_rule(
    r"[Ss]kipp(?:ed|ing)\s+(?:(\d+)\s+)?loci\s+with\s+too\s+few\s+reads|[Ss]kipping\s+(?:region|locus)\s+(?:\S+\s+)?with\s+too\s+few\s+reads",
    "warning", "too_few_reads",
    "Loci skipped (too few reads)",
    "Some loci had insufficient reads after quality filtering. Try lowering "
    "--min-reads or relaxing quality filters (e.g. --read-qual-trim for HipSTR). "
    "The input BAM may also need more coverage at STR regions.",
)

_rule(
    r"[Ss]kipping\s+(?:region|locus).*(?:allele\s+)?length\s+exceeds.*(?:threshold|maximum)\s*\((\d+)\s+vs\s+(\d+)\)",
    "warning", "str_too_long",
    "Locus skipped: reference allele too long ({0} vs max {1})",
    "Some STR loci have reference alleles longer than the tool's maximum. "
    "Increase the max length threshold (e.g. --max-str-len for HipSTR).",
)

# --- Low base quality filtering (HipSTR specific) --------------------------
_rule(
    r"(\d+)\s+(?:reads\s+)?had low base quality scores",
    "info", "low_bq_reads",
    "Reads filtered by base quality",
    "Many reads are being removed by the base quality filter. For HipSTR, "
    "use --read-qual-trim '!' to lower the quality trimming threshold. "
    "Also consider --def-stutter-model if too few reads remain.",
)

# --- No mate pair (BAM slice issue) ----------------------------------------
_rule(
    r"(\d+)\s+(?:reads\s+)?did not have a mate pair",
    "info", "unpaired_reads",
    "Reads filtered (no mate pair)",
    "Reads without mate pairs are being filtered. This is common with BAM slices "
    "where mates fall outside the sliced region. Use --use-unpaired (HipSTR) "
    "or equivalent to allow unpaired reads.",
)

# --- Genotyping summary ---------------------------------------------------
_rule(
    r"[Gg]enotyping succeeded for (\d+)/(\d+) loci",
    "info", "genotyping_summary",
    "Genotyping: {0}/{1} loci succeeded",
    "",
)

# --- Permission / segfault / OOM ------------------------------------------
_rule(
    r"[Ss]egmentation fault|SIGSEGV|core dump",
    "error", "segfault",
    "Tool crashed (segmentation fault)",
    "The tool crashed with a segfault. This may indicate incompatible input data, "
    "a bug in the tool, or insufficient memory. Check the input file format.",
)

_rule(
    r"[Oo]ut of memory|Cannot allocate memory|MemoryError|std::bad_alloc",
    "error", "oom",
    "Out of memory",
    "The tool ran out of memory. Try reducing the input data size or "
    "increasing the timeout. Consider using a smaller BAM slice.",
)

_rule(
    r"No space left on device|[Dd]isk quota exceeded",
    "error", "disk_full",
    "Ran out of disk space",
    "The run filled the CI runner's disk. Public runners cap disk space, so a "
    "tool with large intermediate files may not fit the automated environment.",
)

# --- Environment ceilings the author cannot lift from the form ---------------
# These are what separate "fix your submission and re-run for free" from "the
# automated path structurally cannot express this tool". See HARNESS_INCOMPATIBLE.

_rule(
    r"[Tt]emporary failure in name resolution|[Cc]ould not resolve host"
    r"|[Nn]ame or service not known|[Nn]etwork is unreachable"
    r"|Failed to establish a new connection|getaddrinfo failed",
    "error", "runtime_network",
    "Network access attempted during the run",
    "The tool tried to reach the network while running. Verification is a pinned "
    "snapshot, so anything fetched at run time cannot be recorded or reproduced. "
    "Vendor the data into the image at build time, or request manual verification.",
)

_rule(
    r"cannot connect to X server|[Nn]o display name and no \$DISPLAY"
    r"|QXcbConnection|[Cc]annot open display|GtkWindow|TclError: no display",
    "error", "requires_gui",
    "Tool requires a graphical display",
    "The tool tried to open a GUI. The automated runner is headless, so an "
    "interactive step cannot be executed or evidenced. Request manual verification.",
)

_rule(
    r"no CUDA-capable device|libcuda\.so.*(?:cannot open|not found)"
    r"|CUDA driver version is insufficient|nvidia-smi.*not found"
    r"|torch\.cuda\.is_available\(\) *(?:is |== *)?False|Found no NVIDIA driver",
    "error", "requires_gpu",
    "Tool requires a GPU",
    "The tool needs CUDA hardware. Public CI runners are CPU-only, so this cannot "
    "run on the automated path. Request manual verification.",
)

_rule(
    r"[Ll]icense (?:file )?(?:not found|is invalid|has expired|expired)"
    r"|[Nn]o valid license|FLEXlm|FlexNet|LM_LICENSE_FILE",
    "error", "requires_license",
    "Tool requires a license or licensed data",
    "The tool needs a license or licensed reference data that cannot be published "
    "in a public verification run. Request manual verification.",
)

_rule(
    r"[Pp]ermission denied",
    "error", "permission_denied",
    "Permission denied",
    "A file or directory could not be accessed. This is likely a container "
    "permissions issue. Check that output paths are under /data/out/.",
)

# --- Command not found ------------------------------------------------------
_rule(
    r"(\S+):\s+(?:command )?not found",
    "error", "cmd_not_found",
    "Command not found: {0}",
    "The binary '{0}' was not found in the container. Check the Dockerfile "
    "installs it and that the PATH includes its location.",
)

# --- Python/runtime errors --------------------------------------------------
_rule(
    r"ModuleNotFoundError:\s+No module named ['\"](\S+)['\"]",
    "error", "missing_module",
    "Python module not found: {0}",
    "Install the missing module in the Dockerfile: pip install {0}",
)

_rule(
    r"ImportError:\s+.*['\"](\S+)['\"]",
    "error", "import_error",
    "Import error: {0}",
    "A required library failed to import. Check the Dockerfile installs all dependencies.",
)

# --- Empty output -----------------------------------------------------------
_rule(
    r"Genotyping succeeded for 0/0 loci",
    "error", "zero_genotyped",
    "No loci were genotyped",
    "The tool produced no genotype calls. All loci were filtered out. "
    "Check read quality filters, minimum read thresholds, and input data coverage.",
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
    "The version of '{0}' named in the build no longer exists on PyPI, or is "
    "incompatible with this base image's Python. Relax the pin or pin a version "
    "that is still published.",
)

_rule(
    r"E: Unable to locate package (\S+)",
    "error", "apt_no_package",
    "apt cannot find a package: {0}",
    "The Debian/Ubuntu package '{0}' does not exist in this base image's "
    "repositories. Check the name, or install it another way.",
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
    r"fatal error:\s+(\S+\.h(?:pp)?):\s+No such file or directory",
    "error", "missing_header",
    "A C/C++ header is missing at build time: {0}",
    "The build needs the development package that provides '{0}'. Add it to the "
    "build step (for example the -dev package for that library).",
)

_rule(
    r"(?:COPY failed|ADD failed)[^\n]*|failed to compute cache key[^\n]*not found",
    "error", "build_file_missing",
    "The build referenced a file that is not in the build context",
    "A COPY/ADD line names a file the build cannot see. The container is built "
    "from the tool's directory, and the repository is cloned inside the image — "
    "so paths from your own machine are not available.",
)

_rule(
    r"(?:manifest for \S+ not found|manifest unknown|pull access denied for)",
    "error", "base_image_missing",
    "The base image could not be pulled",
    "STRhub chooses the base image for a generated container, so this is ours to "
    "fix, not the tool's. Nothing to change on the submission.",
)

_rule(
    r"fatal: (?:reference is not a tree|couldn't find remote ref|"
    r"repository '[^']+' not found)[^\n]*",
    "error", "checkout_failed",
    "The pinned commit could not be checked out",
    "The container clones the public repository at the pinned ref. Check that "
    "the commit or tag still exists and is reachable — a force-push or a deleted "
    "branch can strand a ref that once resolved.",
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
        if not line:
            continue
        for pattern, severity, rid, title_tmpl, suggestion_tmpl in _RULES:
            m = pattern.search(line)
            if not m:
                continue
            groups = tuple(_clean(g) if isinstance(g, str) else g for g in m.groups())
            entry = by_rule.get(rid)
            if entry is None:
                title = title_tmpl.format(*groups) if groups else title_tmpl
                suggestion = suggestion_tmpl.format(*groups) if groups else suggestion_tmpl
                entry = {
                    "id": rid,
                    "severity": severity,
                    "title": title,
                    "count": 0,
                    "examples": [],
                }
                if suggestion:
                    entry["suggestion"] = suggestion
                by_rule[rid] = entry
                order.append(rid)
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

# Fixable by the author, for free, by correcting the submission and re-running.
# The auto-run works fine for these tools — the manifest or Dockerfile is simply
# wrong, and every one of these ids already ships a `suggestion` saying how to fix
# it. Routing them to a paid tier would be monetising our own form's friction, so
# they are named here explicitly and can never trigger level 2.
AUTHOR_FIXABLE = {"bad_option", "cmd_not_found", "missing_module", "import_error",
                  "vcf_gz_required", "file_not_found",
                  # Build failures that live in what the submission declared:
                  # its pins, its package names, its own Dockerfile lines.
                  "pip_unresolvable", "apt_no_package", "conda_unsatisfiable",
                  "missing_header", "build_file_missing", "checkout_failed"}

# Ours. Not a fault of the tool or of the submission, and never something to ask
# its author to fix — STRhub picks the base image for a generated container, so
# an image that cannot be pulled is a fault in our pipeline. This set exists
# because the report has to be able to say "this one is on us": every other set
# here answers a different question (can they fix it? is it a ceiling?), and
# without this one a fault of ours reads as a finding about their software.
STRHUB_FIXABLE = {"base_image_missing"}

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
        return ("Every cause identified sits in what the submission declared — "
                "its pinned versions, package names or build steps. These are "
                "correctable, and re-verifying afterwards is free.")
    return ("The cause could not be classified automatically. The full build "
            "output is linked below.")


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
       AUTHOR_FIXABLE errors stays on the free path, where the diagnostics
       already carry the fix.
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

    # 4. Failed, but on something the author can fix and re-run for free.
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
    """Error classes in this run the author can correct themselves, for free.

    The counterpart to `manual_eligibility`: when a run fails on these, the
    honest answer is "fix the submission and re-run at no cost", and the report
    should say so plainly rather than leaving a dead end that reads like a reason
    to pay for help.

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
    every failure with a coverage excuse. The closing line stays actionable: ship
    demo data so the tool can also be run against the author's complete sample.
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
