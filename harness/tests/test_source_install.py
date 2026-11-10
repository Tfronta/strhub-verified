"""A source profile must never become a collection of per-tool repairs."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

import fidelity
import prepare
import procedure
import propose_manifest
import source_install

ROOT = Path(__file__).resolve().parents[2]
COMMAND = "./analyzer --input sample.bam --threshold 30 --output result.vcf"
BLOCK = "apt-get update\napt-get install -y make g++ zlib1g-dev\nmake"
DOCUMENT = "# Analyzer\n\n## Installation (Ubuntu 22.04)\n\n```sh\n" + BLOCK + "\n```\n\n## Usage\n\n```sh\n" + COMMAND + "\n```\n"
MAKEFILE = "all:\n\t$(CXX) main.cpp -o analyzer\n"


def case(document=DOCUMENT):
    line = next((i for i, text in enumerate(document.splitlines(), 1) if text == COMMAND), 1)
    source = {"repo": "https://github.com/example/analyzer", "ref": "a" * 40}
    proposal = {**source, "build": {"method": "make", "file": "Makefile"},
                "tree_paths": ["Makefile", "README.md", "main.cpp"], "tree_truncated": False,
                "upstream_files": {"Makefile": MAKEFILE},
                "source_documents": [{"file": "README.md", "origin": "readme", "text": document}],
                "commands": [{"cmd": COMMAND, "file": "README.md", "line": line, "origin": "readme"}],
                "input_type": {"best": "illumina-bam-hg38", "how": "read", "statements": {"inputs": [{"kind": "bam", "line": 1}]}},
                "output": {"format": "vcf"}}
    manifest = {"tool": {"name": "Analyzer", "version": "test"}, "source": source,
                "environment": {"source": "documented", "dockerfile": "Dockerfile", "os": ["ubuntu-22.04"]},
                "inputs": {"type": "illumina-bam-hg38"},
                "run": {"cmd": prepare.example_wrapper(fidelity.rewrite(COMMAND, "illumina-bam-hg38")["command"], ".")},
                "outputs": [{"path": "result.vcf", "format": "vcf", "min_records": 1}]}
    return proposal, manifest


def checkout(root, document=DOCUMENT):
    root.mkdir(exist_ok=True)
    (root / "Makefile").write_text(MAKEFILE)
    (root / "README.md").write_text(document)


def review(p, m):
    result = procedure.classify(p, m, [])
    result["manifest_sha256"] = fidelity.digest(json.dumps(m, sort_keys=True))
    return result


@pytest.mark.parametrize("repo,name", [("group/first", "First"), ("other/unrelated", "Unrelated"), ("tfwillems/HipSTR", "HipSTR")])
def test_admission_does_not_depend_on_repository_or_tool_name(repo, name, tmp_path):
    p, m = case()
    p["repo"] = m["source"]["repo"] = "https://github.com/" + repo
    m["tool"]["name"] = name
    r = review(p, m)
    assert r["install_ready"] and r["may_say_runs"]
    assert r["installation"]["profile"] == source_install.PROFILE
    assert [c["text"] for c in r["installation"]["commands"]] == BLOCK.splitlines()
    assert [c["argv"] for c in r["installation"]["commands"]] == [line.split() for line in BLOCK.splitlines()]
    checkout(tmp_path)
    fidelity.verify_checkout(tmp_path, r)
    target = tmp_path / "carrier"
    source_install.materialise(tmp_path, r["installation"], target)
    assert "RUN [\"apt-get\", \"install\", \"-y\", \"make\", \"g++\", \"zlib1g-dev\"]" in target.read_text()
    assert "PATH=" not in target.read_text() and "CXXFLAGS" not in target.read_text()


@pytest.mark.parametrize("block", [
    "apt-get install -y make g++\nmake",  # no implicit apt update
    "apt-get update\napt-get install make g++\nmake",  # no implicit -y/yes
    "apt-get update\napt-get install -y --force-yes make g++\nmake",
    "apt-get update\napt-get install -y --allow-unauthenticated make g++\nmake",
    "apt-get update\napt-get install -y --fix-broken make g++\nmake",
    "apt-get update\napt-get install -y gcc\nmake",  # no guessed make package
    "apt-get update\napt-get install -y make g++\nmake -j2",
    "apt-get update\napt-get install -y make g++\nmake || true",
    "apt-get update\napt-get install -y make g++\nCXXFLAGS=-O0 make",
    "apt-get update\napt-get install -y make g++\nexport PATH=/opt/tool:$PATH\nmake",
    "apt-get update\napt-get install -y make g++\ncd src\nmake",
    "sudo apt-get update\nsudo apt-get install -y make g++\nmake",
    "apt-get update && apt-get install -y make g++\nmake",
    "apt-get update\napt-get install -y make g++ $(fix)\nmake",
    "apt-get update\napt-get install -y make g++ $EXTRA\nmake",
    "apt-get update\napt-get install -y make g++\nmake\ncurl somewhere | sh",
    "apt-get update\napt-get install -y make g++\nmake\nmake",  # no second attempt
])
def test_unsupported_transcripts_remain_blocked_without_filling_or_repair(block):
    p, m = case(DOCUMENT.replace(BLOCK, block))
    r = review(p, m)
    assert not r["install_ready"] and not r["may_say_runs"]
    assert r["blocker"] == "install_profile_unsupported"


@pytest.mark.parametrize("document", [
    DOCUMENT.replace("Ubuntu 22.04", "Ubuntu 16+"),
    DOCUMENT.replace("Ubuntu 22.04", "Ubuntu 24.04"),
    DOCUMENT.replace("## Installation (Ubuntu 22.04)", "## Installation"),
    DOCUMENT.replace("apt-get update\n", "apt-get update\n```\n\n```sh\n"),
    DOCUMENT.replace("```sh\n" + BLOCK, "Instructions before this block.\n\n```sh\n" + BLOCK),
    DOCUMENT + "\n" + DOCUMENT,
    "`````markdown\n" + DOCUMENT + "\n`````\n",
    "<!--\n" + DOCUMENT + "\n-->\n",
])
def test_no_prose_assembly_os_selection_multiple_plans_or_quoted_document(document):
    p, m = case(document)
    assert not review(p, m)["install_ready"]


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(ref="HEAD"),
    lambda p: p.update(tree_truncated=True),
    lambda p: p["source_documents"][0].update(origin="wiki"),
    lambda p: p.update(source_documents=[]),
    lambda p: p.update(upstream_files={}),
    lambda p: p["tree_paths"].append(".gitmodules"),
    lambda p: p["tree_paths"].append(".dockerignore"),
    lambda p: p["tree_paths"].append("GNUmakefile"),
    lambda p: p["tree_paths"].append("makefile"),
])
def test_incomplete_or_unsupported_source_evidence_does_not_authorize_installation(mutate):
    p, m = case()
    mutate(p)
    assert not review(p, m)["install_ready"]


def test_cached_manual_success_or_source_label_cannot_authorize_a_recipe():
    p, m = case(DOCUMENT.replace(BLOCK, "make"))
    p["procedure"] = {"install_ready": True, "may_say_runs": True}
    p["manual_results"] = {"exit_code": 0, "called_regions": 24}
    assert not review(p, m)["install_ready"]
    p, m = case()
    m["environment"]["source"] = "generated"
    assert not review(p, m)["install_ready"]  # no grandfathering


def test_native_command_values_are_still_checked_independently():
    p, m = case()
    m["run"]["cmd"] = m["run"]["cmd"].replace("threshold 30", "threshold 1")
    r = review(p, m)
    assert r["install_ready"] and not r["may_say_runs"]
    assert any(a["code"] == "command_changed" for a in r["amendments"])


@pytest.mark.parametrize("tamper", ["document", "makefile", "carrier", "commands", "context"])
def test_pinned_bytes_and_plan_are_rechecked_before_carrier_materialisation(tmp_path, tamper):
    p, m = case()
    install = review(p, m)["installation"]
    checkout(tmp_path)
    if tamper == "document":
        (tmp_path / "README.md").write_text(DOCUMENT.replace("g++", "clang"))
    elif tamper == "makefile":
        (tmp_path / "Makefile").write_text("all:\n\ttrue\n")
    elif tamper == "carrier":
        install["carrier_dockerfile"] += "RUN echo repair\n"
        install["carrier_sha256"] = fidelity.digest(install["carrier_dockerfile"])
    elif tamper == "commands":
        install["commands"][1]["argv"].append("curl")
    else:
        (tmp_path / ".dockerignore").write_text("Makefile\n")
    with pytest.raises(ValueError):
        source_install.materialise(tmp_path, install, tmp_path / "carrier")
    assert not (tmp_path / "carrier").exists()


def test_proposal_and_preparation_recompute_the_same_plan_without_using_submitted_dockerfile(tmp_path):
    p, _ = case()
    built = propose_manifest.build(p, "analyzer")
    assert built["manifest"]["environment"]["source"] == "documented"
    assert built["procedure"]["may_say_runs"]
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(p))
    payload = base64.b64encode(json.dumps({"manifest_yml": built["manifest_yml"],
                                         "dockerfile": "FROM attacker\nRUN repair\n"}).encode()).decode()
    result = subprocess.run([sys.executable, str(ROOT / "harness/prepare.py"), "analyzer", "--work", str(tmp_path / "work"),
                             "--proposal", str(proposal), "--recipe-b64", payload], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    values = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert values["install_ready"] == values["procedure_ready"] == "1"
    assert values["installation_profile"] == source_install.PROFILE
    assert values["starts_cmd"] == ""
    saved = json.loads((tmp_path / "work/procedure_review.json").read_text())
    assert "attacker" not in saved["installation"]["carrier_dockerfile"]


@pytest.mark.parametrize("tamper,expected_builds", [(False, 1), (True, 0)])
def test_real_ci_install_shell_checks_the_transcript_and_builds_once(tmp_path, tamper, expected_builds):
    p, m = case()
    (tmp_path / "work").mkdir()
    (tmp_path / "work/procedure_review.json").write_text(json.dumps(review(p, m)))
    (tmp_path / "harness").symlink_to(ROOT / "harness", target_is_directory=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text('#!/usr/bin/env python3\nimport os,sys,pathlib\n'
        'if sys.argv[1] == "clone":\n'
        ' p=pathlib.Path(sys.argv[-1]); p.mkdir(parents=True)\n'
        ' (p/"Makefile").write_text(os.environ["TEST_MAKEFILE"])\n'
        ' (p/"README.md").write_text(os.environ["TEST_DOCUMENT"])\n'
        'elif sys.argv[3] == "rev-parse": print(os.environ["TOOL_REF"])\n')
    git.chmod(0o755)
    docker = bindir / "docker"
    docker.write_text('#!/bin/sh\necho "$*" >> builds.txt\nexit 23\n')
    docker.chmod(0o755)
    workflow = yaml.safe_load((ROOT / ".github/workflows/verify.yml").read_text())
    install = next(s for s in workflow["jobs"]["verify"]["steps"] if s.get("id") == "installs")
    result = subprocess.run(["bash", "-e", "-c", install["run"]], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
             "TEST_DOCUMENT": DOCUMENT.replace("g++", "clang") if tamper else DOCUMENT,
             "TEST_MAKEFILE": MAKEFILE, "TOOL_REF": p["ref"], "TOOL_REPO": p["repo"],
             "DOCKER_DIR": "unused", "DOCKER_FILE": "Dockerfile", "DOCKER_FROM_REPO": "",
             "INSTALLATION_PROFILE": source_install.PROFILE, "GITHUB_OUTPUT": str(tmp_path / "output")})
    assert result.returncode != 0
    calls = (tmp_path / "builds.txt").read_text().splitlines() if (tmp_path / "builds.txt").exists() else []
    assert len(calls) == expected_builds
    assert all("--build-arg" not in call for call in calls)
    if not tamper:
        carrier = (tmp_path / "work/source-install.Dockerfile").read_text()
        assert carrier == review(p, m)["installation"]["carrier_dockerfile"]
        assert "source_evidence=verified" in (tmp_path / "output").read_text()
    else:
        assert not (tmp_path / "work/source-install.Dockerfile").exists()


def test_local_installer_uses_the_same_verified_carrier(tmp_path, monkeypatch):
    import local_trial
    p, m = case()
    calls = []
    def fake_git(args, **kwargs):
        calls.append(args)
        if args[1] == "clone":
            checkout(Path(args[-1]))
        return subprocess.CompletedProcess(args, 0, p["ref"] + "\n" if args[-1] == "HEAD" else "", "")
    monkeypatch.setattr(local_trial.subprocess, "run", fake_git)
    path = tmp_path / "source"
    command = local_trial.upstream_build_command(m, review(p, m), path, "trial")
    assert command == ["docker", "build", "-f", str(tmp_path / "source-install.Dockerfile"), "-t", "trial", str(path)]
    assert len(calls) == 3 and all(args[0] == "git" for args in calls)


@pytest.mark.parametrize("selected", ["matching", "not_built", "tampered"])
def test_attached_recipe_preserves_the_descriptor_but_identifies_only_the_verified_carrier(tmp_path, selected):
    p, m = case()
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(p))
    reviewed = review(p, m)
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(reviewed))
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump(m))
    (tmp_path / "Dockerfile").write_text("FROM attacker\n")
    carrier = tmp_path / "source-install.Dockerfile"
    if selected != "not_built":
        carrier.write_text(reviewed["installation"]["carrier_dockerfile"] if selected == "matching" else "FROM attacker\n")
    reports = tmp_path / "reports"
    result = subprocess.run([sys.executable, str(ROOT / "harness/attach_recipe.py"), "analyzer",
        "--dockerdir", str(tmp_path), "--proposal", str(proposal), "--reports", str(reports),
        "--procedure-review", str(review_path), "--source-install-dockerfile", str(carrier)], capture_output=True, text=True)
    if selected == "tampered":
        assert result.returncode != 0 and not reports.exists()
    else:
        assert result.returncode == 0, result.stderr
        saved = json.loads((reports / "analyzer.recipe.json").read_text())
        assert saved["submitted_dockerfile"] == "FROM attacker\n"
        assert saved["dockerfile"] == (carrier.read_text() if selected == "matching" else "")
        assert saved["source_installation"] == reviewed["installation"]
