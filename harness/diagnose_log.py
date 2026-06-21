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
    r"[Ss]kipp(?:ed|ing)\s+(?:(\d+)\s+)?loci\s+with\s+too\s+few\s+reads|[Ss]kipping\s+(?:region|locus)\s+\S+\s+with\s+too\s+few\s+reads",
    "warning", "too_few_reads",
    "Loci skipped (too few reads)",
    "Some loci had insufficient reads after quality filtering. Try lowering "
    "--min-reads or relaxing quality filters (e.g. --read-qual-trim for HipSTR). "
    "The input BAM may also need more coverage at STR regions.",
)

_rule(
    r"[Ss]kipping\s+(?:region|locus).*(?:allele\s+)?length\s*\((\d+)\)\s*exceeds.*threshold\s*\((\d+)\)",
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


def diagnose(log_text: str) -> list[dict]:
    """Return a list of diagnostic issues found in the log text."""
    seen: set[str] = set()
    issues: list[dict] = []

    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        for pattern, severity, rid, title_tmpl, suggestion_tmpl in _RULES:
            if rid in seen:
                continue
            m = pattern.search(line)
            if not m:
                continue
            groups = m.groups()
            seen.add(rid)
            title = title_tmpl.format(*groups) if groups else title_tmpl
            suggestion = suggestion_tmpl.format(*groups) if groups else suggestion_tmpl
            entry: dict = {
                "id": rid,
                "severity": severity,
                "title": title,
            }
            if suggestion:
                entry["suggestion"] = suggestion
            issues.append(entry)

    return issues


def diagnose_file(path: str | pathlib.Path) -> list[dict]:
    p = pathlib.Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    return diagnose(p.read_text(errors="replace"))


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
