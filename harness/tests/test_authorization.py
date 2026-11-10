"""Missing proof and saved success cannot authorize an execution or a publication."""
import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

import authorization
import fidelity
import local_trial
import publish_gate
import publish_layout
import verdict
from procedure_context import context, report as bound_report

ROOT = Path(__file__).resolve().parents[2]
GREEN = dict.fromkeys(("available", "installs", "runs", "io", "content"), True)
RED = dict.fromkeys(GREEN, False)


def test_complete_review_is_recomputed_without_mutating_its_evidence():
    _, manifest, reviewed = context()
    before = copy.deepcopy(reviewed)
    checked = authorization.validate(reviewed, manifest)
    assert checked.valid and checked.review == reviewed
    assert checked.review is not reviewed
    assert reviewed == before
    assert verdict.decide(GREEN, procedure=reviewed, manifest=manifest)["code"] == "runs"


@pytest.mark.parametrize("reviewed", [None, {}, True, [], {"may_say_runs": True},
    {"profile": fidelity.PROFILE, "may_say_runs": True, "install_ready": True},
    {"may_say_runs": True, "submission": {"by": "maintainer"}, "recipe": {"origin": "proposed"}}])
@pytest.mark.parametrize("gates", [GREEN, RED])
def test_absent_or_legacy_decision_cannot_claim_success_or_tool_failure(reviewed, gates):
    _, manifest, _ = context()
    for decide in (verdict.decide, verdict._decide):
        result = decide(gates, procedure=reviewed, manifest=manifest)
        assert result["code"] == "undetermined" and result["basis"] == "strhub"


def test_a_full_review_without_the_effective_manifest_is_not_an_authorization():
    _, _, reviewed = context()
    assert verdict.decide(GREEN, procedure=reviewed)["code"] == "undetermined"


@pytest.mark.parametrize("field", ["command", "input", "environment", "source", "output"])
def test_effective_contract_changes_are_not_covered_by_the_old_review(field):
    _, manifest, reviewed = context()
    if field == "command":
        manifest["run"]["cmd"] += "; repair-tool"
    elif field == "input":
        manifest["inputs"]["type"] = "ont-bam-hg38"
    elif field == "environment":
        manifest["environment"]["source"] = "submitted"
    elif field == "source":
        manifest["source"]["ref"] = "b" * 40
    else:
        manifest["outputs"][0]["path"] = "another.vcf"
    assert not authorization.validate(reviewed, manifest).valid
    # Editing just the advertised manifest hash is still not evidence.
    reviewed["manifest_sha256"] = authorization.digest(manifest)
    assert not authorization.validate(reviewed, manifest).valid
    assert verdict.decide(GREEN, procedure=reviewed, manifest=manifest)["code"] == "undetermined"


@pytest.mark.parametrize("tamper", ["ready", "documents", "command", "profile", "capsule"])
def test_even_rehashed_evidence_must_reproduce_the_saved_decision(tamper):
    _, manifest, reviewed = context()
    if tamper == "ready":
        reviewed["may_say_runs"] = False
    elif tamper == "documents":
        reviewed["evidence"]["proposal"]["source_documents"] = []
    elif tamper == "command":
        manifest["run"]["cmd"] += "; repair-tool"
        reviewed["evidence"]["manifest"] = copy.deepcopy(manifest)
        reviewed["manifest_sha256"] = authorization.digest(manifest)
    elif tamper == "profile":
        reviewed["profile"] = "unknown-profile"
    else:
        reviewed["evidence"]["override"] = True
    reviewed["evidence_sha256"] = authorization.digest(reviewed["evidence"])
    assert not authorization.validate(reviewed, manifest).valid


def test_cached_proposal_success_has_no_role_in_the_new_review():
    p, manifest, reviewed = context()
    p["procedure"] = {"may_say_runs": True, "install_ready": True}
    assert authorization.prepare_review(p, manifest) == reviewed
    p["source_documents"] = []
    rejected = authorization.prepare_review(p, manifest)
    assert authorization.validate(rejected, manifest).valid
    assert not rejected["may_say_runs"]
    assert verdict.decide(GREEN, procedure=rejected, manifest=manifest)["code"] == "undetermined"


@pytest.mark.parametrize("identity", ["maintainer", "third_party"])
def test_submitter_identity_does_not_authorize_missing_source_evidence(identity):
    p, manifest, _ = context(manifest_fields={"submission": {"by": identity}})
    p["source_documents"] = []
    reviewed = authorization.prepare_review(p, manifest)
    assert not reviewed["may_say_runs"]
    assert verdict.decide(GREEN, procedure=reviewed, manifest=manifest)["code"] == "undetermined"


def test_legacy_review_is_refused_before_git_or_docker(tmp_path, monkeypatch):
    _, manifest, _ = context()
    monkeypatch.setattr(local_trial.subprocess, "run", lambda *a, **k: pytest.fail("no process may start"))
    with pytest.raises(ValueError, match="no proven"):
        local_trial.upstream_build_command(manifest, {"may_say_runs": True, "installation": {"ready": True}}, tmp_path / "source", "trial")
    with pytest.raises(ValueError, match="no proven"):
        fidelity.verify_checkout(tmp_path, {"may_say_runs": True, "installation": {"ready": True}}, manifest)


@pytest.mark.parametrize("mode", ["missing", "cached_only", "malformed", "forged", "different_ref", "valid"])
def test_standalone_report_cannot_bypass_the_mandatory_review(tmp_path, mode, monkeypatch, capsys):
    p, manifest, reviewed = context(manifest_fields={"recipe": {"origin": "proposed"}})
    manifest_path = tmp_path / "manifest.yml"
    manifest_path.write_text(yaml.safe_dump(manifest))
    (tmp_path / "io.json").write_text('{"passed": true}')
    (tmp_path / "content.json").write_text('{"passed": true}')
    review_path = tmp_path / "review.json"
    if mode == "forged":
        reviewed["command_review"]["executed"] += "; repair-tool"
    review_path.write_text("not JSON" if mode == "malformed" else json.dumps(reviewed))
    p["procedure"] = reviewed
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(p))
    args = [str(ROOT / "harness/report.py"), "--manifest", str(manifest_path),
            "--available", "pass", "--installs", "pass", "--runs", "pass",
            "--io", str(tmp_path / "io.json"), "--content", str(tmp_path / "content.json"), "--mode", "trial"]
    if mode not in ("missing", "cached_only"):
        args += ["--procedure-review", str(review_path)]
    if mode == "cached_only":
        args += ["--recipe-proposal", str(proposal_path)]
    if mode == "different_ref":
        args += ["--ref", "b" * 40]
    import report as report_module
    monkeypatch.setattr(report_module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", args)
    assert report_module.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["gates"] == GREEN  # preserve the supplied observations
    assert report["verdict"]["code"] == ("runs" if mode == "valid" else "undetermined")
    assert report["procedure_validation"]["valid"] is (mode == "valid")


@pytest.mark.parametrize("field", ["evidence", "source", "command", "input", "environment", "tool", "instrument", "verdict", "gates"])
def test_publication_cannot_trust_the_final_label_or_reuse_another_contract(field, tmp_path):
    report = bound_report()
    if field == "evidence":
        report.pop("procedure_review")
    elif field == "source":
        report["source"]["ref_resolved"] = "b" * 40
    elif field == "command":
        report["run"]["effective_cmd"] += "; repair-tool"
    elif field == "input":
        report["input_contract"]["type"] = "ont-bam-hg38"
    elif field == "environment":
        report["environment"]["source"] = "submitted"
    elif field == "tool":
        report["tool"]["name"] = "Another tool"
    elif field == "instrument":
        report["instrument"] = "maintainer"
    elif field == "verdict":
        report["verdict"]["code"] = "fails"
    else:
        report["gates"]["runs"] = False
    ok, _ = publish_gate.decide(report, mode="publish", url_trial=False, trial_publish=True,
                                event_name="workflow_dispatch", index=None)
    assert not ok
    site, reports = tmp_path / "site", tmp_path / "reports"
    site.mkdir(); reports.mkdir()
    sentinel = site / "existing.json"
    sentinel.write_text("original historical record\n")
    (reports / "example.json").write_text(json.dumps(report))
    with pytest.raises(SystemExit, match="mandatory procedure evidence"):
        publish_layout.place(site, reports, "example")
    assert [(p.name, p.read_bytes()) for p in site.iterdir()] == [(sentinel.name, b"original historical record\n")]


def test_valid_private_trial_stays_private_and_a_valid_publication_remains_possible():
    report = bound_report()
    args = dict(mode="trial", url_trial=True, trial_publish=False, event_name="workflow_dispatch", index={"tools": []})
    assert not publish_gate.decide(report, **args)[0]
    args["trial_publish"] = True
    assert publish_gate.decide(report, **args)[0]


@pytest.mark.parametrize("field,value", [("source", []), ("environment", []), ("run", 17),
    ("gates", []), ("diagnostics", ["not a diagnostic map"]), ("verdict", "runs")])
def test_malformed_report_shapes_are_rejected_without_using_a_cached_label(field, value):
    report = bound_report()
    report[field] = value
    assert not authorization.report_validation(report).valid


def test_evaluator_limits_are_not_publishable_through_the_layout_writer(tmp_path):
    p, manifest, _ = context(manifest_fields={"recipe": {"origin": "proposed"}})
    p["source_documents"] = []
    reviewed = authorization.prepare_review(p, manifest)
    report = bound_report()
    report["procedure_review"] = reviewed
    report["verdict"] = verdict.decide(GREEN, procedure=reviewed, manifest=manifest)
    assert report["verdict"]["basis"] == "strhub"
    assert authorization.report_validation(report).valid
    assert not publish_gate.validated_finding(report).valid
    site, reports = tmp_path / "site", tmp_path / "reports"
    site.mkdir(); reports.mkdir()
    (reports / "example.json").write_text(json.dumps(report))
    with pytest.raises(SystemExit, match="mandatory procedure evidence"):
        publish_layout.place(site, reports, "example")
    assert not list(site.iterdir())


def test_historical_success_cannot_displace_a_bound_alias(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    old = bound_report(ref="a" * 40)
    old["source"]["committed"] = "2020-01-01T00:00:00Z"
    historic = copy.deepcopy(old)
    historic.pop("procedure_review")
    historic["source"].update(ref="b" * 40, ref_resolved="b" * 40, committed="2030-01-01T00:00:00Z")
    historic_bytes = (json.dumps(historic) + "\n").encode()
    for ref, data in [("a" * 40, json.dumps(old).encode()), ("b" * 40, historic_bytes)]:
        folder = site / "example" / ref
        folder.mkdir(parents=True)
        (folder / "example.json").write_bytes(data)
    assert publish_layout.alias_source(site, "example")[0] == "a" * 40
    publish_layout.write_alias(site, "example")
    assert (site / "example" / ("b" * 40) / "example.json").read_bytes() == historic_bytes
    assert json.loads((site / "example.json").read_text())["source"]["ref_resolved"] == "a" * 40
