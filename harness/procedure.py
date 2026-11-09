"""Whose failure would this be, before any container is started.

A reviewer handing over a repository link needs the answer before Docker, and
needs it split three ways. A red result that mixes them is the failure mode
this exists to stop:

  tool      the commit states an install a third party can execute (its own
            Dockerfile with a supported, cited build command), STRhub holds
            the input, and the command was not
            rewritten past path substitution. A failure of that run is the
            tool's.
  strhub    STRhub would be supplying the environment, the input, a file, or
            a guess. A failure of that run is ours. It must not be published
            as the tool failing, and a success must not be published as the
            tool running as documented.
  recipe    the commit does not state a procedure, or states one whose input
            STRhub does not hold. Nothing was executed. That is a finding
            about the documentation or about our sample shelf, said as such.

Pure: no network, no Docker. The preview server and the verdict both read it.
"""
from __future__ import annotations

import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare import unwrap_example  # noqa: E402
from prepare import example_wrapper  # noqa: E402
import fidelity  # noqa: E402

# Discovery families are not execution permissions. Only the versioned
# installation profile can establish a citable installation.
CITABLE_INSTALL = {"dockerfile"}
PACKABLE_FROM_REPO = CITABLE_INSTALL | {
    "conda", "pip", "cmake", "make", "autotools", "cargo", "go", "r", "nim", "script", "release_binary",
}
PUBLISHED_INSTALL = {"docker_image", "bioconda"}


def _flags(cmd: str) -> set[str]:
    return set(re.findall(r"(?:^|\s)(--[\w-]+|-\w)\b", cmd))


def _tool_text(cmd: str) -> str:
    """No shell prefix is automatically excused as harness plumbing."""
    return cmd


def _command_amendments(cited: str, rewritten: str, expected: str | None = None) -> list[dict]:
    """Compare the complete text after the closed, recorded substitutions.

    Even apparently harmless whitespace changes are not inferred equivalent:
    adjacency, quoted spaces, newlines and redirection descriptors matter.
    """
    out = []
    if not cited:
        return [{"code": "command_evidence_missing", "what": "No complete upstream command was established."}]
    if "[" in cited and "[" not in rewritten:
        out.append({"code": "synopsis_trimmed", "what": "A usage synopsis was changed instead of executed as documented."})
    baseline = expected if expected is not None else cited
    extra, missing = _flags(rewritten) - _flags(baseline), _flags(baseline) - _flags(rewritten)
    if extra:
        out.append({"code": "flag_injected", "what": "Flags added: " + ", ".join(sorted(extra))})
    if missing:
        out.append({"code": "flag_dropped", "what": "Flags removed: " + ", ".join(sorted(missing))})
    same = rewritten == baseline
    if not same:
        out.append({"code": "command_changed", "what": "The complete executed command differs from the cited command beyond the closed substitution table; executable, values, positional arguments, quoting, order and shell operators are all significant."})
    return out


def classify(proposal: dict, manifest: dict, limitations: list[str],
             caveat_items: list[str] | None = None) -> dict:
    """The review of one proposal. `may_say_runs` is the only bit the verdict
    needs: when it is false, a green gate ladder still cannot say the tool
    runs as documented."""
    proposal = proposal or {}
    manifest = manifest or {}
    limitations = list(limitations or [])
    notes = list(caveat_items or [])
    build = proposal.get("build") or {}
    method = build.get("method") or "unknown"
    source = (manifest.get("environment") or {}).get("source")
    citable = method in CITABLE_INSTALL and (method != "dockerfile" or source == "repository")
    published = method in PUBLISHED_INSTALL

    cited = ""
    commands = proposal.get("commands") or []
    if commands:
        cited = commands[0].get("cmd") or ""
    rewritten, _cwd = unwrap_example((manifest.get("run") or {}).get("cmd") or "")
    transformation = fidelity.rewrite(cited, (manifest.get("inputs") or {}).get("type"))
    expected = transformation["command"]
    citations = [fidelity.cite(proposal, commands[0])] if commands else []
    if commands and commands[0].get("prerequisite"):
        prerequisite = commands[0]["prerequisite"]
        pre_review = fidelity.rewrite(prerequisite["cmd"], (manifest.get("inputs") or {}).get("type"))
        citations.append(fidelity.cite(proposal, prerequisite))
        transformation["limitations"] += pre_review["limitations"]
        transformation["prerequisite"] = pre_review
    amendments = _command_amendments(cited, rewritten, expected)
    if commands and commands[0].get("prerequisite"):
        amendments.append({"code": "prerequisite_profile_unsupported", "what": "A preceding command inferred from a shared filename is not proof of the documented execution sequence; it is not automatically chained."})
    raw_cmd = (manifest.get("run") or {}).get("cmd") or ""
    if _cwd is None:
        amendments.append({"code": "capture_wrapper_missing", "what": "This profile requires the exact evaluator capture wrapper so output routing is established before execution."})
    if _cwd is not None and raw_cmd != example_wrapper(rewritten, _cwd):
        amendments.append({"code": "capture_wrapper_changed", "what": "The capture wrapper differs from the evaluator's exact wrapper; no prefix or suffix may hide a procedure change."})
    if _cwd is not None and _cwd != ".":
        amendments.append({"code": "working_directory_changed", "what": "The command was moved from the upstream image's working directory; this profile does not establish that change."})
    identity = ((manifest.get("source") or {}).get("ref") == proposal.get("ref")
                and str((manifest.get("source") or {}).get("repo", "")).removesuffix(".git").rstrip("/")
                == str(proposal.get("repo") or "").removesuffix(".git").rstrip("/"))
    if not identity or not citations or not all(c["verified"] for c in citations):
        amendments.append({"code": "command_evidence_missing", "what": "The complete command and prerequisite must be established at the cited lines of this same pinned upstream commit; wiki text or a recipe label is not proof."})
    if transformation["limitations"]:
        amendments.append({"code": "command_profile_unsupported", "what": "; ".join(transformation["limitations"])})
    if (manifest.get("inputs") or {}).get("type") and not transformation["read_bindings"]:
        amendments.append({"code": "input_not_substituted", "what": "This evaluator cannot establish that the cited command reads the declared reference input; no config or input list was rewritten to make it do so."})
    regions = (manifest.get("inputs") or {}).get("regions") or {}
    if isinstance(regions, dict) and regions.get("library"):
        amendments.append({"code": "regions_profile_unsupported", "what": "A tool-name lookup or generated region layout is not upstream procedure evidence; this profile does not establish that input conversion."})
    installation = fidelity.installation(proposal, manifest)
    citable = installation["ready"]
    if installation["ready"] and not fidelity.image_invocation_supported(proposal):
        amendments.append({"code": "image_invocation_unsupported", "what": "The upstream image does not declare the shell entrypoint this evaluator needs; ENTRYPOINT is not overridden or repaired."})
    if not installation["ready"]:
        amendments.append({"code": "install_profile_unsupported", "what": installation["reason"]})

    if any("holds no reference sample as" in n or "other documented kind was used" in n for n in notes):
        amendments.append({"code": "input_swapped",
                           "what": "The input kind this run would use is not the one the documentation "
                                   "names first: STRhub substituted a kind it holds a sample of."})
    if "input_type_guessed" in limitations:
        amendments.append({"code": "input_guessed",
                           "what": "No sentence states what the tool reads, so the sample was chosen "
                                   "from mentions alone."})
    tool_cmd = _tool_text(rewritten)
    if any("could not resolve" in n for n in notes):
        amendments.append({"code": "synopsis_trimmed",
                           "what": "The command contains placeholders that neither the repository nor "
                                   "STRhub's substitution table can fill in."})
    has_shipped_example = bool((manifest.get("example") or {}).get("cmd") or (proposal.get("example") or {}).get("cmd"))
    # A data file that is still the path from the README was not pointed at
    # STRhub's sample, and if the repository does not ship those files either,
    # running that command would fail with "file not found" of our staging.
    if cited and not has_shipped_example \
            and re.search(r"\.(?:bam|cram|sam|fastq|fq|fasta|fa|bed|vcf)(?:\.gz)?\b|\b(?:bam|fastq|read|sample)[_-]?list\b", tool_cmd, re.I) \
            and "/data/in" not in tool_cmd and "/data/ref" not in tool_cmd:
        amendments.append({"code": "input_not_substituted",
                           "what": "The command still names the repository's own file paths, not STRhub's "
                                   "sample. Running it would not be the reference-sample test."})
    if any("HTTPS instead" in n for n in notes):
        amendments.append({"code": "ssh_rewritten",
                           "what": "A build step fetches dependencies over SSH; STRhub would rewrite that "
                                   "to HTTPS, which is a change to the procedure."})
    if "regions_format_guessed" in limitations or "regions_format_unknown" in limitations:
        amendments.append({"code": "regions_guessed",
                           "what": "The regions file would be one STRhub guessed a layout for, not one "
                                   "the commit states."})
    glob = ((manifest.get("outputs") or [{}])[0].get("path"))
    if glob in ("**/*", "**/*.*"):
        amendments.append({"code": "output_unnamed",
                           "what": "The documentation does not name an output file, so any file the "
                                   "wrapper copied would have been counted as the documented output."})
    if proposal and method not in PACKABLE_FROM_REPO and method not in PUBLISHED_INSTALL:
        amendments.append({"code": "no_install_procedure",
                           "what": "This commit does not state an install procedure a third party can execute."})
    if published and not citable:
        amendments.append({"code": "published_image",
                           "what": "The install named here is a published image or package. That is a claim "
                                   "about the image, not about this commit, and it was not counted as the commit running."})

    # One lead, in the order a reviewer should read it. The first match is
    # why we will not call a red result the tool's.
    if not proposal:
        blocker, basis = "procedure_evidence_missing", "strhub"
    elif "no_reference_dataset" in limitations:
        blocker, basis = "missing_input", "recipe"
    elif not installation["ready"] and method != "unknown":
        blocker, basis = "install_profile_unsupported", "strhub"
    elif "documented_file_missing" in limitations:
        blocker, basis = "missing_file", "recipe"
    elif any(a["code"] == "input_not_substituted" for a in amendments):
        blocker, basis = "input_not_substituted", "strhub"
    elif "loci_outside_panel" in limitations:
        blocker, basis = "loci_outside_panel", "recipe"
    elif "no_command" in limitations:
        blocker, basis = "no_command", "recipe"
    elif any(a["code"] == "no_install_procedure" for a in amendments):
        blocker, basis = "no_install_procedure", "recipe"
    elif any(a["code"] == "published_image" for a in amendments):
        blocker, basis = "published_image", "strhub"
    elif amendments:
        blocker, basis = amendments[0]["code"], "strhub"
    else:
        blocker, basis = "ready", "gates"

    may_say_runs = blocker == "ready"
    if may_say_runs:
        reason = ("The repository states how to install (" + method + ") and STRhub holds the sample. "
                  "The container is that install, packaged. If the documented command then fails, "
                  "the failure is that command's.")
        attribution = "tool"
    elif basis == "recipe":
        reason = next((a["what"] for a in amendments if a["code"] == blocker), "")
        if not reason:
            reason = {
                "missing_input": "STRhub holds no reference sample of the kind this procedure reads, "
                                 "and the repository ships no example to run, so nothing was executed.",
                "missing_file": "The documented command reads a file that neither the repository nor "
                                "STRhub holds, so the command was not run.",
                "loci_outside_panel": "The loci the documented command genotypes are not in STRhub's "
                                      "reference sample, so the run was not taken as a result about the tool.",
                "no_command": "No command line invoking the tool was found in the commit, so nothing was run.",
            }.get(blocker, "STRhub could not complete a procedure stated at this commit.")
        attribution = "strhub"
    else:
        reason = " ".join(a["what"] for a in amendments)
        attribution = "strhub"

    return {
        "may_say_runs": may_say_runs,
        "basis": basis,
        "attribution": attribution,
        "blocker": blocker,
        "reason": reason,
        "amendments": amendments,
        "install_method": method,
        "citable_install": citable,
        "input_type": (manifest.get("inputs") or {}).get("type"),
        "output_glob": glob,
        "profile": fidelity.PROFILE,
        "install_ready": installation["ready"],
        "installation": installation,
        "command_review": {**transformation, "expected": expected, "executed": rewritten,
                           "cited_sha256": fidelity.digest(cited),
                           "executed_sha256": fidelity.digest(rewritten), "citations": citations},
    }
