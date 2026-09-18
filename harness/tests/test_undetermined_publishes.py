"""An undetermined run publishes, and says what it is on the badge.

A run nobody knew how to complete measured the documentation, not the tool.
It used to be held back from gh-pages until the web could show "could not be
determined" as a card (docs/PLAN-Documented-Is-The-Badge.md, decision 5);
tanda 5b is that card, so the deploy gate lets the verdict through — and the
badge, the one artifact that travels alone, carries the verdict instead of
the rung the run happened to reach."""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_the_deploy_gate_publishes_undetermined_and_never_out_of_scope():
    wf = (ROOT / ".github" / "workflows" / "verify.yml").read_text()
    m = re.search(r'publishable = \(verdict in \(([^)]*)\)', wf)
    assert m, "the attestation step decides `publishable` from the verdict"
    verdicts = set(re.findall(r'"(\w+)"', m.group(1)))
    assert verdicts == {"runs", "fails", "undetermined"}


def test_the_badge_of_an_undetermined_run_says_so_not_the_rung_it_reached(tmp_path):
    """report.py end to end with a proposal whose README was not enough to
    attempt the run: the gates say Installs, the badge says the verdict."""
    manifest = ROOT / "tools" / "strspy-ont" / "manifest.yml"
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({
        "schema": "strhub-verified/recipe-proposal/1",
        "readme": {"gaps": [{"item": "command", "text": "no command line invoking the tool"}],
                   "sufficient_to_attempt": False},
        "limitations": [],
    }))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    res = subprocess.run([sys.executable, str(ROOT / "harness" / "report.py"), "--manifest", str(manifest),
                          "--available", "pass", "--installs", "pass", "--runs", "fail",
                          "--io", str(tmp_path / "no-io.json"), "--content", str(tmp_path / "no-content.json"),
                          "--matrix", str(tmp_path / "no-matrix.json"), "--readme", str(tmp_path / "no-readme.json"),
                          "--example", str(tmp_path / "no-example.json"),
                          "--regions-validation", str(tmp_path / "no-regions.json"),
                          "--recipe-proposal", str(proposal)],
                         cwd=str(ROOT), capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    written = json.loads((ROOT / "reports" / "strspy-ont.json").read_text())
    badge = json.loads((ROOT / "reports" / "strspy-ont.badge.json").read_text())
    for p in (ROOT / "reports").glob("strspy-ont.*"):
        p.unlink()
    assert written["level"] == "installs"
    assert written["verdict"]["code"] == "undetermined"
    assert badge["message"].startswith("Could not be determined")
    assert badge["color"] == "lightgrey"
