"""Score recipe detection against the pinned benchmark (testdata/benchmark/).

    python harness/benchmark_recipes.py              # table + totals
    python harness/benchmark_recipes.py --json out.json

For every tool with an expected.json, the proposal a trial of that commit would
get (detect_recipe on the snapshot, then propose_manifest) is compared with
what the documentation says a user should do:

  install   the build method is one the docs support (acceptable_methods)
  input     the STRhub dataset chosen is the one a faithful run uses (or none,
            when none fits)
  program   the run command invokes the documented program (and subcommand)
  clean     the rewritten command has no placeholder left in it (`,...`,
            `path/to`, `<...>`, "YOUR PATH")
  honest    a tool STRhub cannot run on its data is not attempted as if it
            could, and one it can is not given up on
  viable    runnable, and install + input + program + clean all hold

Offline and deterministic: no network, no Docker. Whether the Dockerfile
really builds is measured by running trials, not here.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import detect_recipe as dr  # noqa: E402
import propose_manifest as pm  # noqa: E402
from prepare import unwrap_example  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "harness" / "testdata" / "benchmark"
METRICS = ("install", "input", "program", "clean", "honest", "viable")
BLOCKING = {"no_command", "install_method_unknown", "no_reference_dataset", "regions_format_unknown",
            "loci_outside_panel", "documented_file_missing"}
LEFTOVER = re.compile(r",\.\.\.|…|\bpath/to\b|/path/to/|YOUR[ _]PATH|<[^<>\s][^<>]*>|\bFILE\.bam\b", re.I)


def rows() -> list[dict]:
    out = []
    for ln in (BENCH / "repos.tsv").read_text().splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        name, repo, tag, sha, which = ln.split("\t")
        out.append({"name": name, "repo": repo, "tag": tag, "sha": sha, "set": which})
    return out


def _norm_prog(p: str | None) -> str:
    p = (p or "").split("/")[-1].lower()
    return re.sub(r"\.(?:py|sh|pl|r|jl)$", "", p)


def propose(name: str) -> tuple[dict, dict]:
    src = dr.load_snapshot(BENCH / name)
    t = src["tree_resp"]
    slug = dr.repo_slug(t["repo"])
    proposal = dr.detect(slug, t["ref"], t, src["readme"], src["readme_name"], extras=src)
    recipe = pm.build(proposal, f"bench-{name}", ref_label=src.get("tag") or "")
    return proposal, recipe


def score(name: str, expected: dict) -> dict:
    proposal, recipe = propose(name)
    m = recipe["manifest"]
    limits = set(recipe["limitations"])
    method = (proposal.get("build") or {}).get("method")
    top = (proposal.get("commands") or [{}])[0]
    run_cmd, _cwd = unwrap_example(m["run"]["cmd"])
    exp_prog = expected["program"]
    runnable = bool(expected["runnable_on_strhub_data"]["value"])
    got_type = (m.get("inputs") or {}).get("type")
    # A type STRhub holds no data for is no dataset at all.
    if got_type and not pm.datasets_lib.resolve(got_type):
        got_type = None

    install = method in expected["install"]["acceptable_methods"]
    input_ok = got_type == expected["input"]["strhub_type"]
    if exp_prog.get("value"):
        prog_ok = bool(top) and _norm_prog(top.get("invokes")) == _norm_prog(exp_prog["value"])
    else:
        # The documentation names no program to run: the right answer is none.
        prog_ok = not top
    if prog_ok and exp_prog.get("subcommand"):
        after = top["cmd"].split(top["invokes"], 1)[-1].split()
        prog_ok = any(tok == exp_prog["subcommand"] for tok in after[:3])
    clean = (bool(top) and not LEFTOVER.search(run_cmd.replace(" > ", " ").replace(" < ", " "))) \
        if exp_prog.get("value") else not top
    blocked = bool(limits & BLOCKING) or not got_type
    honest = (not blocked) if runnable else blocked
    viable = runnable and install and input_ok and prog_ok and clean and not blocked
    return {
        "name": name, "install": install, "input": input_ok, "program": prog_ok, "clean": clean,
        "honest": honest, "viable": viable,
        "got": {"method": method, "type": got_type, "invokes": top.get("invokes"),
                "cmd": run_cmd[:160], "limitations": sorted(limits)},
        "want": {"methods": expected["install"]["acceptable_methods"],
                 "type": expected["input"]["strhub_type"],
                 "program": (exp_prog["value"] or "(none)") + (f" {exp_prog['subcommand']}" if exp_prog.get("subcommand") else ""),
                 "runnable": runnable},
    }


def run(only: set[str] | None = None) -> dict:
    results = []
    for r in rows():
        exp_path = BENCH / r["name"] / "expected.json"
        if not exp_path.exists() or (only and r["name"] not in only):
            continue
        res = score(r["name"], json.loads(exp_path.read_text()))
        res["set"] = r["set"]
        results.append(res)
    totals = {k: sum(1 for x in results if x[k]) for k in METRICS}
    by_set = {s: {k: sum(1 for x in results if x["set"] == s and x[k]) for k in METRICS}
              for s in ("new", "catalogue")}
    return {"n": len(results), "totals": totals, "by_set": by_set,
            "n_by_set": {s: sum(1 for x in results if x["set"] == s) for s in ("new", "catalogue")},
            "results": results}


def table(report: dict) -> str:
    mark = {True: "✓", False: "·"}
    lines = [f"{'tool':24} " + " ".join(f"{k:7}" for k in METRICS) + "  got → want"]
    for x in report["results"]:
        lines.append(f"{x['name']:24} " + " ".join(f"{mark[x[k]]:7}" for k in METRICS)
                     + f"  {x['got']['method']}/{x['got']['type']}/{x['got']['invokes']}"
                     + f" → {'/'.join(x['want']['methods'])}/{x['want']['type']}/{x['want']['program']}")
    t = report["totals"]
    lines.append(f"{'TOTAL of ' + str(report['n']):24} " + " ".join(f"{t[k]:<7}" for k in METRICS))
    for s in ("new", "catalogue"):
        bs = report["by_set"][s]
        lines.append(f"{'  ' + s + ' (' + str(report['n_by_set'][s]) + ')':24} " + " ".join(f"{bs[k]:<7}" for k in METRICS))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    report = run({n for n in args.only.split(",") if n} or None)
    print(table(report))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
