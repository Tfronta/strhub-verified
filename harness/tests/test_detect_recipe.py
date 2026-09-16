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
    # "FASTQ file or BAM-file" (README line 77): both are documented, so both
    # are candidates — read off the sentence, not inferred from a count.
    assert r["input_type"]["how"] == "read"
    assert set(r["input_type"]["candidates"]) >= {"illumina-bam-hg38", "illumina-str-fastq"}
    assert sorted(i["kind"] for i in r["input_type"]["statements"]["inputs"]) == ["bam", "fastq"]


def test_gangstr_builds_the_pinned_commit_and_keeps_the_published_image_as_plan_b():
    r = _detect("gangstr")
    # The README points at a published Docker image (gymreklab/str-toolkit)
    # and installs from Bioconda, but the tree can be built with CMake. What
    # the report names is the pinned commit, so that is what gets built; the
    # image holds whatever was last pushed to it and is kept as the fallback.
    assert r["build"]["method"] == "cmake" and r["build"]["file"] == "CMakeLists.txt"
    fb = r["build"]["fallback"]
    assert (fb["method"], fb["image"]) == ("docker_image", "gymreklab/str-toolkit")
    # The README line the image was read from: the cite, so a reader can open
    # the README there and see the author pointing at it.
    assert fb["readme_line"] == 18
    assert [c["method"] for c in r["build"]["candidates"]] == ["cmake", "docker_image", "bioconda"]
    assert "FROM ubuntu:22.04" in r["dockerfile"] and "cmake . && make" in r["dockerfile"]
    assert r["dockerfile_fallback"].startswith("# Proposed") and "FROM gymreklab/str-toolkit" in r["dockerfile_fallback"]
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


def test_a_help_listing_is_not_a_command():
    # STRspy's README quotes its -h output: a "where:" line followed by one
    # option per line. Joined together that read as a command that "takes a
    # bam and writes with -o", and it was run as one.
    r = _detect("strspy")
    assert all(not c["invokes"].endswith(":") and not c["invokes"].startswith("-") for c in r["commands"])
    assert r["commands"][0]["cmd"] == "bash ./STRspy_run_v2.0_Args.sh config/InputConfig.txt config/ToolsConfig.txt"
    readme = "```\nUsage: tool [-h]\n\nwhere:\n  -h show the help\n  -s input bam\n  -o output dir\n```\n"
    assert dr.detect_commands(readme, ["tool"]) and all(c["invokes"] == "tool" for c in dr.detect_commands(readme, ["tool"]))


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
    for name in ("hipstr", "straitrazor", "gangstr", "strspy", "gangstr:fallback"):
        name, _, which = name.partition(":")
        df = _detect(name)["dockerfile_fallback" if which else "dockerfile"]
        assert df, name
        for line in df.splitlines():
            # A bare `|| true` at the end of a RUN chain hides every earlier
            # failure in the chain. Only a parenthesised step may be tolerated.
            assert not re.search(r"&&\s+[^()\n]*\|\|\s*true\s*$", line), (name, line)


README_WITH_IMAGE = "## Install\n\nA Docker image is available at [x](https://hub.docker.com/r/gymreklab/str-toolkit).\n\n```\nGangSTR --bam file.bam --ref ref.fa --regions r.bed --out o\n```\n"


def test_a_published_docker_image_is_the_environment_only_when_nothing_builds_the_commit():
    # Nothing in the tree to build from: the image is all there is, and no plan B.
    r = dr.detect("gymreklab/gangstr", "abc", {"tree": [], "truncated": False}, README_WITH_IMAGE, "README.md")
    assert r["build"]["method"] == "docker_image" and r["build"]["image"] == "gymreklab/str-toolkit"
    assert r["build"]["fallback"] is None and r["dockerfile_fallback"] is None
    assert r["dockerfile"].startswith("# Proposed") and "FROM gymreklab/str-toolkit" in r["dockerfile"]


def test_a_source_build_outranks_the_published_image_which_becomes_plan_b():
    tree = {"tree": [{"path": "CMakeLists.txt", "type": "blob", "size": 1}], "truncated": False}
    r = dr.detect("gymreklab/gangstr", "abc", tree, README_WITH_IMAGE, "README.md")
    assert r["build"]["method"] == "cmake"
    assert r["build"]["fallback"]["image"] == "gymreklab/str-toolkit"
    assert "FROM ubuntu:22.04" in r["dockerfile"]
    assert "FROM gymreklab/str-toolkit" in r["dockerfile_fallback"]
    # Both lay the tool out the same way, so one command runs on either.
    for df in (r["dockerfile"], r["dockerfile_fallback"]):
        assert "git clone https://github.com/gymreklab/gangstr.git tool" in df
        assert df.rstrip().endswith('ENTRYPOINT ["/bin/bash", "-lc"]')


def test_the_repositorys_own_dockerfile_needs_no_plan_b():
    tree = {"tree": [{"path": "Dockerfile", "type": "blob", "size": 1}, {"path": "CMakeLists.txt", "type": "blob", "size": 1}], "truncated": False}
    r = dr.detect("gymreklab/gangstr", "abc", tree, README_WITH_IMAGE, "README.md")
    assert r["build"]["method"] == "dockerfile"
    assert r["build"]["fallback"] is None and r["dockerfile_fallback"] is None


def test_source_builds_bring_the_autotools():
    df = _detect("hipstr")["dockerfile"]
    assert "autoconf automake libtool" in df


def test_the_author_s_own_known_bug_section_is_carried_out_of_the_readme():
    # STRspy documents that its wrapper can exit without doing any work. A run
    # that died in that wrapper reported nothing about it, because the section
    # never left the README.
    issues = _detect("strspy")["known_issues"]
    assert [i["heading"] for i in issues] == ["Known bug"]
    assert "unable to properly connect with" in issues[0]["text"]
    assert "choose the Normal version" in issues[0]["text"]
    assert issues[0]["line"] == 291  # so a reader can open the README at it

    # STRaitRazor documents one too, about a specific architecture.
    sr = _detect("straitrazor")["known_issues"]
    assert sr and "windows 7" in sr[0]["text"].lower()
    # Its heading is written "known issues<br>"; the markup is not the name.
    assert sr[0]["heading"] == "known issues"

    # Not every repository has one, and inventing a section is worse than none.
    for name in ("gangstr", "strsearch"):
        assert _detect(name)["known_issues"] == [], name


def test_a_known_issue_quote_is_bounded_and_says_when_it_was_cut():
    long_readme = "## Known issues\n\n" + ("word " * 400)
    out = dr.author_known_issues(long_readme)
    assert len(out) == 1 and out[0]["truncated"] is True and len(out[0]["text"]) == 600
    assert dr.author_known_issues("## Known issues\n\ntiny") == []  # too short to be a finding
