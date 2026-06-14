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
LADDER = ["available", "installs", "runs", "io", "content"]
LABELS = {"available": "Available", "installs": "Installs",
          "runs": "Runs", "io": "Runs + Expected IO",
          "content": "Runs + Plausible output"}
# One-line plain-language meaning of each level, for the human summary.
MEANING = {
    "none": "did not clear the first gate",
    "available": "the pinned public source exists",
    "installs": "the environment builds from source",
    "runs": "it executes end-to-end without crashing",
    "io": "it produces a non-empty file in the declared format",
    "content": "its output looks like plausible genotype-bearing data "
               "(declared columns, DNA sequences, integer read counts, and "
               "enough recognisable forensic loci)",
}


def _status(flag: str) -> bool:
    # Accept GitHub Actions step outcomes ("success") alongside our own words.
    return str(flag).lower() in ("pass", "true", "ok", "1", "success")


def _summary_md(report: dict, slug: str) -> str:
    """A human-readable attestation summary: what STRhub shows the user."""
    tool = report["tool"]
    level = report["level"]
    gates = report["gates"]
    mark = {True: "PASS", False: "—"}
    lines = [
        f"# STRhub Verified — {tool['name']} ({slug})",
        "",
        f"**Result: {LABELS.get(level, 'not run')}** — {MEANING.get(level, '')}.",
        "",
        f"- Source: `{report['source']['repo']}` @ `{report['source']['ref_resolved']}`",
        f"- Environment: {', '.join(report['environment'].get('os', []))} "
        f"(`{report['environment']['dockerfile']}`)",
        f"- Generated: {report['generated']}",
    ]
    if report.get("ci_run"):
        lines.append(f"- CI run: {report['ci_run']}")
    lines += [
        "",
        "## Gates",
        "",
        "| Gate | Status | Meaning |",
        "|---|---|---|",
    ]
    for g in LADDER:
        lines.append(f"| {LABELS[g]} | {mark[gates.get(g, False)]} | {MEANING.get(g, '')} |")

    # Content highlights (the genotype-plausibility evidence), if available.
    outs = report.get("content_detail", {}).get("outputs", [])
    stats = outs[0].get("stats") if outs and isinstance(outs[0], dict) else None
    if stats:
        loci = stats.get("loci", [])
        sample = ", ".join(loci[:18]) + (" …" if len(loci) > 18 else "")
        top = ", ".join(f"{l} ({d})" for l, d in stats.get("top_loci_by_depth", [])[:6])
        lines += [
            "",
            "## Output content (plausibility evidence)",
            "",
            f"- Sequence records: **{stats.get('rows', 0)}** "
            f"(malformed: {stats.get('malformed_rows', 0)})",
            f"- Distinct forensic loci detected: **{stats.get('distinct_loci', 0)}**",
            f"- Total reads across calls: **{stats.get('total_reads', 0)}** "
            f"(deepest single sequence: {stats.get('max_sequence_depth', 0)})",
            f"- Loci: {sample}" if loci else "",
            f"- Top loci by read depth: {top}" if top else "",
        ]

    lines += [
        "",
        "## Scope (read this)",
        "",
        report["scope"],
        "",
        "This is **not** a claim that the genotypes are correct, nor that the tool "
        "is fit for casework or meets any regulatory standard. Concordance against "
        "known truth is out of scope.",
        "",
    ]
    return "\n".join(l for l in lines if l is not None) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--available", default="pass")
    ap.add_argument("--installs", default="fail")
    ap.add_argument("--runs", default="fail")
    ap.add_argument("--io", default="io_result.json", help="path to io_result.json")
    ap.add_argument("--content", default="content_result.json",
                    help="path to content_result.json")
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

    content_detail = {}
    content_pass = False
    cp = pathlib.Path(args.content)
    if cp.exists():
        content_detail = json.loads(cp.read_text())
        content_pass = bool(content_detail.get("passed"))

    gates = {
        "available": _status(args.available),
        "installs": _status(args.installs),
        "runs": _status(args.runs),
        "io": io_pass,
        "content": content_pass,
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
        "content_detail": content_detail,
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

    color = "brightgreen" if level == "content" \
        else "green" if level in ("io", "runs") \
        else "yellow" if level in ("installs", "available") else "red"
    badge = {"schemaVersion": 1, "label": "STRhub Verified",
             "message": LABELS.get(level, "not run"), "color": color}
    (reports / f"{slug}.badge.json").write_text(json.dumps(badge, indent=2))

    (reports / f"{slug}.summary.md").write_text(_summary_md(report, slug))

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
