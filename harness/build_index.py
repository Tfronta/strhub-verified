"""Build a navigable index.html from every <slug>.json in a reports directory.

Scans the directory for attestation JSONs (skipping *.badge.json) and renders a
landing page that lists each verified tool with its result badge and a link to
its per-tool page (<slug>.html).

Usage:
  python harness/build_index.py reports --out reports/index.html
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import pathlib

LABELS = {"none": "not run", "available": "Available", "installs": "Installs",
          "runs": "Runs", "io": "Runs + Expected IO",
          "content": "Runs + Plausible output"}
COLOR = {"content": "#16a34a", "io": "#22a722", "runs": "#22a722",
         "installs": "#d4a017", "available": "#d4a017", "none": "#c33"}


def _load(reports: pathlib.Path) -> list[dict]:
    items = []
    for p in sorted(reports.glob("*.json")):
        if p.name.endswith(".badge.json"):
            continue
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        if r.get("schema", "").startswith("strhub-verified"):
            items.append((p.stem, r))
    return items


def _card(slug: str, r: dict) -> str:
    level = r.get("level", "none")
    tool = r.get("tool", {})
    color = COLOR.get(level, "#c33")
    stats = None
    outs = r.get("content_detail", {}).get("outputs", [])
    if outs and isinstance(outs[0], dict):
        stats = outs[0].get("stats")
    extra = ""
    if stats:
        n_str = stats.get("distinct_str_loci", stats.get("distinct_loci", 0))
        n_snp = stats.get("distinct_snp_markers", 0)
        markers = f"{n_str} STR loci"
        if n_snp:
            markers += f" + {n_snp} SNPs"
        extra = (f'<p class="stat">{markers} · '
                 f'{stats.get("total_reads", 0)} reads</p>')
    return f"""
  <a class="card" href="{html.escape(slug)}.html">
    <span class="badge" style="background:{color}">{html.escape(LABELS.get(level, 'not run'))}</span>
    <h2>{html.escape(tool.get('name', slug))}</h2>
    <p class="slug">{html.escape(slug)}</p>
    {extra}
    <p class="src">{html.escape(r.get('source', {}).get('repo', ''))}</p>
  </a>"""


def render(reports: pathlib.Path) -> str:
    items = _load(reports)
    cards = "".join(_card(slug, r) for slug, r in items) or \
        "<p>No attestations yet.</p>"
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STRhub Verified</title>
<style>
  body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 960px; margin: 2rem auto;
          padding: 0 1rem; background:#ffffff; color:#1a1a1a; }}
  header p {{ color:#666; }}
  .grid {{ display:grid; gap:1rem; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); }}
  .card {{ display:block; text-decoration:none; color:inherit; border:1px solid #ddd;
           border-radius:12px; padding:1rem 1.1rem; transition:.15s; }}
  .card:hover {{ border-color:#2563eb; transform:translateY(-2px); }}
  .card h2 {{ margin:.4rem 0 .1rem; font-size:1.15rem; }}
  .badge {{ display:inline-block; padding:.2rem .6rem; border-radius:999px; color:#fff; font-size:.8rem; font-weight:600; }}
  .slug {{ color:#666; font-family:ui-monospace,monospace; font-size:.85rem; margin:.1rem 0; }}
  .stat {{ font-size:.9rem; margin:.3rem 0 0; }}
  .src {{ color:#999; font-size:.78rem; margin:.4rem 0 0; word-break:break-all; }}
  footer {{ color:#999; font-size:.82rem; margin-top:2rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background:#0d1117; color:#e6edf3; }}
    header p {{ color:#9da7b3; }}
    .card {{ border-color:#30363d; }}
    .slug {{ color:#9da7b3; }}
  }}
</style></head><body>
<header>
  <h1>STRhub Verified</h1>
  <p>Reproducible-execution attestations for forensic STR genotyping tools.
     Each card reports the highest verification gate cleared — not a claim of
     genotype accuracy or casework fitness.</p>
</header>
<main class="grid">{cards}</main>
<footer>Generated {html.escape(now)} · {len(items)} tool(s)</footer>
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", help="directory containing <slug>.json reports")
    ap.add_argument("--out", default=None, help="output html path (default: <reports>/index.html)")
    args = ap.parse_args()
    reports = pathlib.Path(args.reports)
    out = pathlib.Path(args.out) if args.out else reports / "index.html"
    out.write_text(render(reports))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
