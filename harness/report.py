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
import diagnose_log  # noqa: E402

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
        str_loci = stats.get("str_loci", stats.get("loci", []))
        n_str = stats.get("distinct_str_loci", len(str_loci))
        n_snp = stats.get("distinct_snp_markers", 0)
        sample = ", ".join(str_loci[:18]) + (" …" if len(str_loci) > 18 else "")
        top = ", ".join(f"{l} ({d})" for l, d in stats.get("top_loci_by_depth", [])[:6])
        markers_line = f"- STR loci detected: **{n_str}**"
        if n_snp:
            markers_line += (f"  ·  identity SNPs (rsNNNN): **{n_snp}**  "
                             f"(total panel markers: {stats.get('distinct_loci', 0)})")
        lines += [
            "",
            "## Output content (plausibility evidence)",
            "",
            f"- Sequence records: **{stats.get('rows', 0)}** "
            f"(malformed: {stats.get('malformed_rows', 0)})",
            markers_line,
            f"- Total reads across calls: **{stats.get('total_reads', 0)}** "
            f"(deepest single sequence: {stats.get('max_sequence_depth', 0)})",
            f"- STR loci: {sample}" if str_loci else "",
            f"- Top markers by read depth: {top}" if top else "",
        ]

    # Verification matrix (own / external legs), if present.
    datasets = report.get("datasets") or []
    if datasets:
        lines += ["", "## Verification matrix", "",
                  "| Leg | Available | Result | Dataset |", "|---|---|---|---|"]
        for leg in datasets:
            avail = leg.get("available", True)
            status = "N/A" if not avail else ("PASS" if leg.get("passed") else "—")
            lines.append(
                f"| {leg.get('label', leg.get('leg', '?'))} | "
                f"{'yes' if avail else 'N/A'} | {status} | "
                f"{leg.get('dataset', leg.get('type', '—'))} |"
            )
        if any(leg.get("fixture_source") == "strhub" for leg in datasets):
            lines += ["",
                "> **Note:** this tool's manifest does not point to a test file in its "
                "own public repository, so the *STRhub fixture* leg also ran on a "
                "STRhub-provided reference dataset — the same data provenance as the "
                "*External data* leg. Neither leg uses test data from the tool's own "
                "repository; both verify reproducible execution on open-access STRhub data."]

    # README minimum-to-run checklist (advisory).
    rc = report.get("readme_check")
    if rc:
        lines += ["", "## README check (advisory)", "",
                  f"Score: **{rc.get('score', 0)}/{rc.get('max', 5)}** — advisory only, "
                  "does not affect the execution badge.", ""]
        for name, c in (rc.get("checks") or {}).items():
            lines.append(f"- {'PASS' if c.get('present') else '—'} {name}")

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


def _summary_html(report: dict, slug: str) -> str:
    """A standalone, styled HTML page for one tool — navigable as a web page."""
    import html as _html

    tool = report["tool"]
    level = report["level"]
    gates = report["gates"]
    badge = {"content": "#16a34a", "io": "#22a722", "runs": "#22a722",
             "installs": "#d4a017", "available": "#d4a017"}.get(level, "#c33")

    def esc(s):
        return _html.escape(str(s))

    rows = []
    for g in LADDER:
        ok = gates.get(g, False)
        chip = ('<span class="ok">PASS</span>' if ok
                else '<span class="no">—</span>')
        rows.append(f"<tr><td>{esc(LABELS[g])}</td><td>{chip}</td>"
                    f"<td>{esc(MEANING.get(g, ''))}</td></tr>")

    content_block = ""
    outs = report.get("content_detail", {}).get("outputs", [])
    stats = outs[0].get("stats") if outs and isinstance(outs[0], dict) else None
    if stats:
        str_loci = stats.get("str_loci", stats.get("loci", []))
        n_str = stats.get("distinct_str_loci", len(str_loci))
        n_snp = stats.get("distinct_snp_markers", 0)
        sample = ", ".join(str_loci[:18]) + (" …" if len(str_loci) > 18 else "")
        top = ", ".join(f"{l} ({d})" for l, d in stats.get("top_loci_by_depth", [])[:6])
        markers_li = f"<li>STR loci detected: <b>{esc(n_str)}</b>"
        if n_snp:
            markers_li += (f" &middot; identity SNPs (rsNNNN): <b>{esc(n_snp)}</b> "
                           f"(total panel markers: {esc(stats.get('distinct_loci', 0))})")
        markers_li += "</li>"
        content_block = f"""
    <h2>Output content (plausibility evidence)</h2>
    <ul class="stats">
      <li>Sequence records: <b>{esc(stats.get('rows', 0))}</b> (malformed: {esc(stats.get('malformed_rows', 0))})</li>
      {markers_li}
      <li>Total reads across calls: <b>{esc(stats.get('total_reads', 0))}</b> (deepest single sequence: {esc(stats.get('max_sequence_depth', 0))})</li>
      {'<li>STR loci: ' + esc(sample) + '</li>' if str_loci else ''}
      {'<li>Top markers by read depth: ' + esc(top) + '</li>' if top else ''}
    </ul>"""

    # Verification matrix (own / external legs).
    matrix_block = ""
    datasets = report.get("datasets") or []
    if datasets:
        mrows = []
        for leg in datasets:
            avail = leg.get("available", True)
            if not avail:
                chip = '<span class="no">N/A</span>'
            elif leg.get("passed"):
                chip = '<span class="ok">PASS</span>'
            else:
                chip = '<span class="no">—</span>'
            mrows.append(
                f"<tr><td>{esc(leg.get('label', leg.get('leg', '?')))}</td>"
                f"<td>{chip}</td>"
                f"<td>{esc(leg.get('dataset', leg.get('type', '—')))}</td></tr>"
            )
        note = ""
        if any(leg.get("fixture_source") == "strhub" for leg in datasets):
            note = (
                '<p style="font-size:.85rem;color:#555"><b>Note:</b> this tool\'s '
                "manifest does not point to a test file in its own public repository, "
                "so the <i>STRhub fixture</i> leg also ran on a STRhub-provided "
                "reference dataset — the same data provenance as the <i>External data</i> "
                "leg. Neither leg uses test data from the tool's own repository; both "
                "verify reproducible execution on open-access STRhub data.</p>"
            )
        matrix_block = (
            "<h2>Verification matrix</h2>"
            "<table><thead><tr><th>Leg</th><th>Result</th><th>Dataset</th></tr></thead>"
            f"<tbody>{''.join(mrows)}</tbody></table>{note}"
        )

    # README minimum-to-run checklist (advisory).
    readme_block = ""
    rc = report.get("readme_check")
    if rc:
        items = "".join(
            f"<li>{'<b>PASS</b>' if c.get('present') else '—'} {esc(name)}</li>"
            for name, c in (rc.get("checks") or {}).items()
        )
        readme_block = (
            "<h2>README check <span style='font-weight:400;color:#888'>(advisory)</span></h2>"
            f"<p>Score: <b>{esc(rc.get('score', 0))}/{esc(rc.get('max', 5))}</b> — "
            "advisory only; does not affect the execution badge.</p>"
            f"<ul class='stats'>{items}</ul>"
        )

    ci = (f'<a href="{esc(report["ci_run"])}">CI run</a>'
          if report.get("ci_run") else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STRhub Verified — {esc(tool['name'])} ({esc(slug)})</title>
<style>
  body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 820px; margin: 2rem auto;
          padding: 0 1rem; background:#ffffff; color:#1a1a1a; }}
  a {{ color: #2563eb; }}
  .badge {{ display:inline-block; padding:.25rem .7rem; border-radius:999px; color:#fff; font-weight:600; background:{badge}; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #ddd; }}
  .ok {{ color:#16a34a; font-weight:700; }}
  .no {{ color:#999; }}
  .meta li, .stats li {{ margin:.15rem 0; }}
  .scope {{ background:#f3f4f6; border-left:4px solid {badge}; padding:.8rem 1rem; border-radius:6px; }}
  code {{ background:#eef0f2; padding:.1rem .3rem; border-radius:4px; }}
  nav {{ margin-bottom:1rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background:#0d1117; color:#e6edf3; }}
    a {{ color:#58a6ff; }}
    th, td {{ border-bottom:1px solid #30363d; }}
    .scope {{ background:#161b22; }}
    code {{ background:#21262d; }}
  }}
</style></head><body>
<nav><a href="index.html">← All tools</a></nav>
<h1>STRhub Verified — {esc(tool['name'])}</h1>
<p><span class="badge">{esc(LABELS.get(level, 'not run'))}</span></p>
<p>{esc(MEANING.get(level, ''))}.</p>
<ul class="meta">
  <li>Variant: <code>{esc(slug)}</code></li>
  <li>Source: <code>{esc(report['source']['repo'])}</code> @ <code>{esc(report['source']['ref_resolved'])}</code></li>
  <li>Environment: {esc(', '.join(report['environment'].get('os', [])))} (<code>{esc(report['environment']['dockerfile'])}</code>)</li>
  <li>Generated: {esc(report['generated'])}</li>
  {f'<li>{ci}</li>' if ci else ''}
</ul>
<h2>Gates</h2>
<table><thead><tr><th>Gate</th><th>Status</th><th>Meaning</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{content_block}
{matrix_block}
{readme_block}
<h2>Scope</h2>
<p class="scope">{esc(report['scope'])}<br><br>
This is <b>not</b> a claim that the genotypes are correct, nor that the tool is
fit for casework or meets any regulatory standard. Concordance against known
truth is out of scope.</p>
<p style="color:#888;font-size:.85rem">Machine-readable:
<a href="{esc(slug)}.json">{esc(slug)}.json</a> ·
<a href="{esc(slug)}.badge.json">badge</a> ·
<a href="{esc(slug)}.summary.md">summary.md</a></p>
{''.join(f'<p style="font-size:.85rem">Log ({esc(leg)}): <a href="{esc(fname)}">{esc(fname)}</a></p>' for leg, fname in (report.get("logs") or {}).items())}
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--available", default="pass")
    ap.add_argument("--installs", default="fail")
    ap.add_argument("--runs", default="fail")
    ap.add_argument("--io", default="io_result.json", help="path to io_result.json")
    ap.add_argument("--content", default="content_result.json",
                    help="path to content_result.json")
    ap.add_argument("--matrix", default="matrix.json",
                    help="path to matrix.json (own/external legs, Fase 3)")
    ap.add_argument("--readme", default="readme_result.json",
                    help="path to readme_result.json (advisory, Fase 3)")
    ap.add_argument("--log-own", default="",
                    help="path to captured stdout+stderr from own-data run")
    ap.add_argument("--log-external", default="",
                    help="path to captured stdout+stderr from external-data run")
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

    # Fase 3: matrix of verification legs (own + external) and the advisory
    # README check. Both are optional; absence keeps the legacy single-leg shape.
    datasets = []
    mp = pathlib.Path(args.matrix)
    if mp.exists():
        try:
            loaded = json.loads(mp.read_text())
            datasets = loaded if isinstance(loaded, list) else loaded.get("legs", [])
        except Exception:  # noqa: BLE001
            datasets = []

    readme_check = None
    rp = pathlib.Path(args.readme)
    if rp.exists():
        try:
            readme_check = json.loads(rp.read_text())
        except Exception:  # noqa: BLE001
            readme_check = None

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
        "datasets": datasets,
        "readme_check": readme_check,
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

    import shutil
    logs = {}
    for leg, flag in [("own", args.log_own), ("external", args.log_external)]:
        if not flag:
            continue
        lp = pathlib.Path(flag)
        if lp.exists() and lp.stat().st_size > 0:
            dest = f"{slug}.log-{leg}.txt"
            shutil.copy2(lp, reports / dest)
            logs[leg] = dest
    if logs:
        report["logs"] = logs

    diagnostics = {}
    for leg, flag in [("own", args.log_own), ("external", args.log_external)]:
        if not flag:
            continue
        issues = diagnose_log.diagnose_file(flag)
        if issues:
            diagnostics[leg] = issues
    if diagnostics:
        report["diagnostics"] = diagnostics

    (reports / f"{slug}.json").write_text(json.dumps(report, indent=2))

    color = "brightgreen" if level == "content" \
        else "green" if level in ("io", "runs") \
        else "yellow" if level in ("installs", "available") else "red"
    badge = {"schemaVersion": 1, "label": "STRhub Verified",
             "message": LABELS.get(level, "not run"), "color": color}
    (reports / f"{slug}.badge.json").write_text(json.dumps(badge, indent=2))

    (reports / f"{slug}.summary.md").write_text(_summary_md(report, slug))
    (reports / f"{slug}.html").write_text(_summary_html(report, slug))

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
