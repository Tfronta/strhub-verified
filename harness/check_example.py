"""The tool's own example: did the README's command produce what it says?

This is the reviewer's gate. It asks nothing of STRhub's datasets and nothing of
the /data/in contract: the command ran inside the image, in the clone, exactly
as the README shows it, and the wrapper (prepare.example_wrapper) copied every
file it created under /data/out. This script decides whether that counts.

  - With `example.outputs` declared: each glob must match a non-empty file.
  - Without: any non-empty regular file the command created counts. A README
    example that runs to completion and writes nothing is reported as such.
  - With `example.expected`: the produced file named by outputs[0] is compared
    to the golden file the repository publishes, whitespace-normalised. A
    mismatch is reported, not failed: the tool's own example output can lag
    the code by a release, and "produced a file that differs from the
    published one" is a finding for the author, not a broken tool.

Usage:  python harness/check_example.py <manifest.yml> <out_dir> [--json example.json]
Exit:   0 if the example produced its output, 1 otherwise.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402


def _normalised(path: pathlib.Path) -> list[str]:
    return [" ".join(ln.split()) for ln in path.read_text(errors="replace").splitlines()
            if ln.strip() and not ln.startswith("#")]


def check(manifest_path: str, out_dir: str) -> dict:
    m = _manifest.load(manifest_path)
    spec = m.get("example") or {}
    out = pathlib.Path(out_dir)
    result: dict = {"gate": "example", "applicable": bool(spec.get("cmd")), "passed": False,
                    "declared_outputs": spec.get("outputs") or [], "produced": [], "checks": {}}
    if not result["applicable"]:
        return result

    produced = sorted(str(p.relative_to(out)) for p in out.rglob("*")
                      if p.is_file() and p.stat().st_size > 0)
    result["produced"] = produced[:100]
    result["produced_count"] = len(produced)

    declared = spec.get("outputs") or []
    if declared:
        per_glob = {}
        for g in declared:
            matches, refused = _manifest.safe_glob(out, g)
            per_glob[g] = {"matched": [str(p.relative_to(out)) for p in matches[:10]],
                           "ok": refused is None and bool(matches)}
            if refused:
                per_glob[g]["error"] = refused
        result["checks"]["declared_outputs_present"] = all(v["ok"] for v in per_glob.values())
        result["outputs_detail"] = per_glob
        result["passed"] = result["checks"]["declared_outputs_present"]
    else:
        result["checks"]["created_non_empty_file"] = bool(produced)
        result["passed"] = bool(produced)

    expected = spec.get("expected")
    if expected and declared:
        first = result["outputs_detail"][declared[0]]["matched"]
        cwd = pathlib.Path(spec.get("cwd") or "/opt/tool")
        golden = out / pathlib.PurePosixPath(expected)
        # The golden file lives in the clone, not under /data/out; the wrapper
        # only copies files the command touched. It is fetched by the workflow
        # into out_dir/_expected/ when declared (see verify.yml), so look there.
        golden = out / "_expected" / pathlib.PurePosixPath(expected).name
        if first and golden.is_file():
            same = _normalised(out / first[0]) == _normalised(golden)
            result["checks"]["matches_expected"] = same
            result["expected_detail"] = {"golden": expected, "produced": first[0], "cwd": str(cwd)}
        else:
            result["checks"]["matches_expected"] = None
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("out_dir")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    r = check(args.manifest, args.out_dir)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(r, indent=2))
    print(json.dumps(r, indent=2))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
