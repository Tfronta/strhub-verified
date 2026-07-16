#!/usr/bin/env python3
"""Generate datasets/<type>/loci.bed — the supported-loci panel for a slice BAM.

STRhub Verified ships SLICES, not whole genomes. The panel is the contract with
the tool author: "your regions BED may target anything inside these windows, and
we guarantee reads are there." A submitted BED that falls outside the panel is a
rejected submission, NOT a failed tool.

Because it is a promise, it is derived from EVIDENCE, not intent:

  window = (locus +/- FLANK), trimmed inward until every base has >= FLOOR reads

A locus whose STR region itself cannot reach FLOOR is EXCLUDED — promising it
would hand the author a low-confidence call and let them think their tool broke.
(This is what happens at DYS385_1 in HG002: the palindromic DYS385a/b pair is
collapsed in the GIAB alignment, starving the 'a' copy to ~10x. Not a slicing
artifact — the reads are absent from the source BAM.)

Output: 5-column BED — chrom, start, end, name, score=min_depth
Regenerate after ANY change to a slice BAM; the score column is the regression signal.

Usage:
  python harness/build_panel.py                 # regenerate all panels
  python harness/build_panel.py --check         # verify committed panels are current
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

FLANK = 1000   # bp each side of the STR, matching how the Illumina slices were cut
FLOOR = 10     # min reads/base; below this no STR caller can attempt a call

# dataset slug -> (slice BAM, STR-coordinate source, flank)
# The STR source is a HipSTR-format BED: chrom start end period copies NAME [motif]
PANELS = {
    "illumina-bam-hg38": (
        "illumina_slices/NA12878.autosomal.bam",
        "tools/hipstr-v0-7/assets/regions.bed",
        FLANK,
    ),
    "illumina-bam-hg38-y": (
        "illumina_slices/HG002.ystr.bam",
        "tools/hipstr-v0-7-y/assets/regions.bed",
        FLANK,
    ),
}


def read_str_bed(path: pathlib.Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith(("#", "track", "browser")):
            continue
        f = line.split("\t")
        rows.append({"chrom": f[0], "start": int(f[1]), "end": int(f[2]), "name": f[5]})
    return rows


def depths(bam: pathlib.Path, chrom: str, start: int, end: int) -> dict[int, int]:
    """Per-base depth across [start, end), 0-based half-open. -a keeps zero-depth bases."""
    p = subprocess.run(
        ["samtools", "depth", "-a", "-r", f"{chrom}:{start + 1}-{end}", str(bam)],
        capture_output=True, text=True, check=True,
    )
    d = {}
    for line in p.stdout.splitlines():
        if not line:
            continue
        _, pos, dep = line.split("\t")
        d[int(pos) - 1] = int(dep)  # back to 0-based
    return d


def base_locus(name: str) -> str:
    """DYS389II.1 -> DYS389II ; DYS448.1 -> DYS448 ; DYS19/DYS394 kept as-is."""
    return name.split(".")[0]


def merge_overlapping(wins: list[dict]) -> list[dict]:
    """DYS389I/II.1/II.2 sit on top of each other; so do DYS448.1/.2."""
    wins = sorted(wins, key=lambda w: (w["chrom"], w["start"]))
    out: list[dict] = []
    for w in wins:
        if out and out[-1]["chrom"] == w["chrom"] and w["start"] <= out[-1]["end"]:
            out[-1]["end"] = max(out[-1]["end"], w["end"])
            out[-1]["strs"].extend(w["strs"])
        else:
            out.append(dict(w, strs=list(w["strs"])))
    return out


def window_around_str(
    dep: dict[int, int], lo: int, hi: int, str_min: int, str_max: int, floor: int
) -> tuple[int, int] | None:
    """Largest contiguous run of bases >= floor that fully contains the STR.

    Grown OUTWARD from the STR rather than trimmed inward from the edges: an
    inward trim stops at the first base above the floor and so silently keeps
    interior dips below it, which would break the >= floor promise mid-window.

    Returns None when the STR itself dips below floor — the locus is unsupported.
    """
    if any(dep.get(p, 0) < floor for p in range(str_min, str_max)):
        return None
    s = str_min
    while s > lo and dep.get(s - 1, 0) >= floor:
        s -= 1
    e = str_max
    while e < hi and dep.get(e, 0) >= floor:
        e += 1
    return s, e


def build_panel(slug: str, bam_rel: str, str_rel: str, flank: int) -> tuple[list[dict], list[dict]]:
    bam = ROOT / bam_rel
    strs = read_str_bed(ROOT / str_rel)

    wins = [
        {"chrom": s["chrom"], "start": max(0, s["start"] - flank), "end": s["end"] + flank, "strs": [s]}
        for s in strs
    ]

    kept: list[dict] = []
    dropped: list[dict] = []

    for w in merge_overlapping(wins):
        dep = depths(bam, w["chrom"], w["start"], w["end"])

        names = sorted({base_locus(x["name"]) for x in w["strs"]})
        str_min = min(x["start"] for x in w["strs"])
        str_max = max(x["end"] for x in w["strs"])
        str_min_depth = min((dep.get(p, 0) for p in range(str_min, str_max)), default=0)

        record = {
            "chrom": w["chrom"], "name": "/".join(names),
            "str_span": (str_min, str_max), "str_min_depth": str_min_depth,
        }

        span = window_around_str(dep, w["start"], w["end"], str_min, str_max, FLOOR)
        if span is None:
            record["reason"] = (
                f"STR {w['chrom']}:{str_min}-{str_max} drops to {str_min_depth}x, "
                f"below the {FLOOR}x floor"
            )
            dropped.append(record)
            continue

        s, e = span
        record["start"], record["end"] = s, e
        record["min_depth"] = min(dep.get(p, 0) for p in range(s, e))
        kept.append(record)

    kept.sort(key=lambda r: (chrom_key(r["chrom"]), r["start"]))
    dropped.sort(key=lambda r: (chrom_key(r["chrom"]), r["str_span"][0]))
    return kept, dropped


def chrom_key(c: str):
    v = c.replace("chr", "")
    return (0, int(v)) if v.isdigit() else (1, v)


def render(slug: str, bam_rel: str, kept: list[dict], dropped: list[dict], flank: int) -> str:
    lines = [
        f"# STRhub Verified — supported-loci panel for `{slug}`",
        f"# Generated by harness/build_panel.py from {bam_rel}. DO NOT EDIT BY HAND.",
        "#",
        "# This slice is NOT a whole genome. A regions BED submitted for verification",
        "# must overlap these windows; anything outside is a rejected submission, not a",
        "# failed tool.",
        "#",
        f"# window = the widest span around the STR, capped at +/-{flank}bp, in which EVERY",
        f"# base has >= {FLOOR} reads. Loci whose STR itself drops below that floor are excluded.",
        "# columns: chrom  start  end  name  score(=min depth across the window)",
    ]
    if dropped:
        lines.append("#")
        lines.append(f"# EXCLUDED — the slice cannot support these ({len(dropped)}):")
        for d in dropped:
            lines.append(f"#   {d['name']}: {d['reason']}")
    lines.append("#")
    for r in kept:
        lines.append(f"{r['chrom']}\t{r['start']}\t{r['end']}\t{r['name']}\t{r['min_depth']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if a committed panel differs from what the BAM implies")
    args = ap.parse_args()

    stale = []
    for slug, (bam_rel, str_rel, flank) in PANELS.items():
        out_path = ROOT / "datasets" / slug / "loci.bed"
        kept, dropped = build_panel(slug, bam_rel, str_rel, flank)
        text = render(slug, bam_rel, kept, dropped, flank)

        print(f"\n{'=' * 74}\n{slug}\n{'=' * 74}")
        print(f"  {len(kept)} loci soportados, {len(dropped)} excluidos "
              f"(min-depth global: {min(r['min_depth'] for r in kept)}x)")
        for r in kept:
            print(f"    {r['name']:<22}{r['chrom']}:{r['start']}-{r['end']}  {r['min_depth']}x")
        for d in dropped:
            print(f"    EXCLUIDO  {d['name']:<12} {d['reason']}")

        if args.check:
            current = out_path.read_text() if out_path.exists() else ""
            if current != text:
                stale.append(slug)
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text)
            print(f"  -> escrito {out_path.relative_to(ROOT)}")

    if args.check and stale:
        print(f"\nPaneles desactualizados: {', '.join(stale)}. Corré harness/build_panel.py.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
