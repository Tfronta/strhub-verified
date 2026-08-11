"""Validate an author-supplied regions BED against a dataset's supported-loci panel.

STRhub Verified ships SLICES, not whole genomes. A regions BED whose intervals
fall outside the slice's supported loci is a REJECTED SUBMISSION, not a failed
tool: the tool would find no reads there and the author would wrongly conclude it
broke. So this runs as a PRE-FLIGHT check before any gate — a failure aborts the
run and produces no report or badge (see .github/workflows/verify.yml).

Format-agnostic by design: only the chromosome and its two coordinate columns are
read, so any tool's BED layout — HipSTR (7 cols), GangSTR (5), plain BED3 — is
accepted. A header row is skipped and the coordinate columns are located rather
than assumed, so a file that merely arranges them differently still works.

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
import re
import sys


def norm_chrom(c: str) -> str:
    """Normalise chromosome naming so 'Y' and 'chrY' compare equal (hg38 UCSC style)."""
    c = c.strip()
    return c if c.lower().startswith("chr") else f"chr{c}"


SNIFF_ROWS = 50
SNIFF_AGREEMENT = 0.8

CHROM_RE = re.compile(r"^(chr)?([0-9]{1,2}|[XYxy]|MT?|mt?)$")
INT_RE = re.compile(r"^\d+$")


def _split(line: str) -> list[str]:
    return line.split("\t") if "\t" in line else line.split()


def _is_int(value: str | None) -> bool:
    return value is not None and bool(INT_RE.match(value.strip()))


def _looks_like_chrom(value: str | None) -> bool:
    return value is not None and bool(CHROM_RE.match(value.strip()))


def _at(fields: list[str], i: int) -> str | None:
    return fields[i] if 0 <= i < len(fields) else None


def sniff_chrom_column(rows: list[list[str]]) -> int | None:
    """Which column holds the chromosome, the next two holding the coordinates.

    Columns 0,1,2 is the BED convention and nearly always right, so it is tried
    first and only displaced if it does not hold. Ordering is deliberately not
    part of the test: a file whose end precedes its start is a coordinate mistake
    the author needs told about by name, not a reason to decide these were never
    the coordinate columns.
    """
    sample = rows[:SNIFF_ROWS]
    if not sample:
        return None
    width = max(len(f) for f in sample)
    candidates = [0] + [i for i in range(width) if i != 0]
    for c in candidates:
        if c + 2 >= width + 1:
            continue
        agreeing = sum(
            1
            for f in sample
            if _looks_like_chrom(_at(f, c)) and _is_int(_at(f, c + 1)) and _is_int(_at(f, c + 2))
        )
        if agreeing / len(sample) >= SNIFF_AGREEMENT:
            return c
    return None


def parse_bed3(text: str) -> list[dict]:
    """Read a BED's chromosome and coordinate columns.

    Only three values are ever needed, so every tool's layout works: extra
    columns are ignored, a header row is skipped, and the coordinate columns are
    located rather than assumed.

    Mirrors `parseBed3` in strhub-web/lib/verified/validate-regions.ts, which runs
    the same checks in the submit form. The two must agree — a BED accepted there
    and rejected here aborts a run with no report, which is a far worse failure
    than being told about it in the form.
    """
    data: list[tuple[str, int]] = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(("#", "track", "browser")):
            continue
        data.append((line, n))
    if not data:
        return []

    split = [_split(line) for line, _ in data]

    # A header names the columns, so it cannot carry coordinates. Dropping it is
    # safe precisely because a real data row would have failed this test.
    if len(split) > 1 and not _is_int(_at(split[0], 1)) and not _is_int(_at(split[0], 2)):
        data = data[1:]
        split = split[1:]

    chrom_column = sniff_chrom_column(split)
    if chrom_column is None:
        shown = data[0][0].strip()[:120]
        raise ValueError(
            f"line {data[0][1]}: could not find chromosome, start and end columns in {shown!r}"
        )

    rows = []
    for fields, (line, n) in zip(split, data):
        if len(fields) < chrom_column + 3:
            raise ValueError(
                f"line {n}: expected at least {chrom_column + 3} columns, got {len(fields)}"
            )
        try:
            start, end = int(fields[chrom_column + 1]), int(fields[chrom_column + 2])
        except ValueError as exc:
            raise ValueError(f"line {n}: non-integer coordinates: {line!r}") from exc
        if end <= start:
            raise ValueError(f"line {n}: end <= start: {line!r}")
        # The name column is only ever cosmetic here: coverage is credited to the
        # panel window a row overlaps, never to what the author called it.
        name_column = chrom_column + 3
        named = len(fields) > name_column and fields[name_column] not in ("", ".")
        rows.append(
            {
                "chrom": norm_chrom(fields[chrom_column]),
                "start": start,
                "end": end,
                # norm_chrom, not the raw field: the row's own chrom is
                # normalised, so a name built from the raw one disagreed with it
                # for any BED written without chr prefixes — and disagreed with
                # the web mirror, which has always normalised here.
                "name": fields[name_column]
                if named
                else f"{norm_chrom(fields[chrom_column])}:{start}-{end}",
            }
        )
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
