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


# How the submitter is named in prose, by what the manifest declares. `None` is
# not a third state to describe but an absence: manifests written before the form
# asked carry no answer, and the reports fall back to "the submitter", which is
# true of everyone and claims nothing.
SUBMITTER_SHORT = {
    "maintainer": "the tool's maintainer",
    "third_party": "a third party — not the tool's maintainer",
}


def _submitter_phrase(by: str | None) -> str:
    """Noun phrase for whoever supplied the submission, for use mid-sentence."""
    if by == "maintainer":
        return "The tool's maintainer"
    if by == "third_party":
        return "A third party, not the tool's maintainer,"
    return "The submitter"


def _regions_note(rg: dict, submitted_by: str | None = None) -> str:
    """One sentence on who defined the target regions, and that the data is a slice.

    Shared by the markdown and HTML renders so the two cannot drift. Returns "" for
    tools that take no regions BED (FASTQ-based).
    """
    total = rg.get("panel_size")
    slice_note = (
        f" The reference dataset is a slice around {total} forensic STR loci, not a "
        "whole genome: it carries reads only at those loci."
        if total else ""
    )
    if rg.get("source") == "tool":
        covered = rg.get("covered_loci")
        detail = (f", covering {covered} of {total} supported loci"
                  if covered and total else "")
        # Never "the tool's author" unless the manifest says so. `provided_by`
        # records that the BED came through the form, not who wrote it, and the
        # two are the same person only when a tool's own maintainer submits it.
        # STRhub verifying somebody else's tool is the other case, and there this
        # claimed authorship that the tool's developer never had — over a file
        # that materially changes the result.
        return f"{_submitter_phrase(submitted_by)} supplied the regions BED{detail}.{slice_note}"
    if rg.get("source") == "strhub":
        return f"STRhub supplied the regions BED.{slice_note}"
    return ""


# Said in full only for a third-party submission. A maintainer submitting their
# own tool is what a reader already assumes, so it needs one line and no more;
# the other case contradicts that assumption and has to say so plainly, because
# every configured choice in this report is then somebody else's.
THIRD_PARTY_NOTE = (
    "This tool was submitted for verification by somebody other than its "
    "maintainer. The maintainer took no part in the run and supplied none of "
    "what it used: the command, the environment, and any target regions were "
    "chosen by the submitter. Where a maintainer is named above, that names who "
    "answers for the software — not who asked for this report, and not an "
    "endorsement of it."
)


def _summary_md(report: dict, slug: str) -> str:
    """A human-readable attestation summary: what STRhub shows the user."""
    tool = report["tool"]
    level = report["level"]
    gates = report["gates"]
    mark = {True: "PASS", False: "—"}
    lines = [
        f"# STRhub Verified: {tool['name']} ({slug})",
        "",
        f"**Result: {LABELS.get(level, 'not run')}.** {MEANING.get(level, '')}.",
        "",
        f"- Source: `{report['source']['repo']}` @ `{report['source']['ref_resolved']}`",
        f"- Environment: {', '.join(report['environment'].get('os', []))} "
        f"(`{report['environment']['dockerfile']}`)",
        f"- Generated: {report['generated']}",
    ]
    submitted_by = (report.get("submission") or {}).get("by")
    if submitted_by in SUBMITTER_SHORT:
        lines.append(f"- Submitted by: {SUBMITTER_SHORT[submitted_by]}")
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

    # Why the build failed, immediately after the ladder that says it did.
    # Nothing below this point ran, so the reader needs the reason here rather
    # than at the foot of a report about a run that never happened.
    inst = report.get("install_detail") or {}
    if inst.get("diagnostics"):
        lines += ["", "## Why the environment did not build", "",
                  "The container could not be built from the declared install "
                  "steps, so nothing below the Installs gate ran.",
                  "",
                  diagnose_log.install_fault_sentence(inst.get("faults") or [], submitted_by),
                  "",
                  "| What happened | Times | Suggested fix |",
                  "|---|---|---|"]
        for issue in inst["diagnostics"]:
            fix = issue.get("suggestion", "—").replace("\n", " ")
            lines.append(f"| {issue['title']} | {issue.get('count', 1)} | {fix} |")
        build_log = (report.get("logs") or {}).get("build")
        if build_log:
            lines += ["", f"Full build output: [`{build_log}`]({build_log})"]

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
    # Legs where fixture_source=="strhub" are omitted: both legs run on the same
    # STRhub data, so showing them separately would be misleading.
    # Which legs reported errors — the matrix flags THAT, the section below says what.
    legs_with_errors = {
        leg for leg, issues in (report.get("diagnostics") or {}).items()
        if any(i.get("severity") == "error" for i in issues)
    }

    datasets = report.get("datasets") or []
    visible = [leg for leg in datasets if leg.get("fixture_source") != "strhub"]
    if visible:
        lines += ["", "## Verification matrix", "",
                  "| Leg | Available | Result | Errors reported | Dataset |",
                  "|---|---|---|---|---|"]
        for leg in visible:
            avail = leg.get("available", True)
            status = "N/A" if not avail else ("PASS" if leg.get("passed") else "—")
            err = "yes" if leg.get("leg") in legs_with_errors else "—"
            lines.append(
                f"| {leg.get('label', leg.get('leg', '?'))} | "
                f"{'yes' if avail else 'N/A'} | {status} | {err} | "
                f"{leg.get('dataset', leg.get('type', '—'))} |"
            )

    # Who chose the regions, and the fact that the dataset is a slice. A
    # coordinate-based tool only calls where its BED points, so both are material.
    rg = report.get("regions") or {}
    if rg.get("source") in ("tool", "strhub"):
        note = _regions_note(rg, submitted_by)
        if note:
            lines += ["", "## Regions", "", note]

    # Placed after the evidence and before the caveats: a reader who has just
    # seen a green ladder needs to know whose run produced it before they decide
    # what it says about the tool.
    if submitted_by == "third_party":
        lines += ["", "## Who submitted this", "", THIRD_PARTY_NOTE]

    # Errors the tool itself reported. Its own section: the matrix says whether a
    # leg passed, this says what went wrong, and a reviewer should not have to open
    # a container log to find out.
    errs = diagnose_log.summarize(report.get("diagnostics") or {})
    if errs:
        n_items = sum(len(e["items"]) for e in errs) or sum(1 for _ in errs)
        lines += ["", "## Errors reported during the run", "",
                  f"The tool reported errors on {n_items} item(s) during the run.",
                  "This does not assess whether the results produced are correct.",
                  "", "| What happened | Times | Affected |", "|---|---|---|"]
        for e in errs:
            items = ", ".join(e["items"]) if e["items"] else "—"
            lines.append(f"| {e['title']} | {e['count']} | {items} |")
        for note in diagnose_log.external_leg_notes(report.get("diagnostics") or {}):
            lines += ["", note]

        # A failure the author can fix costs nothing to re-run. Saying so here is
        # what keeps the paid tier from looking like the way out of a dead end.
        fixable = diagnose_log.author_fixable_ids(report.get("diagnostics") or {})
        if fixable and not (report.get("manual_verification") or {}).get("eligible"):
            lines += ["", diagnose_log.configuration_fault_sentence(submitted_by)]

    # Manual verification (level 2), when the automated path structurally cannot
    # run this tool. Never offered over a run that produced its expected output.
    mv = report.get("manual_verification") or {}
    if mv.get("eligible"):
        lines += ["", "## Manual verification available", "",
                  mv["reason"],
                  "",
                  "This is a limitation of the automated environment, not a fault "
                  "found in the tool. STRhub can run it by hand and issue a "
                  "certificate labelled **manual verification**: a separate, paid "
                  "service, distinct from this automated attestation.",
                  "",
                  f"Eligibility reason code: `{mv['reason_code']}` "
                  f"({mv['basis']}).",
                  ]

    # README minimum-to-run checklist (advisory).
    rc = report.get("readme_check")
    if rc:
        lines += ["", "## README check (advisory)", "",
                  f"Score: **{rc.get('score', 0)}/{rc.get('max', 5)}**. Advisory only; "
                  "does not affect the execution badge.", ""]
        for name, c in (rc.get("checks") or {}).items():
            lines.append(f"- {'PASS' if c.get('present') else '—'} {name}")

    # Notes from reading the repository. Last before the scope statement, and
    # labelled for what they are: nothing here was established by running the
    # tool, so it must not be read alongside the gates as though it had been.
    # Before the notes and the scope: what the reader needs to hold the ladder
    # against. Phrased as requirements, not as a shortfall — every tool needs
    # something, and the useful question is what.
    needed = report.get("needed_beyond_repo") or []
    if needed:
        lines += ["", "## What this run needed beyond the repository", "",
                  "The result above describes a run configured as follows. Anyone "
                  "repeating it needs the same things.", ""]
        for item in needed:
            lines.append(f"- {item}")

    cav = report.get("caveats") or {}
    if cav.get("items"):
        # The model id stays in the JSON for auditing and out of the prose. A
        # reviewer reading a forensic report has no use for it, and naming it here
        # invites the impression that the report was written by one, when the gates
        # above were measured by running the tool. What matters to the reader is
        # that this was read rather than executed, which the sentence already says.
        lines += ["", "## Notes from reading the repository", "",
                  "Recorded automatically from the tool's public files when this run "
                  "was configured. **Not verified by execution**, and not part of the "
                  "gates above. Useful for what to check by hand.", ""]
        for item in cav["items"]:
            lines.append(f"- {item}")

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
    # Read once, up here: several blocks below phrase themselves differently
    # depending on whether the tool's own maintainer submitted it.
    submitted_by = (report.get("submission") or {}).get("by")
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

    # Why the build failed — see the markdown render for why it sits this high.
    install_block = ""
    inst = report.get("install_detail") or {}
    if inst.get("diagnostics"):
        irows = "".join(
            f"<tr><td>{esc(i['title'])}</td><td>{esc(i.get('count', 1))}</td>"
            f"<td>{esc(i.get('suggestion', '—'))}</td></tr>"
            for i in inst["diagnostics"]
        )
        build_log = (report.get("logs") or {}).get("build")
        log_link = (f'<p><a href="{esc(build_log)}">Full build output</a></p>'
                    if build_log else "")
        install_block = (
            "<h2>Why the environment did not build</h2>"
            "<p>The container could not be built from the declared install steps, "
            "so nothing below the Installs gate ran.</p>"
            f"<p>{esc(diagnose_log.install_fault_sentence(inst.get('faults') or [], submitted_by))}</p>"
            "<table><thead><tr><th>What happened</th><th>Times</th>"
            "<th>Suggested fix</th></tr></thead>"
            f"<tbody>{irows}</tbody></table>{log_link}"
        )

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
    # Legs where fixture_source=="strhub" are omitted: both legs run on the same
    # STRhub data, so showing them separately would be misleading.
    matrix_block = ""
    # Which legs reported errors — the matrix flags THAT, the section below says what.
    all_diags = report.get("diagnostics") or {}
    legs_with_errors = {
        leg for leg, issues in all_diags.items()
        if any(i.get("severity") == "error" for i in issues)
    }

    datasets = report.get("datasets") or []
    visible_ds = [leg for leg in datasets if leg.get("fixture_source") != "strhub"]
    if visible_ds:
        mrows = []
        for leg in visible_ds:
            avail = leg.get("available", True)
            if not avail:
                chip = '<span class="no">N/A</span>'
            elif leg.get("passed"):
                chip = '<span class="ok">PASS</span>'
            else:
                chip = '<span class="no">—</span>'
            err = ('<span class="warn">yes</span>'
                   if leg.get("leg") in legs_with_errors else '<span class="no">—</span>')
            mrows.append(
                f"<tr><td>{esc(leg.get('label', leg.get('leg', '?')))}</td>"
                f"<td>{chip}</td>"
                f"<td>{err}</td>"
                f"<td>{esc(leg.get('dataset', leg.get('type', '—')))}</td></tr>"
            )
        matrix_block = (
            "<h2>Verification matrix</h2>"
            "<table><thead><tr><th>Leg</th><th>Result</th><th>Errors reported</th>"
            "<th>Dataset</th></tr></thead>"
            f"<tbody>{''.join(mrows)}</tbody></table>"
        )

    # Who chose the regions + the slice caveat (see _regions_note).
    regions_note = _regions_note(report.get("regions") or {}, submitted_by)
    regions_block = (
        f"<h2>Regions</h2><p>{esc(regions_note)}</p>" if regions_note else ""
    )

    # Only for a third-party submission — see THIRD_PARTY_NOTE.
    submitter_block = (
        f"<h2>Who submitted this</h2><p>{esc(THIRD_PARTY_NOTE)}</p>"
        if submitted_by == "third_party" else ""
    )
    submitted_li = (
        f"<li>Submitted by: {esc(SUBMITTER_SHORT[submitted_by])}</li>"
        if submitted_by in SUBMITTER_SHORT else ""
    )

    # Errors the tool reported, in its own section: the matrix says a leg had them,
    # this says what they were, so a reviewer never has to open a container log.
    errors_block = ""
    errs = diagnose_log.summarize(all_diags)
    if errs:
        n_items = sum(len(e["items"]) for e in errs) or len(errs)
        erows = "".join(
            f"<tr><td>{esc(e['title'])}</td><td>{e['count']}</td>"
            f"<td>{esc(', '.join(e['items']) if e['items'] else '—')}</td></tr>"
            for e in errs
        )
        notes = "".join(
            f"<p>{esc(n)}</p>"
            for n in diagnose_log.external_leg_notes(all_diags)
        )
        mv_eligible = bool((report.get("manual_verification") or {}).get("eligible"))
        fixable = diagnose_log.author_fixable_ids(all_diags)
        free_note = (
            f"<p>{esc(diagnose_log.configuration_fault_sentence(submitted_by))}</p>"
            if fixable and not mv_eligible else ""
        )
        errors_block = (
            "<h2>Errors reported during the run</h2>"
            f"<p>The tool reported errors on {n_items} item(s) during the run. "
            "This does not assess whether the results produced are correct.</p>"
            "<table><thead><tr><th>What happened</th><th>Times</th>"
            "<th>Affected</th></tr></thead>"
            f"<tbody>{erows}</tbody></table>{notes}{free_note}"
        )

    # Manual verification (level 2). Only rendered when the engine itself marked
    # the run eligible, so the offer can never appear on a run that worked.
    manual_block = ""
    mv = report.get("manual_verification") or {}
    if mv.get("eligible"):
        manual_block = (
            "<h2>Manual verification available</h2>"
            f"<div class='scope'><p>{esc(mv['reason'])}</p>"
            "<p>This is a limitation of the automated environment, not a fault "
            "found in the tool. STRhub can run it by hand and issue a certificate "
            "labelled <b>manual verification</b>: a separate, paid service, "
            "distinct from this automated attestation.</p>"
            f"<p style='color:#888;font-size:.85rem'>Eligibility reason code: "
            f"<code>{esc(mv['reason_code'])}</code> ({esc(mv['basis'])}).</p></div>"
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
            f"<p>Score: <b>{esc(rc.get('score', 0))}/{esc(rc.get('max', 5))}</b>. "
            "Advisory only; does not affect the execution badge.</p>"
            f"<ul class='stats'>{items}</ul>"
        )

    ci = (f'<a href="{esc(report["ci_run"])}">CI run</a>'
          if report.get("ci_run") else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STRhub Verified · {esc(tool['name'])} ({esc(slug)})</title>
<style>
  body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 820px; margin: 2rem auto;
          padding: 0 1rem; background:#ffffff; color:#1a1a1a; }}
  a {{ color: #2563eb; }}
  .badge {{ display:inline-block; padding:.25rem .7rem; border-radius:999px; color:#fff; font-weight:600; background:{badge}; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #ddd; }}
  .ok {{ color:#16a34a; font-weight:700; }}
  .no {{ color:#999; }}
  .warn {{ color:#b45309; font-weight:700; }}
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
<h1>STRhub Verified · {esc(tool['name'])}</h1>
<p><span class="badge">{esc(LABELS.get(level, 'not run'))}</span></p>
<p>{esc(MEANING.get(level, ''))}.</p>
<ul class="meta">
  <li>Variant: <code>{esc(slug)}</code></li>
  <li>Source: <code>{esc(report['source']['repo'])}</code> @ <code>{esc(report['source']['ref_resolved'])}</code></li>
  <li>Environment: {esc(', '.join(report['environment'].get('os', [])))} (<code>{esc(report['environment']['dockerfile'])}</code>)</li>
  <li>Generated: {esc(report['generated'])}</li>
  {submitted_li}
  {f'<li>{ci}</li>' if ci else ''}
</ul>
<h2>Gates</h2>
<table><thead><tr><th>Gate</th><th>Status</th><th>Meaning</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{install_block}
{content_block}
{matrix_block}
{regions_block}
{submitter_block}
{errors_block}
{manual_block}
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
    ap.add_argument("--log-build", default="",
                    help="path to captured output from the docker build (Installs)")
    ap.add_argument("--ref", default="")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--regions-source", default="",
                    help="who supplied the regions BED: tool | strhub | none")
    ap.add_argument("--regions-validation", default="regions_validation.json",
                    help="path to validate_bed.py output (panel coverage)")
    ap.add_argument("--supported-loci", default="",
                    help="path to the dataset's loci.bed — panel size fallback when "
                         "no validation ran (STRhub-supplied BEDs skip the pre-flight)")
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

    # Who defined the regions this run targeted. Material to a reader: it says
    # whether the author chose the loci (within our panel) or STRhub did. Absent
    # for tools that take no regions BED (FASTQ-based).
    regions = None
    if args.regions_source and args.regions_source != "none":
        regions = {"source": args.regions_source}
        vp = pathlib.Path(args.regions_validation)
        if vp.exists():
            try:
                v = json.loads(vp.read_text())
                regions["covered_loci"] = v.get("covered_count")
                regions["panel_size"] = v.get("panel_size")
            except Exception:  # noqa: BLE001
                pass
        # Only author-supplied BEDs are pre-flighted, so a STRhub-supplied one has
        # no validation file. Count the panel directly — the "this is a slice"
        # caveat is true either way and the reader needs it either way.
        if not regions.get("panel_size") and args.supported_loci:
            sp = ROOT / args.supported_loci
            if sp.is_file():
                regions["panel_size"] = sum(
                    1 for ln in sp.read_text().splitlines()
                    if ln.strip() and not ln.startswith("#")
                ) or None

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
        # Who filled in the submission, straight from the manifest. `tool` names
        # whoever answers for the software; this names whoever asked for the run,
        # and the report must not let a reader read the first as the second.
        # None on manifests written before the form asked — an absence the prose
        # handles by naming nobody.
        "submission": m.get("submission"),
        "source": {**m["source"], "ref_resolved": args.ref or m["source"]["ref"]},
        "environment": m["environment"],
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ci_run": args.run_url,
        "gates": gates,
        "level": level,
        "io_detail": io_detail,
        "content_detail": content_detail,
        "datasets": datasets,
        "regions": regions,
        "readme_check": readme_check,
        "scope": SCOPE,
    }

    # What the run needed that the repository does not provide.
    #
    # A green ladder reads as a property of the software, and quietly folds in
    # whatever it took to get there. For STRsearch that was an 11-column hg38
    # configuration file with flanking sequences, built by hand over half a day,
    # against a repository whose only example is hg19 and covers five markers.
    # None of that appeared anywhere, so the badge claimed more than the run
    # measured. Stating the requirements is stronger than hedging the badge: each
    # line is a checkable fact, and for a reader deciding whether to adopt the
    # tool it is the practical question — what will this cost me to run.
    needed = []
    if (regions or {}).get("source") == "tool":
        needed.append(
            "A regions configuration file, supplied with the submission rather "
            "than taken from the repository."
        )
    if not any(d.get("leg") == "own" and d.get("available") for d in (datasets or [])):
        # Says what we know, not what we would have to have checked. An absent own
        # leg means no repository test data was USED; it does not establish that
        # the repository ships none. STRsearch ships some — for hg19, against an
        # hg38 dataset — so the stronger sentence would have been false exactly
        # where it was about to be published.
        needed.append(
            "Test data: no sample from the repository was used, so a public "
            "reference sample stood in."
        )
    env_source = (m.get("environment") or {}).get("source")
    if env_source == "generated":
        needed.append(
            "A container environment, built from the tool's declared install "
            "steps rather than from a recipe the repository ships."
        )
    elif env_source == "submitted":
        needed.append(
            "A container environment, supplied with the submission."
        )
    if needed:
        report["needed_beyond_repo"] = needed

    # Notes taken while reading the repository, carried straight from the manifest
    # and kept OUT of "gates" and "diagnostics" on purpose. Those two are what
    # running the tool established; this is what somebody read beforehand, and a
    # reader has to be able to tell the difference. The provenance travels with
    # the text so they can weigh it.
    if m.get("caveats", {}).get("items"):
        report["caveats"] = m["caveats"]

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
    # The build log rides along with the run logs. A reader told the build failed
    # will want the same thing a reader told a run failed wants: the output.
    for leg, flag in [("own", args.log_own), ("external", args.log_external),
                      ("build", args.log_build)]:
        if not flag:
            continue
        lp = pathlib.Path(flag)
        if lp.exists() and lp.stat().st_size > 0:
            dest = f"{slug}.log-{leg}.txt"
            shutil.copy2(lp, reports / dest)
            logs[leg] = dest
    if logs:
        report["logs"] = logs

    # Why the environment did not build.
    #
    # Kept out of `diagnostics`, which is keyed by verification leg and means
    # "errors the tool reported while running". A build failure happens before
    # any run, so folding it in there would put it under a heading that says
    # "during the run" and count it toward a badge suffix about a run that never
    # happened. It is its own thing, and only meaningful when Installs failed:
    # a warning in a build that succeeded is not news.
    install_detail = None
    if args.log_build and not gates["installs"]:
        issues = diagnose_log.diagnose_file(args.log_build)
        install_detail = {
            "passed": False,
            "diagnostics": issues,
            # The side each cause falls on, decided by class rather than by
            # reading the text — so a fault of ours can never be published as a
            # finding about somebody's software.
            "faults": sorted({
                f for f in (diagnose_log.fault_of(i["id"]) for i in issues) if f
            }),
        }
        report["install_detail"] = install_detail

    diagnostics = {}
    for leg, flag in [("own", args.log_own), ("external", args.log_external)]:
        if not flag:
            continue
        issues = diagnose_log.diagnose_file(flag)
        if issues:
            diagnostics[leg] = issues
    if diagnostics:
        report["diagnostics"] = diagnostics

    # Whether this run may be offered the paid, human-run verification (level 2).
    # Emitted unconditionally — including `eligible: false` — so the web can tell a
    # report that was checked and did not qualify from an older one that predates
    # the check. The decision is entirely mechanical (see diagnose_log): a declared
    # environment ceiling, or one the log proves we hit. Nobody grants it by hand.
    report["manual_verification"] = diagnose_log.manual_eligibility(
        diagnostics, gates, m.get("compatibility"),
    )

    (reports / f"{slug}.json").write_text(json.dumps(report, indent=2))

    color = "brightgreen" if level == "content" \
        else "green" if level in ("io", "runs") \
        else "yellow" if level in ("installs", "available") else "red"
    message = LABELS.get(level, "not run")

    # A run can clear its gates and still have reported errors: a tool that fails
    # on some loci, writes a partial file and exits 0 clears "Expected IO" on the
    # strength of what did come out. The badge is the most-seen artifact, so an
    # unqualified green there hides that. Saying so is descriptive — the tool's own
    # log emitted the errors — and stays clear of judging genotype correctness,
    # which needs a truth set we do not have. Warnings never count: benign stderr
    # noise is common and marking it would be unfair.
    n_errors = sum(
        issue.get("count", 1)
        for leg_issues in diagnostics.values()
        for issue in leg_issues
        if issue.get("severity") == "error"
    )
    if n_errors and color in ("brightgreen", "green"):
        color = "yellow"
        message = f"{message} (errors reported)"

    badge = {"schemaVersion": 1, "label": "STRhub Verified",
             "message": message, "color": color}
    (reports / f"{slug}.badge.json").write_text(json.dumps(badge, indent=2))

    (reports / f"{slug}.summary.md").write_text(_summary_md(report, slug))
    (reports / f"{slug}.html").write_text(_summary_html(report, slug))

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
