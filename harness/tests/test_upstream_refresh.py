"""Newer upstream releases are found from the catalogue and re-run as trials."""
import upstream_refresh as ur

VERIFIED = "b2033bfbb5cf55496b776463bdf2993fa763a4be"
NEW = "1111111111111111111111111111111111111111"
INDEX = {"tools": [
    {"slug": "hipstr", "source_repo": "https://github.com/tfwillems/HipSTR", "source_ref": VERIFIED},
    {"slug": "hipstr-y", "source_repo": "https://github.com/tfwillems/HipSTR", "source_ref": VERIFIED},
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
    assert slugs == ["hipstr", "hipstr-y"]
    assert all(n["latest_tag"] == "v0.8" and n["latest_sha"] == NEW for n in newer)
    # `other` is verified at the tag that IS the latest tag: nothing to do.


def test_dispatch_uses_the_new_commit_and_its_own_procedure():
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
    assert len(calls) == 1
    assert {"tool=trial-hipstr-1111111", f"ref={NEW}", "repo=https://github.com/tfwillems/HipSTR",
            "ref_label=v0.8", "publish=false"} <= set(calls[0])
    assert not any(a.startswith("recipe=") for a in calls[0])
    body = ur.issue_body(done)
    assert "hipstr" in body and "v0.8" in body and "trial" in body
