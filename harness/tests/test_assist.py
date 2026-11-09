"""The retired recipe agent cannot dispatch trials, even through its old CLI."""
import os
import pathlib
import subprocess
import sys

import assist
import assist_report

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_legacy_cli_refuses_even_with_credentials_and_arguments(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "harness" / "assist.py"),
         "--repo", "https://github.com/example/tool", "--ref", "a" * 40,
         "--max-attempts", "8", "--out", str(tmp_path / "result")],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "ANTHROPIC_API_KEY": "synthetic-test-value",
             "GH_TOKEN": "synthetic-test-value"},
    )
    assert result.returncode == 2
    assert "Recipe repair is disabled" in result.stderr
    assert result.stdout == ""
    assert list(tmp_path.iterdir()) == []


def test_imported_entry_point_also_refuses(capsys):
    assert assist.main() == 2
    assert "documented upstream" in capsys.readouterr().err
    assert not hasattr(assist, "Agent")
    assert not hasattr(assist, "GitHubTrials")


def test_historical_reports_remain_readable():
    result = {
        "repo": "https://github.com/example/tool", "ref": "a" * 40,
        "slug": "tool", "model": "historical", "success": True,
        "attempts": [
            {"n": 1, "result": {"verdict": "fails", "run": "https://example/run/1"}},
            {"n": 2, "result": {"verdict": "runs", "run": "https://example/run/2"}},
        ],
        "workarounds": [{"what": "Historical dependency adjustment",
                         "instead_of": "Original install", "why": "Historical note"}],
        "finish": {"summary": "Historical run", "recommendations": ["Document the build."]},
        "usage": {},
        "documented": {"result": {"verdict": "fails", "reason": "build failed",
                                  "run": "https://example/run/0"}},
    }
    text = assist_report.render(result, pr=True)
    assert "| 1 | fails |" in text and "| 2 | runs |" in text
    assert "Historical dependency adjustment" in text
    assert "curated" in text
