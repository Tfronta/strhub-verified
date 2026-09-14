"""One of four verdicts, for a reader who does not program.

The gate ladder is exact and stays; this is the sentence on top of it that a
paper reviewer, or somebody who could not get the tool running at home, can
act on without reading a log:

  runs           it installed and produced its documented output
  fails          it did not, and the evidence says the tool (or its recipe)
                 is what failed
  undetermined   STRhub could not work out how to run it, and says what the
                 README did not tell it; a finding about documentation
  out_of_scope   it needs something the free runner cannot give (GPU, a
                 display, a licence, network at run time, another OS)

The order of the checks IS the policy. A tool that produced its output is
"runs" whatever else the log grumbled about; anything the runner structurally
cannot do beats a failure it caused; a recipe that was proposed from the
repository and could not be completed is the documentation's finding, not the
tool's; only then is a failure attributed to the tool.

Pure function, no I/O, so the policy is testable line by line.
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import diagnose_log  # noqa: E402

TITLES = {
    "runs": "Runs",
    "fails": "Fails",
    "undetermined": "Could not be determined",
    "out_of_scope": "Out of scope for automated verification",
}


def _ids(diagnostics: dict[str, list[dict]] | None) -> set[str]:
    return {i.get("id") for issues in (diagnostics or {}).values() for i in issues}


def decide(gates: dict, diagnostics: dict[str, list[dict]] | None = None,
           manual_verification: dict | None = None, recipe_proposal: dict | None = None,
           declared_compatibility: dict | None = None) -> dict:
    """Return {code, title, reason, readme_gaps, basis}."""
    gates = gates or {}
    mv = manual_verification or {}
    proposal = recipe_proposal or {}
    gaps = [g for g in (proposal.get("readme") or {}).get("gaps", []) if g.get("item") != "example_data"]
    ids = _ids(diagnostics)
    produced = bool(gates.get("io")) or bool(gates.get("example"))

    if produced:
        return {"code": "runs", "title": TITLES["runs"], "basis": "gates",
                "reason": "The tool installed and its run produced its documented output.",
                "readme_gaps": []}

    declared = {k for k, v in (declared_compatibility or {}).items() if v}
    incompatible = ids & diagnose_log.HARNESS_INCOMPATIBLE
    if declared or incompatible or mv.get("reason_code") in diagnose_log.HARNESS_INCOMPATIBLE:
        what = sorted(declared | incompatible | ({mv["reason_code"]} if mv.get("reason_code") in diagnose_log.HARNESS_INCOMPATIBLE else set()))
        return {"code": "out_of_scope", "title": TITLES["out_of_scope"], "basis": "environment",
                "reason": "The tool needs something the automated runner cannot provide: "
                          + ", ".join(what) + ". A manual verification can cover it.",
                "readme_gaps": []}

    # A recipe proposed from the repository, incomplete: the run (if any) says
    # nothing about the tool, because nobody knew how to run it.
    auto = proposal.get("schema", "").startswith("strhub-verified/recipe-proposal")
    if auto and not (proposal.get("readme") or {}).get("sufficient_to_attempt", True):
        return {"code": "undetermined", "title": TITLES["undetermined"], "basis": "readme",
                "reason": "STRhub could not work out how to install or run this tool from "
                          "its repository. The README does not say enough for a stranger to "
                          "run it; each missing item is listed below.",
                "readme_gaps": gaps}

    # It was run, and did not produce. If the recipe was auto-proposed and the
    # failure is one an author fixes by naming the right flag or file, the
    # proposal may be what is wrong, not the tool.
    fixable = ids & diagnose_log.AUTHOR_FIXABLE
    if auto and fixable and not gates.get("runs"):
        return {"code": "undetermined", "title": TITLES["undetermined"], "basis": "recipe",
                "reason": "The proposed way of running this tool did not work ("
                          + ", ".join(sorted(fixable)) + "). That may be the proposal rather "
                          "than the tool: a maintainer-supplied command would settle it.",
                "readme_gaps": gaps}

    if not gates.get("available"):
        reason = "The pinned source could not be fetched."
    elif not gates.get("installs"):
        reason = "The environment did not build from the declared install steps."
    elif not gates.get("runs"):
        reason = "The tool exited with an error on the reference data."
    else:
        reason = "The tool ran to completion but produced no output in the documented format."
    return {"code": "fails", "title": TITLES["fails"], "basis": "gates", "reason": reason,
            "readme_gaps": gaps}
