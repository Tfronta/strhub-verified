"""What the certificate claims, as text derived from the gates.

Kept apart from the rendering (generate_pdf) on purpose: these sentences are
the report's claims about somebody's software, and they have to be testable
without a PDF toolchain — the CI job that gates every run installs no
renderer. The rendering decides where a sentence sits on the page; this
decides whether it may be said at all.
"""
from __future__ import annotations

import diagnose_log


#: Which instrument a run is, and what the badge may rest on
#: (docs/PLAN-Documented-Is-The-Badge.md). `documented` and `maintainer` may
#: stand behind the badge; `curated` is a note under the documented result.
INSTRUMENT_LINE = {
    "documented": "the repository's own instructions, read off the README and the tree at the pinned commit",
    "maintainer": "a recipe the tool's maintainer submitted",
    "curated": "a recipe STRhub wrote by hand, not read off the repository: a note under the documented result, never the badge",
}
BADGE_INSTRUMENTS = ("documented", "maintainer")

#: The two chapters of a report, in this order (docs/PLAN-Documented-Is-The-
#: Badge.md, tanda 5c): first what happens to the tool as it is in its
#: repository — the label, where it stopped, why, how; then, apart, what
#: STRhub had to do to run it. The second never changes the label.
AS_IS_HEADING = "As it is in the repository"
STRHUB_DID_HEADING = "What STRhub had to do to run this tool"
STRHUB_DID_LEAD = ("STRhub wrote its own recipe for this tool — an environment and a command of "
                   "its own, not the repository's instructions — and ran that. Each item below "
                   "is something a first-time user following the README would have to work out "
                   "for themselves, and so a recommendation to the author. This run does not "
                   "change the tool's label: the label is what happens as it is in the repository.")
FULL_RUN_HEADING = "This run, in full"
NOT_DOCUMENTED = "Not verified as documented"
# Older names, kept for callers.
CURATED_HEADING = STRHUB_DID_HEADING
CURATED_LEAD = STRHUB_DID_LEAD
CURATED_NEEDED = ("A container environment and a command written by STRhub, not taken from the "
                  "repository's instructions; what they do differently is listed under "
                  f"\"{STRHUB_DID_HEADING}\".")

#: Where a run that does not run stopped, in the label's words, by the rung
#: it reached. The rung itself stays in the ladder.
STOPS_AT = {
    "none": "source not available",
    "available": "stops at install",
    "installs": "stops at run",
    "runs": "no output",
    "io": "output not plausible",
}
#: The rung reached, for the line under the label. Same words as report.LABELS.
REACHED = {"none": "not run", "available": "Available", "installs": "Installs",
           "runs": "Runs", "io": "Runs + Expected IO", "content": "Runs + Plausible output"}
#: shields.io colour → the hex the HTML copies use.
COLOR_HEX = {"brightgreen": "#16a34a", "green": "#22a722", "yellow": "#d4a017",
             "red": "#c33", "lightgrey": "#9ca3af"}


def errors_reported(report: dict) -> bool:
    return any(i.get("severity") == "error"
               for issues in (report.get("diagnostics") or {}).values() for i in issues)


def headline(report: dict) -> tuple[str, str]:
    """The label, in words, and its shields colour: what the run says about
    the tool AS IT IS in its repository. The badge, both summaries, the
    index and the certificate all print this and nothing else as the result;
    the rung reached is a detail under it.

      Runs as documented                          the documented run produced its output
      Runs as documented (errors reported)        … and the tool's log reported errors
      Does not run as documented: stops at run   the documented run did not, and where
      Could not be determined                     nobody knew how to attempt it (the README)
      Out of scope                                the free runner cannot provide something
      Not verified as documented                  the run is of a recipe STRhub wrote
    """
    if instrument_of_report(report) not in BADGE_INSTRUMENTS:
        return NOT_DOCUMENTED, "lightgrey"
    code = (report.get("verdict") or {}).get("code")
    level = report.get("level", "none")
    if code == "undetermined":
        return "Could not be determined", "lightgrey"
    if code == "out_of_scope":
        return "Out of scope", "lightgrey"
    runs = code == "runs" if code else level in ("io", "content")
    if runs:
        if errors_reported(report):
            return "Runs as documented (errors reported)", "yellow"
        return "Runs as documented", ("brightgreen" if level == "content" else "green")
    return f"Does not run as documented: {STOPS_AT.get(level, 'stops at ' + level)}", "red"


def instrument_of(m: dict) -> str:
    """`documented` | `maintainer` | `curated`, from the manifest's recipe.origin;
    for a manifest from before that field, derived: proposed if detect_recipe
    wrote its notes, the maintainer's if the submission says so, curated
    otherwise — which is every recipe STRhub wrote to fill the catalogue."""
    origin = (m.get("recipe") or {}).get("origin")
    if origin == "proposed":
        return "documented"
    if origin in ("maintainer", "curated"):
        return origin
    if (m.get("caveats") or {}).get("source") == "detect_recipe":
        return "documented"
    if (m.get("submission") or {}).get("by") == "maintainer":
        return "maintainer"
    return "curated"


def instrument_of_report(report: dict) -> str:
    """The same reading for a published report, which carries `instrument`
    since this plan and can only be derived before it."""
    return report.get("instrument") or instrument_of(report)


def workaround_lines(report: dict) -> list[str]:
    """One line per workaround of a curated recipe, for any rendering."""
    out = []
    for w in ((report.get("recipe") or {}).get("workarounds") or []):
        line = f"{w.get('what', '')} — instead of: {w.get('instead_of', '')}"
        if w.get("why"):
            line += f" {w['why']}"
        out.append(line)
    return out


def test_data_item(cfg: dict, ds_name: str) -> tuple[str, str]:
    """What the run used for input, and — only on evidence — whether the
    repository ships any of its own.

    "This tool does not include its own demo or test data" was printed for
    every tool, whatever the repository held. It is false for STRsearch, which
    ships 35 files including example/test_data/test.bam. Absence of test data
    is a finding about somebody's work and needs to be established, not
    assumed: only a run whose recipe was proposed from the repository has read
    the tree, and only that run may say so.
    """
    used = (f"STRhub Verified supplied {ds_name} as the reference input for this "
            "verification run. Users replicating this result should use the same or "
            "equivalent publicly available reference material.")
    td = cfg.get("repo_test_data") or {}
    if not td.get("known"):
        return ("Reference input", used)
    if td.get("present"):
        n = td.get("count") or 0
        return ("Repository test data not used",
                f"The repository ships example data ({n} file(s)), which this run did not "
                f"use: the gates above ran on STRhub's reference dataset. {used}")
    return ("No bundled demo data",
            f"{cfg['tool_name']} ships no test or demo data of its own. {used}")


def conclusion_items_for(cfg: dict) -> list[tuple[str, str]]:
    """The certificate's closing claims, each one derived from a gate.

    This used to be four fixed paragraphs asserting success with the numbers
    interpolated, so a run that stopped at Installs was certified as "installs
    and executes without error ... generated a structurally valid output file",
    with "0 loci" and a read depth of "0 at —" as the only hint that nothing
    had run. A PDF travels on its own, detached from the page and the log; it
    may not say the opposite of the report it renders.
    """
    stats = cfg.get("stats") or {}
    top_loci = stats.get("top_loci_by_depth", [])
    n_loci = stats.get("distinct_str_loci", 0)
    max_depth = stats.get("max_sequence_depth", 0)
    deepest_locus = top_loci[0][0] if top_loci else "—"
    fmt = (cfg.get("declared_format") or "").strip()
    fmt_label = f"{fmt} " if fmt and fmt != "—" else ""
    ds_name = (cfg.get("dataset") or {}).get("name") or "a public reference dataset"
    where = (f"an environment built from {cfg.get('fallback_reason')}, after the build "
             "from the pinned commit failed"
             if cfg.get("fallback_used") else
             "a clean ubuntu-22.04 environment at the pinned commit")
    gates = dict(cfg.get("gates") or {})
    verdict = cfg.get("verdict") or {}

    if gates.get("runs"):
        ran = ("Runs end-to-end",
               f"{cfg['tool_display']} installs and executes without error in {where}.")
    elif gates.get("installs"):
        ran = ("Does not run end-to-end",
               f"{cfg['tool_display']} installs in {where}, but the documented command "
               "stopped with an error before finishing. The messages it printed are in "
               "the execution log; Section 4 shows how far it got.")
    else:
        ran = ("Does not install",
               f"The environment for {cfg['tool_display']} could not be built from the "
               "declared install steps, so nothing further was attempted.")

    if gates.get("content"):
        produced = ("Produces plausible output",
                    f"The tool generated a structurally valid {fmt_label}output file with genotype "
                    f"calls across {n_loci} target forensic STR loci, with a "
                    f"maximum read depth of {max_depth} at {deepest_locus}.")
    elif gates.get("io"):
        produced = ("Produces output in the declared format",
                    f"The tool wrote a non-empty {fmt_label}file. Whether its contents look like "
                    "genotype data was not established at this level.")
    else:
        produced = ("No output produced",
                    "No file in the declared format was written, so nothing could be checked "
                    "for structure or content. This says the run did not get that far; it is "
                    "not a finding about the quality of the software.")

    items = [ran, produced]
    # The one sentence the web leads with, in the certificate too.
    if verdict.get("title") and verdict.get("reason"):
        items.append((f"Verdict: {verdict['title']}", verdict["reason"]))
    items += [
        test_data_item(cfg, ds_name),
        ("Reproducibility statement",
         "The exact command reported in Section 3, executed at the pinned "
         "commit in the described environment, is sufficient to reproduce "
         "this verification result independently."),
    ]
    return items


def install_meaning(fallback_used: bool, faults: list[str]) -> list[tuple[str, str]]:
    """What a failed build means for each reader, in their own terms.

    The report used to say "plan B: the published image ... after the build
    from the pinned commit failed" and stop. That is the mechanism, in the
    engine's words, and nobody who opens a certificate asked about the
    mechanism. Three readers do open it — someone about to run the tool, a
    reviewer holding a manuscript, its maintainer — and each needs one
    sentence in their own terms. The maintainer's is the fault sentence, which
    already says whose side the cause is on; the other two claim only what
    the run established: that a build from source stopped, and (on plan B)
    that the ready-made environment ran.
    """
    if fallback_used:
        run = ("A build from source at this commit fails in a clean environment; the "
               "cause is below. The ready-made environment the README points at does "
               "work: it is what this run used.")
        review = ("This result describes the software inside that environment, whatever "
                  "its publisher last put there, and not the pinned commit, which is the "
                  "version a manuscript would cite.")
    else:
        run = ("A build from source at this commit fails in a clean environment; the "
               "cause and a suggested fix are below.")
        review = ("Nothing ran, so this says nothing about the software's output. It "
                  "records that this attempt to build it stopped, and whose side the "
                  "cause is on.")
    return [("If you are trying to run it", run),
            ("If you are reviewing a paper", review),
            ("If you maintain it", diagnose_log.install_fault_sentence(faults))]
