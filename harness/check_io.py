"""IO gate: does the tool produce the output it claims, in the declared format?

This is the line that keeps the project on the executability side and off the
concordance side. We check that files exist, are non-empty, parse as the
declared format, and clear a minimum record count (to catch exit-0-but-empty
silent failures). We do NOT check whether the values are biologically correct.

Usage:  python harness/check_io.py <manifest.yml> <output_dir> [--json io_result.json]
Exit:   0 if all required checks pass, 1 otherwise.
"""
from __future__ import annotations
import argparse
import csv
import glob
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402


def _count_records(path: pathlib.Path, fmt: str) -> int:
    text = path.read_text(errors="replace")
    if fmt == "vcf":
        return sum(1 for ln in text.splitlines() if ln and not ln.startswith("#"))
    if fmt == "json":
        obj = json.loads(text)
        return len(obj) if isinstance(obj, (list, dict)) else 1
    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        rows = list(csv.reader(text.splitlines(), delimiter=delim))
        return max(0, len(rows) - 1)  # minus header
    return sum(1 for ln in text.splitlines() if ln.strip())  # text


def check(manifest_path: str, out_dir: str) -> dict:
    m = _manifest.load(manifest_path)
    out = pathlib.Path(out_dir)
    checks = []
    ok = True

    for spec in m["outputs"]:
        matches = sorted(out.glob(spec["path"]))
        entry = {"path": spec["path"], "format": spec["format"], "checks": {}}

        present = bool(matches)
        entry["checks"]["exists"] = present
        if not present:
            entry["passed"] = ok = False
            checks.append(entry)
            continue

        f = matches[0]
        entry["resolved"] = str(f.relative_to(out))
        nonempty = f.stat().st_size > 0
        entry["checks"]["non_empty"] = nonempty

        try:
            n = _count_records(f, spec["format"])
            parses = True
        except Exception as exc:  # noqa: BLE001
            n, parses = 0, False
            entry["parse_error"] = str(exc)
        entry["checks"]["parses_as_" + spec["format"]] = parses
        entry["records"] = n
        entry["checks"]["min_records"] = n >= spec.get("min_records", 1)

        if spec.get("must_contain"):
            blob = f.read_text(errors="replace")
            missing = [s for s in spec["must_contain"] if s not in blob]
            entry["checks"]["must_contain"] = not missing
            if missing:
                entry["missing"] = missing

        entry["passed"] = all(entry["checks"].values())
        ok = ok and entry["passed"]
        checks.append(entry)

    return {"gate": "io", "passed": ok, "outputs": checks}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("output_dir")
    ap.add_argument("--json", default="io_result.json")
    args = ap.parse_args()

    result = check(args.manifest, args.output_dir)
    pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
