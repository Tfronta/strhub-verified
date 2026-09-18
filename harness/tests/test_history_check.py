"""A history check holds each commit to what the issues say, names every
claim that misses, dispatches one trial per case with the right instrument,
and finds each run back by the id in its name."""
import json
import pathlib
import subprocess

import history_check as hc

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHA_A = "e069e19c304720f92587199f66c9e18360e944ef"
SHA_B = "dafdee7e7e5672c8dc732e8577dbe153f53a12f5"


def _doc(**over):
    doc = {"tool": "strspy-ont", "repo": "https://github.com/unique379r/strspy",
           "cases": [
               {"ref": SHA_A, "label": "first v2", "run": "proposed",
                "expect": {"verdict": "fails", "log_contains": "same directory"}},
               {"ref": SHA_B, "label": "after the fixes", "run": "committed",
                "expect": {"verdict": "runs", "level": "io", "diagnostics": ["cannot_open"]}},
           ]}
    doc.update(over)
    return doc


def _report(verdict="runs", level="io", diags=("cannot_open",), install=()):
    return {"schema": "strhub-verified/1", "level": level, "verdict": {"code": verdict},
            "gates": {"available": True, "installs": level != "none", "runs": level in ("runs", "io", "content")},
            "diagnostics": {"external": [{"id": d, "severity": "error"} for d in diags]} if diags else {},
            "install_detail": {"diagnostics": [{"id": d} for d in install]} if install else None}


def test_every_expectation_is_a_separate_claim_and_every_miss_is_named():
    case = _doc()["cases"][1]
    ok = hc.evaluate(case, _report(), {"external": "…"})
    assert ok["ok"] and ok["misses"] == []
    bad = hc.evaluate(case, _report(verdict="fails", level="runs", diags=()), {})
    assert not bad["ok"]
    assert bad["misses"] == ["verdict 'fails', expected 'runs'", "level 'runs', expected 'io'",
                             "diagnostic 'cannot_open' not reported (got none)"]


def test_the_log_is_held_to_what_the_user_saw():
    case = _doc()["cases"][0]
    logs = {"external": "please make sure you are in the same directory of STRspy\n"}
    assert hc.evaluate(case, _report(verdict="fails", level="runs", diags=()), logs)["ok"]
    missing = hc.evaluate(case, _report(verdict="fails", level="runs", diags=()), {"external": "ran fine"})
    assert missing["misses"] == ["log does not contain 'same directory'"]
    gone = {"ref": SHA_B, "run": "proposed", "expect": {"log_not_contains": "same directory"}}
    assert hc.evaluate(gone, _report(), logs)["misses"] == ["log still contains 'same directory'"]


def test_a_run_that_left_no_report_misses_everything_and_says_so():
    r = hc.evaluate(_doc()["cases"][1], None, {})
    assert r["misses"][0] == "no report: the run left no attestation"
    assert not r["ok"]


def test_install_diagnostics_count_as_diagnostics():
    case = {"ref": SHA_A, "run": "committed", "expect": {"diagnostics": ["build_file_missing"]}}
    assert hc.evaluate(case, _report(verdict="fails", level="available", diags=(), install=("build_file_missing",)), {})["ok"]


def test_dispatch_uses_the_committed_recipe_or_the_url_by_instrument():
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    done = hc.dispatch(_doc(), run=run)
    assert [d["id"] for d in done] == ["strspy-ont@e069e19-p", "strspy-ont@dafdee7-c"]
    proposed, committed = calls
    assert "mode=trial" in proposed and f"repo=https://github.com/unique379r/strspy" in proposed
    assert f"ref={SHA_A}" in proposed and "tool=trial-strspy-e069e19" in proposed
    assert "dispatch_id=hc_e069e19_p_strspy-ont" in proposed
    assert not any(a.startswith("recipe=") for a in proposed)
    assert "tool=strspy-ont" in committed and any(a.startswith("recipe=") for a in committed)
    assert not any(a.startswith("repo=") for a in committed)
    assert done[0]["artifact"] == "trial-trial-strspy-e069e19" and done[1]["artifact"] == "trial-strspy-ont"
    # The retargeted recipe pins the case's commit, not the recipe's own.
    recipe = json.loads(__import__("base64").b64decode(next(a for a in committed if a.startswith("recipe="))[7:]))
    assert SHA_B in recipe["manifest_yml"] and SHA_B in recipe["dockerfile"]


def test_runs_are_found_by_the_id_in_their_name_and_waited_for(tmp_path):
    dispatched = [{"id": "strspy-ont@dafdee7-c", "dispatch_id": "hc_dafdee7_c_strspy-ont",
                   "tool": "strspy-ont", "artifact": "trial-strspy-ont", "ref": SHA_B, "run": "committed",
                   "dispatched": True, "error": ""}]
    listings = iter([
        [{"databaseId": 1, "displayTitle": "Trial strspy-ont [hc_dafdee7_c_strspy-ont]", "status": "in_progress", "conclusion": None},
         {"databaseId": 2, "displayTitle": "Trial other [hc_other]", "status": "completed", "conclusion": "success"}],
        [{"databaseId": 1, "displayTitle": "Trial strspy-ont [hc_dafdee7_c_strspy-ont]", "status": "completed", "conclusion": "success"}],
    ])
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(next(listings)), "")
        if cmd[:3] == ["gh", "run", "download"]:
            dest = pathlib.Path(cmd[cmd.index("-D") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "strspy-ont.json").write_text(json.dumps(_report()))
            (dest / "strspy-ont.log-external.txt").write_text("Cannot open file: x.bam")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(cmd)

    slept = []
    done = hc.wait(dispatched, tmp_path / "results", run=run, poll_s=7, sleep=slept.append)
    assert slept == [7]                       # one poll found it running, the next found it done
    assert done[0]["completed"] and done[0]["run_id"] == 1 and done[0]["downloaded"]
    assert ["gh", "run", "download", "1", "-n", "trial-strspy-ont", "-D", str(tmp_path / "results" / "strspy-ont@dafdee7-c")] in calls
    report, logs = hc.read_result(tmp_path / "results" / "strspy-ont@dafdee7-c")
    assert report["level"] == "io" and logs == {"external": "Cannot open file: x.bam"}


def test_the_summary_is_the_table_the_note_is_written_from(tmp_path):
    doc = _doc()
    results = tmp_path / "results"
    a = results / "strspy-ont@e069e19-p"; a.mkdir(parents=True)
    (a / "trial-strspy-e069e19.json").write_text(json.dumps(_report(verdict="fails", level="runs", diags=())))
    (a / "trial-strspy-e069e19.log-external.txt").write_text("please make sure you are in the same directory of STRspy")
    b = results / "strspy-ont@dafdee7-c"; b.mkdir(parents=True)
    (b / "strspy-ont.json").write_text(json.dumps(_report(verdict="runs", level="content", diags=("cannot_open",))))
    rows = hc.evaluate_all(doc, results)
    assert [r["ok"] for r in rows] == [True, False]
    text = hc.summary(doc, rows)
    assert "1/2 as the issues say" in text
    assert "| `e069e19` | first v2 | proposed |" in text and "| yes |" in text
    assert "**no**: level 'content', expected 'io'" in text


def test_the_committed_cases_read_and_validate():
    doc = hc.load_cases(ROOT / "history" / "strspy-ont.yml")
    assert doc["tool"] == "strspy-ont" and len(doc["cases"]) >= 4
    assert {c["run"] for c in doc["cases"]} == {"committed", "proposed"}
    assert all(len(c["ref"]) == 40 for c in doc["cases"])
    assert (ROOT / "tools" / doc["tool"] / "manifest.yml").is_file()
