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
from prepare import unwrap_example  # noqa: E402
from certificate_text import (  # noqa: E402
    install_meaning, instrument_of, instrument_of_report, workaround_lines,
    INSTRUMENT_LINE, BADGE_INSTRUMENTS, CURATED_HEADING, CURATED_LEAD, CURATED_NEEDED,
)
import verdict as verdict_lib  # noqa: E402
import upstream  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCOPE = ("Executed end-to-end in the stated environment with output in the "
         "expected format. Concerns reproducible execution only; no claim of "
         "accuracy, casework fitness, or regulatory validation.")

# Highest gate cleared, in order. The badge reflects the furthest green gate.
LADDER = ["available", "installs", "runs", "io", "content"]
#: Written into the build log by the Installs step between the attempt that
#: failed and the plan-B build that followed it (see verify.yml).
FALLBACK_MARKER = "==== STRhub: the build above failed; building the fallback environment"
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


#: How the summary names each evidence claim. Every kind detect_recipe emits
#: needs a line here, or the reader gets the raw id ("platform_advice").
CLAIM_LABELS = {
    "install_method": "Install method", "published_image": "Published image",
    "bioconda_package": "Bioconda package", "fallback_environment": "Fallback environment",
    "run_command": "Run command", "example_data": "Example data", "known_issue": "Known issue",
    "documented_input": "Documented input", "author_recommendation": "Author's recommendation",
    "platform_advice": "Platform advice",
}
EVIDENCE_LEAD = ("What this run's configuration rests on, each item at the verified commit. "
                 "Open any of them to check the claim it supports.")
NEEDED_LEAD = ("The result above describes a run configured as follows. Anyone "
               "repeating it needs the same things.")
# Word for word the certificate's sentence (generate_pdf), so the two renderings
# of one note stay one registered claim.
CAVEATS_LEAD = ("Recorded automatically from the tool's public files when this run was "
                "configured. Not verified by execution, and not part of the gates "
                "above. Useful for what to check by hand.")
RUN_LEAD = ("Executed verbatim inside the container, at the pinned commit. Paths "
            "under /data are STRhub's mounts: the input sample, the reference "
            "genome and the output directory.")

def _status(flag: str) -> bool:
    # Accept GitHub Actions step outcomes ("success") alongside our own words.
    return str(flag).lower() in ("pass", "true", "ok", "1", "success")


def _regions_note(rg: dict) -> str:
    """One sentence on where the target regions came from, and that the data is a slice.

    Shared by the markdown and HTML renders so the two cannot drift. Returns "" for
    tools that take no regions BED (FASTQ-based).

    Never "the tool's author": `provided_by` records that the BED came with the
    submission, not who wrote it. A verification is the same fact whoever
    triggered it, so the sentence names the submission and claims nothing
    about the person behind it.
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
        return f"The submission supplied the regions BED{detail}.{slice_note}"
    if rg.get("source") == "strhub":
        return f"STRhub supplied the regions BED.{slice_note}"
    return ""


# One line, on every report: what a result is and is not. Who triggered the
# run used to get a section of its own; a verification is the same fact
# whoever asked for it, and the one thing a reader must not infer is that
# the tool's author stands behind it.
RECORD_NOTE = (
    "Verified automatically, in a clean environment, on the tool's public "
    "source at the pinned commit. This is a record of what happened, not an "
    "endorsement by the tool's author."
)


LABELS.setdefault("example", "Reproduces own example")
MEANING.setdefault("example", "the README's own command produced its documented output on the repository's own data")


def _verdict_md(report: dict) -> list[str]:
    v = report.get("verdict")
    if not v:
        return []
    lines = ["", f"**Verdict: {v['title']}.** {v['reason']}"]
    if v.get("blockers"):
        lines += ["", "What stopped it, and what can be done:", ""]
        for b in v["blockers"]:
            lines += [f"- {b['what']}",
                      f"  - Yourself: {b['self_fix_text']}",
                      f"  - The tool's owner: open an issue, \"{b['ask_owner']['title']}\"."]
    if v.get("readme_gaps"):
        lines += ["", "What the README does not say:", ""]
        lines += [f"- {g['text']}" for g in v["readme_gaps"]]
    return lines


def _fallback_reason(env: dict) -> str:
    fb = env.get("fallback") or {}
    return fb.get("reason") or "the fallback environment the manifest declares"


def _environment_line(env: dict, code=lambda t: f"`{t}`") -> str:
    """'ubuntu-22.04 (`Dockerfile`)', plus plan B when that is what ran.
    `code` wraps a file name: backticks for markdown, <code> for HTML."""
    line = f"{', '.join(env.get('os', []))} ({code(env['dockerfile'])})"
    if env.get("fallback_used"):
        fb = env.get("fallback") or {}
        line += (f" — plan B: {_fallback_reason(env)} ({code(fb.get('dockerfile', 'Dockerfile.fallback'))}), "
                 "after the build from the pinned commit failed")
    return line


def _install_heading(inst: dict) -> str:
    # Plain words, not the mechanism: "why the pinned commit did not build"
    # told a reader who did not know what a pinned commit was that something
    # with a name they did not know had failed.
    return ("It did not build from source; the run used the README's ready-made environment"
            if inst.get("fallback_used") else "It did not build from source")


def _install_lead(inst: dict, env: dict) -> str:
    tried = ("STRhub tried to build the tool from its source at the pinned commit, "
             "following the build steps the repository declares, and the build failed.")
    if inst.get("fallback_used"):
        return (f"{tried} {_fallback_reason(env)[0].upper()}{_fallback_reason(env)[1:]} "
                "was used instead, and every gate below ran on it.")
    return f"{tried} Nothing below the Installs gate ran."


def _primary_build_log(path: str) -> str:
    """The build log up to the plan-B marker: the attempt on the pinned commit."""
    p = pathlib.Path(path)
    if not p.exists():
        return ""
    return p.read_text(errors="replace").split(FALLBACK_MARKER, 1)[0]


def _run_record(m: dict) -> dict | None:
    """`run.cmd` for the report: the tool's own command, out of the wrapper a
    proposed recipe puts around it, and the directory it ran from when the
    wrapper named one."""
    cmd = (m.get("run") or {}).get("cmd")
    if not cmd:
        return None
    inner, cwd = unwrap_example(cmd)
    return {"cmd": inner, **({"cwd": cwd} if cwd else {})}


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
        *_verdict_md(report),
        "",
        f"- Source: `{report['source']['repo']}` @ `{report['source']['ref_resolved']}`",
        f"- Environment: {_environment_line(report['environment'])}",
        f"- Generated: {report['generated']}",
    ]
    up_note = upstream.note(report.get("upstream"))
    if up_note:
        lines.append(f"- Upstream: {up_note}")
    lines.append(f"- Recipe: {INSTRUMENT_LINE[instrument_of_report(report)]}")
    if report.get("ci_run"):
        lines.append(f"- CI run: {report['ci_run']}")
    run = report.get("run") or {}
    if run.get("cmd"):
        lines += ["", "## Command that ran", "", RUN_LEAD, "", "```", run["cmd"], "```"]
    lines += [
        "",
        "## Gates",
        "",
        "| Gate | Status | Meaning |",
        "|---|---|---|",
    ]
    for g in LADDER:
        lines.append(f"| {LABELS[g]} | {mark[gates.get(g, False)]} | {MEANING.get(g, '')} |")
    if "example" in gates:
        lines.append(f"| {LABELS['example']} | {mark[bool(gates['example'])]} | {MEANING['example']} |")

    # Why the build failed, immediately after the ladder that says it did.
    # Nothing below this point ran, so the reader needs the reason here rather
    # than at the foot of a report about a run that never happened.
    inst = report.get("install_detail") or {}
    if inst.get("diagnostics"):
        lines += ["", f"## {_install_heading(inst)}", "",
                  _install_lead(inst, report["environment"]),
                  "",
                  "What this means:", ""]
        lines += [f"- **{who}:** {what}" for who, what in
                  install_meaning(bool(inst.get("fallback_used")), inst.get("faults") or [])]
        lines += ["", "What failed:", "",
                  "| What happened | Times | Suggested fix |",
                  "|---|---|---|"]
        for issue in inst["diagnostics"]:
            fix = issue.get("suggestion", "—").replace("\n", " ")
            lines.append(f"| {issue['title']} | {issue.get('count', 1)} | {fix} |")
        build_log = (report.get("logs") or {}).get("build")
        if build_log:
            lines += ["", f"Full build output: [`{build_log}`]({build_log})"]

    # The author's own words about their own software, before any of STRhub's
    # findings: a run that stops where the README says it stops is not news,
    # and a reader must be able to see that without opening the repository.
    known = report.get("author_known_issues") or []
    if known:
        lines += ["", "## What the author documents as a known issue", "",
                  "Quoted from the repository's README at the verified commit. "
                  "STRhub did not establish any of this by running the tool; it is "
                  "the author's own note about their own software."]
        for k in known:
            quote = k["text"] + ("…" if k.get("truncated") else "")
            lines += ["", f"**{k['heading']}** (README line {k['line']})", "", f"> {quote}"]

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
        note = _regions_note(rg)
        if note:
            lines += ["", "## Regions", "", note]

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
            lines += ["", diagnose_log.configuration_fault_sentence()]

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
    ev = report.get("evidence") or []
    if ev:
        lines += ["", "## Evidence", "", EVIDENCE_LEAD]
        for e in ev:
            where = f"`{e['path']}`" + (f" line {e['line']}" if e.get("line") else "")
            # Whole, not clipped: the platform advice is the one line a reader
            # most needs entire, since the run may have gone against it.
            txt = f" — `{e['text']}`" if e.get("text") and e["kind"] == "readme" else ""
            lines.append(f"- {CLAIM_LABELS.get(e['claim'], e['claim'])}: [{where}]({e['url']}){txt}")

    needed = report.get("needed_beyond_repo") or []
    if needed:
        lines += ["", "## What this run needed beyond the repository", "", NEEDED_LEAD, ""]
        for item in needed:
            lines.append(f"- {item}")

    if instrument_of_report(report) == "curated":
        lines += ["", f"## {CURATED_HEADING}", "", CURATED_LEAD, ""]
        lines += [f"- {w}" for w in workaround_lines(report)] or ["- (not itemised for this recipe)"]

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
        RECORD_NOTE,
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
    badge = {"content": "#16a34a", "io": "#22a722", "runs": "#22a722",
             "installs": "#d4a017", "available": "#d4a017"}.get(level, "#c33")

    def esc(s):
        return _html.escape(str(s))

    rows = []
    for g in LADDER + (["example"] if "example" in gates else []):
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
        meaning = "".join(
            f"<li><b>{esc(who)}:</b> {esc(what)}</li>" for who, what in
            install_meaning(bool(inst.get("fallback_used")), inst.get("faults") or []))
        install_block = (
            f"<h2>{esc(_install_heading(inst))}</h2>"
            f"<p>{esc(_install_lead(inst, report['environment']))}</p>"
            f"<p><b>What this means</b></p><ul class='stats'>{meaning}</ul>"
            "<p><b>What failed</b></p>"
            "<table><thead><tr><th>What happened</th><th>Times</th>"
            "<th>Suggested fix</th></tr></thead>"
            f"<tbody>{irows}</tbody></table>{log_link}"
        )

    known_block = ""
    known = report.get("author_known_issues") or []
    if known:
        quotes = "".join(
            f"<p><b>{esc(k['heading'])}</b> (README line {esc(k['line'])})</p>"
            f"<blockquote>{esc(k['text'])}{'…' if k.get('truncated') else ''}</blockquote>"
            for k in known)
        known_block = (
            "<h2>What the author documents as a known issue</h2>"
            "<p>Quoted from the repository's README at the verified commit. STRhub did "
            "not establish any of this by running the tool; it is the author's own note "
            "about their own software.</p>" + quotes)

    # The verdict the page leads with. A copy that omits it can read as a pass
    # while the page it mirrors says "Fails".
    v = report.get("verdict") or {}
    verdict_block = (f"<p><b>Verdict: {esc(v['title'])}.</b> {esc(v['reason'])}</p>"
                     if v.get("title") and v.get("reason") else "")

    # The command the gates ran — the certificate's "Exact Run Command".
    run = report.get("run") or {}
    run_block = (
        f"<h2>Command that ran</h2><p>{esc(RUN_LEAD)}</p>"
        f"<pre><code>{esc(run['cmd'])}</code></pre>"
        if run.get("cmd") else ""
    )

    content_block = ""
    outs = report.get("content_detail", {}).get("outputs", [])
    stats = outs[0].get("stats") if outs and isinstance(outs[0], dict) else None
    if stats:
        str_loci = stats.get("str_loci", stats.get("loci", []))
        n_str = stats.get("distinct_str_loci", len(str_loci))
        n_snp = stats.get("distinct_snp_markers", 0)
        markers_li = f"<li>STR loci detected: <b>{esc(n_str)}</b>"
        if n_snp:
            markers_li += (f" &middot; identity SNPs (rsNNNN): <b>{esc(n_snp)}</b> "
                           f"(total panel markers: {esc(stats.get('distinct_loci', 0))})")
        markers_li += "</li>"
        # Which file, from the IO gate: the content gate describes the same one.
        io_outs = (report.get("io_detail") or {}).get("outputs") or []
        io0 = io_outs[0] if io_outs and isinstance(io_outs[0], dict) else {}
        file_li = ""
        if io0.get("resolved") or io0.get("path"):
            fmt = f" ({esc(str(io0.get('format')).upper())})" if io0.get("format") else ""
            file_li = f"<li>Output file: <code>{esc(io0.get('resolved') or io0.get('path'))}</code>{fmt}</li>"
        given, hit = stats.get("regions_given"), stats.get("regions_hit")
        coverage_li = (f"<li>Panel loci called: <b>{esc(hit)}</b> of {esc(given)}</li>"
                       if isinstance(given, int) and isinstance(hit, int) and given > 0 else "")
        # Every locus with its depth, as the certificate's appendix has it: a
        # reader sees the shape of the output, not six names and an ellipsis.
        depth = stats.get("top_loci_by_depth") or []
        depth_table = ""
        if depth:
            mx = max((d for _, d in depth), default=0) or 1
            drows = "".join(
                f"<tr><td><code>{esc(l)}</code></td><td>{esc(d)}</td>"
                f"<td><span class=\"bar\" style=\"width:{max(1, round(100 * d / mx))}%\"></span></td></tr>"
                for l, d in depth)
            depth_table = ("<h3>Read depth per locus</h3>"
                           "<table class=\"depth\"><thead><tr><th>Locus</th><th>Reads</th><th></th></tr></thead>"
                           f"<tbody>{drows}</tbody></table>")
        content_block = f"""
    <h2>Output content (plausibility evidence)</h2>
    <ul class="stats">
      {file_li}
      <li>Sequence records: <b>{esc(stats.get('rows', 0))}</b> (malformed: {esc(stats.get('malformed_rows', 0))})</li>
      {markers_li}
      <li>Total reads across calls: <b>{esc(stats.get('total_reads', 0))}</b> (deepest single locus: {esc(stats.get('max_sequence_depth', 0))})</li>
      {coverage_li}
      {'<li>STR loci: ' + esc(", ".join(str_loci)) + '</li>' if str_loci else ''}
    </ul>{depth_table}"""

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
    regions_note = _regions_note(report.get("regions") or {})
    regions_block = (
        f"<h2>Regions</h2><p>{esc(regions_note)}</p>" if regions_note else ""
    )
    _up_note = upstream.note(report.get("upstream"))
    upstream_li = f"<li>Upstream: {esc(_up_note)}</li>" if _up_note else ""

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
            f"<p>{esc(diagnose_log.configuration_fault_sentence())}</p>"
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

    # What the run rests on, what it needed, what was read rather than run:
    # the page and the certificate carry all three, and this copy did not.
    evidence_block = ""
    ev = report.get("evidence") or []
    if ev:
        items = []
        for e in ev:
            where = esc(e["path"]) + (f" line {esc(e['line'])}" if e.get("line") else "")
            quote = (f" — <code>{esc(e['text'])}</code>"
                     if e.get("text") and e.get("kind") == "readme" else "")
            items.append(f"<li>{esc(CLAIM_LABELS.get(e['claim'], e['claim']))}: "
                         f"<a href=\"{esc(e['url'])}\">{where}</a>{quote}</li>")
        evidence_block = (f"<h2>Evidence</h2><p>{esc(EVIDENCE_LEAD)}</p>"
                          f"<ul class='stats'>{''.join(items)}</ul>")

    needed_block = ""
    needed = report.get("needed_beyond_repo") or []
    if needed:
        needed_block = (
            f"<h2>What this run needed beyond the repository</h2><p>{esc(NEEDED_LEAD)}</p>"
            f"<ul class='stats'>{''.join(f'<li>{esc(i)}</li>' for i in needed)}</ul>")

    curated_block = ""
    if instrument_of_report(report) == "curated":
        items = "".join(f"<li>{esc(w)}</li>" for w in workaround_lines(report)) or "<li>(not itemised for this recipe)</li>"
        curated_block = (f"<h2>{esc(CURATED_HEADING)}</h2><p>{esc(CURATED_LEAD)}</p>"
                         f"<ul class='stats'>{items}</ul>")

    caveats_block = ""
    cav = report.get("caveats") or {}
    if cav.get("items"):
        caveats_block = (
            f"<h2>Notes from reading the repository</h2><p>{esc(CAVEATS_LEAD)}</p>"
            f"<ul class='stats'>{''.join(f'<li>{esc(i)}</li>' for i in cav['items'])}</ul>")

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
  pre {{ background:#eef0f2; padding:.8rem 1rem; border-radius:6px; overflow-x:auto; white-space:pre-wrap; word-break:break-all; font-size:.85rem; }}
  pre code {{ background:none; padding:0; }}
  table.depth td {{ padding:.25rem .6rem; }}
  table.depth td:nth-child(2) {{ text-align:right; font-variant-numeric:tabular-nums; width:5rem; }}
  table.depth td:nth-child(3) {{ width:50%; }}
  .bar {{ display:inline-block; height:.6rem; background:{badge}; border-radius:3px; vertical-align:middle; }}
  nav {{ margin-bottom:1rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background:#0d1117; color:#e6edf3; }}
    a {{ color:#58a6ff; }}
    th, td {{ border-bottom:1px solid #30363d; }}
    .scope {{ background:#161b22; }}
    code, pre {{ background:#21262d; }}
  }}
</style></head><body>
<nav><a href="index.html">← All tools</a></nav>
<h1>STRhub Verified · {esc(tool['name'])}</h1>
<p><span class="badge">{esc(LABELS.get(level, 'not run'))}</span></p>
<p>{esc(MEANING.get(level, ''))}.</p>
{verdict_block}
<ul class="meta">
  <li>Variant: <code>{esc(slug)}</code></li>
  <li>Source: <code>{esc(report['source']['repo'])}</code> @ <code>{esc(report['source']['ref_resolved'])}</code></li>
  <li>Environment: {_environment_line({**report['environment'], 'os': [esc(o) for o in report['environment'].get('os', [])]}, code=lambda t: f"<code>{esc(t)}</code>")}</li>
  <li>Generated: {esc(report['generated'])}</li>
  {upstream_li}
  <li>Recipe: {esc(INSTRUMENT_LINE[instrument_of_report(report)])}</li>
  {f'<li>{ci}</li>' if ci else ''}
</ul>
{run_block}
<h2>Gates</h2>
<table><thead><tr><th>Gate</th><th>Status</th><th>Meaning</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{install_block}
{known_block}
{content_block}
{matrix_block}
{regions_block}
{errors_block}
{manual_block}
{readme_block}
{evidence_block}
{needed_block}
{curated_block}
{caveats_block}
<h2>Scope</h2>
<p class="scope">{esc(report['scope'])}<br><br>
This is <b>not</b> a claim that the genotypes are correct, nor that the tool is
fit for casework or meets any regulatory standard. Concordance against known
truth is out of scope.</p>
<p style="color:#888;font-size:.85rem">{esc(RECORD_NOTE)}</p>
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
    ap.add_argument("--environment-built", default="", choices=["", "primary", "fallback"],
                    help="which Dockerfile produced the image the gates ran on: 'fallback' "
                         "when the pinned commit did not build and the manifest's plan B "
                         "(environment.fallback) was built instead")
    ap.add_argument("--check-upstream", action="store_true",
                    help="ask GitHub how far the pinned ref has fallen behind the "
                         "repository's default branch, and whether it still exists")
    ap.add_argument("--ref", default="")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--example-runs", default="skipped",
                    help="outcome of the own-example step (success/failure/skipped)")
    ap.add_argument("--example", default="example.json", help="path to check_example.py output")
    ap.add_argument("--log-example", default="", help="log of the own-example leg")
    ap.add_argument("--recipe-proposal", default="",
                    help="detect_recipe.py output when the recipe was proposed from the "
                         "repository; lets the verdict tell a documentation gap from a failure")
    ap.add_argument("--repo-read", default="",
                    help="detect_recipe.py output for a run whose recipe was NOT proposed "
                         "(a committed tool). Evidence only — what the repository holds and "
                         "what its README documents — and never treated as a proposed recipe, "
                         "which would change the verdict")
    ap.add_argument("--mode", default="publish", choices=["publish", "trial"],
                    help="trial: an unpublished rehearsal of a recipe; stamped into the "
                         "report so a trial can never be mistaken for an attestation")
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
    # The tool's own example, outside the ladder: present only when the manifest
    # declared one, so older readers that iterate the five ladder gates see
    # nothing new and newer ones can show the reviewer's line.
    example_detail = {}
    ep = pathlib.Path(args.example)
    if ep.exists():
        try:
            example_detail = json.loads(ep.read_text())
        except Exception:  # noqa: BLE001
            example_detail = {}
    if example_detail.get("applicable"):
        gates["example"] = bool(example_detail.get("passed"))

    # Highest contiguous green gate from the bottom of the ladder.
    level = "none"
    for g in LADDER:
        if gates[g]:
            level = g
        else:
            break

    report = {
        "schema": "strhub-verified/1",
        # "trial" is a rehearsal: same gates, same honesty, no catalogue entry,
        # no badge anyone can cite. Readers (the web, build_index) key on it.
        "mode": args.mode,
        "tool": m["tool"],
        # Who filled in the submission, straight from the manifest. `tool` names
        # whoever answers for the software; this names whoever asked for the run,
        # and the report must not let a reader read the first as the second.
        # None on manifests written before the form asked — an absence the prose
        # handles by naming nobody.
        "submission": m.get("submission"),
        "source": {**m["source"], "ref_resolved": args.ref or m["source"]["ref"]},
        # Plan B is recorded on the environment itself: a reader of the JSON
        # must not have to open the build log to learn that what ran was not
        # built from the pinned commit.
        "environment": ({**m["environment"], "fallback_used": True}
                        if args.environment_built == "fallback" else m["environment"]),
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ci_run": args.run_url,
        # What the gates ran, as the tool saw it. The certificate has printed
        # the command since the start; the page could not, because the JSON
        # never carried it, so a reader of a published attestation had to open
        # the log to learn what was executed.
        "run": _run_record(m),
        # Which instrument this is, and — for a recipe somebody wrote — what it
        # does that the repository's instructions do not. The badge may rest
        # only on `documented` or `maintainer`; `curated` is STRhub's note.
        "instrument": instrument_of(m),
        "recipe": {"origin": (m.get("recipe") or {}).get("origin")
                             or {"documented": "proposed"}.get(instrument_of(m), instrument_of(m)),
                   **({"workarounds": m["recipe"]["workarounds"]}
                      if (m.get("recipe") or {}).get("workarounds") else {})},
        "gates": gates,
        "level": level,
        "io_detail": io_detail,
        "content_detail": content_detail,
        "example_detail": example_detail or None,
        "datasets": datasets,
        "regions": regions,
        "readme_check": readme_check,
        "scope": SCOPE,
    }

    # Where the pinned commit sits now. One or two API calls, no CI: it answers
    # the question a reviewer actually has — is what was verified the version I
    # am looking at — and catches the case that matters, a ref nobody can fetch
    # any more. Omitted entirely when the check could not be made: silence beats
    # a guess about how current somebody's software is.
    if args.check_upstream:
        up = upstream.check(m["source"]["repo"], args.ref or m["source"]["ref"])
        if up:
            # When the pinned commit was made: a fact about the source, not
            # about where the branch has gone since, so it lives with the
            # source. It is what orders a tool's history (docs/PLAN-Version-
            # History.md); a report that lacks it is one from before.
            committed = up.pop("committed", None)
            if committed:
                report["source"]["committed"] = committed
            report["upstream"] = up

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
    proposal = None
    if args.recipe_proposal and pathlib.Path(args.recipe_proposal).exists():
        try:
            proposal = json.loads(pathlib.Path(args.recipe_proposal).read_text())
        except Exception:  # noqa: BLE001
            proposal = None
    env_source = (m.get("environment") or {}).get("source")
    if args.environment_built == "fallback":
        needed.append(
            f"A container environment: the build from the pinned commit failed, so "
            f"{_fallback_reason(m['environment'])} was built instead. What ran is the "
            "version that environment holds, not necessarily the pinned commit."
        )
    elif env_source == "generated":
        needed.append(
            "A container environment, built from the tool's declared install "
            "steps rather than from a recipe the repository ships."
        )
    elif env_source == "submitted":
        needed.append(
            "A container environment, supplied with the submission."
        )
    elif instrument_of(m) == "curated":
        needed.append(CURATED_NEEDED)
    if needed:
        report["needed_beyond_repo"] = needed

    # Whether the repository ships example data, as EVIDENCE rather than as an
    # assumption. Only a run whose recipe was proposed from the repository has
    # read the tree; for a committed recipe nobody looked, and a report must
    # then say what STRhub used rather than what the author ships. The
    # certificate used to state "This tool does not include its own demo or
    # test data" unconditionally — false for STRsearch, which ships 35 files
    # including example/test_data/test.bam.
    # What the author already wrote down as wrong or incomplete, quoted from
    # their README at the pinned ref. STRspy documents that its wrapper can
    # exit without doing any work; a report on a run that died in that wrapper
    # said nothing about it, because nobody carried the section out of the
    # README. A reader deciding whether a failure is news needs this first.
    # Reading the repository is evidence collection, and it is worth doing for
    # every run — not only for one whose recipe STRhub proposed. A published
    # tool's recipe is committed, so no proposal exists, and the catalogue
    # carried none of this: no known-issue section, and a certificate still
    # claiming the tool ships no test data because nobody had looked. The
    # verdict keeps reading `proposal` alone, since "the recipe was proposed
    # from the repository" is what changes a verdict, and reading a repository
    # is not that.
    evidence = proposal
    if evidence is None and args.repo_read and pathlib.Path(args.repo_read).exists():
        try:
            evidence = json.loads(pathlib.Path(args.repo_read).read_text())
        except Exception:  # noqa: BLE001
            evidence = None
    if evidence is not None and evidence.get("known_issues"):
        report["author_known_issues"] = evidence["known_issues"]
    # Every fact the run's configuration rests on, as something a reader can
    # open: file, line, the text as read, and the URL at the pinned ref.
    # Phase B of docs/PLAN-Claims-Need-Evidence.md — a claim that cannot be
    # checked in one click cannot be challenged either.
    if evidence is not None and evidence.get("evidence"):
        report["evidence"] = evidence["evidence"]
    if evidence is not None:
        examples = evidence.get("example_data") or []
        report["repo_test_data"] = {
            "known": True,
            "present": bool(examples),
            "count": len(examples),
            "examples": [e.get("path") for e in examples[:5] if isinstance(e, dict)],
        }

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
                      ("example", args.log_example), ("build", args.log_build)]:
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
    if args.log_build and args.environment_built == "fallback" and gates["installs"]:
        # The gate passed on plan B; why the pinned commit did not build is
        # still the finding a maintainer wants, so the first attempt's log is
        # diagnosed on its own, cut at the marker the Installs step wrote.
        issues = diagnose_log.diagnose(_primary_build_log(args.log_build))
        install_detail = {
            "passed": True,
            "fallback_used": True,
            "diagnostics": issues,
            "faults": sorted({
                f for f in (diagnose_log.fault_of(i["id"]) for i in issues) if f
            }),
        }
    elif args.log_build and not gates["installs"]:
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
    if install_detail is not None:
        report["install_detail"] = install_detail

    diagnostics = {}
    for leg, flag in [("own", args.log_own), ("external", args.log_external),
                      ("example", args.log_example)]:
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

    # The one sentence for a reader who does not program. Decided from the gates,
    # the diagnostics and, when the recipe was proposed from the repository, the
    # README gaps detect_recipe found (see harness/verdict.py for the policy).
    report["verdict"] = verdict_lib.decide(
        gates, diagnostics, report["manual_verification"], proposal, m.get("compatibility"),
        fallback_used=args.environment_built == "fallback",
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

    # A result of a recipe STRhub wrote must not read as the tool's own on
    # the one artifact that travels alone.
    if report["instrument"] not in BADGE_INSTRUMENTS:
        message = f"{message} · STRhub's recipe"
    badge = {"schemaVersion": 1, "label": "STRhub Verified",
             "message": message, "color": color}
    (reports / f"{slug}.badge.json").write_text(json.dumps(badge, indent=2))

    (reports / f"{slug}.summary.md").write_text(_summary_md(report, slug))
    (reports / f"{slug}.html").write_text(_summary_html(report, slug))

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
