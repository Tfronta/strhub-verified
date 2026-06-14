"""Assemble the attestation report + a shields.io endpoint badge.

Gate statuses for available/installs/runs come from the CI steps (passed as
flags). The io gate detail is read from io_result.json. Output:
  reports/<tool>.json        - full machine-readable attestation
  reports/<tool>.badge.json  - shields.io endpoint badge

Usage:
  python harness/report.py --manifest tools/strait-razor-PowerSeqv2.31/manifest.yml \
      --available pass --installs pass --runs pass --io io_result.json \
      --ref <sha> --run-url <ci_run_url>
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCOPE = ("Executed end-to-end in the stated environment with output in the "
         "expected format. Concerns reproducible execution only; no claim of "
         "accuracy, casework fitness, or regulatory validation.")

# Highest gate cleared, in order. The badge reflects the furthest green gate.
LADDER = ["available", "installs", "runs", "io"]
LABELS = {"available": "Available", "installs": "Installs",
          "runs": "Runs", "io": "Runs + Expected IO"}


def _status(flag: str) -> bool:
    # Accept GitHub Actions step outcomes ("success") alongside our own words.
    return str(flag).lower() in ("pass", "true", "ok", "1", "success")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--available", default="pass")
    ap.add_argument("--installs", default="fail")
    ap.add_argument("--runs", default="fail")
    ap.add_argument("--io", default="io_result.json", help="path to io_result.json")
    ap.add_argument("--ref", default="")
    ap.add_argument("--run-url", default="")
    args = ap.parse_args()

    m = _manifest.load(args.manifest)
    io_detail = {}
    io_pass = False
    p = pathlib.Path(args.io)
    if p.exists():
        io_detail = json.loads(p.read_text())
        io_pass = bool(io_detail.get("passed"))

    gates = {
        "available": _status(args.available),
        "installs": _status(args.installs),
        "runs": _status(args.runs),
        "io": io_pass,
    }

    # Highest contiguous green gate from the bottom of the ladder.
    level = "none"
    for g in LADDER:
        if gates[g]:
            level = g
        else:
            break

    report = {
        "schema": "strhub-verified/1",
        "tool": m["tool"],
        "source": {**m["source"], "ref_resolved": args.ref or m["source"]["ref"]},
        "environment": m["environment"],
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ci_run": args.run_url,
        "gates": gates,
        "level": level,
        "io_detail": io_detail,
        "scope": SCOPE,
    }

    # Prefer an explicit per-variant slug from the manifest (e.g. so the PowerSeq
    # and ForenSeq variants of the same tool get distinct badges); otherwise fall
    # back to a slug derived from the tool name.
    slug = m.get("report", {}).get("slug")
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", m["tool"]["name"].lower()).strip("-")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{slug}.json").write_text(json.dumps(report, indent=2))

    color = "brightgreen" if level == "io" else "green" if level == "runs" \
        else "yellow" if level in ("installs", "available") else "red"
    badge = {"schemaVersion": 1, "label": "STRhub Verified",
             "message": LABELS.get(level, "not run"), "color": color}
    (reports / f"{slug}.badge.json").write_text(json.dumps(badge, indent=2))

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
