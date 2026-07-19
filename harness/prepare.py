"""Prepare a verify run: read the manifest, resolve the external dataset, and
stage the input for each matrix leg (own + external).

Centralising this in Python (vs bash in the workflow) keeps it testable and
keeps the YAML small. It emits GitHub-Actions `key=value` step outputs and
stages files under <work>/in_own and <work>/in_external.

Legs:
  own       — the author's BYOR fixture (a path in this repo, OR a remote
              repo+ref+path fetched from raw.githubusercontent.com).
  external  — a typed reference dataset from datasets/ matched by inputs.type.
              Absent/unmatched → external_ready=0 → the leg is reported N/A.

Usage:
  python harness/prepare.py <tool> --work work [--github-output]
"""
from __future__ import annotations
import argparse
import pathlib
import shutil
import sys
import urllib.request

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import datasets as datasets_lib  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com"

# Coordinate-based tools read /data/in/regions.bed; the author's BED (whatever its
# original name) is staged under this canonical name so one run cmd fits both legs.
REGIONS_CANONICAL = "regions.bed"


def _bam_sidecar(bam: pathlib.Path) -> pathlib.Path:
    """Return the .bai path for a BAM (handles *.codis.bam → *.codis.bam.bai)."""
    return bam.parent / f"{bam.name}.bai"


def _copy_bam_pair(
    src_bam: pathlib.Path,
    dest_dir: pathlib.Path,
    canonical: str | None = None,
) -> bool:
    """Copy a BAM and its .bai sidecar into dest_dir, optionally renaming to
    a canonical filename so that the same run command works for both legs."""
    if not src_bam.is_file():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = canonical or src_bam.name
    shutil.copy2(src_bam, dest_dir / dest_name)
    bai = _bam_sidecar(src_bam)
    if bai.is_file():
        shutil.copy2(bai, dest_dir / f"{dest_name}.bai")
    return True


def _repo_path(repo_url: str) -> str:
    return (
        repo_url.strip()
        .replace("https://github.com/", "")
        .rstrip("/")
        .removesuffix(".git")
    )


def stage_own(
    fixture,
    work_in: pathlib.Path,
    canonical: str | None = None,
) -> bool:
    """Stage the author's own fixture. Returns True if staged.

    When *canonical* is set (e.g. ``"input.bam"``), the primary data file is
    renamed so that the same run command works identically for the own and
    external legs.
    """
    work_in.mkdir(parents=True, exist_ok=True)
    if isinstance(fixture, dict):
        # Remote BYOR: fetch the single file from the author's PUBLIC repo.
        repo = _repo_path(fixture["repo"])
        ref = fixture["ref"]
        path = fixture["path"].lstrip("/")
        url = f"{RAW}/{repo}/{ref}/{path}"
        raw_name = pathlib.Path(path).name
        dest_name = canonical or raw_name
        dest = work_in / dest_name
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 (public raw URL)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::could not fetch BYOR fixture {url}: {exc}",
                  file=sys.stderr)
            return False
        if dest.stat().st_size > 0:
            # For BAM files fetched remotely, also try to fetch the .bai sidecar.
            if dest_name.endswith(".bam"):
                for bai_suffix in [".bai", ".bam.bai"]:
                    bai_url = f"{RAW}/{repo}/{ref}/{path}{bai_suffix}"
                    bai_dest = work_in / f"{dest_name}.bai"
                    try:
                        urllib.request.urlretrieve(bai_url, bai_dest)  # noqa: S310
                        if bai_dest.stat().st_size > 0:
                            break
                        bai_dest.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        bai_dest.unlink(missing_ok=True)
            return True
        return False
    # Local path in this repo: copy the directory contents.
    src = ROOT / str(fixture)
    if not src.exists():
        print(f"::warning::own fixture path not found: {src}", file=sys.stderr)
        return False
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, work_in / f.name)
    elif src.suffix == ".bam" or src.name.endswith(".bam"):
        if not _copy_bam_pair(src, work_in, canonical):
            return False
    else:
        dest_name = canonical or src.name
        shutil.copy2(src, work_in / dest_name)
    return any(work_in.iterdir())


def stage_regions(regions, legs: list[pathlib.Path]) -> str:
    """Stage the regions BED into every leg as canonical ``regions.bed``.

    An explicit ``inputs.regions`` takes precedence over any per-tool asset
    regions.bed already staged (which is why this runs after asset staging).

    Returns the provenance, used by the workflow to decide whether to validate and
    by the report to say who chose the regions:
      "tool"   — the author chose them: uploaded through the form (stored under the
                 tool's assets/), or a remote pointer. VALIDATED against the panel.
      "strhub" — a path committed by us, or a legacy per-tool asset. Trusted.
      "none"   — no regions BED anywhere.
    """
    def _fan_out(src: pathlib.Path) -> bool:
        for leg in legs:
            leg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, leg / REGIONS_CANONICAL)
        return True

    if isinstance(regions, dict) and "path" in regions and "repo" not in regions:
        # Author uploaded it; we store it. The file is ours to read, but the CHOICE
        # of loci was theirs — provenance must survive that, or the report would
        # credit STRhub for the author's panel.
        src = ROOT / regions["path"]
        if not src.is_file():
            print(f"::error::uploaded regions BED not found: {src}", file=sys.stderr)
            return "none"
        _fan_out(src)
        return "tool" if regions.get("provided_by") == "author" else "strhub"

    if isinstance(regions, dict):
        # Remote pointer (deprecated; hand-written manifests only). Fetch once from
        # the author's PUBLIC repo, then fan out.
        repo = _repo_path(regions["repo"])
        ref = regions["ref"]
        path = regions["path"].lstrip("/")
        url = f"{RAW}/{repo}/{ref}/{path}"
        first = legs[0] / REGIONS_CANONICAL
        legs[0].mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, first)  # noqa: S310 (public raw URL)
        except Exception as exc:  # noqa: BLE001
            print(f"::error::could not fetch regions BED {url}: {exc}", file=sys.stderr)
            return "none"
        if first.stat().st_size == 0:
            print(f"::error::regions BED is empty: {url}", file=sys.stderr)
            return "none"
        for leg in legs[1:]:
            leg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(first, leg / REGIONS_CANONICAL)
        return "tool"

    if isinstance(regions, str):
        src = ROOT / regions
        if not src.is_file():
            print(f"::warning::regions path not found: {src}", file=sys.stderr)
            return "none"
        _fan_out(src)
        return "strhub"

    # No explicit regions — a legacy per-tool asset may already have staged one.
    if any((leg / REGIONS_CANONICAL).is_file() for leg in legs):
        return "strhub"
    return "none"


def stage_external(input_type, work_in: pathlib.Path) -> tuple[bool, str]:
    """Stage the typed external dataset. Returns (staged, dataset_name).

    Files are renamed to their ``canonical_input`` name (if configured) so the
    same run command works identically for both the own and external legs.
    """
    rec = datasets_lib.resolve(input_type)
    if not rec:
        return False, ""
    data = ROOT / rec["data"]
    if not data.exists():
        return False, ""
    work_in.mkdir(parents=True, exist_ok=True)
    canonical = rec.get("canonical_input")
    if rec.get("format") == "bam" or str(data).endswith(".bam"):
        if not _copy_bam_pair(data, work_in, canonical):
            return False, ""
        # Verify the index was staged too.
        expected_bai = f"{canonical}.bai" if canonical else None
        bam_index = rec.get("bam_index")
        if bam_index:
            idx_src = ROOT / bam_index
            if idx_src.is_file() and expected_bai:
                idx_dest = work_in / expected_bai
                if not idx_dest.exists():
                    shutil.copy2(idx_src, idx_dest)
    else:
        dest_name = canonical or data.name
        shutil.copy2(data, work_in / dest_name)
    return True, rec.get("name", input_type or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tool")
    ap.add_argument("--work", default="work")
    args = ap.parse_args()

    mf = ROOT / "tools" / args.tool / "manifest.yml"
    m = yaml.safe_load(mf.read_text())
    inputs = m.get("inputs", {})
    fixture = inputs.get("fixture")
    input_type = inputs.get("type")
    regions = inputs.get("regions")

    # Resolve canonical filename so both legs use identical names.
    canonical = None
    if input_type:
        ds_rec = datasets_lib.resolve(input_type)
        if ds_rec:
            canonical = ds_rec.get("canonical_input")

    work = pathlib.Path(args.work)
    # The own leg runs only when the author declared a BYOR fixture. Without one
    # we do NOT fall back to a placeholder fixture (that produced spurious
    # Content failures on a 2-read dummy); the own leg is simply N/A and the
    # badge rests on the external typed-dataset leg (chosen by inputs.type).
    if fixture is None:
        own_ready = False
        fixture_source = "none"
    else:
        own_ready = stage_own(fixture, work / "in_own", canonical)
        fixture_source = "tool" if isinstance(fixture, dict) else "strhub"
    external_ready, dataset_name = stage_external(input_type, work / "in_external")

    # Stage tool-specific assets into both legs. A legacy per-tool regions.bed
    # lives here; an explicit inputs.regions (staged next) overrides it.
    legs = [work / "in_own", work / "in_external"]
    assets_dir = ROOT / "tools" / args.tool / "assets"
    if assets_dir.is_dir():
        for leg in legs:
            leg.mkdir(parents=True, exist_ok=True)
            for f in assets_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, leg / f.name)

    # Regions BED (coordinate-based tools). Precedence over the asset above.
    regions_source = stage_regions(regions, legs)

    # Supported-loci panel for this input type — the validator's reference. Emitted
    # so the workflow can pre-flight the author's BED before any gate runs.
    supported_loci = ""
    min_loci = ""
    if input_type:
        ds_rec = datasets_lib.resolve(input_type)
        if ds_rec:
            supported_loci = ds_rec.get("supported_loci", "") or ""
            min_loci = str(ds_rec.get("min_loci", "") or "")

    ref_genome_url = ""
    ref_genome_filename = ""
    if input_type:
        ds_rec = datasets_lib.resolve(input_type)
        if ds_rec and ds_rec.get("reference_genome"):
            rg = ds_rec["reference_genome"]
            ref_genome_url = rg.get("url", "")
            ref_genome_filename = rg.get("filename", "")

    out = [
        f"ref={m['source']['ref']}",
        f"cmd={' '.join(m['run']['cmd'].split())}",
        f"dockerdir=tools/{args.tool}",
        f"dockerfile={m['environment']['dockerfile']}",
        f"timeout={m['run'].get('timeout_minutes', 30)}",
        f"manifest={mf}",
        f"repo={m['source']['repo']}",
        f"input_type={input_type or ''}",
        f"own_ready={'1' if own_ready else '0'}",
        f"external_ready={'1' if external_ready else '0'}",
        f"dataset_name={dataset_name}",
        f"ref_genome_url={ref_genome_url}",
        f"ref_genome_filename={ref_genome_filename}",
        f"fixture_source={fixture_source}",
        f"regions_source={regions_source}",
        f"supported_loci={supported_loci}",
        f"min_loci={min_loci}",
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
