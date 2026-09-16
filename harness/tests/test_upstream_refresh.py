"""Newer upstream releases are found from the catalogue and re-run as trials."""
import base64
import json

import retarget_recipe
import upstream_refresh as ur

VERIFIED = "b2033bfbb5cf55496b776463bdf2993fa763a4be"
NEW = "1111111111111111111111111111111111111111"
INDEX = {"tools": [
    {"slug": "hipstr-v0-7", "source_repo": "https://github.com/tfwillems/HipSTR", "source_ref": VERIFIED},
    {"slug": "hipstr-v0-7-y", "source_repo": "https://github.com/tfwillems/HipSTR", "source_ref": VERIFIED},
    {"slug": "other", "source_repo": "https://github.com/x/other", "source_ref": "v1.0"},
]}


def fake_get(path, token):
    routes = {
        "/repos/tfwillems/HipSTR/releases/latest": {"tag_name": "v0.8"},
        f"/repos/tfwillems/HipSTR/commits/v0.8": {"sha": NEW},
        "/repos/x/other/releases/latest": {"__status__": 404},
        "/repos/x/other/tags?per_page=1": [{"name": "v1.0"}],
        "/repos/x/other/commits/v1.0": {"sha": "2" * 40},
    }
    return routes.get(path)


def test_finds_newer_release_once_per_repo_and_skips_current_tools():
    newer = ur.find_newer(INDEX, None, get=fake_get)
    slugs = sorted(n["slug"] for n in newer)
    assert slugs == ["hipstr-v0-7", "hipstr-v0-7-y"]
    assert all(n["latest_tag"] == "v0.8" and n["latest_sha"] == NEW for n in newer)
    # `other` is verified at the tag that IS the latest tag: nothing to do.


def test_retarget_swaps_ref_in_manifest_and_dockerfile_and_renames_slug():
    r = retarget_recipe.retarget("hipstr-v0-7", NEW)
    assert r["slug"] == "hipstr-v0-7-1111111"
    manifest = r["recipe"]["manifest_yml"]
    assert f'ref: "{NEW}"' in manifest and VERIFIED not in manifest
    assert 'slug: "hipstr-v0-7-1111111"' in manifest
    assert f"ARG TOOL_REF={NEW}" in r["recipe"]["dockerfile"]
    # This recipe ships its own regions BED (assets/regions.bed), so retarget
    # carries it along for the trial rather than leaning on a named library.
    assert r["recipe"]["regions_bed"]
    decoded = json.loads(base64.b64decode(r["recipe_b64"]))
    assert decoded["manifest_yml"] == manifest


def test_dispatch_is_a_trial_with_the_retargeted_recipe():
    calls = []

    class R:
        returncode = 0
        stderr = ""

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return R()

    newer = ur.find_newer(INDEX, None, get=fake_get)
    done = ur.dispatch_trials(newer, run=fake_run)
    assert all(d["dispatched"] for d in done)
    assert calls[0][:4] == ["gh", "workflow", "run", "verify.yml"]
    assert "mode=trial" in calls[0]
    assert any(a.startswith("tool=hipstr-v0-7-1111111") for a in calls[0])
    body = ur.issue_body(done)
    assert "hipstr-v0-7" in body and "v0.8" in body and "trial" in body
