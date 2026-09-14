"""detect_recipe against snapshots of the five tools in the catalogue.

The snapshots (tree + README at the pinned ref) live in testdata/repos so this
runs offline. Each assertion is a fact a person checked against the real
repository; a change that breaks one is either a regression or a reason to
re-snapshot on purpose.
"""
import json
import pathlib

import detect_recipe as dr

REPOS = pathlib.Path(__file__).resolve().parents[1] / "testdata" / "repos"


def _detect(name):
    tree, readme, repo = dr.load_offline(REPOS / name)
    return dr.detect(dr.repo_slug(repo), tree["ref"], tree, readme, "README.md")


def test_hipstr_builds_with_make_takes_bam_writes_vcf():
    r = _detect("hipstr")
    assert r["build"]["method"] == "make"
    assert r["input_type"]["best"] == "illumina-bam-hg38"
    assert r["output"]["format"] == "vcf"
    # htslib's test files are vendored, not HipSTR's examples.
    assert all("htslib" not in e["path"] for e in r["example_data"])
    assert r["commands"][0]["invokes"] == "HipSTR"
    assert r["readme"]["gaps"] == []
    assert "FROM ubuntu:22.04" in r["dockerfile"]


def test_straitrazor_has_no_example_data_but_a_runnable_command():
    r = _detect("straitrazor")
    assert r["build"]["method"] == "make"
    assert r["example_data"] == []
    assert [g["item"] for g in r["readme"]["gaps"]] == ["example_data"]
    # The binary is not a script in the tree, so it is found by its flags.
    assert r["commands"][0]["invokes"] == "str8rzr"
    assert r["commands"][0]["has_input_flag"] and r["commands"][0]["has_output_flag"]
    assert r["input_type"]["best"] == "illumina-str-fastq"
    assert r["output"]["format"] == "tsv"


def test_strsearch_ships_dockerfile_and_examples_and_warns_about_hg19():
    r = _detect("strsearch")
    assert r["build"]["method"] == "dockerfile"
    assert r["dockerfile"] is None  # the repository's own is used
    kinds = {e["kind"] for e in r["example_data"]}
    assert {"bam", "fastq", "bed"} <= kinds
    # Continuation lines are joined into one command.
    assert r["commands"][0]["cmd"].startswith("python3 pipeline.py from_")
    assert "--fq1" in r["commands"][0]["cmd"] or "--bam" in r["commands"][0]["cmd"]
    assert any("hg19" in w for w in r["input_type"]["warnings"])
    assert any("try both" in w for w in r["input_type"]["warnings"])


def test_gangstr_builds_with_cmake_and_names_its_binary():
    r = _detect("gangstr")
    assert r["build"]["method"] == "cmake"
    assert r["commands"][0]["invokes"] == "GangSTR"
    assert r["input_type"]["best"] == "illumina-bam-hg38"
    assert r["output"]["format"] == "vcf"


def test_strspy_conda_env_under_setup_dir_is_found():
    r = _detect("strspy")
    assert r["build"]["method"] == "conda"
    assert r["build"]["file"] == "setup/STRspy_2.0_env.yml"
    assert "micromamba create" in r["dockerfile"]
    assert "ont-bam-hg38" in r["input_type"]["candidates"]


def test_empty_repository_reports_every_gap():
    r = dr.detect("x/y", "abc", {"tree": [], "truncated": False}, "", None)
    items = [g["item"] for g in r["readme"]["gaps"]]
    assert items == ["readme", "install", "command", "input", "output", "example_data"]
    assert r["readme"]["sufficient_to_attempt"] is False
    assert r["dockerfile"] is None


def test_proposal_is_json_serialisable():
    json.dumps(_detect("hipstr"))
