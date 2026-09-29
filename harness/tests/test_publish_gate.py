"""What goes to the catalogue. A failure of the tool does; a fault of ours, a
trial handed a recipe, and a trial landing on another repository's card do not."""
import publish_gate

INDEX = {"tools": [{"slug": "hipstr", "source_repo": "https://github.com/tfwillems/HipSTR"}]}


def report(code="fails", basis="gates", slug="hipstr", repo="https://github.com/tfwillems/HipSTR"):
    return {"verdict": {"code": code, "basis": basis},
            "report": {"slug": slug}, "source": {"repo": repo}}


def decide(r, **kw):
    args = dict(mode="trial", url_trial=True, trial_publish=True, event_name="workflow_dispatch",
                index=INDEX)
    args.update(kw)
    return publish_gate.decide(r, **args)


def test_a_failure_of_the_tool_is_published():
    ok, _ = decide(report("fails"))
    assert ok


def test_committed_manifest_publishes_without_reading_the_catalogue():
    ok, _ = decide(report("runs"), mode="publish", url_trial=False, index=None)
    assert ok


def test_strhub_fault_is_not_published():
    ok, why = decide(report("undetermined", basis="strhub"))
    assert not ok and "infrastructure" in why


def test_pull_request_never_publishes():
    ok, _ = decide(report("runs"), event_name="pull_request")
    assert not ok


def test_out_of_scope_is_not_published():
    ok, _ = decide(report("out_of_scope", basis="environment"))
    assert not ok


def test_trial_with_a_handed_recipe_never_publishes():
    ok, _ = decide(report("runs"), url_trial=False)
    assert not ok


def test_dispatch_can_keep_a_trial_out_of_the_catalogue():
    ok, _ = decide(report("runs"), trial_publish=False)
    assert not ok


def test_another_repository_named_like_a_card_does_not_take_it():
    ok, why = decide(report("fails", repo="https://github.com/someone/HipSTR"))
    assert not ok and "belongs to" in why


def test_same_repository_in_another_spelling_is_the_same_card():
    ok, _ = decide(report("runs", repo="https://github.com/TFWillems/hipstr.git/"))
    assert ok


def test_a_new_card_from_a_url_trial_is_published():
    ok, _ = decide(report("fails", slug="longtr", repo="https://github.com/gymrek-lab/LongTR"))
    assert ok


def test_unreadable_catalogue_fails_closed_for_url_trials():
    ok, why = decide(report("runs"), index=None)
    assert not ok and "catalogue" in why
