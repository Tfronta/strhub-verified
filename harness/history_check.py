"""Hold a tool's history to what its issues say.

A history check is a list of commits of one tool with what each should do,
taken from the issues its users opened: the commit before a fix should stop
where the user said, with the error the user saw; the commit after should
not. Each commit is run through the engine as a trial and the result is held
to the expectation. Where they disagree, either the expectation was wrong or
the engine misses what a person found — and both are the thing worth knowing,
which is why this exists: test_truth.py holds the engine to snapshots, this
holds it to history. Tanda 4 of docs/PLAN-Version-History.md.

Cases live in history/<slug>.yml (see history/strspy-ont.yml). Two instruments:
`committed` re-points the recipe under tools/<slug>/ at the commit (a curated
environment; the run never publishes), `proposed` runs what a new user would
get, the recipe the engine reads off the repository at that commit (publishes
on the usual terms, and lands in the tool's history as the commit it is —
unless the case says `publish: false`, for a commit whose curated result the
catalogue should keep).

Three steps, so the workflow can wait between them:

    python harness/history_check.py dispatch history/strspy-ont.yml --out dispatched.json
    python harness/history_check.py wait dispatched.json --results results
    python harness/history_check.py evaluate history/strspy-ont.yml --results results --summary summary.md

`evaluate` exits 1 when any case misses its expectation.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import retarget_recipe  # noqa: E402

WORKFLOW = "verify.yml"


# ── Cases ─────────────────────────────────────────────────────────────────────

def load_cases(path: pathlib.Path) -> dict:
    doc = yaml.safe_load(path.read_text())
    for key in ("tool", "repo", "cases"):
        if key not in doc:
            raise SystemExit(f"{path}: missing '{key}'")
    for c in doc["cases"]:
        c.setdefault("run", "committed")
        if c["run"] not in ("committed", "proposed"):
            raise SystemExit(f"{path}: run must be committed or proposed, not {c['run']!r}")
        if not re.match(r"^[0-9a-f]{40}$", str(c.get("ref", ""))):
            raise SystemExit(f"{path}: every case needs a full commit sha (ref), got {c.get('ref')!r}")
        c.setdefault("expect", {})
    return doc


def case_id(doc: dict, case: dict) -> str:
    """One commit can be run with both instruments; the id says which."""
    return f"{doc['tool']}@{case['ref'][:7]}-{case['run'][0]}"


def dispatch_id(doc: dict, case: dict) -> str:
    return f"hc_{case['ref'][:7]}_{case['run'][0]}_{doc['tool']}"[:60]


def run_tool_input(doc: dict, case: dict) -> str:
    """The `tool` input of the trial: the committed slug, or a trial name the
    way the web names one (trial-<repo name>-<sha7>)."""
    if case["run"] == "committed":
        return doc["tool"]
    name = doc["repo"].rstrip("/").split("/")[-1].lower()
    name = re.sub(r"[^a-z0-9.-]+", "-", name)
    return f"trial-{name}-{case['ref'][:7]}"


# ── Dispatch and wait ─────────────────────────────────────────────────────────

def dispatch(doc: dict, run=subprocess.run) -> list[dict]:
    """One trial per case. Returns what was dispatched, with the id the run
    name carries and the artifact it will leave."""
    out = []
    for case in doc["cases"]:
        did = dispatch_id(doc, case)
        tool = run_tool_input(doc, case)
        cmd = ["gh", "workflow", "run", WORKFLOW, "-f", f"tool={tool}", "-f", "mode=trial",
               "-f", f"dispatch_id={did}"]
        if case["run"] == "committed":
            r = retarget_recipe.retarget(doc["tool"], case["ref"])
            cmd += ["-f", f"recipe={r['recipe_b64']}"]
        else:
            cmd += ["-f", f"repo={doc['repo']}", "-f", f"ref={case['ref']}"]
            # A proposed case at a commit the catalogue holds a curated result
            # for must not replace it: both runs are true, one is the card's.
            if case.get("publish") is False:
                cmd += ["-f", "publish=false"]
        res = run(cmd, capture_output=True, text=True)
        out.append({
            "id": case_id(doc, case), "dispatch_id": did, "tool": tool,
            "artifact": f"trial-{tool}", "ref": case["ref"], "run": case["run"],
            "dispatched": res.returncode == 0,
            "error": (res.stderr or "").strip() if res.returncode else "",
        })
    return out


def find_runs(dispatched: list[dict], run=subprocess.run) -> dict[str, dict]:
    """The workflow run of each dispatch, by the id in its name, as `gh run
    list` reports it: {dispatch_id: {databaseId, status, conclusion}}."""
    res = run(["gh", "run", "list", "--workflow", WORKFLOW, "--event", "workflow_dispatch",
               "--limit", "80", "--json", "databaseId,displayTitle,status,conclusion"],
              capture_output=True, text=True)
    runs = json.loads(res.stdout or "[]") if res.returncode == 0 else []
    found = {}
    for d in dispatched:
        tag = f"[{d['dispatch_id']}]"
        for r in runs:
            if tag in (r.get("displayTitle") or ""):
                found[d["dispatch_id"]] = r
                break
    return found


def wait(dispatched: list[dict], results: pathlib.Path, run=subprocess.run,
         timeout_s: float = 90 * 60, poll_s: float = 60, sleep=time.sleep) -> list[dict]:
    """Poll until every dispatched run has completed (or the clock runs out),
    then download each run's artifact into results/<case id>/."""
    pending = [d for d in dispatched if d["dispatched"]]
    deadline = time.monotonic() + timeout_s
    done: dict[str, dict] = {}
    while pending and time.monotonic() < deadline:
        found = find_runs(pending, run)
        still = []
        for d in pending:
            r = found.get(d["dispatch_id"])
            if r and r.get("status") == "completed":
                done[d["dispatch_id"]] = r
            else:
                still.append(d)
        pending = still
        if pending:
            sleep(poll_s)
    out = []
    for d in dispatched:
        r = done.get(d["dispatch_id"])
        entry = {**d, "run_id": (r or {}).get("databaseId"), "conclusion": (r or {}).get("conclusion"),
                 "completed": r is not None, "downloaded": False}
        if r:
            dest = results / d["id"]
            dest.mkdir(parents=True, exist_ok=True)
            res = run(["gh", "run", "download", str(r["databaseId"]), "-n", d["artifact"], "-D", str(dest)],
                      capture_output=True, text=True)
            entry["downloaded"] = res.returncode == 0
            if res.returncode:
                entry["error"] = (res.stderr or "").strip()
        out.append(entry)
    return out


# ── Evaluate ──────────────────────────────────────────────────────────────────

def read_result(folder: pathlib.Path) -> tuple[dict | None, dict[str, str]]:
    """The report and the logs a trial's artifact holds, wherever gh put them."""
    report = None
    logs: dict[str, str] = {}
    if not folder.is_dir():
        return None, logs
    for p in sorted(folder.rglob("*.json")):
        if p.name.endswith((".badge.json", ".recipe.json")):
            continue
        try:
            r = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(r, dict) and r.get("schema") == "strhub-verified/1":
            report = r
            break
    for p in sorted(folder.rglob("*.log-*.txt")):
        logs[p.name.rsplit(".log-", 1)[1][:-4]] = p.read_text(errors="replace")
    return report, logs


def observed_of(report: dict | None) -> dict:
    if not report:
        return {"verdict": None, "level": None, "diagnostics": [], "gates": {}}
    ids = set()
    for issues in (report.get("diagnostics") or {}).values():
        ids.update(i.get("id") for i in issues if i.get("id"))
    for i in ((report.get("install_detail") or {}).get("diagnostics") or []):
        if i.get("id"):
            ids.add(i["id"])
    return {
        "verdict": (report.get("verdict") or {}).get("code"),
        "level": report.get("level"),
        "diagnostics": sorted(ids),
        "gates": report.get("gates") or {},
    }


def evaluate(case: dict, report: dict | None, logs: dict[str, str]) -> dict:
    """Hold one result to its expectation. Every key of `expect` is a
    separate claim, and every one that misses is named."""
    exp = case.get("expect") or {}
    obs = observed_of(report)
    misses = []
    if report is None:
        misses.append("no report: the run left no attestation")
    if "verdict" in exp and obs["verdict"] != exp["verdict"]:
        misses.append(f"verdict {obs['verdict']!r}, expected {exp['verdict']!r}")
    if "level" in exp and obs["level"] != exp["level"]:
        misses.append(f"level {obs['level']!r}, expected {exp['level']!r}")
    for want in exp.get("diagnostics") or []:
        if want not in obs["diagnostics"]:
            misses.append(f"diagnostic {want!r} not reported (got {obs['diagnostics'] or 'none'})")
    for unwanted in exp.get("no_diagnostics") or []:
        if unwanted in obs["diagnostics"]:
            misses.append(f"diagnostic {unwanted!r} reported, expected gone")
    text = "\n".join(logs.values())
    if "log_contains" in exp and exp["log_contains"] not in text:
        misses.append(f"log does not contain {exp['log_contains']!r}")
    if "log_not_contains" in exp and exp["log_not_contains"] in text:
        misses.append(f"log still contains {exp['log_not_contains']!r}")
    return {"ref": case["ref"], "label": case.get("label", ""), "run": case["run"],
            "expected": exp, "observed": obs, "ok": not misses, "misses": misses}


def evaluate_all(doc: dict, results: pathlib.Path) -> list[dict]:
    out = []
    for case in doc["cases"]:
        report, logs = read_result(results / case_id(doc, case))
        out.append({"id": case_id(doc, case), **evaluate(case, report, logs)})
    return out


def summary(doc: dict, results: list[dict]) -> str:
    """The table the technical note is written from: commit, what the issues
    say, what the engine found, and whether they agree."""
    lines = [f"## History check · {doc['tool']}", "",
             f"{doc['repo']} — {sum(r['ok'] for r in results)}/{len(results)} as the issues say.", "",
             "| Commit | What | Instrument | Expected | Observed | Agree |", "|---|---|---|---|---|---|"]
    for r in results:
        exp = ", ".join(f"{k}={v}" for k, v in r["expected"].items()) or "—"
        o = r["observed"]
        obs = f"{o['verdict'] or '—'} · {o['level'] or '—'}"
        if o["diagnostics"]:
            obs += " · " + ", ".join(o["diagnostics"])
        agree = "yes" if r["ok"] else "**no**: " + "; ".join(r["misses"])
        lines.append(f"| `{r['ref'][:7]}` | {r['label']} | {r['run']} | {exp} | {obs} | {agree} |")
    return "\n".join(lines) + "\n"


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispatch", help="start one trial per case")
    d.add_argument("cases")
    d.add_argument("--out", default="dispatched.json")
    w = sub.add_parser("wait", help="wait for the trials and download their artifacts")
    w.add_argument("dispatched")
    w.add_argument("--results", default="results")
    w.add_argument("--timeout-minutes", type=float, default=90)
    e = sub.add_parser("evaluate", help="hold the results to the cases")
    e.add_argument("cases")
    e.add_argument("--results", default="results")
    e.add_argument("--summary", default="", help="write the markdown table here too")
    args = ap.parse_args()

    if args.cmd == "dispatch":
        doc = load_cases(pathlib.Path(args.cases))
        done = dispatch(doc)
        pathlib.Path(args.out).write_text(json.dumps(done, indent=2))
        for x in done:
            print(("started " if x["dispatched"] else "FAILED  ") + x["id"] + (f": {x['error']}" if x["error"] else ""))
        return 0 if all(x["dispatched"] for x in done) else 1
    if args.cmd == "wait":
        dispatched = json.loads(pathlib.Path(args.dispatched).read_text())
        done = wait(dispatched, pathlib.Path(args.results), timeout_s=args.timeout_minutes * 60)
        pathlib.Path(args.dispatched).write_text(json.dumps(done, indent=2))
        for x in done:
            print(f"{x['id']}: {'completed' if x['completed'] else 'NOT finished'}"
                  f"{', artifact downloaded' if x['downloaded'] else ''}{': ' + x['error'] if x.get('error') else ''}")
        return 0 if all(x["completed"] for x in done) else 1
    doc = load_cases(pathlib.Path(args.cases))
    results = evaluate_all(doc, pathlib.Path(args.results))
    text = summary(doc, results)
    print(text)
    if args.summary:
        pathlib.Path(args.summary).write_text(text)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
