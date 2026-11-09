import copy
import json

import pytest
import yaml

import generate_pdf
import report
from command_record import presentation
from test_html_copy_carries_the_report import REPORT


@pytest.mark.parametrize("outcome", ["skipped", "cancelled", "unknown", None])
def test_absent_execution_is_not_presented_as_an_executed_command(outcome):
    r = copy.deepcopy(REPORT)
    r["gates"]["installs"] = False
    r["run"].pop("step_outcome")
    if outcome is not None:
        r["run"]["step_outcome"] = outcome
    for text in (report._summary_html(r, "hipstr"), report._summary_md(r, "hipstr")):
        assert "Planned command" in text
        assert "Executed verbatim" not in text
        assert "Command that ran" not in text


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_attempt_outcome_records_exact_wrapper_without_claiming_program_start(outcome):
    cmd = "cd /opt/tool && missing-program --input /data/in/x.bam"
    r = report._run_record({"run": {"cmd": cmd}}, outcome)
    assert r["effective_cmd"] == cmd and r["step_outcome"] == outcome
    heading, lead = presentation(r)
    assert heading == "Command submitted to runner"
    assert "does not prove the program started" in lead


def test_pdf_uses_recorded_command_instead_of_a_later_manifest_edit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = {"tool": {"name": "Example", "version": "1"}, "report": {"slug": "example"},
                "source": {"repo": "https://github.com/example/tool", "ref": "a" * 40},
                "run": {"cmd": "changed-command"}, "outputs": []}
    mpath = tmp_path / "manifest.yml"
    mpath.write_text(yaml.safe_dump(manifest))
    r = copy.deepcopy(REPORT)
    r["run"] = {"cmd": "original-command", "step_outcome": "skipped"}
    (tmp_path / "example.json").write_text(json.dumps(r))
    cfg = generate_pdf.load_config(str(mpath))
    assert "original-command" in " ".join(cfg["cmd_lines"])
    assert "changed-command" not in " ".join(cfg["cmd_lines"])
    assert cfg["command_presentation"][0] == "Planned command"
