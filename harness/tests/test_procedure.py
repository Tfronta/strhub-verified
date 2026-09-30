"""A green gate does not make an amended procedure a run, and a missing
input is not the tool failing."""
import verdict
import procedure

G_OK = {"available": True, "installs": True, "runs": True, "io": True, "content": True}
PROPOSAL = {"schema": "strhub-verified/recipe-proposal/1",
            "readme": {"gaps": [], "sufficient_to_attempt": True}}


def _manifest(method="conda", source="generated", outputs="**/*", cmd="tool --in sample.bam"):
    return {
        "environment": {"source": source},
        "run": {"cmd": cmd},
        "inputs": {"type": "illumina-bam-hg38"},
        "outputs": [{"path": outputs, "format": "text"}],
    }


def test_conda_from_the_repo_with_our_sample_can_be_run():
    """STRspy: the commit ships an environment file and STRhub holds the BAM.
    Packaging that into a container is the run, not a reason to refuse it."""
    proposal = {"build": {"method": "conda"}, "commands": [{"cmd": "tool --in x.bam"}]}
    got = procedure.classify(proposal, _manifest(cmd="tool --in /data/in/input.bam", outputs="out.txt"),
                             [], ["Environment: generated"])
    assert got["may_say_runs"] is True
    assert got["blocker"] == "ready"
    assert verdict.decide(G_OK, procedure=got)["code"] == "runs"


def test_no_install_in_the_repo_is_a_limitation_not_a_run():
    proposal = {"build": {"method": "unknown"}, "commands": [{"cmd": "tool --in x.bam"}]}
    got = procedure.classify(proposal, _manifest(cmd="tool --in /data/in/input.bam", outputs="out.txt"),
                             ["install_method_unknown"], [])
    assert got["may_say_runs"] is False
    assert got["blocker"] == "no_install_procedure"


def test_a_repository_dockerfile_with_the_input_is_the_tools_to_fail():
    proposal = {"build": {"method": "dockerfile"}, "commands": [{"cmd": "tool --in x.bam"}]}
    manifest = _manifest(method="dockerfile", source="repository", outputs="out.vcf",
                         cmd="tool --in /data/in/input.bam")
    got = procedure.classify(proposal, manifest, [], [])
    assert got["may_say_runs"] is True
    assert got["attribution"] == "tool"
    assert got["blocker"] == "ready"
    assert verdict.decide(G_OK, procedure=got)["code"] == "runs"


def test_missing_input_is_not_a_failure_of_the_tool():
    proposal = {"build": {"method": "dockerfile"}, "commands": [{"cmd": "tool --in x.bam"}]}
    manifest = _manifest(method="dockerfile", source="repository", outputs="out.vcf")
    got = procedure.classify(proposal, manifest, ["no_reference_dataset"], [])
    assert got["blocker"] == "missing_input" and got["basis"] == "recipe"
    v = verdict.decide(G_OK, recipe_proposal={**PROPOSAL, "limitations": ["no_reference_dataset"]},
                       procedure=got)
    assert v["code"] == "undetermined"
    assert "nothing was executed" in v["reason"] or "reference sample" in v["reason"]


def test_a_file_appearing_does_not_confirm_a_guessed_input():
    v = verdict.decide(G_OK, recipe_proposal={**PROPOSAL, "limitations": ["input_type_guessed"]})
    assert v["code"] == "undetermined" and v["basis"] == "recipe"


def test_mkdir_plumbing_is_not_a_flag_of_the_tool():
    proposal = {"build": {"method": "dockerfile"},
                "commands": [{"cmd": "python3 pipeline.py --bam in.bam"}]}
    manifest = _manifest(method="dockerfile", source="repository", outputs="out.txt",
                         cmd="mkdir -p example && python3 pipeline.py --bam /data/in/input.bam")
    got = procedure.classify(proposal, manifest, [], [])
    assert got["blocker"] == "ready"
    assert not any(a["code"] == "flag_injected" for a in got["amendments"])


def test_a_command_still_pointing_at_the_repos_files_is_not_our_sample():
    proposal = {"build": {"method": "release_binary"},
                "commands": [{"cmd": "trgt genotype --reads example/sample.bam"}]}
    manifest = _manifest(method="release_binary", source="generated", outputs="out.vcf",
                         cmd="trgt genotype --reads example/sample.bam")
    # release_binary is citable even when source is not "repository".
    got = procedure.classify(proposal, manifest, [], [])
    assert got["blocker"] == "input_not_substituted"
    assert got["may_say_runs"] is False


def test_plan_b_after_a_generated_build_is_ours():
    procedure_review = {"may_say_runs": False, "basis": "strhub",
                        "reason": "The environment would be a container STRhub generated."}
    v = verdict.decide(G_OK, fallback_used=True, procedure=procedure_review)
    assert v["code"] == "undetermined" and v["basis"] == "strhub"
