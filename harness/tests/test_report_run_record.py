"""The report carries the command the gates ran.

The certificate has printed it since the start ("Exact Run Command"); the JSON
never had it, so the page — which most readers see — could not show what was
executed without sending them to the log."""
import report
from prepare import example_wrapper


def test_a_committed_manifest_command_is_recorded_as_written():
    m = {"run": {"cmd": "GangSTR --bam /data/in/input.bam --out /data/out/output", "timeout_minutes": 20}}
    assert report._run_record(m) == {"cmd": "GangSTR --bam /data/in/input.bam --out /data/out/output"}


def test_a_proposed_recipe_records_the_tools_command_not_the_wrapper():
    inner = "./HipSTR --bams /data/in/input.bam --str-vcf str_calls.vcf.gz"
    m = {"run": {"cmd": example_wrapper(inner, "/opt/tool")}}
    assert report._run_record(m) == {"cmd": inner, "cwd": "/opt/tool"}


def test_no_command_records_nothing():
    assert report._run_record({}) is None
    assert report._run_record({"run": {"cmd": ""}}) is None
