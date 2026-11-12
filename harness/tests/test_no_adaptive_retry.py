"""Exercise the actual workflow shell with a fake runner; no STR tool or Docker."""
import hashlib
import json
import os
import pathlib
import subprocess

import pytest
import yaml

import input_provenance
from procedure_context import context

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"


def step(step_id):
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return next(s for s in workflow["jobs"]["verify"]["steps"] if s.get("id") == step_id)


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
    return manifest, {**os.environ, "DOCKER_HARDENING": "", "ENTRY": "", "ENTRY_ARGS": "",
                      "TOOL_CMD": contract["run"]["cmd"], "RUN_MINUTES": "1",
                      "MANIFEST": str(manifest), "GITHUB_OUTPUT": str(tmp_path / "step-output")}


@pytest.mark.parametrize("exit_code", [0, 17, 124, 137])
def test_external_leg_preserves_first_result_without_switching_dataset(tmp_path, external_trial, exit_code):
    manifest, env = external_trial
    before = manifest.read_bytes()
    (tmp_path / "work/in_external_med").mkdir()
    (tmp_path / "work/ref").mkdir()
    env.update(TEST_EXIT_CODE=str(exit_code), MED_FALLBACK_READY="1", MED_INPUT_TYPE="illumina-bam-hg38-med")
    result = subprocess.run(["bash", "-e", "-c", step("runs_ext")["run"]],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == exit_code, result.stderr
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
    assert "/data/ref" not in step("runs_ext")["run"]


@pytest.mark.parametrize("tamper", ["extra_catalog", "bam_bytes", "bam_index", "command"])
def test_workflow_stops_before_launch_if_mount_or_command_differs(tmp_path, external_trial, tamper):
    _, env = external_trial
    mount = tmp_path / "work/in_external"
    if tamper == "extra_catalog":
        (mount / "regions.json").write_text("extra data")
    elif tamper == "bam_bytes":
        (mount / "input.bam").write_bytes(b"different BAM")
    elif tamper == "bam_index":
        (mount / "input.bam.bai").unlink()
    else:
        env["TOOL_CMD"] += " --new-argument"
    result = subprocess.run(["bash", "-e", "-c", step("runs_ext")["run"]],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Input provenance could not be established" in result.stderr
    assert not (tmp_path / "attempts.txt").exists()
    assert not (tmp_path / "work/mounted_inputs.json").exists()


def test_workflow_dispatch_only_accepts_upstream_identity_for_procedure():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert {"repo", "ref"} <= inputs.keys()
    assert not {"recipe", "cmd", "dockerfile", "fixture", "regions"} & inputs.keys()


def test_generated_install_is_refused_before_docker_without_trying_an_alternative(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text('#!/bin/sh\necho "$*" >> builds.txt\nexit 23\n')
    docker.chmod(0o755)
    output = tmp_path / "step-output"
    result = subprocess.run(
        ["bash", "-e", "-c", step("installs")["run"]], cwd=tmp_path,
        env={**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
             "TOOL_REF": "a" * 40, "TOOL_REPO": "https://github.com/example/tool",
             "DOCKER_DIR": ".", "DOCKER_FILE": "Dockerfile",
             "DOCKER_FROM_REPO": "", "GITHUB_OUTPUT": str(output)},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert not (tmp_path / "builds.txt").exists()
    assert "source_evidence=unverified" in output.read_text()


def test_no_workflow_can_launch_the_retired_agent():
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "assist.yml").exists()
    for path in workflows.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow.get("jobs", {}).values():
            for item in job.get("steps", []):
                assert "harness/assist.py" not in item.get("run", ""), path
