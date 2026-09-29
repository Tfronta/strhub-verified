"""Run the recipe benchmark on real runners: unpublished trials, then a table.

    python harness/benchmark_trials.py dispatch [--ref BRANCH] [--only a,b] [--tag round1]
    python harness/benchmark_trials.py collect --tag round1 [--json out.json]

benchmark_recipes.py scores what a proposal SAYS, offline. Whether the
Dockerfile builds and the command runs is only known by running it, so this
dispatches one trial per benchmark tool (mode=trial, publish=false: nothing
reaches the catalogue, and a run from a branch never deploys), each named
`bench_<tag>_<name>`, and then reads their reports back into one table:
installs, runs (STRhub's data), the tool's own example, level and verdict.

Needs the GitHub CLI, authenticated. Not part of the test suite.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmark_recipes as br  # noqa: E402

WORKFLOW = "verify.yml"


def dispatch(ref: str, tag: str, only: set[str]) -> int:
    failed = 0
    for r in br.rows():
        if only and r["name"] not in only:
            continue
        label = r["tag"] or r["sha"][:7]
        cmd = ["gh", "workflow", "run", WORKFLOW, "--ref", ref,
               "-f", f"tool=trial-{r['name']}-{label}", "-f", "mode=trial",
               "-f", f"repo=https://github.com/{r['repo']}", "-f", f"ref={r['sha']}",
               "-f", f"ref_label={r['tag']}", "-f", "publish=false",
               "-f", f"dispatch_id=bench_{tag}_{r['name']}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"{r['name']}: {'dispatched' if res.returncode == 0 else 'FAILED ' + res.stderr.strip()}")
        failed += res.returncode != 0
    return 1 if failed else 0


def _runs(tag: str) -> dict[str, dict]:
    out = subprocess.run(["gh", "run", "list", "--workflow", WORKFLOW, "-L", "200", "--json",
                          "databaseId,displayTitle,status,conclusion"], capture_output=True, text=True, check=True)
    found = {}
    for run in json.loads(out.stdout):
        title = run["displayTitle"]
        marker = f"[bench_{tag}_"
        if marker in title:
            name = title.split(marker, 1)[1].rstrip("]")
            found.setdefault(name, run)  # newest first
    return found


def collect(tag: str) -> list[dict]:
    rows = []
    runs = _runs(tag)
    for name, run in sorted(runs.items()):
        row = {"name": name, "run": run["databaseId"], "status": run["status"], "job": run["conclusion"]}
        if run["status"] == "completed":
            with tempfile.TemporaryDirectory() as d:
                reports = []
                for _ in range(2):  # a download can fail transiently
                    subprocess.run(["gh", "run", "download", str(run["databaseId"]), "-D", d],
                                   capture_output=True, text=True)
                    reports = [p for p in pathlib.Path(d).rglob("*.json")
                               if not p.name.endswith((".badge.json", ".recipe.json"))]
                    if reports:
                        break
                if reports:
                    rep = json.loads(reports[0].read_text())
                    g = rep.get("gates") or {}
                    v = rep.get("verdict") or {}
                    row.update({"installs": g.get("installs"), "runs": g.get("runs"), "io": g.get("io"),
                                "example": g.get("example"), "level": rep.get("level"),
                                "verdict": v.get("code"), "basis": v.get("basis"),
                                "fallback_used": (rep.get("environment") or {}).get("fallback_used", False),
                                "reason": (v.get("reason") or "")[:200]})
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["dispatch", "collect"])
    ap.add_argument("--ref", default="main")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    if args.action == "dispatch":
        return dispatch(args.ref, args.tag, {n for n in args.only.split(",") if n})
    rows = collect(args.tag)
    mark = {True: "Y", False: "-", None: "·"}
    print(f"{'tool':22} {'installs':8} {'runs':5} {'example':7} {'level':9} verdict")
    for r in rows:
        print(f"{r['name']:22} {mark[r.get('installs')]:8} {mark[r.get('runs')]:5} {mark[r.get('example')]:7} "
              f"{str(r.get('level')):9} {r.get('verdict')}/{r.get('basis')}"
              + (" (plan B)" if r.get("fallback_used") else ""))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
