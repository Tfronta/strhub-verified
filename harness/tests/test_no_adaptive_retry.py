"""Exercise the actual workflow shell with a fake runner; no STR tool or Docker."""
import os
import pathlib
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"


def step(step_id):
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return next(s for s in workflow["jobs"]["verify"]["steps"] if s.get("id") == step_id)


@pytest.mark.parametrize("exit_code", [0, 17, 124, 137])
def test_external_leg_preserves_first_result_without_switching_dataset(tmp_path, exit_code):
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "run_container.sh").write_text(
        'echo attempt >> attempts.txt\n'
        'printf "original log\\n" > "$3"\n'
        'printf "original output\\n" > work/out_external/result.txt\n'
        'exit "$TEST_EXIT_CODE"\n'
    )
    # Even if an old workspace has an alternative dataset, failure must not
    # select it or rewrite the manifest. Exit 0 with invalid output is included.
    (tmp_path / "work" / "in_external_med").mkdir(parents=True)
    manifest = tmp_path / "manifest.yml"
    manifest.write_text("original manifest\n")
    before = manifest.read_bytes()
    env = {**os.environ, "TEST_EXIT_CODE": str(exit_code),
           "DOCKER_HARDENING": "", "ENTRY": "", "ENTRY_ARGS": "",
           "TOOL_CMD": "not executed by this test", "RUN_MINUTES": "1",
           "MANIFEST": str(manifest), "MED_FALLBACK_READY": "1",
           "MED_INPUT_TYPE": "illumina-bam-hg38-med"}
    result = subprocess.run(["bash", "-e", "-c", step("runs_ext")["run"]],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == exit_code, result.stderr
    assert (tmp_path / "attempts.txt").read_text() == "attempt\n"
    assert (tmp_path / "work" / "log_external.txt").read_text() == "original log\n"
    assert (tmp_path / "work" / "out_external" / "result.txt").read_text() == "original output\n"
    assert manifest.read_bytes() == before


def test_failed_install_never_builds_a_second_environment(tmp_path):
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
    builds = (tmp_path / "builds.txt").read_text().splitlines()
    assert len(builds) == 1 and builds[0].startswith("build ")
    assert not output.exists()


def test_no_workflow_can_launch_the_retired_agent():
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "assist.yml").exists()
    for path in workflows.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow.get("jobs", {}).values():
            for item in job.get("steps", []):
                assert "harness/assist.py" not in item.get("run", ""), path
