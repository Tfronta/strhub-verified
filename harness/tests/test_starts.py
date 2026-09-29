"""Starts: whether the installed program answers --help, outside the ladder."""
import json

import check_starts
import prepare
import verdict


def test_exit_zero_or_a_printed_usage_is_starting():
    assert check_starts.judge(0, "")["passed"]
    assert check_starts.judge(1, "usage: straglr.py [-h] bam genome_fasta out_prefix\n")["passed"]
    assert check_starts.judge(2, "Options:\n  --bams   BAM files\n")["passed"]


def test_a_program_that_is_missing_or_broken_does_not_start():
    assert not check_starts.judge(127, "bash: line 1: ./trgt: No such file or directory")["passed"]
    assert not check_starts.judge(127, "vamos: error while loading shared libraries: libhts.so.3: "
                                       "cannot open shared object file")["passed"]
    assert not check_starts.judge(1, "Traceback (most recent call last):\n  ...\nTypeError: x\n")["passed"]
    assert not check_starts.judge(1, "something went wrong\n")["passed"]


def test_the_command_is_the_program_the_run_calls_then_help():
    w = prepare.example_wrapper
    assert prepare.starts_command(w("./LongTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa", "/opt/tool")) \
        == "cd '/opt/tool' && ./LongTR --help"
    assert prepare.starts_command(w("python straglr.py /data/in/input.bam /data/ref/hg38.fa sample", "/opt/tool")) \
        == "cd '/opt/tool' && python straglr.py --help"
    # STRhub's plumbing before it (mkdir) and the first step of a chain.
    assert prepare.starts_command(w("strling extract -f r.fa in.bam s.bin && mkdir -p out && strling call x", "/opt/tool")) \
        == "cd '/opt/tool' && strling --help"
    assert prepare.starts_command(w("mkdir -p out && GangSTR --bam x --out out/y", "/opt/tool")) \
        == "cd '/opt/tool' && GangSTR --help"
    # Nothing to ask when there is no program.
    assert prepare.starts_command("true  # no command found in the README; nothing to run") == ""


def test_the_verdict_says_whether_the_program_starts_when_nothing_ran_to_the_end():
    gaps = {"schema": "strhub-verified/recipe-proposal/1",
            "readme": {"gaps": [{"item": "command", "text": "no command"}], "sufficient_to_attempt": False}}
    g = {"available": True, "installs": True, "runs": False, "io": False, "content": False}
    v = verdict.decide({**g, "starts": True}, recipe_proposal=gaps)
    assert v["code"] == "undetermined" and v["reason"].endswith("The installed program starts: it answers --help.")
    v = verdict.decide({**g, "starts": False})
    assert v["code"] == "fails" and v["reason"].endswith("The installed program does not start: --help fails.")
    # A run that produced its output needs no such sentence.
    ok = {"available": True, "installs": True, "runs": True, "io": True, "content": True, "starts": True}
    assert "--help" not in verdict.decide(ok)["reason"]


def test_a_readme_with_no_command_still_asks_the_packaged_program(tmp_path):
    import detect_recipe as dr
    import propose_manifest as pm
    tree = {"tree": [{"path": "pyproject.toml", "type": "blob", "size": 1}], "truncated": False}
    files = {"pyproject.toml": "[project]\nname = \"fdstools\"\n[project.scripts]\nfdstools = \"fdstools.fdstools:main\"\n"}
    proposal = dr.detect("x/fdstools", "abc", tree, "# FDSTools\n\nSee the website.\n", "README.md",
                         extras={"files": files})
    r = pm.build(proposal, "fdstools-trial")
    assert "no_command" in r["limitations"]
    assert r["manifest"]["starts"] == {"cmd": "fdstools --help", "cwd": "/opt/tool"}
