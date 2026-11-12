"""No success or failure can authorize a change to the upstream procedure."""
import copy
import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

import fidelity
import prepare
import procedure
import verdict
import authorization

ROOT = pathlib.Path(__file__).resolve().parents[2]
CITED = 'tool --reads x.bam --threshold 30 --label "two  spaces" --output out.vcf'
DOCKERFILE = 'FROM scratch\nENTRYPOINT ["/bin/bash", "-lc"]\n'


def case():
    doc = f"# Tool\n```sh\ndocker build -t upstream .\n{CITED}\n```\n"
    source = {"repo": "https://github.com/example/tool", "ref": "a" * 40}
    proposal = {**source, "build": {"method": "dockerfile", "file": "Dockerfile"},
        "commands": [{"cmd": CITED, "file": "README.md", "line": 4, "origin": "readme"}],
        "source_documents": [{"file": "README.md", "origin": "readme", "text": doc}],
        "upstream_files": {"Dockerfile": DOCKERFILE}, "tree_paths": ["Dockerfile", "README.md"]}
    manifest = {"tool": {"name": "Tool", "version": "test"}, "source": source,
        "environment": {"source": "repository", "from_repo": "Dockerfile", "dockerfile": "Dockerfile"},
        "inputs": {"type": "illumina-bam-hg38"},
        "run": {"cmd": prepare.example_wrapper(fidelity.rewrite(CITED, "illumina-bam-hg38")["command"], ".")},
        "outputs": [{"path": "out.vcf", "format": "vcf", "min_records": 1}]}
    return proposal, manifest


def review(proposal, manifest):
    return authorization.prepare_review(proposal, manifest, [], [])


def test_full_citation_and_closed_path_substitution_can_establish_a_procedure():
    p, m = case()
    r = review(p, m)
    assert r["may_say_runs"] and r["install_ready"]
    assert r["command_review"]["substitutions"] == [{"token": 2, "original": "x.bam",
        "replacement": "/data/in/input.bam", "role": "read_path", "basis": "declared dataset mount"}]
    assert '"two  spaces"' in r["command_review"]["executed"]
    assert r["installation"]["citation"]["verified"]
    assert verdict.decide(dict.fromkeys(["available", "installs", "runs", "io", "content"], True), procedure=r, manifest=m)["code"] == "runs"


@pytest.mark.parametrize("change", [
    lambda c: c.replace("threshold 30", "threshold 1"),
    lambda c: c.replace("tool ", "other-tool ", 1),
    lambda c: c.replace("--label", "genotype --label"),
    lambda c: c.replace("--threshold 30", "--threshold 30 --threshold 1"),
    lambda c: c.replace("--threshold 30 --label", "--label"),
    lambda c: c.replace('"two  spaces"', '"two spaces"'),
    lambda c: c.replace('"two  spaces"', "two  spaces"),
    lambda c: c + " | other-tool",
    lambda c: c + " || true",
    lambda c: c + " > another.vcf",
    lambda c: "mkdir -p /tmp && " + c,
    lambda c: "MODE=repair " + c,
    lambda c: c.replace(" --threshold", "\n--threshold"),
    lambda c: c.replace('"two  spaces"', '"two  ""spaces"'),
])
def test_complete_command_changes_are_blocked_even_with_green_gates(change):
    p, m = case()
    command, _ = prepare.unwrap_example(m["run"]["cmd"])
    m["run"]["cmd"] = prepare.example_wrapper(change(command), ".")
    r = review(p, m)
    assert not r["may_say_runs"]
    assert any(a["code"] == "command_changed" for a in r["amendments"])
    assert verdict.decide(dict.fromkeys(["available", "installs", "runs", "io", "content"], True), procedure=r, manifest=m)["code"] == "undetermined"


def test_same_flags_with_changed_threshold_reproduces_the_audit_finding():
    r = procedure._command_amendments("tool --threshold 30 --input x.bam", "tool --threshold 1 --input /data/in/input.bam")
    assert any(a["code"] == "command_changed" for a in r)


@pytest.mark.parametrize("mutate", [
    lambda p, m: p.update(source_documents=[]),
    lambda p, m: p["commands"][0].update(line=3),
    lambda p, m: p["source_documents"][0].update(origin="wiki"),
    lambda p, m: p.update(ref="HEAD"),
    lambda p, m: m["source"].update(ref="b" * 40),
    lambda p, m: p.update(source_documents=[], procedure={"may_say_runs": True, "install_ready": True}),
])
def test_absent_or_mismatched_evidence_cannot_be_replaced_by_a_cached_label(mutate):
    p, m = case()
    # Source dictionaries must not alias each other in adversarial mutations.
    p, m = copy.deepcopy(p), copy.deepcopy(m)
    mutate(p, m)
    assert not review(p, m)["may_say_runs"]


@pytest.mark.parametrize("method", ["make", "cmake", "conda", "pip", "cargo", "go", "r", "nim", "autotools", "script", "release_binary", "docker_image", "bioconda"])
def test_build_family_never_authorizes_a_generated_installation(method):
    p, m = case()
    p["build"]["method"] = method
    m["environment"]["source"] = "generated"
    r = review(p, m)
    assert not r["install_ready"] and not r["may_say_runs"]


@pytest.mark.parametrize("command", ["docker build ..", "docker build -t image ../tool", "docker build --build-arg FIX=1 .", "docker build . || true", "docker build -f other .", "docker build --network host ."])
def test_unsupported_build_semantics_are_not_reinterpreted(command):
    p, m = case()
    p["source_documents"][0]["text"] = p["source_documents"][0]["text"].replace("docker build -t upstream .", command)
    assert not review(p, m)["install_ready"]


def test_capture_suffix_or_working_directory_cannot_hide_an_extra_command():
    p, m = case()
    m["run"]["cmd"] += "; patch-tool"
    assert not review(p, m)["may_say_runs"]
    command = fidelity.rewrite(CITED, "illumina-bam-hg38")["command"]
    m["run"]["cmd"] = prepare.example_wrapper(command, "/another-directory")
    assert not review(p, m)["may_say_runs"]


def test_no_synopsis_variables_configs_lists_or_executable_path_fixes():
    for cmd in ["tool [--threshold 30]", "tool --threads $N", "./tool --reads a.bam,b.bam", "tool -c configFile fastqfile"]:
        r = fidelity.rewrite(cmd, "illumina-bam-hg38")
        assert r["command"] == cmd and r["limitations"]
    import propose_manifest
    assert propose_manifest.from_the_path("./tool --reads x.bam", set(), True) == ("./tool --reads x.bam", [])


@pytest.mark.parametrize("dockerfile", ['FROM scratch\n', 'FROM scratch\nENTRYPOINT ["tool"]\n',
    'FROM scratch\nENTRYPOINT ["/bin/bash", "-lc"]\nFROM another\n',
    'FROM scratch\nRUN cat <<EOF\nENTRYPOINT ["/bin/bash", "-lc"]\nEOF\n'])
def test_image_entrypoint_is_never_overridden_to_force_a_command(dockerfile):
    p, m = case()
    p["upstream_files"]["Dockerfile"] = dockerfile
    r = review(p, m)
    assert r["install_ready"]
    assert not r["may_say_runs"]
    assert any(a["code"] == "image_invocation_unsupported" for a in r["amendments"])


@pytest.mark.parametrize("command,input_type", [("tool --bam reads.cram", "illumina-bam-hg38"),
    ("tool --bam reads.bam", "illumina-str-fastq"), ("tool --reads <FASTQ reads>", "illumina-bam-hg38"),
    ("tool --reads reads.fastq.gz", "illumina-str-fastq")])
def test_input_format_is_not_swapped_to_fit_available_data(command, input_type):
    r = fidelity.rewrite(command, input_type)
    assert r["command"] == command and r["limitations"]


def test_a_mount_path_in_an_unrelated_argument_is_not_input_evidence():
    p, m = case()
    command = "tool --label /data/in/input.bam --output out.vcf"
    p["commands"][0]["cmd"] = command
    p["source_documents"][0]["text"] = p["source_documents"][0]["text"].replace(CITED, command)
    m["run"]["cmd"] = prepare.example_wrapper(command, ".")
    assert not review(p, m)["may_say_runs"]


def test_citation_does_not_join_flag_lines_without_a_shell_continuation():
    p, _ = case()
    p["source_documents"][0]["text"] = "```\ntool\n --reads x.bam\n```\n"
    candidate = {"cmd": "tool --reads x.bam", "file": "README.md", "line": 2}
    assert not fidelity.cite(p, candidate)["verified"]
    p["source_documents"][0]["text"] = "```\ntool \\\n --reads x.bam\n```\n"
    assert fidelity.cite(p, candidate)["verified"]


def test_checked_out_evidence_is_read_only_and_every_cited_file_is_checked(tmp_path):
    p, m = case()
    r = review(p, m)
    for name, text in {**p["upstream_files"], "README.md": p["source_documents"][0]["text"]}.items():
        (tmp_path / name).write_text(text)
    before = {f.name: f.read_bytes() for f in tmp_path.iterdir()}
    fidelity.verify_checkout(tmp_path, r, m)
    assert before == {f.name: f.read_bytes() for f in tmp_path.iterdir()}
    (tmp_path / "README.md").write_text("changed documentation\n")
    with pytest.raises(ValueError, match="evidence differs"):
        fidelity.verify_checkout(tmp_path, r, m)
    (tmp_path / "README.md").write_bytes(before["README.md"])
    (tmp_path / "Dockerfile").write_text("FROM a-different-image\n")
    with pytest.raises(ValueError, match="evidence differs"):
        fidelity.verify_checkout(tmp_path, r, m)


def test_preparation_recomputes_instead_of_trusting_a_forged_ready_flag(tmp_path):
    p, m = case()
    proposal = tmp_path / "proposal.json"
    p["source_documents"] = []
    p["procedure"] = {"may_say_runs": True, "install_ready": True}
    proposal.write_text(json.dumps(p))
    descriptor = tmp_path / "work/proposal"
    descriptor.mkdir(parents=True)
    (descriptor / "manifest.yml").write_text(yaml.safe_dump(m))
    (descriptor / "Dockerfile").write_text("FROM attacker\n")
    result = subprocess.run([sys.executable, str(ROOT / "harness/prepare.py"), "test", "--work", str(tmp_path / "work"),
        "--proposal", str(proposal), "--trial"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert all(output[k] == "0" for k in ["install_ready", "procedure_ready", "own_ready", "external_ready", "example_ready"])
    assert output["starts_cmd"] == ""
    assert not json.loads((tmp_path / "work/procedure_review.json").read_text())["may_say_runs"]


def test_local_installer_refuses_without_upstream_evidence_before_any_subprocess(tmp_path, monkeypatch):
    import local_trial
    p, m = case()
    p["source_documents"] = []
    monkeypatch.setattr(local_trial.subprocess, "run", lambda *a, **k: pytest.fail("Git or Docker must not run"))
    with pytest.raises(ValueError, match="no proven"):
        local_trial.upstream_build_command(m, review(p, m), tmp_path / "source", "test")


def test_local_trial_requested_with_docker_does_not_execute_an_unsupported_recipe(tmp_path, monkeypatch):
    import local_trial
    original = subprocess.run
    def guarded(args, *a, **kwargs):
        if args[0] in ("docker", "git") or any(str(value).endswith("run_container.sh") for value in args):
            pytest.fail("an unsupported recipe must not reach Git, Docker or the STR runner")
        return original(args, *a, **kwargs)
    monkeypatch.setattr(local_trial.subprocess, "run", guarded)
    result = local_trial.build_local_trial("https://github.com/tfwillems/HipSTR", "", "",
        tmp_path / "trial", prefer_offline=True, run_docker=True)
    assert not result["gates"]["installs"] and not result["gates"]["runs"]
    assert result["verdict"]["code"] == "undetermined"
    assert result["verdict"]["basis"] == "strhub"


@pytest.mark.parametrize("tamper,expected_builds", [(False, 1), (True, 0)])
def test_real_install_gate_checks_sources_and_never_repairs_a_failed_build(tmp_path, tamper, expected_builds, monkeypatch):
    from engine import stages
    from engine.executor import Executor
    from engine.record import StageResult
    p, m = case()
    (tmp_path / "work").mkdir()
    (tmp_path / "work/procedure_review.json").write_text(json.dumps(review(p, m)))
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump(m))
    (tmp_path / "harness").symlink_to(ROOT / "harness", target_is_directory=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text('#!/usr/bin/env python3\nimport os,sys,pathlib\n'
        'if sys.argv[1] == "clone":\n'
        ' p=pathlib.Path(sys.argv[-1]); p.mkdir(parents=True)\n'
        ' (p/"Dockerfile").write_text(os.environ["TEST_DOCKERFILE"])\n'
        ' (p/"README.md").write_text(os.environ["TEST_DOCUMENT"])\n'
        'elif sys.argv[3] == "rev-parse": print(os.environ["TOOL_REF"])\n')
    git.chmod(0o755)
    docker = bindir / "docker"
    docker.write_text('#!/bin/sh\necho "$*" >> builds.txt\nexit 23\n')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("TEST_DOCUMENT", "altered\n" if tamper else p["source_documents"][0]["text"])
    monkeypatch.setenv("TEST_DOCKERFILE", DOCKERFILE)
    monkeypatch.setenv("TOOL_REF", p["ref"])
    ctx = stages.Ctx(plan={"repo": p["repo"], "ref": p["ref"], "install_ready": "1", "dockerdir": "unused",
                           "dockerfile": "Dockerfile", "dockerfile_from_repo": "Dockerfile",
                           "installation_profile": "", "manifest": str(tmp_path / "manifest.yml")},
                     work=pathlib.Path("work"), root=tmp_path, exe=Executor())
    result = stages.installs(ctx, StageResult(stage="available", status="passed", exit_code=0))
    assert result.status == "failed"
    calls = (tmp_path / "builds.txt").read_text().splitlines() if (tmp_path / "builds.txt").exists() else []
    assert len(calls) == expected_builds
    assert all("--build-arg" not in call for call in calls)
    if not tamper:
        assert result.outputs["source_evidence"] == "verified"
    else:
        assert result.outputs["source_evidence"] == "unverified"
        assert "evidence differs" in (tmp_path / "work/log_build.txt").read_text()


def test_positive_preparation_binds_the_review_to_the_actual_manifest(tmp_path):
    p, m = case()
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(p))
    descriptor = tmp_path / "work/proposal"
    descriptor.mkdir(parents=True)
    (descriptor / "manifest.yml").write_text(yaml.safe_dump(m))
    (descriptor / "Dockerfile").write_text("# descriptor only\n")
    (descriptor / "assets").mkdir()
    (descriptor / "assets/regions.bed").write_text("historical tool-specific regions")
    result = subprocess.run([sys.executable, str(ROOT / "harness/prepare.py"), "test", "--work", str(tmp_path / "work"),
        "--proposal", str(proposal), "--trial"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert values["install_ready"] == values["procedure_ready"] == "1"
    assert values["external_ready"] == "1"
    assert {p.name for p in (tmp_path / "work/in_external").iterdir()} == {"input.bam", "input.bam.bai"}
    assert values["cmd"] == m["run"]["cmd"]
    r = json.loads((tmp_path / "work/procedure_review.json").read_text())
    assert r["manifest_sha256"] == fidelity.digest(json.dumps(m, sort_keys=True))
    assert values["starts_cmd"] == ""  # never invent an extra --help command


@pytest.mark.parametrize("declared", [
    {"fixture": "tools/example/assets/input.bam"},
    {"regions": {"path": "tools/example/assets/regions.bed", "provided_by": "author"}},
    {"regions": {"repo": "https://github.com/example/tool", "ref": "a" * 40, "path": "regions.bed"}},
    {"regions": {"library": "hipstr"}},
])
def test_a_cited_command_does_not_authorize_a_separately_supplied_file(declared):
    p, m = case()
    m["inputs"].update(declared)
    r = review(p, m)
    assert r["install_ready"] and not r["may_say_runs"]
    assert r["blocker"] in {"regions_profile_unsupported", "fixture_profile_unsupported"}


@pytest.mark.parametrize("command", [
    "tool --reads hg19.bam --out result.vcf",
    "tool --reads x.bam --bam y.bam --out result.vcf",
    "tool --reads x.bam --ref /data/ref/hg38.fa --out result.vcf",
    "tool --reads x.bam --catalog /data/in/regions.json --out result.vcf",
])
def test_unproven_assembly_or_mount_cannot_feed_an_external_run(command):
    assert fidelity.rewrite(command, "illumina-bam-hg38")["limitations"]


@pytest.mark.parametrize("evidence", ["missing", "invalid", "wrong_manifest", "rejected"])
def test_report_cannot_promote_green_gates_over_a_missing_or_rejected_review(tmp_path, evidence, monkeypatch, capsys):
    import report as report_module
    p, m = case()
    m["recipe"] = {"origin": "proposed"}
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump(m))
    path = tmp_path / "review.json"
    r = review(p, m)
    if evidence == "wrong_manifest":
        r["manifest_sha256"] = "wrong"
    elif evidence == "rejected":
        p["source_documents"] = []
        r = review(p, m)
    if evidence != "missing":
        path.write_text("not JSON" if evidence == "invalid" else json.dumps(r))
    (tmp_path / "io.json").write_text('{"passed": true}')
    (tmp_path / "content.json").write_text('{"passed": true}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(report_module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["report.py", "--manifest", str(manifest),
        "--available", "pass", "--installs", "pass", "--runs", "pass", "--io", "io.json",
        "--content", "content.json", "--procedure-review", str(path), "--mode", "trial"])
    assert report_module.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"]["code"] == "undetermined"
    assert report["verdict"]["basis"] == "strhub"
    assert not report["procedure_review"]["may_say_runs"]


@pytest.mark.parametrize("correct_receipt", [True, False])
def test_report_requires_mount_evidence_from_the_reviewed_procedure(tmp_path, correct_receipt, monkeypatch, capsys):
    import input_provenance
    import report as report_module

    p, m = case()
    reviewed = review(p, m)
    work = tmp_path / "work"
    input_provenance.stage(ROOT, work, m["inputs"]["type"])
    receipt = input_provenance.verify(ROOT, work, m, reviewed, m["run"]["cmd"])
    if not correct_receipt:
        receipt["procedure_evidence_sha256"] = "a different review"
    (tmp_path / "mounted.json").write_text(json.dumps(receipt))
    (tmp_path / "review.json").write_text(json.dumps(reviewed))
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump(m))
    (tmp_path / "io.json").write_text('{"passed": true}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(report_module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["report.py", "--manifest", "manifest.yml", "--available", "pass",
        "--installs", "pass", "--runs", "pass", "--io", "io.json", "--procedure-review", "review.json",
        "--mounted-inputs", "mounted.json", "--mode", "trial"])
    assert report_module.main() == 0
    result = json.loads(capsys.readouterr().out)
    if correct_receipt:
        assert result["mounted_inputs"] == receipt
        assert result["verdict"]["code"] == "runs"
    else:
        assert "mounted_inputs" not in result
        assert result["verdict"]["code"] == "undetermined"
