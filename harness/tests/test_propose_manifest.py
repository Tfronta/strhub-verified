"""A proposal becomes a schema-valid trial recipe, and says what it guessed."""
import json
import pathlib

import _manifest
import detect_recipe as dr
import propose_manifest as pm

REPOS = pathlib.Path(__file__).resolve().parents[1] / "testdata" / "repos"


def _proposal(name):
    tree, readme, repo = dr.load_offline(REPOS / name)
    return dr.detect(dr.repo_slug(repo), tree["ref"], tree, readme, "README.md")


def _valid(manifest_yml, tmp_path):
    p = tmp_path / "manifest.yml"
    p.write_text(manifest_yml)
    return _manifest.load(str(p))  # raises on schema violation


def test_hipstr_recipe_is_generated_and_rewritten_to_strhub_mounts(tmp_path):
    r = pm.build(_proposal("hipstr"), "hipstr-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert m["environment"]["source"] == "generated"
    assert "FROM ubuntu:22.04" in r["dockerfile"]
    assert m["inputs"]["type"] == "illumina-bam-hg38"
    assert "/data/in/input.bam" in m["run"]["cmd"]
    assert "--fasta /data/ref/hg38.fa" in m["run"]["cmd"]
    assert "--regions /data/in/regions.bed" in m["run"]["cmd"]
    assert m["run"]["cmd"].startswith("cd '/opt/tool' && touch /tmp/.strhub_mark")
    assert m["outputs"][0] == {"path": "**/*.vcf*", "format": "vcf", "min_records": 1}
    # HipSTR reads the hipstr layout: the library file is used, no limitation.
    assert m["inputs"]["regions"] == {"library": "hipstr"}
    assert r["limitations"] == []
    assert m["caveats"]["source"] == "detect_recipe"
    assert "example" not in m  # README shows placeholders, not shipped data


def test_strsearch_uses_the_repository_dockerfile_and_its_example(tmp_path):
    r = pm.build(_proposal("strsearch"), "strsearch-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert m["environment"]["source"] == "repository"
    assert m["environment"]["from_repo"] == "Dockerfile"
    assert m["example"]["cmd"].startswith("python3 pipeline.py from_")
    assert m["example"]["cwd"] == "."
    assert any("hg19" in c for c in m["caveats"]["items"])


def test_straitrazor_fastq_is_pointed_at_the_nist_sample(tmp_path):
    r = pm.build(_proposal("straitrazor"), "straitrazor-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert m["inputs"]["type"] == "illumina-str-fastq"
    # README placeholders resolved: the kit-matched config from the tree, and
    # `fastqfile` pointed at the NIST sample. The un-piped form is chosen.
    assert "str8rzr -c ForenSeqv1.27.config /data/in/sample.fastq > allsequences.txt" in m["run"]["cmd"]
    assert "zcat" not in m["run"]["cmd"]
    assert any("ForenSeq kit" in c for c in m["caveats"]["items"])
    assert m["outputs"][0]["path"] == "**/*.t[sx][vt]"
    assert r["limitations"] == []


def test_empty_repository_yields_a_recipe_that_reports_its_gaps(tmp_path):
    proposal = dr.detect("x/y", "abcdef0123", {"tree": [], "truncated": False}, "", None)
    r = pm.build(proposal, "x-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert "install_method_unknown" in r["limitations"] and "no_command" in r["limitations"]
    assert m["outputs"][0]["format"] == "text"
    assert r["readme_gaps"]


def test_rewrite_leaves_unknown_types_alone():
    cmd, notes = pm.rewrite_for_strhub("tool -i reads.fsa -o out", "capillary-fsa")
    assert cmd == "tool -i reads.fsa -o out" and notes


def test_recipe_round_trips_through_json():
    r = pm.build(_proposal("gangstr"), "gangstr-trial")
    json.dumps({"manifest_yml": r["manifest_yml"], "dockerfile": r["dockerfile"]})


def test_a_list_of_input_files_becomes_one_canonical_input(tmp_path):
    cmd, _ = pm.rewrite_for_strhub("./HipSTR --bams run1.bam,run2.bam,run3.bam --fasta g.fa", "illumina-bam-hg38")
    assert cmd == "./HipSTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa"


def test_gangstr_recipe_declares_the_published_image_as_plan_b(tmp_path):
    r = pm.build(_proposal("gangstr"), "gangstr-trial")
    m = _valid(r["manifest_yml"], tmp_path)  # environment.fallback is schema-valid
    assert m["environment"]["source"] == "generated"
    assert m["environment"]["fallback"] == {
        "dockerfile": "Dockerfile.fallback",
        "reason": "the published image gymreklab/str-toolkit the README points at",
    }
    assert "FROM ubuntu:22.04" in r["dockerfile"]
    assert "FROM gymreklab/str-toolkit" in r["dockerfile_fallback"]
    env_caveat = next(c for c in m["caveats"]["items"] if c.startswith("Environment:"))
    assert "at the pinned commit" in env_caveat and "If that build fails" in env_caveat


def test_a_recipe_without_a_plan_b_declares_none(tmp_path):
    r = pm.build(_proposal("hipstr"), "hipstr-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert "fallback" not in m["environment"]
    assert r["dockerfile_fallback"] is None


def test_strspy_runs_on_the_input_type_strhub_has_data_for(tmp_path):
    # The README names FASTQ first and STRhub has ONT reads only as hg38 BAM:
    # the run uses the BAM and the caveat says so. Nothing is forced past
    # that — the documented command runs as documented, config files and all.
    r = pm.build(_proposal("strspy"), "strspy-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert m["inputs"]["type"] == "ont-bam-hg38"
    assert any(c.startswith("Input: the README suggests ont-fastq first") for c in m["caveats"]["items"])
    assert "bash ./STRspy_run_v2.0_Args.sh config/InputConfig.txt config/ToolsConfig.txt" in m["run"]["cmd"]
    assert "no_reference_dataset" not in r["limitations"]


def test_nothing_to_run_on_is_a_limitation_not_a_failure(tmp_path):
    proposal = _proposal("strspy")
    proposal["input_type"] = {"best": "ont-fastq", "candidates": ["ont-fastq"], "signals": {}, "warnings": []}
    proposal["example"] = None
    r = pm.build(proposal, "strspy-trial")
    m = _valid(r["manifest_yml"], tmp_path)
    assert m["inputs"] == {"type": "ont-fastq"}
    assert "no_reference_dataset" in r["limitations"]



def test_the_tool_is_named_the_way_its_repository_writes_it():
    # A GitHub path is case-flattened by its owner as often as not
    # (unique379r/strspy); the certificate used to .title() that into "Strspy".
    for repo, expected in [("strspy", "STRspy"), ("gangstr", "GangSTR"),
                           ("hipstr", "HipSTR"), ("strsearch", "STRsearch")]:
        proposal = _proposal(repo)
        assert pm.tool_name_as_written(proposal["repo"], proposal) == expected, repo
    # Nothing to go on: the path segment, not an invented capitalisation.
    assert pm.tool_name_as_written("https://github.com/x/mytool", {"readme_text": ""}) == "mytool"
