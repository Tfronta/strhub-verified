"""Run the shared BED-parsing cases against parse_bed3.

The same file is run by the web form's vitest suite, so a change that makes one
side accept a BED the other rejects fails here. That divergence is the failure
this guards: a BED accepted in the form and rejected by this pre-flight aborts a
run with no report and no badge.

Usage:  python harness/test_validate_bed.py
Exits non-zero on the first disagreement, listing every failure.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from validate_bed import parse_bed3  # noqa: E402

CASES = pathlib.Path(__file__).resolve().parent / "testdata" / "bed_cases.json"
WEB_COPY = (
    pathlib.Path(__file__).resolve().parents[2]
    / "strhub-web"
    / "lib"
    / "verified"
    / "bed-cases.json"
)


def check_web_copy_matches() -> list[str]:
    """The web keeps its own copy so its CI can run these without this checkout."""
    if not WEB_COPY.exists():
        return []
    if WEB_COPY.read_text() != CASES.read_text():
        return [
            f"{WEB_COPY} differs from {CASES}. The shared cases must be identical "
            "in both repositories — copy one over the other."
        ]
    return []


def run() -> list[str]:
    data = json.loads(CASES.read_text())
    failures: list[str] = []

    for case in data["cases"]:
        name = case["name"]
        try:
            rows = parse_bed3(case["bed"])
        except ValueError as exc:
            if not case.get("throws"):
                failures.append(f"{name}: raised {exc}, expected rows")
            continue

        if case.get("throws"):
            failures.append(f"{name}: parsed {len(rows)} row(s), expected an error")
            continue

        got = [
            {"chrom": r["chrom"], "start": r["start"], "end": r["end"], "name": r["name"]}
            for r in rows
        ]
        if got != case["rows"]:
            failures.append(f"{name}:\n    expected {case['rows']}\n    got      {got}")

    return failures + check_web_copy_matches()


if __name__ == "__main__":
    problems = run()
    if problems:
        print(f"{len(problems)} failure(s):\n")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    total = len(json.loads(CASES.read_text())["cases"])
    print(f"{total} shared BED cases passed")
