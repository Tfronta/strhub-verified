"""The picker's own selftest, run under pytest so one command covers the harness."""
import subprocess
import sys
import pathlib


def test_selftest_passes():
    script = pathlib.Path(__file__).resolve().parents[1] / "pick_tools.py"
    subprocess.run([sys.executable, str(script), "--selftest"], check=True)
