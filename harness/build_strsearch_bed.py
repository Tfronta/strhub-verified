#!/usr/bin/env python3
"""Build a STRsearch --ref_bed from the illumina-bam-hg38 candidate coordinates.

STRsearch's BED is 11 columns and carries the anchoring flanks as SEQUENCE, so it
cannot be derived from coordinates alone: every field below is read out of hg38 at
the tract the panel already fixed.

Column layout consumed by STRsearch (scripts/STR_search.py:main,
scripts/get_STR_fastq.py:main, scripts/STR_parse.py:main):

  0 Chr      1 Start   2 End     3 Period  4 RefAllele  5 Marker
  6 Official 7 Struct  8 Strand  9 Flank5  10 Flank3

  - Start/End feed `samtools view chr:start-end`, so 1-based inclusive.
  - Strand is read as content_list[-3] but never used by STR_search; it only picks
    which mate get_STR_fastq reverse-complements.
  - Flanks are content_list[-2:], matched literally against the read by match_flank.

Everything is emitted in hg38 PLUS orientation so the motif, the flanks and the
strand column agree with each other.
"""
from __future__ import annotations

import argparse
import collections
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Where hg38 lives on the machine running this. Not committed to the repo (it is
# 3 GB); pass --hg38 or set STRHUB_HG38. The default is the maintainer's layout.
HG38 = os.environ.get("STRHUB_HG38", str(Path.home() / "genomes" / "hg38" / "hg38.fa"))
CANDIDATES = ROOT / "datasets" / "illumina-bam-hg38" / "str_candidates.bed"
FLANK = 15
READ_LEN = 148  # measured on illumina_slices/NA12878.autosomal.bam

# Widen the EXTRACTION interval past the repeat tract.
#
# Start/End feed one thing only: `samtools view chr:start-end` in get_STR_fastq.
# That step then runs `bamToFastq -fq -fq2`, which emits a read only when BOTH
# mates are present. On a shotgun WGS BAM the mate of a read overlapping a 28bp
# tract almost always falls outside it and is never extracted, so bedtools drops
# the read as an orphan. Measured on NA12878: TH01 has 280 reads over the tract
# and 8 survive — under STRsearch's reads_threshold of 30, so the locus is skipped
# entirely. Only D21S11 (127bp, the widest tract) cleared it, which is exactly what
# the first run reported.
#
# Widening costs nothing in accuracy: the STR is located by FLANK SEQUENCE in
# match_flank, never by these coordinates, so the flank columns below are still
# cut from the true tract boundaries. Reads pulled in from the padding that do not
# reach the STR simply fail the unit search and are dropped.
#
# ±300 measured at 544-948 reads/locus. ±1000 would match the panel windows but
# quadruples find_lcseque, a pure-Python double loop per read per unit, against a
# 15-minute job timeout.
WINDOW_PAD = 300

# hg38 chr1. hg19 is 249,250,621 — a one-line discriminator, so the build is
# checked rather than assumed.
HG38_CHR1_LEN = 248956422


def faidx(region: str) -> str:
    out = subprocess.run(
        ["samtools", "faidx", HG38, region],
        capture_output=True, text=True, check=True,
    ).stdout
    return "".join(out.splitlines()[1:]).upper()


def dominant_motif(tract: str, period: int) -> str:
    """Most frequent period-mer in the tract.

    For a pure repeat this is the unit. For a compound repeat (D21S11, vWA, SE33,
    ...) it is the dominant unit, which is what a `[MOTIF]n` structure declares.
    """
    counts = collections.Counter(
        tract[i:i + period] for i in range(len(tract) - period + 1)
    )
    return counts.most_common(1)[0][0]


def assert_hg38() -> None:
    """Refuse to build against the wrong reference.

    Every coordinate here is meaningless under another build, and the failure is
    silent: a BED with hg19 coordinates parses fine, validates against nothing,
    and simply finds no reads.
    """
    fai = Path(f"{HG38}.fai")
    sizes = dict(
        (ln.split("\t")[0], int(ln.split("\t")[1]))
        for ln in fai.read_text().splitlines() if ln.strip()
    )
    got = sizes.get("chr1")
    if got != HG38_CHR1_LEN:
        raise SystemExit(
            f"{HG38} is not hg38: chr1 is {got:,}bp, expected {HG38_CHR1_LEN:,}bp "
            f"({'looks like hg19' if got == 249250621 else 'unknown build'})"
        )
    print(f"reference OK: hg38 (chr1 = {got:,} bp)")


def main() -> int:
    global HG38, CANDIDATES
    ap = argparse.ArgumentParser(
        description="Build the 11-column STRsearch --ref_bed from the hg38 panel candidates."
    )
    ap.add_argument("out", help="where to write the BED (e.g. tools/strsearch-<sha>/assets/regions.bed)")
    ap.add_argument("--hg38", default=HG38, help=f"hg38 FASTA with .fai (default: $STRHUB_HG38 or {HG38})")
    ap.add_argument("--candidates", default=str(CANDIDATES), help=f"candidate tracts BED (default: {CANDIDATES.relative_to(ROOT)})")
    args = ap.parse_args()
    HG38, CANDIDATES = args.hg38, Path(args.candidates)
    if not Path(HG38).exists():
        raise SystemExit(f"hg38 FASTA not found at {HG38}; pass --hg38 or set STRHUB_HG38")
    assert_hg38()
    rows, notes = [], []
    for line in CANDIDATES.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        chrom, start, end = f[0], int(f[1]), int(f[2])
        period, ref_copies, name = int(f[3]), f[4], f[5]

        tract = faidx(f"{chrom}:{start}-{end}")
        left = faidx(f"{chrom}:{start - FLANK}-{start - 1}")
        right = faidx(f"{chrom}:{end + 1}-{end + FLANK}")
        motif = dominant_motif(tract, period)

        # Tract length must equal ref_copies * period if the candidate is a clean
        # 1-based inclusive interval; a mismatch means the coordinate convention
        # or the copy count is off, and the flanks would land inside the repeat.
        expected = round(float(ref_copies) * period)
        if len(tract) != expected:
            notes.append(
                f"{name}: tract {len(tract)}bp != {ref_copies} x {period} = {expected}bp"
            )
        # A flank that is itself repeat sequence anchors ambiguously.
        if motif in left or motif in right:
            notes.append(f"{name}: motif {motif} occurs inside a flank")
        for label, seq in (("5'", left), ("3'", right)):
            if set(seq) - set("ACGT"):
                notes.append(f"{name}: {label} flank is not pure ACGT: {seq}")

        span = len(tract) + 2 * FLANK
        if span > READ_LEN:
            # Not fatal: match_flank returns the least-mismatched position whether
            # or not the flank fits in the read, so the locus still yields calls,
            # anchored less firmly. Worth knowing, not worth excluding.
            notes.append(
                f"{name}: {span}bp to span both flanks vs {READ_LEN}bp reads "
                f"-> anchored on partial flanks"
            )

        # Extraction window: padded. Flanks above: cut from the true tract.
        win_start, win_end = start - WINDOW_PAD, end + WINDOW_PAD
        # The panel windows are tract±1000, so tract±300 sits strictly inside them
        # and validate_bed.py still reports full coverage.
        if WINDOW_PAD > 1000:
            notes.append(f"{name}: window exceeds the ±1000bp panel and would be rejected")

        rows.append([
            chrom, str(win_start), str(win_end), str(period), ref_copies,
            name, name, f"[{motif}]n", "+", left, right,
        ])

    header = "#Chr\tStart\tEnd\tPeriod\tReference allele\tMarker\tOfficial name\t" \
             "STR sequence structure\tStrand\t5' Flanking sequence\t3' Flanking sequence"
    body = "\n".join("\t".join(r) for r in rows)
    Path(args.out).write_text(header + "\n" + body + "\n")

    print(f"wrote {len(rows)} loci to {args.out}")
    print("\n-- checks --")
    print("\n".join(notes) if notes else "all clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
