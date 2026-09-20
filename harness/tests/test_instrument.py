"""Which instrument a run is, and what each rendering says about it.

The badge may rest only on a run of the repository's own instructions or of
a recipe the maintainer submitted; a recipe STRhub wrote is a note under the
documented result, and every copy of the report says so and lists what that
recipe did that the README does not."""
import html
import json
import pathlib
import subprocess
import sys

import yaml

import certificate_text as ct
import report

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_the_instrument_comes_from_recipe_origin_and_is_derived_for_older_manifests():
    assert ct.instrument_of({"recipe": {"origin": "proposed"}}) == "documented"
    assert ct.instrument_of({"recipe": {"origin": "maintainer"}}) == "maintainer"
    assert ct.instrument_of({"recipe": {"origin": "curated"}}) == "curated"
    # Before recipe.origin: detect_recipe's notes mean a proposal; the
    # maintainer's submission is theirs; anything else STRhub wrote by hand.
    assert ct.instrument_of({"caveats": {"source": "detect_recipe", "items": []}}) == "documented"
    assert ct.instrument_of({"submission": {"by": "maintainer"}}) == "maintainer"
    assert ct.instrument_of({"submission": {"by": "third_party"}}) == "curated"
    assert ct.instrument_of({}) == "curated"
    # A published report carries it; one from before is read the same way.
    assert ct.instrument_of_report({"instrument": "documented"}) == "documented"
    assert ct.instrument_of_report({"caveats": {"source": "detect_recipe"}}) == "documented"


def test_every_committed_recipe_declares_its_origin_and_a_curated_one_its_workarounds():
    """tools/ holds the recipes STRhub wrote by hand AND, since a trial from a
    URL that publishes commits the recipe it ran (verify.yml), recipes the
    engine proposed from the repository — tools/straitrazor is the first.
    Each says which it is; only a curated one owes the list of departures."""
    seen = set()
    for m in sorted((ROOT / "tools").glob("*/manifest.yml")):
        doc = yaml.safe_load(m.read_text())
        origin = doc["recipe"]["origin"]
        assert origin in ("curated", "proposed", "maintainer"), m
        seen.add(origin)
        if origin != "curated":
            assert not doc["recipe"].get("workarounds"), f"{m}: only a curated recipe departs from the README"
            continue
        assert doc["recipe"]["workarounds"], f"{m}: a curated recipe lists what it does that the README does not"
        for w in doc["recipe"]["workarounds"]:
            assert w["what"] and w["instead_of"], m
    assert "curated" in seen


def _report(instrument, workarounds=None):
    r = {"schema": "strhub-verified/1", "tool": {"name": "STRspy", "version": "v2.0"}, "level": "io",
         "gates": {"available": True, "installs": True, "runs": True, "io": True, "content": False},
         "source": {"repo": "https://github.com/unique379r/strspy", "ref_resolved": "dafdee7"},
         "environment": {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"]},
         "generated": "2026-09-18T13:38:00+00:00", "scope": report.SCOPE,
         "instrument": instrument, "recipe": {"origin": {"documented": "proposed"}.get(instrument, instrument)}}
    if workarounds:
        r["recipe"]["workarounds"] = workarounds
    return r


WORKAROUNDS = [{"what": "Runs src/STRspy_Normal_v2.0_Args.sh directly.",
                "instead_of": "The wrapper, the only documented command.",
                "why": "The wrapper checks the repository root for scripts that live in src/ and exits."}]


def test_a_curated_report_opens_with_what_strhub_had_to_do_and_is_not_verified_as_documented():
    r = _report("curated", WORKAROUNDS)
    for text in (report._summary_md(r, "strspy-ont"), html.unescape(report._summary_html(r, "strspy-ont"))):
        assert ct.NOT_DOCUMENTED in text
        assert ct.STRHUB_DID_HEADING in text and ct.AS_IS_HEADING not in text
        assert "Runs src/STRspy_Normal_v2.0_Args.sh directly." in text
        assert "Instead of: The wrapper, the only documented command." in text
        # The chapter comes first; the run follows in full.
        assert text.index(ct.STRHUB_DID_HEADING) < text.index(ct.FULL_RUN_HEADING) < text.index("Gates")


def test_a_documented_report_opens_with_the_tool_as_it_is_and_carries_no_strhub_chapter():
    r = _report("documented")
    for text in (report._summary_md(r, "strspy-ont"), html.unescape(report._summary_html(r, "strspy-ont"))):
        assert ct.AS_IS_HEADING in text
        assert ct.STRHUB_DID_HEADING not in text and ct.NOT_DOCUMENTED not in text
        assert "Runs as documented" in text


def test_the_label_says_the_result_in_words_not_the_rung():
    """One rule for the badge, both copies, the index and the certificate."""
    doc = lambda level, code, **k: {**_report("documented"), "level": level,
                                    "verdict": {"code": code, "title": "", "reason": ""}, **k}
    assert ct.headline(doc("content", "runs")) == ("Runs as documented", "brightgreen")
    assert ct.headline(doc("io", "runs")) == ("Runs as documented", "green")
    assert ct.headline(doc("io", "runs", diagnostics={"external": [{"id": "cannot_open", "severity": "error"}]})) \
        == ("Runs as documented (errors reported)", "yellow")
    assert ct.headline(doc("installs", "fails")) == ("Does not run as documented: stops at run", "red")
    assert ct.headline(doc("available", "fails")) == ("Does not run as documented: stops at install", "red")
    assert ct.headline(doc("runs", "fails")) == ("Does not run as documented: no output", "red")
    assert ct.headline(doc("installs", "undetermined")) == ("Could not be determined", "lightgrey")
    assert ct.headline(doc("installs", "out_of_scope")) == ("Out of scope", "lightgrey")
    # A recipe STRhub wrote, whatever it reached.
    assert ct.headline({**_report("curated"), "level": "content"}) == (ct.NOT_DOCUMENTED, "lightgrey")
    # A report from before the verdict: read off the rung.
    old = {**_report("documented")}; old.pop("verdict", None)
    assert ct.headline({**old, "level": "content"})[0] == "Runs as documented"
    assert ct.headline({**old, "level": "installs"})[0] == "Does not run as documented: stops at run"


def test_the_badge_of_a_curated_run_says_whose_recipe_it_was(tmp_path):
    """The badge travels alone; a green one from a recipe STRhub wrote must
    not read as the tool's own. Run report.py end to end on the STRspy
    manifest with every gate passed and read the badge it writes."""
    manifest = ROOT / "tools" / "strspy-ont" / "manifest.yml"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    res = subprocess.run([sys.executable, str(ROOT / "harness" / "report.py"), "--manifest", str(manifest),
                          "--available", "pass", "--installs", "pass", "--runs", "pass",
                          "--io", str(tmp_path / "no-io.json"), "--content", str(tmp_path / "no-content.json"),
                          "--matrix", str(tmp_path / "no-matrix.json"), "--readme", str(tmp_path / "no-readme.json"),
                          "--example", str(tmp_path / "no-example.json"),
                          "--regions-validation", str(tmp_path / "no-regions.json")],
                         cwd=str(ROOT), capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    written = json.loads((ROOT / "reports" / "strspy-ont.json").read_text())
    badge = json.loads((ROOT / "reports" / "strspy-ont.badge.json").read_text())
    for p in (ROOT / "reports").glob("strspy-ont.*"):
        p.unlink()
    assert written["instrument"] == "curated"
    assert written["recipe"]["origin"] == "curated" and len(written["recipe"]["workarounds"]) == 4
    assert badge["message"] == ct.NOT_DOCUMENTED and badge["color"] == "lightgrey"
    assert any("written by STRhub" in n for n in written["needed_beyond_repo"])
