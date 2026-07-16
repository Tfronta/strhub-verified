"""Validate an author-supplied regions BED against a dataset's supported-loci panel.

STRhub Verified ships SLICES, not whole genomes. A regions BED whose intervals
fall outside the slice's supported loci is a REJECTED SUBMISSION, not a failed
tool: the tool would find no reads there and the author would wrongly conclude it
broke. So this runs as a PRE-FLIGHT check before any gate — a failure aborts the
run and produces no report or badge (see .github/workflows/verify.yml).

Format-agnostic by design: only columns 1-3 (chrom, start, end) are read, so any
tool's BED layout — HipSTR (7 cols), GangSTR (5), plain BED3 — is accepted.

Rules:
  - every BED interval must OVERLAP a supported window (permissive: partial overlap
    is fine, the run's output gate catches a BED that overlaps but is useless);
  - the BED must cover at least `min_loci` distinct supported loci.

Keep in lockstep with the web mirror `strhub-web/lib/verified/validate-regions.ts`;
a shared fixture guards divergence.

Usage:
  python harness/validate_bed.py --bed work/in_external/regions.bed \
      --supported datasets/illumina-bam-hg38-y/loci.bed --min-loci 5 --json out.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def norm_chrom(c: str) -> str:
    """Normalise chromosome naming so 'Y' and 'chrY' compare equal (hg38 UCSC style)."""
    c = c.strip()
    return c if c.lower().startswith("chr") else f"chr{c}"


def parse_bed3(text: str) -> list[dict]:
    """Read cols 1-3 of a BED. Ignores comments/track lines and any extra columns."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(("#", "track", "browser")):
            continue
        f = line.split("\t") if "\t" in line else line.split()
        if len(f) < 3:
            raise ValueError(f"line {n}: expected at least 3 columns, got {len(f)}")
        try:
            start, end = int(f[1]), int(f[2])
        except ValueError as exc:
            raise ValueError(f"line {n}: non-integer coordinates: {line!r}") from exc
        if end <= start:
            raise ValueError(f"line {n}: end <= start: {line!r}")
        name = f[3] if len(f) > 3 and f[3] not in ("", ".") else f"{f[0]}:{start}-{end}"
        rows.append({"chrom": norm_chrom(f[0]), "start": start, "end": end, "name": name})
    return rows


def overlaps(a: dict, b: dict) -> bool:
    return a["chrom"] == b["chrom"] and a["start"] < b["end"] and a["end"] > b["start"]


def validate(bed_rows: list[dict], panel: list[dict], min_loci: int) -> dict:
    covered: set[str] = set()
    out_of_panel: list[dict] = []

    for row in bed_rows:
        hits = [w for w in panel if overlaps(row, w)]
        if hits:
            for w in hits:
                covered.add(w["name"])
        else:
            out_of_panel.append(row)

    reasons = []
    if out_of_panel:
        preview = ", ".join(f"{r['chrom']}:{r['start']}-{r['end']}" for r in out_of_panel[:5])
        more = f" (+{len(out_of_panel) - 5} more)" if len(out_of_panel) > 5 else ""
        reasons.append(
            f"{len(out_of_panel)} interval(s) fall outside the supported panel: {preview}{more}. "
            f"This slice is not a whole genome — target only the supported loci."
        )
    if len(covered) < min_loci:
        reasons.append(
            f"covers {len(covered)} supported loci, need at least {min_loci}."
        )

    return {
        "pass": not reasons,
        "covered_loci": sorted(covered),
        "covered_count": len(covered),
        "out_of_panel": [f"{r['chrom']}:{r['start']}-{r['end']}" for r in out_of_panel],
        "min_loci": min_loci,
        "panel_size": len(panel),
        "reason": " ".join(reasons) if reasons else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True, help="author-supplied regions BED")
    ap.add_argument("--supported", required=True, help="dataset supported-loci panel (loci.bed)")
    ap.add_argument("--min-loci", type=int, default=5)
    ap.add_argument("--json", help="write the result JSON here")
    args = ap.parse_args()

    bed_path = pathlib.Path(args.bed)
    panel_path = pathlib.Path(args.supported)

    if not bed_path.is_file():
        print(f"::error::regions BED not found: {bed_path}", file=sys.stderr)
        return 2
    if not panel_path.is_file():
        print(f"::error::supported-loci panel not found: {panel_path}", file=sys.stderr)
        return 2

    try:
        bed_rows = parse_bed3(bed_path.read_text())
    except ValueError as exc:
        result = {"pass": False, "covered_loci": [], "covered_count": 0,
                  "out_of_panel": [], "min_loci": args.min_loci, "panel_size": 0,
                  "reason": f"malformed regions BED: {exc}"}
    else:
        panel = parse_bed3(panel_path.read_text())
        result = validate(bed_rows, panel, args.min_loci)

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2))

    if result["pass"]:
        print(f"regions OK — {result['covered_count']}/{result['panel_size']} supported loci covered: "
              f"{', '.join(result['covered_loci'])}")
        return 0

    print(f"::error::regions BED rejected — {result['reason']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
