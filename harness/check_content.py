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


def _is_header_row(fields: list[str], count_cols: list, dna_col) -> bool:
    """True when row 0 fails a type every data row must satisfy.

    Deliberately conservative: it only fires on a column the author DECLARED as
    numeric or as DNA, so a real data row can never be mistaken for a header. A
    label in the locus column is indistinguishable from a locus name and is left
    alone.

    Without this, a tool whose TSV carries a header could not declare its
    read-count columns at all: `counts_are_integers` compares invalid rows
    against zero, and the header's own word ("Supporting reads", "Depth", ...)
    is one. The cost of that was silent — authors dropped the field and the
    report showed `0 reads` for a run with hundreds per locus, which reads as an
    empty result rather than an undeclared one.
    """
    for c in count_cols or []:
        if c < len(fields):
            try:
                int(fields[c])
            except ValueError:
                return True
    if dna_col is not None and dna_col < len(fields):
        if not _DNA_RE.match(fields[dna_col]):
            return True
    return False


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

    # Drop a leading header row, but only when a declared typed column proves it
    # is one, and never the file's only row.
    header_dropped = False
    if len(rows) > 1 and _is_header_row(rows[0].split("\t"), count_cols, dna_col):
        rows = rows[1:]
        header_dropped = True

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
        if count_cols:
            for c in count_cols:
                if c < len(f):
                    try:
                        v = int(f[c])
                        if v < 0:
                            ok_counts = False
                        depth += v
                    except ValueError:
                        ok_counts = False
        elif len(f) > 9 and ":" in f[8]:
            # VCF output without count_columns (e.g. HipSTR, GangSTR): derive read
            # depth from the per-sample DP sub-field of the FORMAT column (cols 9+),
            # so genotypers report real coverage instead of 0.
            fmt = f[8].split(":")
            if "DP" in fmt:
                di = fmt.index("DP")
                for sample in f[9:]:
                    sp = sample.split(":")
                    if di < len(sp):
                        try:
                            depth += int(sp[di])
                        except ValueError:
                            pass
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
        # Recorded, not silent: a row we removed from the author's file is a
        # decision the report has to own.
        "header_row_dropped": header_dropped,
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
        "top_loci_by_depth": locus_reads.most_common(),
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
