"""Read-only rendering of historical reports from the retired recipe agent.

    python harness/assist_report.py work/assist/result.json [--pr]
"""
from __future__ import annotations

import argparse
import json
import pathlib

#: Claude Opus 5.5, per million tokens: input, output, cache read, 1-hour cache write.
PRICE = {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 8.0}


def cost(usage: dict) -> float:
    return sum(usage.get(k, 0) / 1e6 * p for k, p in PRICE.items())


def render(r: dict, pr: bool = False) -> str:
    sha7 = (r.get("ref") or "")[:7]
    lines = [f"## Historical recipe agent: {r.get('slug')} at {sha7}", "",
             "The repair agent is retired. This report preserves a past run; "
             "it does not authorize a repair or a new verification.", ""]
    doc = (r.get("documented") or {}).get("result") or {}
    if doc:
        lines.append(f"**The documented instructions, run literally:** {doc.get('verdict')}. "
                     f"{doc.get('reason') or ''} ([run]({doc.get('run')}))")
        lines.append("")
    fin = r.get("finish") or {}
    if r.get("stop") == "documented_runs":
        lines.append("The documented recipe runs; there was nothing for the agent to do.")
        return "\n".join(lines) + "\n"
    lines.append(f"**Outcome:** {'it runs' if r.get('success') else 'it did not run'} "
                 f"(stopped: {r.get('stop')}). {fin.get('summary', '')}")
    lines.append("")
    attempts = r.get("attempts") or []
    if attempts:
        lines += ["| attempt | verdict | reached | trial |", "|---|---|---|---|"]
        for a in attempts:
            res = a.get("result") or {}
            lines.append(f"| {a['n']} | {res.get('verdict')} | {res.get('level')} | [run]({res.get('run')}) |")
        lines.append("")
    if r.get("workarounds"):
        lines += ["### What the recipe that ran does that the documentation does not", "",
                  "| what | instead of | why |", "|---|---|---|"]
        for w in r["workarounds"]:
            cells = [str(w.get(k, "")).replace("|", "\\|") for k in ("what", "instead_of", "why")]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    if fin.get("recommendations"):
        lines += ["### For the tool's author", ""] + [f"- {x}" for x in fin["recommendations"]] + [""]
    u = r.get("usage") or {}
    if u:
        lines.append(f"Model {r.get('model')}: {u.get('requests', 0)} requests; tokens in {u.get('input', 0):,}, "
                     f"out {u.get('output', 0):,}, cache read {u.get('cache_read', 0):,}, "
                     f"cache write {u.get('cache_write', 0):,}; about ${cost(u):.2f}.")
        lines.append("")
    if pr:
        lines += [
            "### Historical curated recipe",
            "",
            "- This **curated** recipe records historical departures from the documented procedure; it cannot support the documented badge.",
            "- Preserve its linked evidence. Do not merge or rerun it to repair a failed verification.",
            "- Any correction must be documented upstream before a separate verification is requested.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--pr", action="store_true")
    args = ap.parse_args()
    p = pathlib.Path(args.result)
    if not p.exists():
        print("The agent produced no result.")
        return 0
    print(render(json.loads(p.read_text()), args.pr), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
