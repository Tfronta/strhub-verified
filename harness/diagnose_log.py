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
            "We recommend the tool ship its own demo or test data in its official "
            "repository, so it can be evaluated against the author's complete data "
            "as well as STRhub's slice."
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
