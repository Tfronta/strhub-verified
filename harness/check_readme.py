"""README "minimum-to-run" check (Eje 3) — ADVISORY ONLY, never pass/fail.

This is not a free review. It is a presence checklist over the author's README:
is there enough for a third party to run the tool end-to-end without help? Five
items (plan §4):
  1. Install / environment setup
  2. The run command
  3. What input it expects (format)
  4. What output it produces
  5. Dependencies / versions

The result is advisory: it NEVER gates the execution badge. It is deterministic
(keyword/heuristic based) so it has no API cost and no non-determinism; an
optional AI reviewer could be layered on later but must stay advisory.

Usage:
  python harness/check_readme.py <readme_path> [--json out.json] [--slug NAME]
Exit: always 0 (advisory).
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re

ITEMS = [
    (
        "install",
        [r"\binstall(ation|ing|)\b", r"\bsetup\b", r"pip install", r"conda ",
         r"docker build", r"\bmake\b", r"\bcmake\b", r"requirements\.txt",
         r"environment\.ya?ml", r"build instructions"],
    ),
    (
        "command",
        [r"\busage\b", r"how to run", r"\brun\b", r"\bcommand\b",
         r"```[a-z]*\s*\$?\s*\S+", r"example", r"\bcli\b", r"--\w"],
    ),
    (
        "input",
        [r"\binput\b", r"\bfastq\b", r"\bbam\b", r"\bcram\b", r"\bvcf\b",
         r"\breads?\b", r"--in(put)?\b", r"accepts", r"expects"],
    ),
    (
        "output",
        [r"\boutput\b", r"\bproduces?\b", r"\bresult", r"--out(put)?\b",
         r"\btsv\b", r"\bcsv\b", r"writes", r"generates"],
    ),
    (
        "dependencies",
        [r"\bdependenc(y|ies)\b", r"requirements", r"\bversions?\b",
         r"python\s*3", r"\bdepends\b", r"prerequisite", r"==\d", r">=\d"],
    ),
]


def check_text(text: str) -> dict:
    low = text.lower()
    checks: dict[str, dict] = {}
    score = 0
    for name, patterns in ITEMS:
        matched = next((p for p in patterns if re.search(p, low)), None)
        present = matched is not None
        if present:
            score += 1
        checks[name] = {"present": present, "matched": matched}
    return {
        "gate": "readme",
        "advisory": True,
        "score": score,
        "max": len(ITEMS),
        "checks": checks,
        "empty": len(text.strip()) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("readme", help="path to the README file (or '-' for none)")
    ap.add_argument("--json", default="readme_result.json")
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()

    p = pathlib.Path(args.readme)
    text = p.read_text(errors="replace") if args.readme != "-" and p.exists() else ""
    result = check_text(text)
    if args.slug:
        result["slug"] = args.slug

    pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0  # advisory: never fail the workflow


if __name__ == "__main__":
    raise SystemExit(main())
