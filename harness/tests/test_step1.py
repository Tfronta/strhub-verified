"""The three sentences of step 1, and what none of them is allowed to say.

docs/PLAN-Paso-1.md fixes the wording. A report that cannot run a tool says so
about the documentation or about STRhub's own shelf; it never says the tool
does not work, because that is not what it observed.
"""
import certificate_text as ct
import verdict

G_OK = {"available": True, "installs": True, "runs": True, "io": True, "content": True}


def test_the_development_fixtures_show_the_message_they_claim():
    """The trials on disk are what a maintainer is walked through, so a page
    illustrating the wrong rule would teach the wrong rule."""
    import trial_fixtures
    assert trial_fixtures.disagreements() == []


def _report(code, blocker="", reason="", basis="gates", gaps=None):
    return {
        "verdict": {"code": code, "title": verdict.TITLES.get(code, code), "reason": reason,
                    "basis": basis, "readme_gaps": gaps or []},
        "procedure_review": {"blocker": blocker, "reason": reason} if blocker else {},
    }


def test_a_run_that_finished_says_it_runs_and_claims_nothing_more():
    s = ct.step1_says(_report("runs", reason="The tool installed and produced its output."))
    assert s["code"] == "runs"
    assert s["headline"] == "As documented, it runs."
    assert "says nothing about genotypes" in s["body"]
    assert s["missing"] == []


def test_a_failure_of_the_documented_run_invites_a_fix_and_does_not_condemn_the_tool():
    s = ct.step1_says(_report("fails", reason="The tool exited with an error."))
    assert s["code"] == "does_not_run"
    assert s["headline"] == "As documented, it does not run."
    assert "does not mean the tool does not work" in s["body"]
    assert "try the link again" in s["body"]


def test_a_missing_command_names_the_block_of_the_guide():
    s = ct.step1_says(_report("undetermined", blocker="no_command",
                              reason="No command line invoking the tool was found."))
    assert s["code"] == "cannot_tell"
    assert s["missing"] == ["command"]
    assert s["missing_text"] == [ct.GUIDE_BLOCKS["command"]]
    assert s["guide"] == ct.GUIDE
    assert "does not mean the tool does not work" in s["body"]


def test_each_blocker_of_the_commit_maps_onto_one_named_block():
    """The block travels as the guide's key so the web can say it in es/en/pt,
    and every key it can emit has a name on both sides."""
    for blocker, (block, whose) in ct.STEP1_BLOCKERS.items():
        if whose != "commit":
            continue
        s = ct.step1_says(_report("undetermined", blocker=blocker, reason="."))
        assert s["missing"] == [block], blocker
        assert s["missing_text"] == [ct.GUIDE_BLOCKS[block]], blocker


def test_a_limitation_of_ours_is_not_told_as_a_gap_of_theirs():
    """STRhub holding no sample of that kind, or our own reader rewriting the
    command, is ours. It asks for an example file; it does not ask the author
    to fix a README that is not at fault."""
    for blocker in ("missing_input", "loci_outside_panel", "flag_dropped", "regions_guessed"):
        s = ct.step1_says(_report("undetermined", blocker=blocker, reason="."))
        assert s["code"] == "ours", blocker
        assert s["missing"] == [], blocker
        assert "limitation is ours" in s["body"]
        assert "Nothing here is a finding about the tool" in s["body"]


def test_a_synopsis_or_an_unnamed_output_is_the_commits_gap_not_ours():
    """The classifier calls trimming a synopsis, or accepting an unnamed
    output, an amendment of ours, because performing it would be. What the
    author can act on is still that the commit states no command and names no
    output, so the reader gets the block of the guide and not a sentence about
    STRhub's machinery. The blocker decides, not the verdict's basis."""
    for blocker, block in (("synopsis_trimmed", "command"), ("output_unnamed", "output")):
        s = ct.step1_says(_report("undetermined", blocker=blocker, reason=".", basis="strhub"))
        assert s["code"] == "cannot_tell", blocker
        assert s["missing"] == [block], blocker


def test_an_unknown_blocker_falls_back_to_the_verdicts_basis():
    ours = ct.step1_says(_report("undetermined", blocker="something_new", reason=".", basis="strhub"))
    assert ours["code"] == "ours"
    theirs = ct.step1_says(_report("undetermined", blocker="something_new", reason=".", basis="readme"))
    assert theirs["code"] == "cannot_tell"


def test_no_sentence_of_step_1_says_the_tool_does_not_work():
    """The only permitted occurrence of that phrase is inside the disclaimer
    that denies it."""
    codes = ["runs", "fails", "undetermined"]
    blockers = [""] + list(ct.STEP1_BLOCKERS)
    for code in codes:
        for blocker in blockers:
            body = ct.step1_says(_report(code, blocker=blocker, reason="."))["body"]
            for claim in ("the tool does not work", "the tool is broken", "the tool fails"):
                if claim in body:
                    assert f"does not mean {claim}" in body, (code, blocker, claim)


def test_an_amended_procedure_is_not_published_as_the_tool_failing():
    """The gate ladder came back green on a procedure STRhub had to amend. The
    headline may not be `runs`, and a red is not attributed to the tool
    either: the verdict is undetermined, and step 1 calls the limitation ours."""
    review = {"may_say_runs": False, "basis": "strhub", "blocker": "flag_injected",
              "reason": "Flags were added that the cited command does not carry."}
    v = verdict.decide(G_OK, procedure=review)
    assert v["code"] == "undetermined"
    s = ct.step1_says({"verdict": v, "procedure_review": review})
    assert s["code"] == "ours"
    assert s["headline"] != "As documented, it does not run."
