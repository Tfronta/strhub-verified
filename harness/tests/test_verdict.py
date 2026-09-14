"""The four verdicts, one policy line each."""
import verdict

G_OK = {"available": True, "installs": True, "runs": True, "io": True, "content": True}
G_INSTALL_FAIL = {"available": True, "installs": False, "runs": False, "io": False, "content": False}
G_RUN_FAIL = {"available": True, "installs": True, "runs": False, "io": False, "content": False}
G_NO_OUTPUT = {"available": True, "installs": True, "runs": True, "io": False, "content": False}
PROPOSAL_OK = {"schema": "strhub-verified/recipe-proposal/1", "readme": {"gaps": [], "sufficient_to_attempt": True}}
PROPOSAL_GAPS = {"schema": "strhub-verified/recipe-proposal/1",
                 "readme": {"gaps": [{"item": "command", "text": "no command"}], "sufficient_to_attempt": False}}


def test_output_produced_is_runs_whatever_the_log_said():
    v = verdict.decide(G_OK, {"external": [{"id": "cannot_open"}]})
    assert v["code"] == "runs"


def test_example_output_alone_is_runs():
    v = verdict.decide({**G_NO_OUTPUT, "example": True})
    assert v["code"] == "runs"


def test_gpu_in_log_is_out_of_scope():
    v = verdict.decide(G_RUN_FAIL, {"external": [{"id": "requires_gpu"}]})
    assert v["code"] == "out_of_scope" and "requires_gpu" in v["reason"]


def test_declared_incompatibility_is_out_of_scope():
    v = verdict.decide(G_RUN_FAIL, declared_compatibility={"requires_gui": True})
    assert v["code"] == "out_of_scope"


def test_incomplete_proposal_is_undetermined_with_gaps():
    v = verdict.decide(G_INSTALL_FAIL, recipe_proposal=PROPOSAL_GAPS)
    assert v["code"] == "undetermined"
    assert v["basis"] == "readme"
    assert [g["item"] for g in v["readme_gaps"]] == ["command"]


def test_auto_recipe_with_fixable_failure_is_undetermined_not_fails():
    v = verdict.decide(G_RUN_FAIL, {"external": [{"id": "bad_option"}]}, recipe_proposal=PROPOSAL_OK)
    assert v["code"] == "undetermined" and v["basis"] == "recipe"


def test_submitted_recipe_with_fixable_failure_is_fails():
    v = verdict.decide(G_RUN_FAIL, {"external": [{"id": "bad_option"}]})
    assert v["code"] == "fails"


def test_install_failure_is_fails_with_the_reason():
    v = verdict.decide(G_INSTALL_FAIL)
    assert v["code"] == "fails" and "did not build" in v["reason"]


def test_ran_but_no_output_is_fails():
    v = verdict.decide(G_NO_OUTPUT)
    assert v["code"] == "fails" and "no output" in v["reason"]


def test_example_data_gap_is_never_a_reason():
    p = {"schema": "strhub-verified/recipe-proposal/1",
         "readme": {"gaps": [{"item": "example_data", "text": "none"}], "sufficient_to_attempt": True}}
    v = verdict.decide(G_INSTALL_FAIL, recipe_proposal=p)
    assert v["code"] == "fails" and v["readme_gaps"] == []


def test_proposal_with_known_limitations_is_undetermined():
    p = {**PROPOSAL_OK, "limitations": ["regions_format_unknown"]}
    v = verdict.decide(G_RUN_FAIL, recipe_proposal=p)
    assert v["code"] == "undetermined" and "regions" in v["reason"]


def test_blockers_name_the_regions_file_and_both_actions():
    p = {**PROPOSAL_OK, "limitations": ["regions_format_unknown"]}
    v = verdict.decide(G_RUN_FAIL, recipe_proposal=p)
    assert [b["code"] for b in v["blockers"]] == ["regions_format_unknown"]
    b = v["blockers"][0]
    assert b["self_fix"] == "upload_regions"
    assert "hg38" in b["ask_owner"]["title"]


def test_blockers_follow_the_gate_that_failed():
    assert [b["code"] for b in verdict.decide(G_INSTALL_FAIL)["blockers"]] == ["build_failed"]
    assert [b["code"] for b in verdict.decide(G_RUN_FAIL)["blockers"]] == ["run_failed"]
    assert [b["code"] for b in verdict.decide(G_NO_OUTPUT)["blockers"]] == ["no_output"]


def test_runs_has_no_blockers():
    assert verdict.decide(G_OK)["blockers"] == []


def test_readme_gaps_become_blockers_without_duplicates():
    v = verdict.decide(G_INSTALL_FAIL, recipe_proposal=PROPOSAL_GAPS)
    assert [b["code"] for b in v["blockers"]] == ["no_command", "build_failed"]


def test_output_on_plan_b_is_still_runs_but_says_which_version_ran():
    v = verdict.decide(G_OK, fallback_used=True)
    assert v["code"] == "runs" and v["blockers"] == []
    assert "pinned commit failed" in v["reason"] and "published environment" in v["reason"]
    assert "pinned" not in verdict.decide(G_OK)["reason"]

