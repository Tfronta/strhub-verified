"""What the certificate claims, as text derived from the gates.

Kept apart from the rendering (generate_pdf) on purpose: these sentences are
the report's claims about somebody's software, and they have to be testable
without a PDF toolchain — the CI job that gates every run installs no
renderer. The rendering decides where a sentence sits on the page; this
decides whether it may be said at all.
"""
from __future__ import annotations

import diagnose_log


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
