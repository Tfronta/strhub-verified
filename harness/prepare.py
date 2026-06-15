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


def _repo_path(repo_url: str) -> str:
    return (
        repo_url.strip()
        .replace("https://github.com/", "")
        .rstrip("/")
        .removesuffix(".git")
    )


def stage_own(fixture, work_in: pathlib.Path) -> bool:
    """Stage the author's own fixture. Returns True if staged."""
    work_in.mkdir(parents=True, exist_ok=True)
    if isinstance(fixture, dict):
        # Remote BYOR: fetch the single file from the author's PUBLIC repo.
        repo = _repo_path(fixture["repo"])
        ref = fixture["ref"]
        path = fixture["path"].lstrip("/")
        url = f"{RAW}/{repo}/{ref}/{path}"
        dest = work_in / pathlib.Path(path).name
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 (public raw URL)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::could not fetch BYOR fixture {url}: {exc}",
                  file=sys.stderr)
            return False
        return dest.stat().st_size > 0
    # Local path in this repo: copy the directory contents.
    src = ROOT / str(fixture)
    if not src.exists():
        print(f"::warning::own fixture path not found: {src}", file=sys.stderr)
        return False
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, work_in / f.name)
    else:
        shutil.copy2(src, work_in / src.name)
    return any(work_in.iterdir())


def stage_external(input_type, work_in: pathlib.Path) -> tuple[bool, str]:
    """Stage the typed external dataset. Returns (staged, dataset_name)."""
    rec = datasets_lib.resolve(input_type)
    if not rec:
        return False, ""
    data = ROOT / rec["data"]
    if not data.exists():
        return False, ""
    work_in.mkdir(parents=True, exist_ok=True)
    shutil.copy2(data, work_in / data.name)
    return True, rec.get("name", input_type or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tool")
    ap.add_argument("--work", default="work")
    args = ap.parse_args()

    mf = ROOT / "tools" / args.tool / "manifest.yml"
    m = yaml.safe_load(mf.read_text())
    inputs = m.get("inputs", {})
    fixture = inputs.get("fixture", "fixtures/example")
    input_type = inputs.get("type")

    work = pathlib.Path(args.work)
    own_ready = stage_own(fixture, work / "in_own")
    external_ready, dataset_name = stage_external(input_type, work / "in_external")

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
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
