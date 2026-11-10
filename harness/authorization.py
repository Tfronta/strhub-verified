"""Recompute procedure eligibility; cached decisions and origin labels have no authority.

This is evidence consistency, not a cryptographic signature. The build producer
must still check cited bytes against the real pinned checkout before Docker.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

SCHEMA = "strhub-procedure-evidence/1"


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _copy(value):
    return json.loads(canonical(value))


def prepare_review(proposal: dict, manifest: dict, limitations: list | None = None,
                   caveat_items: list | None = None) -> dict:
    import procedure
    # A proposal's previous decision is not part of its source evidence. This
    # also prevents recursive capsules when a proposal carries its own review.
    evidence = {"schema": SCHEMA, "manifest": _copy(manifest),
                "proposal": _copy({k: v for k, v in proposal.items() if k != "procedure"}),
                "limitations": _copy(limitations or []), "caveat_items": _copy(caveat_items or [])}
    reviewed = procedure.classify(evidence["proposal"], evidence["manifest"],
                                  evidence["limitations"], evidence["caveat_items"])
    return {**reviewed, "manifest_sha256": digest(manifest),
            "evidence_sha256": digest(evidence), "evidence": evidence}


@dataclass(frozen=True)
class Validation:
    valid: bool
    reason: str
    review: dict | None = None


def validate(review, manifest) -> Validation:
    """Require the effective manifest and re-derive the entire decision.

    No flag, digest, schema label, submitter identity or saved success can
    replace the complete evidence or authorize changed effective inputs.
    """
    if not isinstance(review, dict) or not isinstance(manifest, dict):
        return Validation(False, "The effective manifest and complete procedure evidence are required.")
    try:
        import _manifest
        _manifest.validate(manifest)
        evidence = review.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("schema") != SCHEMA:
            return Validation(False, "The versioned procedure evidence is missing or unsupported.")
        if evidence.get("manifest") != manifest or review.get("manifest_sha256") != digest(manifest):
            return Validation(False, "The procedure evidence belongs to a different effective manifest.")
        if (not isinstance(evidence.get("proposal"), dict)
                or not isinstance(evidence.get("limitations"), list)
                or not isinstance(evidence.get("caveat_items"), list)):
            return Validation(False, "The procedure evidence is incomplete or malformed.")
        if review.get("evidence_sha256") != digest(evidence):
            return Validation(False, "The preserved procedure evidence digest does not match.")
        expected = prepare_review(evidence["proposal"], manifest, evidence["limitations"], evidence["caveat_items"])
        if review != expected:
            return Validation(False, "The saved procedure decision differs from its recomputed evidence.")
        return Validation(True, "Procedure evidence matches the effective manifest and recomputed decision.", expected)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        return Validation(False, "The procedure evidence could not be validated: " + type(exc).__name__)
    except Exception as exc:
        # Schema validation raises its library-specific exception. Treat it as
        # a failure of the evidence, never as permission to use cached flags.
        return Validation(False, "The effective contract could not be validated: " + type(exc).__name__)


def rejection(reason: str) -> dict:
    return {"may_say_runs": False, "install_ready": False, "basis": "strhub", "attribution": "strhub",
            "blocker": "procedure_evidence_invalid", "reason": reason}


def binding_validation(report: dict, manifest: dict) -> Validation:
    """Compare the reported execution contract without trusting its final label."""
    if not isinstance(report, dict):
        return Validation(False, "A structured report is required.")
    from prepare import unwrap_example
    if report.get("tool") != manifest["tool"]:
        return Validation(False, "The report tool identity does not match its effective manifest.")
    from certificate_text import instrument_of
    if report.get("instrument") != instrument_of(manifest):
        return Validation(False, "The report instrument does not match its effective manifest.")
    source = report.get("source") or {}
    if not isinstance(source, dict) or not isinstance(source.get("repo"), str):
        return Validation(False, "The report source is malformed.")
    actual = manifest["source"]
    # Normalize only GitHub's equivalent URL spellings, not refs or commands.
    from publish_gate import normalize_repo
    if (normalize_repo(source.get("repo", "")) != normalize_repo(actual["repo"])
            or source.get("ref") != actual["ref"]
            or source.get("ref_resolved") != actual["ref"]):
        return Validation(False, "The report source does not match its effective manifest.")
    if not isinstance(report.get("environment"), dict):
        return Validation(False, "The report environment is malformed.")
    environment = dict(report["environment"])
    environment.pop("fallback_used", None)
    if environment != manifest["environment"]:
        return Validation(False, "The report environment does not match its effective manifest.")
    command, cwd = unwrap_example(manifest["run"]["cmd"])
    run = report.get("run") or {}
    if not isinstance(run, dict):
        return Validation(False, "The report command is malformed.")
    if (run.get("cmd") != command or run.get("effective_cmd") != manifest["run"]["cmd"]
            or run.get("cwd") != cwd):
        return Validation(False, "The report command does not match its effective manifest.")
    if report.get("input_contract") != manifest.get("inputs", {}):
        return Validation(False, "The report inputs do not match its effective manifest.")
    gates = report.get("gates")
    if not isinstance(gates, dict) or any(type(gates.get(k)) is not bool for k in ("available", "installs", "runs", "io", "content")):
        return Validation(False, "The report gate observations are missing or malformed.")
    return Validation(True, "The report execution contract matches its manifest.")


def report_validation(report: dict) -> Validation:
    """Check the preserved evidence, actual report contract and derived verdict."""
    if not isinstance(report, dict):
        return Validation(False, "A structured report is required.")
    review = report.get("procedure_review")
    evidence = review.get("evidence") if isinstance(review, dict) else None
    manifest = evidence.get("manifest") if isinstance(evidence, dict) else None
    result = validate(review, manifest)
    if not result.valid:
        return result
    binding = binding_validation(report, manifest)
    if not binding.valid:
        return binding
    gates = report["gates"]
    diagnostics = report.get("diagnostics")
    if diagnostics is not None and (not isinstance(diagnostics, dict)
            or any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                   for rows in diagnostics.values())):
        return Validation(False, "The report diagnostics are malformed.")
    if report.get("manual_verification") is not None and not isinstance(report["manual_verification"], dict):
        return Validation(False, "The report manual-verification metadata is malformed.")
    # A final label is not a second authorization channel. Recompute it too.
    import verdict
    expected = verdict.decide(gates, report.get("diagnostics"), report.get("manual_verification"),
                              declared_compatibility=manifest.get("compatibility"),
                              fallback_used=bool((report.get("environment") or {}).get("fallback_used")),
                              procedure=result.review, manifest=manifest)
    supplied = report.get("verdict") or {}
    if not isinstance(supplied, dict):
        return Validation(False, "The report verdict is malformed.")
    if any(supplied.get(key) != expected.get(key) for key in ("code", "basis")):
        return Validation(False, "The report verdict differs from its evidence and gate observations.")
    return result
