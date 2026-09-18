"""Every tool whose only recipe is STRhub's gets a trial of its repository's
own instructions at the same commit — the run the badge may rest on."""
import subprocess

import documented_refresh as dr


def test_every_committed_recipe_strhub_wrote_is_listed_with_its_commit():
    tools = dr.curated_tools()
    # One trial per repository and commit: hipstr-y and the PowerSeq kit ride
    # with hipstr and the ForenSeq kit, which pin the same commits.
    assert [t["slug"] for t in tools] == ["gangstr", "hipstr", "strait-razor-forenseq", "strsearch", "strspy-ont"]
    assert next(t for t in tools if t["slug"] == "hipstr")["also_for"] == ["hipstr-y"]
    strspy = next(t for t in tools if t["slug"] == "strspy-ont")
    assert strspy["repo"] == "https://github.com/unique379r/strspy"
    assert strspy["ref"] == "dafdee7e7e5672c8dc732e8577dbe153f53a12f5" and strspy["version"] == "v2.0"


def test_a_proposed_or_maintainer_recipe_is_not_listed(tmp_path):
    for slug, recipe in (("prop", {"origin": "proposed"}), ("own", {"origin": "maintainer"}), ("cur", {"origin": "curated"})):
        d = tmp_path / "tools" / slug; d.mkdir(parents=True)
        (d / "manifest.yml").write_text(
            f"tool: {{name: {slug}, version: v1}}\nsource: {{repo: https://github.com/x/{slug}, ref: {'a' * 40}}}\n"
            f"recipe: {recipe}\nenvironment: {{dockerfile: Dockerfile}}\nrun: {{cmd: x}}\noutputs: []\n")
    assert [t["slug"] for t in dr.curated_tools(tmp_path)] == ["cur"]


def test_dispatch_is_a_trial_from_the_url_at_the_pinned_commit_with_its_version():
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    done = dr.dispatch([{"slug": "strspy-ont", "repo": "https://github.com/unique379r/strspy",
                         "ref": "dafdee7e7e5672c8dc732e8577dbe153f53a12f5", "version": "v2.0"}], run=run)
    (cmd,) = calls
    assert "mode=trial" in cmd and "repo=https://github.com/unique379r/strspy" in cmd
    assert "ref=dafdee7e7e5672c8dc732e8577dbe153f53a12f5" in cmd and "ref_label=v2.0" in cmd
    assert "tool=trial-strspy-dafdee7" in cmd and "dispatch_id=doc_dafdee7_strspy-ont" in cmd
    assert not any(a.startswith("recipe=") or a.startswith("publish=") for a in cmd)   # publishes on the usual terms
    assert done[0]["dispatched"]
