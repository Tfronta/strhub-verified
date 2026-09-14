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


LIMITATION_TEXT = {
    "regions_format_guessed": "the tool needs a regions file and STRhub does not know its format; "
                              "a plain chrom/start/end/name file was tried",
    "no_command": "no command line invoking the tool was found in the README",
    "install_method_unknown": "no install method was found in the repository",
    "regions_format_unknown": "the tool needs a regions file in its own format, which STRhub "
                              "does not yet generate for it",
}

#: What stopped the run, as something a person can act on. Each blocker names
#: the thing that was missing, what the person looking at the report can do
#: about it right now (`self_fix`: which part of the recipe to supply and retry),
#: and what to ask the tool's owner for (`ask_owner`: the issue to open). The
#: web renders these as two buttons; the codes are the contract.
BLOCKERS = {
    "regions_format_unknown": {
        "what": "The tool needs a regions file (BED) in its own format. STRhub has ready-made files "
                "for the HipSTR, GangSTR and STRsearch layouts and a plain BED; none of them is known "
                "to fit this tool, and the repository ships none for hg38 covering forensic STR loci.",
        "self_fix": "upload_regions",
        "self_fix_text": "Pick one of STRhub's ready-made regions files, or provide the tool's own, and try again.",
        "ask_owner": {
            "title": "Publish a regions file (hg38) for forensic STR loci",
            "body": "STRhub Verified tried to run the tool in a clean environment on a public hg38 "
                    "reference sample, but could not: the tool needs a regions file in its own "
                    "format and the repository does not ship one for hg38 covering forensic STR "
                    "loci (CODIS and the usual expanded panel). Publishing one in the repository "
                    "would let anyone run the documented example and let STRhub verify the tool "
                    "automatically.",
        },
    },
    "no_command": {
        "what": "No command line invoking the tool was found in the README.",
        "self_fix": "edit_command",
        "self_fix_text": "Write the command that runs the tool and try again.",
        "ask_owner": {
            "title": "Document the command that runs the tool",
            "body": "STRhub Verified could not find, in the README, a command line that invokes the "
                    "tool. A one-line example with an input file and the output it writes would let "
                    "a new user run it and let STRhub verify it automatically.",
        },
    },
    "install_method_unknown": {
        "what": "No way to install the tool was found: no Dockerfile, environment file, "
                "requirements, setup script, Makefile or CMake, and no install command in the README.",
        "self_fix": "choose_install",
        "self_fix_text": "Say how the tool is installed and try again.",
        "ask_owner": {
            "title": "Document how to install the tool",
            "body": "STRhub Verified could not work out how to install the tool from the repository: "
                    "no Dockerfile, environment.yml, requirements.txt, setup script, Makefile or "
                    "CMakeLists, and no install command in the README. Any one of those would let a "
                    "stranger build it and let STRhub verify it automatically.",
        },
    },
    "build_failed": {
        "what": "The environment did not build from the install steps found in the repository.",
        "self_fix": "edit_install",
        "self_fix_text": "Adjust the install steps (or provide a Dockerfile) and try again.",
        "ask_owner": {
            "title": "Build fails from a clean checkout",
            "body": "STRhub Verified tried to build the tool from a clean checkout at the pinned "
                    "commit, following the repository's own install steps, and the build failed. "
                    "The build log is linked from the run.",
        },
    },
    "run_failed": {
        "what": "The tool was installed but exited with an error when run.",
        "self_fix": "edit_command",
        "self_fix_text": "Adjust the command and try again.",
        "ask_owner": {
            "title": "Documented command fails on a public reference sample",
            "body": "STRhub Verified installed the tool from a clean checkout at the pinned commit "
                    "and ran the command the README documents on a public hg38 reference sample; "
                    "it exited with an error. The log is linked from the run.",
        },
    },
    "no_output": {
        "what": "The tool ran to completion but produced no output file in the documented format.",
        "self_fix": "edit_output",
        "self_fix_text": "Say which file the tool writes and try again.",
        "ask_owner": {
            "title": "Document the output the tool writes",
            "body": "STRhub Verified ran the tool to completion in a clean environment, but no output "
                    "file in the documented format appeared. Documenting the output file name and "
                    "format would let a user find the result and let STRhub verify it automatically.",
        },
    },
}


def blockers_for(gates: dict, limits: list[str], gaps: list[dict], ids: set[str]) -> list[dict]:
    """The blockers that apply, most actionable first, at most three."""
    out: list[str] = []
    for l in limits:
        if l == "regions_format_guessed" and not gates.get("io"):
            out.append("regions_format_unknown")
        elif l in BLOCKERS:
            out.append(l)
    gap_items = {g.get("item") for g in gaps}
    if "install" in gap_items and "install_method_unknown" not in out:
        out.append("install_method_unknown")
    if "command" in gap_items and "no_command" not in out:
        out.append("no_command")
    if gates.get("available") and not gates.get("installs") and "install_method_unknown" not in out:
        out.append("build_failed")
    elif gates.get("installs") and not gates.get("runs") and "no_command" not in out \
            and "regions_format_unknown" not in out:
        out.append("run_failed")
    elif gates.get("runs") and not gates.get("io"):
        out.append("no_output")
    seen: list[str] = []
    for code in out:
        if code not in seen:
            seen.append(code)
    return [{"code": c, **BLOCKERS[c]} for c in seen[:3]]


def _ids(diagnostics: dict[str, list[dict]] | None) -> set[str]:
    return {i.get("id") for issues in (diagnostics or {}).values() for i in issues}


def _decide(gates: dict, diagnostics: dict[str, list[dict]] | None = None,
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

    # A proposed recipe that knew it was incomplete (no command, no install
    # method, a regions BED in a format STRhub cannot write) did not test the
    # tool; it tested the proposal.
    limits = [l for l in proposal.get("limitations", []) if l in LIMITATION_TEXT]
    # A guessed regions format only counts against the proposal when the run
    # did not get its output: if the plain BED worked, it worked.
    if "regions_format_guessed" in limits and gates.get("io"):
        limits.remove("regions_format_guessed")
    if auto and limits:
        return {"code": "undetermined", "title": TITLES["undetermined"], "basis": "recipe",
                "reason": "STRhub could not complete a way to run this tool: "
                          + "; ".join(LIMITATION_TEXT[l] for l in limits) + ".",
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


def decide(gates: dict, diagnostics: dict[str, list[dict]] | None = None,
           manual_verification: dict | None = None, recipe_proposal: dict | None = None,
           declared_compatibility: dict | None = None) -> dict:
    """The verdict, plus the blockers a reader can act on when it is not 'runs'."""
    v = _decide(gates, diagnostics, manual_verification, recipe_proposal, declared_compatibility)
    if v["code"] in ("runs", "out_of_scope"):
        v["blockers"] = []
        return v
    proposal = recipe_proposal or {}
    limits = [l for l in proposal.get("limitations", []) if l in LIMITATION_TEXT]
    gaps = [g for g in (proposal.get("readme") or {}).get("gaps", []) if g.get("item") != "example_data"]
    v["blockers"] = blockers_for(gates or {}, limits, gaps, _ids(diagnostics))
    return v
