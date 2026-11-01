"""Starts: does the installed program answer `--help` in the built image?

    python harness/check_starts.py --rc 0 --log work/log_starts.txt --json starts.json

A check outside the ladder, like the tool's own example. It says one thing a
reviewer can use when nothing else could be run: the program is there and it
starts. Many tools print their usage and exit 1 or 2 when asked for help, so a
usage text counts as starting too; "command not found", a missing library or a
Python traceback does not.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

USAGE = re.compile(r"\busage\b|^\s*options?:|^\s*arguments:|--help\b|\bsubcommands?\b|\bcommands?:", re.I | re.M)
BROKEN = re.compile(r"command not found|No such file or directory|cannot open shared object|"
                    r"Traceback \(most recent call last\)|Segmentation fault|exec format error|"
                    r"not found in PATH|Permission denied", re.I)


def judge(rc: int, log: str) -> dict:
    if BROKEN.search(log):
        return {"gate": "starts", "applicable": True, "passed": False, "rc": rc,
                "how": "the program did not start: " + BROKEN.search(log).group(0)}
    if rc == 0:
        return {"gate": "starts", "applicable": True, "passed": True, "rc": rc, "how": "--help exited 0"}
    if rc in (1, 2) and USAGE.search(log):
        return {"gate": "starts", "applicable": True, "passed": True, "rc": rc,
                "how": f"--help printed its usage (exit {rc})"}
    return {"gate": "starts", "applicable": True, "passed": False, "rc": rc,
            "how": f"--help exited {rc} without printing a usage"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rc", type=int, required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()
    p = pathlib.Path(args.log)
    log = p.read_text(errors="replace") if p.exists() else ""
    result = judge(args.rc, log)
    pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
