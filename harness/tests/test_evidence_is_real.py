"""Every piece of evidence a proposal cites can be opened and says what it says.

Phase B of docs/PLAN-Claims-Need-Evidence.md. The register (claims.py) holds
the engine to naming a SOURCE for every finding; this holds it to the source
being real: the file is in the tree at the pinned ref, the README line exists
and reads as quoted, and the URL is the one GitHub would serve for it. A
claim whose evidence fails here is a claim nobody could check — which is the
STRspy sentence all over again, with a footnote.

Runs on the snapshots of the five catalogue repositories, so it needs no
network and fails on the commit that breaks it.
"""
import pathlib
import re

import detect_recipe as dr

REPOS = pathlib.Path(__file__).resolve().parents[1] / "testdata" / "repos"
NAMES = ("hipstr", "straitrazor", "strsearch", "gangstr", "strspy")
CLAIMS = {"install_method", "published_image", "bioconda_package", "fallback_environment",
          "run_command", "example_data", "known_issue",
          # Phase C: what the README states about input, read by sentence.
          "documented_input", "author_recommendation", "platform_advice"}
#: Cited by SENTENCE: the text is one statement off a line that may hold two
#: ("designed for Illumina. We do not recommend Nanopore"), so it is contained
#: in the line rather than equal to it.
SENTENCE_CLAIMS = {"documented_input", "author_recommendation", "platform_advice"}


def _proposal(name):
    tree, readme, repo = dr.load_offline(REPOS / name)
    prop = dr.detect(dr.repo_slug(repo), tree["ref"], tree, readme, "README.md")
    return prop, tree, readme


def test_every_evidence_entry_points_at_something_that_exists():
    for name in NAMES:
        prop, tree, readme = _proposal(name)
        paths = {e["path"] for e in tree["tree"]}
        lines = readme.splitlines()
        assert prop["evidence"], f"{name}: a proposal with no evidence at all"
        for e in prop["evidence"]:
            assert e["claim"] in CLAIMS, (name, e["claim"])
            assert e["kind"] in ("tree", "readme"), (name, e)
            if e["kind"] == "tree":
                assert e["path"] in paths, f"{name}: {e['claim']} cites {e['path']}, not in the tree"
            else:
                assert 1 <= e["line"] <= len(lines), f"{name}: {e['claim']} cites README line {e['line']} of {len(lines)}"
            # The URL is what GitHub serves for that file at that ref — and
            # for a README line, it lands on the line.
            expected = f"https://github.com/{dr.repo_slug(prop['repo'])}/blob/{prop['ref']}/{e['path']}"
            assert e["url"].split("#")[0] == expected, (name, e["url"])
            if e["kind"] == "readme":
                assert e["url"].endswith(f"#L{e['line']}"), (name, e["url"])


def test_a_readme_citation_reads_as_quoted():
    """The text shown for a README line is that line, not a paraphrase."""
    for name in NAMES:
        prop, _, readme = _proposal(name)
        lines = readme.splitlines()
        for e in prop["evidence"]:
            if e["kind"] != "readme" or e["claim"] == "known_issue":
                continue
            line = lines[e["line"] - 1].strip()
            if e["claim"] in SENTENCE_CLAIMS:
                assert e["text"] and e["text"] in line, (name, e["claim"], e["line"], e["text"][:60])
            else:
                assert e["text"] == line[:300], (name, e["claim"], e["line"])


def test_the_command_is_cited_where_the_readme_wrote_it():
    """The line a proposal says it read the command on contains that command.

    A joined multi-line command starts on the cited line; its first token
    must be there. This is the check that would have caught "where:" — the
    help listing — being cited as the README's own command."""
    for name in NAMES:
        prop, _, readme = _proposal(name)
        if not prop["commands"]:
            continue
        cmd = prop["commands"][0]
        line = readme.splitlines()[cmd["line"] - 1]
        first = re.split(r"\s+", cmd["cmd"].strip())[0]
        assert first in line, f"{name}: command starts with {first!r} but README line {cmd['line']} is {line!r}"


def test_known_issues_carry_the_url_of_their_line():
    for name in ("strspy", "straitrazor"):
        prop, _, _ = _proposal(name)
        assert prop["known_issues"], name
        for k in prop["known_issues"]:
            assert k["url"].endswith(f"/README.md#L{k['line']}"), (name, k["url"])
