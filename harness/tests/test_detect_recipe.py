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
    assert "--regions" in r["commands"][0]["cmd"] and "--str-vcf" in r["commands"][0]["cmd"]
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


def test_gangstr_installs_from_bioconda_and_reads_the_full_command():
    r = _detect("gangstr")
    # The README points at a published Docker image (gymreklab/str-toolkit)
    # and installs from Bioconda; both outrank compiling the CMake tree, and
    # the image, being the author's own environment, comes first.
    assert r["build"]["method"] == "docker_image" and r["build"]["image"] == "gymreklab/str-toolkit"
    assert [c["method"] for c in r["build"]["candidates"]][:2] == ["docker_image", "bioconda"]
    assert "FROM gymreklab/str-toolkit" in r["dockerfile"]
    assert r["commands"][0]["invokes"] == "GangSTR"
    # One option per line in the README, no backslashes: all of them are kept.
    assert "--regions" in r["commands"][0]["cmd"] and "--out" in r["commands"][0]["cmd"]
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


def test_example_is_proposed_only_when_the_command_runs_on_shipped_data():
    strsearch = _detect("strsearch")["example"]
    assert strsearch and strsearch["source"] == "detected"
    assert any(p.startswith("example/test_data/") for p in strsearch["inputs_in_repo"])
    # Placeholders like run1.bam / file.bam are not files in the tree.
    assert _detect("hipstr")["example"] is None
    assert _detect("gangstr")["example"] is None


def test_generated_dockerfiles_never_mask_a_failed_clone():
    import re
    for name in ("hipstr", "straitrazor", "gangstr", "strspy"):
        df = _detect(name)["dockerfile"]
        assert df, name
        for line in df.splitlines():
            # A bare `|| true` at the end of a RUN chain hides every earlier
            # failure in the chain. Only a parenthesised step may be tolerated.
            assert not re.search(r"&&\s+[^()\n]*\|\|\s*true\s*$", line), (name, line)


def test_a_published_docker_image_in_the_readme_is_the_environment():
    readme = "## Install\n\nA Docker image is available at [x](https://hub.docker.com/r/gymreklab/str-toolkit).\n\n```\nGangSTR --bam file.bam --ref ref.fa --regions r.bed --out o\n```\n"
    r = dr.detect("gymreklab/gangstr", "abc", {"tree": [{"path": "CMakeLists.txt", "type": "blob", "size": 1}], "truncated": False}, readme, "README.md")
    assert r["build"]["method"] == "docker_image" and r["build"]["image"] == "gymreklab/str-toolkit"
    assert r["dockerfile"].startswith("# Proposed") and "FROM gymreklab/str-toolkit" in r["dockerfile"]


def test_source_builds_bring_the_autotools():
    df = _detect("hipstr")["dockerfile"]
    assert "autoconf automake libtool" in df
