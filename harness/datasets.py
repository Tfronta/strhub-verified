"""Resolve a typed external reference dataset for a given input type.

The verify workflow's external matrix leg calls this to find a dataset
compatible with the manifest's `inputs.type`. If nothing matches, the external
leg is N/A (never a failure) — STRhub does not penalise a tool just because no
shared dataset exists yet for its assay.

Usage:
  python harness/datasets.py <type>            # prints the data path or '' (N/A)
  python harness/datasets.py <type> --json     # prints the full dataset record
"""
from __future__ import annotations
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "datasets" / "index.json"


def load_index() -> dict:
    if not INDEX.exists():
        return {"datasets": {}}
    return json.loads(INDEX.read_text())


def resolve(input_type: str | None) -> dict | None:
    """Return the dataset record for input_type, or None if no match (N/A)."""
    if not input_type:
        return None
    entry = load_index().get("datasets", {}).get(input_type)
    if not entry:
        return None
    data = entry.get("data")
    if data and not (ROOT / data).exists():
        return None  # indexed but the file is missing → treat as N/A
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("type", nargs="?", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rec = resolve(args.type)
    if args.json:
        print(json.dumps(rec or {}, indent=2))
    else:
        print(rec.get("data", "") if rec else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
