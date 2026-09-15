"""What the engine says about a repository must agree with what is true of it.

Phase D1 of docs/PLAN-Claims-Need-Evidence.md. Every test before this one
checked that the engine PRODUCES something — a caveat, a detection, a
citation that points somewhere real. None checked that what it says is TRUE.
That is how "the README suggests ont-fastq first" reached a published page:
the caveat was generated, cited nothing false, and was wrong.

Each snapshot repository under testdata/repos carries a facts.json: facts a
person established by reading the README and the tree at the pinned ref,
each with the line it was read on. This file builds everything the engine
would publish about that repository — the proposal, the recipe's caveats,
the verdict and its blockers, the evidence list — and holds all of it to
those facts. A heuristic that starts contradicting one breaks the build on
the commit that did it.

Adding a repository: snapshot it, write its facts.json by hand, add it to
NAMES. Adding a fact: add the key here and to every facts.json.
"""
import json
import pathlib
import re

import claims
import detect_recipe as dr
import propose_manifest as pm
import verdict

REPOS = pathlib.Path(__file__).resolve().parents[1] / "testdata" / "repos"
NAMES = ("hipstr", "gangstr", "strsearch", "straitrazor", "strspy")

#: The STRhub input types each documented input kind may be run as.
KIND_OF_TYPE = {
    "illumina-bam-hg38": "bam", "illumina-bam-hg38-y": "bam", "ont-bam-hg38": "bam",
    "illumina-str-fastq": "fastq", "ont-fastq": "fastq", "ce-fsa": "fsa",
}
PLATFORM_OF_TYPE = {
    "illumina-bam-hg38": "illumina", "illumina-bam-hg38-y": "illumina", "illumina-str-fastq": "illumina",
    "ont-bam-hg38": "ont", "ont-fastq": "ont",
}


def _everything_the_engine_says(name):
    """The proposal, the recipe, and every sentence either would publish."""
    tree, readme, repo = dr.load_offline(REPOS / name)
    proposal = dr.detect(dr.repo_slug(repo), tree["ref"], tree, readme, "README.md")
    recipe = pm.build(proposal, f"{name}-trial")
    proposal["limitations"] = recipe["limitations"]
    # The verdict a stopped run would get, so its blockers are included in
    # what is checked: those are the sentences that reach an author's issue
    # tracker under a reader's name.
    stopped = {"available": True, "installs": True, "runs": False, "io": False, "content": False}
    v = verdict.decide(stopped, recipe_proposal=proposal)
    sentences = list(recipe["manifest"].get("caveats", {}).get("items", []))
    sentences += [g["text"] for g in proposal["readme"]["gaps"]]
    sentences += [v["reason"]]
    for b in v.get("blockers", []):
        sentences += [b["what"], b["self_fix_text"], b["ask_owner"]["title"], b["ask_owner"]["body"]]
    return proposal, recipe, sentences


def _facts(name):
    return json.loads((REPOS / name / "facts.json").read_text())


def _fact(facts, key):
    return facts[key]["value"]


def test_the_input_the_engine_runs_is_one_the_readme_documents():
    for name in NAMES:
        proposal, recipe, _ = _everything_the_engine_says(name)
        facts = _facts(name)
        chosen = recipe["manifest"].get("inputs", {}).get("type")
        assert chosen, name
        kind = KIND_OF_TYPE[chosen]
        assert kind in _fact(facts, "documented_inputs"), (
            f"{name}: the run uses a {kind} but the README documents only "
            f"{_fact(facts, 'documented_inputs')} ({facts['documented_inputs']['where']})")


def test_the_engine_never_runs_a_platform_the_author_advises_against():
    # HipSTR: "We do not recommend running it on PacBio or Oxford Nanopore
    # data" (README.md:435). Choosing an ONT dataset for it would be a run the
    # author said not to do, reported as a finding about HipSTR.
    for name in NAMES:
        _, recipe, _ = _everything_the_engine_says(name)
        facts = _facts(name)
        chosen = recipe["manifest"].get("inputs", {}).get("type")
        platform = PLATFORM_OF_TYPE.get(chosen)
        assert platform == _fact(facts, "documented_platform"), (
            f"{name}: ran as {chosen} ({platform}) but the README documents "
            f"{_fact(facts, 'documented_platform')} ({facts['documented_platform']['where']})")


def test_no_sentence_puts_a_preference_in_the_authors_mouth():
    """The STRspy sentence. Also: the source-level lint sees string literals;
    this sees the text after f-string interpolation, which is what ships."""
    for name in NAMES:
        _, _, sentences = _everything_the_engine_says(name)
        for text in sentences:
            for pattern, why in claims.FORBIDDEN:
                assert not re.search(pattern, text, re.I), f"{name}: {text!r} — {why}"


def test_what_the_engine_says_about_example_data_is_true():
    for name in NAMES:
        proposal, _, sentences = _everything_the_engine_says(name)
        facts = _facts(name)
        ships = _fact(facts, "ships_example_data")
        assert bool(proposal["example_data"]) == ships, (
            f"{name}: engine sees {len(proposal['example_data'])} example files; "
            f"fact: ships_example_data={ships} ({facts['ships_example_data']['where']})")
        if ships:
            for text in sentences:
                assert not re.search(r"ships no (?:test|demo|example)|no example data|does not (?:ship|include)", text, re.I), (
                    f"{name}: {text!r}, but the repository ships example data "
                    f"({facts['ships_example_data']['where']})")


def test_the_install_method_and_command_are_the_repositorys_own():
    for name in NAMES:
        proposal, _, _ = _everything_the_engine_says(name)
        facts = _facts(name)
        assert proposal["build"]["method"] == _fact(facts, "install_method"), (
            name, proposal["build"]["method"], facts["install_method"]["where"])
        assert proposal["commands"], name
        assert proposal["commands"][0]["invokes"] == _fact(facts, "readme_command_program"), (
            f"{name}: proposed {proposal['commands'][0]['invokes']!r} from "
            f"{proposal['commands'][0]['cmd'][:60]!r}; fact: {facts['readme_command_program']['where']}")


def test_a_published_image_is_reported_only_when_the_readme_names_one():
    for name in NAMES:
        proposal, _, _ = _everything_the_engine_says(name)
        facts = _facts(name)
        seen = [c.get("image") for c in proposal["build"]["candidates"] if c.get("image")]
        expected = _fact(facts, "published_image")
        assert (seen[0] if seen else None) == expected, (
            f"{name}: engine sees {seen}; fact: {expected} ({facts['published_image']['where']})")


def test_the_known_issue_sections_are_the_ones_the_readme_has():
    for name in NAMES:
        proposal, _, _ = _everything_the_engine_says(name)
        facts = _facts(name)
        got = [k["heading"].lower() for k in proposal["known_issues"]]
        want = [h.lower() for h in _fact(facts, "known_issue_headings")]
        assert got == want, (name, got, facts["known_issue_headings"]["where"])


def test_every_fact_file_cites_where_each_fact_was_read():
    """A fact without a cite is an opinion, and this file would then hold the
    engine to opinions."""
    keys = None
    for name in NAMES:
        facts = _facts(name)
        assert facts["_about"].startswith("Hand-checked against https://github.com/"), name
        these = sorted(k for k in facts if not k.startswith("_"))
        keys = keys or these
        assert these == keys, f"{name}: facts differ from the others: {these} vs {keys}"
        for k in these:
            assert "value" in facts[k] and facts[k].get("where"), f"{name}: {k} has no cite"
