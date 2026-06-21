"""Content gate: does the output look like plausible genotype-bearing data?

This is the rung ABOVE the IO gate. IO proves "a non-empty file in the declared
format appeared". Content proves "the rows look like real STR/SNP calls": the
declared number of columns, a DNA column that is only ACGTN, integer read-count
columns, and a locus column carrying enough distinct, recognisable forensic
loci. It still makes NO claim that the genotypes are biologically correct — that
is concordance, which STRhub deliberately does not assert.

Checks are driven entirely by the manifest's `outputs[].content` block, so the
harness stays generic; the manifest remains the single source of truth.

Usage:  python harness/check_content.py <manifest.yml> <output_dir> [--json content_result.json]
Exit:   0 if all required content checks pass, 1 otherwise.
"""
from __future__ import annotations
import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402

_DNA_RE = re.compile(r"^[ACGTN]+$", re.IGNORECASE)
# ForenSeq-style panels mix STR loci with identity SNPs (named rsNNNN). We count
# both but report them separately so "distinct loci" is never conflated with the
# much larger SNP marker count.
_SNP_RE = re.compile(r"^rs\d+$", re.IGNORECASE)


def _analyze(path: pathlib.Path, spec: dict) -> dict:
    """Parse a TSV-ish output and compute structural + locus statistics."""
    cols = spec.get("columns")
    dna_col = spec.get("dna_column")
    count_cols = spec.get("count_columns", [])
    locus_col = spec.get("locus_column")
    locus_sep = spec.get("locus_sep", ":")

    if path.suffix == ".gz" or path.name.endswith(".gz"):
        text = gzip.open(path, "rt", errors="replace").read()
    else:
        text = path.read_text(errors="replace")
    rows = [r for r in text.splitlines()
            if r.strip() and not r.startswith("#")]

    malformed = 0
    dna_bad = 0
    counts_bad = 0
    locus_reads: collections.Counter = collections.Counter()
    locus_rows: collections.Counter = collections.Counter()
    total_reads = 0
    max_depth = 0

    for r in rows:
        f = r.split("\t")
        if cols is not None and len(f) != cols:
            malformed += 1
            continue
        if dna_col is not None and dna_col < len(f):
            if not _DNA_RE.match(f[dna_col]):
                dna_bad += 1
        depth = 0
        ok_counts = True
        for c in count_cols:
            if c < len(f):
                try:
                    v = int(f[c])
                    if v < 0:
                        ok_counts = False
                    depth += v
                except ValueError:
                    ok_counts = False
        if not ok_counts:
            counts_bad += 1
        if locus_col is not None and locus_col < len(f):
            locus = f[locus_col].split(locus_sep)[0]
            locus_rows[locus] += 1
            locus_reads[locus] += depth
        total_reads += depth
        max_depth = max(max_depth, depth)

    snp_markers = sorted(l for l in locus_rows if _SNP_RE.match(l))
    str_loci = sorted(l for l in locus_rows if not _SNP_RE.match(l))

    return {
        "rows": len(rows),
        "malformed_rows": malformed,
        "dna_invalid_rows": dna_bad,
        "count_invalid_rows": counts_bad,
        "distinct_loci": len(locus_rows),        # all panel markers (STR + SNP)
        "distinct_str_loci": len(str_loci),      # STR loci only (e.g. CODIS/ForenSeq STRs)
        "distinct_snp_markers": len(snp_markers),  # identity SNPs (rsNNNN)
        "loci": str_loci + snp_markers,
        "str_loci": str_loci,
        "snp_markers": snp_markers,
        "total_reads": total_reads,
        "max_sequence_depth": max_depth,
        "top_loci_by_depth": locus_reads.most_common(8),
    }


def _check_one(path: pathlib.Path, spec: dict) -> dict:
    stats = _analyze(path, spec)
    checks: dict = {}

    if "columns" in spec:
        checks["columns_consistent"] = stats["malformed_rows"] == 0
    if "dna_column" in spec:
        checks["dna_is_acgtn"] = stats["dna_invalid_rows"] == 0
    if spec.get("count_columns"):
        checks["counts_are_integers"] = stats["count_invalid_rows"] == 0
    if "min_distinct_loci" in spec:
        checks["min_distinct_loci"] = stats["distinct_loci"] >= spec["min_distinct_loci"]
    if "min_total_reads" in spec:
        checks["min_total_reads"] = stats["total_reads"] >= spec["min_total_reads"]

    missing: list = []
    if spec.get("expect_loci"):
        present = set(stats["loci"])
        missing = [l for l in spec["expect_loci"] if l not in present]
        checks["expect_loci"] = not missing

    entry = {"checks": checks, "stats": stats, "passed": all(checks.values()) if checks else False}
    if missing:
        entry["missing_loci"] = missing
    return entry


def check(manifest_path: str, out_dir: str) -> dict:
    m = _manifest.load(manifest_path)
    out = pathlib.Path(out_dir)
    results = []
    ok = True
    any_content = False

    for spec in m["outputs"]:
        content_spec = spec.get("content")
        if not content_spec:
            continue
        any_content = True
        matches = sorted(out.glob(spec["path"]))
        entry = {"path": spec["path"]}
        if not matches:
            entry["passed"] = False
            entry["error"] = "output not found"
            ok = False
            results.append(entry)
            continue
        f = matches[0]
        entry["resolved"] = str(f.relative_to(out))
        entry.update(_check_one(f, content_spec))
        ok = ok and entry["passed"]
        results.append(entry)

    # If no output declares a content block, the gate is not applicable; report
    # it as not-passed so the ladder does not over-claim.
    return {"gate": "content", "applicable": any_content, "passed": ok and any_content, "outputs": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("output_dir")
    ap.add_argument("--json", default="content_result.json")
    args = ap.parse_args()

    result = check(args.manifest, args.output_dir)
    pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
