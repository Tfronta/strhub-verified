"""    python -m harness.engine run --plan work/plan.json --work work --record run_record.json

Runs the gates the plan describes and writes the RunRecord. Exits 0 whatever
the gates found: a failed gate is a result, written down. A non-zero exit is
the engine itself crashing, which the workflow reports as a fault of STRhub's.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import record, runner


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.engine")
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the gates of one plan")
    r.add_argument("--plan", required=True, help="plan.json written by harness/prepare.py --plan-out")
    r.add_argument("--work", default="work")
    r.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[2]))
    r.add_argument("--record", default="run_record.json")
    args = ap.parse_args(argv)

    plan = json.loads(pathlib.Path(args.plan).read_text())
    rec = runner.run(plan, pathlib.Path(args.work), pathlib.Path(args.root))
    record.write(rec, args.record)
    print(f"[engine] record written to {args.record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
