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


def test_conda_file_alone_does_not_prove_generated_install_steps():
    """STRspy: the commit ships an environment file and STRhub holds the BAM.
    Packaging that into a container is the run, not a reason to refuse it."""
    proposal = {"build": {"method": "conda"}, "commands": [{"cmd": "tool --in x.bam"}]}
    got = procedure.classify(proposal, _manifest(cmd="tool --in /data/in/input.bam", outputs="out.txt"),
                             [], ["Environment: generated"])
    assert got["may_say_runs"] is False
    assert got["install_ready"] is False
    assert verdict.decide(G_OK, procedure=got)["code"] == "undetermined"


def test_no_install_in_the_repo_is_a_limitation_not_a_run():
    proposal = {"build": {"method": "unknown"}, "commands": [{"cmd": "tool --in x.bam"}]}
    got = procedure.classify(proposal, _manifest(cmd="tool --in /data/in/input.bam", outputs="out.txt"),
                             ["install_method_unknown"], [])
    assert got["may_say_runs"] is False
    assert got["blocker"] == "no_install_procedure"


def test_repository_source_label_without_cited_files_is_not_proof():
    proposal = {"build": {"method": "dockerfile"}, "commands": [{"cmd": "tool --in x.bam"}]}
    manifest = _manifest(method="dockerfile", source="repository", outputs="out.vcf",
                         cmd="tool --in /data/in/input.bam")
    got = procedure.classify(proposal, manifest, [], [])
    assert got["may_say_runs"] is False
    assert got["attribution"] == "strhub"
    assert verdict.decide(G_OK, procedure=got)["code"] == "undetermined"


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


def test_mkdir_is_not_silently_excused_as_plumbing():
    proposal = {"build": {"method": "dockerfile"},
                "commands": [{"cmd": "python3 pipeline.py --bam in.bam"}]}
    manifest = _manifest(method="dockerfile", source="repository", outputs="out.txt",
                         cmd="mkdir -p example && python3 pipeline.py --bam /data/in/input.bam")
    got = procedure.classify(proposal, manifest, [], [])
    assert got["may_say_runs"] is False
    assert any(a["code"] == "command_changed" for a in got["amendments"])


def test_a_command_still_pointing_at_the_repos_files_is_not_our_sample():
    proposal = {"build": {"method": "release_binary"},
                "commands": [{"cmd": "trgt genotype --reads example/sample.bam"}]}
    manifest = _manifest(method="release_binary", source="generated", outputs="out.vcf",
                         cmd="trgt genotype --reads example/sample.bam")
    # release_binary is citable even when source is not "repository".
    got = procedure.classify(proposal, manifest, [], [])
    assert any(a["code"] == "input_not_substituted" for a in got["amendments"])
    assert got["may_say_runs"] is False


def test_plan_b_after_a_generated_build_is_ours():
    procedure_review = {"may_say_runs": False, "basis": "strhub",
                        "reason": "The environment would be a container STRhub generated."}
    v = verdict.decide(G_OK, fallback_used=True, procedure=procedure_review)
    assert v["code"] == "undetermined" and v["basis"] == "strhub"
