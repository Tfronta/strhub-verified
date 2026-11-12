"""Exercise the engine's gates (harness/engine, what the workflow runs) with a
fake runner; no STR tool or Docker."""
import hashlib
import json
import os
import pathlib
import pytest
import yaml

import input_provenance
from engine import stages
from engine.executor import Executor
from engine.record import StageResult
from procedure_context import context

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"


def step(step_id):
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return next(s for s in workflow["jobs"]["verify"]["steps"] if s.get("id") == step_id)


PASSED = StageResult(stage="installs", status="passed", exit_code=0)


def ctx_for(tmp_path, manifest, plan_over=None):
    _, contract, _ = context()
    plan = {"ref": "a" * 40, "repo": "https://github.com/example/tool", "manifest": str(manifest),
            "cmd": contract["run"]["cmd"], "timeout": "1", "step_timeout": "4", "external_ready": "1",
            "input_type": contract["inputs"]["type"], "dockerfile_from_repo": "Dockerfile", "install_ready": "1",
            "installation_profile": "", "supported_loci": "", **(plan_over or {})}
    return stages.Ctx(plan=plan, work=pathlib.Path("work"), root=tmp_path, exe=Executor())


@pytest.fixture
def external_trial(tmp_path):
    _, contract, review = context()
    harness = tmp_path / "harness"
    harness.mkdir()
    (harness / "input_provenance.py").symlink_to(ROOT / "harness/input_provenance.py")
    (harness / "run_container.sh").write_text(
        'echo attempt >> attempts.txt\n'
        'printf "original log\\n" > "$3"\n'
        'printf "original output\\n" > work/out_external/result.txt\n'
        'exit "$TEST_EXIT_CODE"\n'
    )
    work = tmp_path / "work"
    input_provenance.stage(ROOT, work, contract["inputs"]["type"])
    (work / "procedure_review.json").write_text(json.dumps(review))
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump(contract))
    return manifest, ctx_for(tmp_path, manifest)


@pytest.mark.parametrize("exit_code", [0, 17, 124, 137])
def test_external_leg_preserves_first_result_without_switching_dataset(tmp_path, external_trial, exit_code, monkeypatch):
    manifest, ctx = external_trial
    before = manifest.read_bytes()
    (tmp_path / "work/in_external_med").mkdir()
    (tmp_path / "work/ref").mkdir()
    monkeypatch.setenv("TEST_EXIT_CODE", str(exit_code))
    result = stages.runs_external(ctx, PASSED)
    assert result.exit_code == exit_code and result.outputs["input_evidence"] == "verified"
    assert (tmp_path / "attempts.txt").read_text() == "attempt\n"
    assert (tmp_path / "work/log_external.txt").read_text() == "original log\n"
    assert (tmp_path / "work/out_external/result.txt").read_text() == "original output\n"
    assert manifest.read_bytes() == before

    receipt = json.loads((tmp_path / "work/mounted_inputs.json").read_text())
    assert receipt["input_type"] == "illumina-bam-hg38" and receipt["assembly"] == "hg38"
    assert [row["mount_path"] for row in receipt["files"]] == ["/data/in/input.bam", "/data/in/input.bam.bai"]
    for row in receipt["files"]:
        mounted = tmp_path / "work/in_external" / pathlib.Path(row["mount_path"]).name
        assert row["sha256"] == hashlib.sha256(mounted.read_bytes()).hexdigest()
    assert "/data/ref" not in " ".join(result.command) and "in_external_med" not in " ".join(result.command)


@pytest.mark.parametrize("tamper", ["extra_catalog", "bam_bytes", "bam_index", "command"])
def test_workflow_stops_before_launch_if_mount_or_command_differs(tmp_path, external_trial, tamper):
    _, ctx = external_trial
    mount = tmp_path / "work/in_external"
    if tamper == "extra_catalog":
        (mount / "regions.json").write_text("extra data")
    elif tamper == "bam_bytes":
        (mount / "input.bam").write_bytes(b"different BAM")
    elif tamper == "bam_index":
        (mount / "input.bam.bai").unlink()
    else:
        ctx.plan["cmd"] += " --new-argument"
    result = stages.runs_external(ctx, PASSED)
    assert result.status == "failed" and result.exit_code == 1
    assert result.outputs["input_evidence"] == "unverified"
    assert "Input provenance could not be established" in result.outputs["provenance"]
    assert not (tmp_path / "attempts.txt").exists()
    assert not (tmp_path / "work/mounted_inputs.json").exists()


def test_workflow_dispatch_only_accepts_upstream_identity_for_procedure():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert {"repo", "ref"} <= inputs.keys()
    assert not {"recipe", "cmd", "dockerfile", "fixture", "regions"} & inputs.keys()


def test_generated_install_is_refused_before_docker_without_trying_an_alternative(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text('#!/bin/sh\necho "$*" >> builds.txt\nexit 23\n')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    (tmp_path / "work").mkdir()
    ctx = ctx_for(tmp_path, tmp_path / "manifest.yml",
                  {"dockerdir": ".", "dockerfile": "Dockerfile", "dockerfile_from_repo": "", "installation_profile": ""})
    result = stages.installs(ctx, StageResult(stage="available", status="passed", exit_code=0))
    assert result.status == "failed"
    assert not (tmp_path / "builds.txt").exists()
    assert result.outputs["source_evidence"] == "unverified"


def test_no_workflow_can_launch_the_retired_agent():
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "assist.yml").exists()
    for path in workflows.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow.get("jobs", {}).values():
            for item in job.get("steps", []):
                assert "harness/assist.py" not in item.get("run", ""), path
