#!/usr/bin/env python3
"""Generate the medical STR panel candidates from STRchive and four tool catalogs.

The medical panel is defined by literature, not by STRhub: a disease-associated
STR locus enters when STRchive lists it AND the default catalogs of at least
MIN_CATALOGS of the four tools below ship it. "Most common" therefore means
"what the medical STR tools genotype out of the box", which is exactly what a
verification run with a tool's unamended catalog needs reads for.

Every source is pinned to a commit, so the selection is reproducible:

  STRchive      coordinates, motif and copy number, as published (hg38)
  EH            ExpansionHunter's variant catalog
  TRGT          TRGT's pathogenic repeat definitions
  STRipy        the STRipy pipeline catalog
  str-analysis  the Broad's disease-locus catalog (gnomAD, TRExplorer)

A catalog "has" a STRchive locus when one of its intervals overlaps the STRchive
interval padded by TOL bp: the catalogs mix 0- and 1-based coordinates and trim
flanking interruptions differently, so names (C9ORF72 vs C9orf72) and exact
coordinates both undercount.

Writes, under datasets/illumina-bam-hg38-med/:
  catalog_crosswalk.tsv   every STRchive locus with its catalog membership
  str_candidates.bed      the selected loci, HipSTR layout (input to build_panel.py)
and pacbio_slices/medical_pm10kb.bed, the ±10 kb long-read slice windows.

Usage:  python harness/build_medical_candidates.py [--check]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "illumina-bam-hg38-med"
LONG_READ_WINDOWS = ROOT / "pacbio_slices" / "medical_pm10kb.bed"

MIN_CATALOGS = 3
TOL = 25
LONG_READ_FLANK = 10_000

STRCHIVE = ("dashnowlab/STRchive", "e964fa88df3b2189ee478cbd6eaad15bb28e3a0a", "data/STRchive-loci.json")
CATALOGS = {
    "EH": ("Illumina/ExpansionHunter", "7ff9aa5335fdb5b3124cc0f365a64bb7a185803a",
           "variant_catalog/hg38/variant_catalog.json"),
    "TRGT": ("PacificBiosciences/trgt", "3d10c759baa0c6eda579299d789ecb87aaee4d2e",
             "repeats/pathogenic_repeats.hg38.bed"),
    "STRipy": ("andreassh/stripy-pipeline", "e8265c5a22ce3e2f665d899b0c1f23d647289ec8", "catalog.json"),
    "str-analysis": ("broadinstitute/str-analysis", "57a6ac8cf91782cf504b6c0e300c0b7d6daa4669",
                     "str_analysis/variant_catalogs/variant_catalog_without_offtargets.GRCh38.json"),
}


def raw_url(repo: str, ref: str, path: str) -> str:
    if repo.startswith("andreassh/"):
        return f"https://gitlab.com/{repo}/-/raw/{ref}/{path}"
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def fetch(spec: tuple[str, str, str]) -> str:
    with urllib.request.urlopen(raw_url(*spec), timeout=60) as r:
        return r.read().decode()


def parse_region(r: str) -> tuple[str, int, int]:
    m = re.match(r"(chr[0-9XYM]+):(\d+)-(\d+)$", r.strip())
    if not m:
        raise ValueError(f"unreadable region {r!r}")
    return m.group(1), int(m.group(2)), int(m.group(3))


def regions_of(value) -> list[tuple[str, int, int]]:
    return [parse_region(r) for r in (value if isinstance(value, list) else [value])]


def catalog_intervals(name: str, text: str) -> list[tuple[str, list[tuple[str, int, int]]]]:
    if name == "TRGT":
        out = []
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            f = line.split("\t")
            out.append((re.search(r"ID=([^;]+)", f[3]).group(1), [(f[0], int(f[1]), int(f[2]))]))
        return out
    data = json.loads(text)
    if name == "STRipy":
        return [(x["Locus"], [parse_region(x["LocationCoordinates"]["hg38"])]) for x in data]
    return [(x["LocusId"], regions_of(x["ReferenceRegion"])) for x in data]


def build() -> dict[pathlib.Path, str]:
    strchive = json.loads(fetch(STRCHIVE))
    members = {e["id"]: [] for e in strchive}
    for name, spec in CATALOGS.items():
        for _label, regs in catalog_intervals(name, fetch(spec)):
            for e in strchive:
                if any(c == e["chrom"] and s <= e["stop_hg38"] + TOL and t >= e["start_hg38"] - TOL
                       for c, s, t in regs):
                    if name not in members[e["id"]]:
                        members[e["id"]].append(name)

    def key(e):
        return (-len(members[e["id"]]), e["chrom"], e["start_hg38"])

    loci = sorted(strchive, key=key)
    selected = [e for e in loci if len(members[e["id"]]) >= MIN_CATALOGS]
    names = [e["gene"] for e in selected]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SystemExit(f"gene symbols repeat in the selection, panel names would collide: {dupes}")

    pins = "".join(f"#   {n:<13} {r} @ {ref[:10]}  {p}\n" for n, (r, ref, p) in
                   [("STRchive", STRCHIVE)] + list(CATALOGS.items()))

    cross = ["# Every STRchive locus and which of the four tool catalogs ship it. Generated by\n"
             "# harness/build_medical_candidates.py; DO NOT EDIT BY HAND. Sources:\n" + pins +
             "\t".join(["strchive_id", "gene", "chrom", "start_hg38", "stop_hg38", "motif",
                        "evidence", "n_catalogs", *CATALOGS, "selected"]) + "\n"]
    for e in loci:
        m = members[e["id"]]
        cross.append("\t".join([
            e["id"], e["gene"], e["chrom"], str(e["start_hg38"]), str(e["stop_hg38"]),
            ",".join(e["reference_motif_reference_orientation"] or []),
            ",".join(e["evidence"] or []), str(len(m)),
            *("yes" if c in m else "" for c in CATALOGS),
            "yes" if len(m) >= MIN_CATALOGS else "",
        ]) + "\n")

    cands = [
        "# Medical STR candidates for the illumina-bam-hg38-med slice (HipSTR layout:\n"
        "# chrom start end period ref_copies NAME motif; start 1-based, as HipSTR reads it).\n"
        "#\n"
        f"# The STRchive loci that at least {MIN_CATALOGS} of 4 tool catalogs ship (see\n"
        "# catalog_crosswalk.tsv). Coordinates, motif (reference orientation) and reference\n"
        "# copy number are STRchive's (length / period where STRchive gives none or 0);\n"
        "# the name is its gene symbol. Generated by\n"
        "# harness/build_medical_candidates.py; DO NOT EDIT BY HAND. Sources:\n" + pins +
        "#\n"
        "# Input to harness/build_panel.py, which measures each against the BAM and decides\n"
        "# which make the panel (loci.bed).\n"
    ]
    windows = []
    for e in sorted(selected, key=lambda e: (e["chrom"], e["start_hg38"])):
        motif = (e["reference_motif_reference_orientation"] or ["N/A"])[0]
        period = e["motif_len"] or len(motif)
        # STRchive gives no copy number for a few loci, and 0 where the
        # reference carries none of the pathogenic motif (DAB1, XYLT1). HipSTR's
        # column means copies of the reference tract, so those get length / period.
        copies = e["ref_copies"]
        if not copies:
            copies = round((e["stop_hg38"] - e["start_hg38"]) / period, 1)
        cands.append(f"{e['chrom']}\t{e['start_hg38'] + 1}\t{e['stop_hg38']}\t{period}\t{copies}\t"
                     f"{e['gene']}\t{motif}\n")
        windows.append(f"{e['chrom']}\t{max(0, e['start_hg38'] - LONG_READ_FLANK)}\t"
                       f"{e['stop_hg38'] + LONG_READ_FLANK}\t{e['gene']}\n")

    return {
        DATASET / "catalog_crosswalk.tsv": "".join(cross),
        DATASET / "str_candidates.bed": "".join(cands),
        LONG_READ_WINDOWS: "".join(windows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed files differ")
    args = ap.parse_args()
    drift = []
    for path, text in build().items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                drift.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path.relative_to(ROOT)}")
    if drift:
        print("out of date: " + ", ".join(drift), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
