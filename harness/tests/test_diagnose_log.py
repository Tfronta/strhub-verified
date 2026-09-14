"""Diagnostic rules: the real failures still fire, the look-alikes no longer do.

A false positive here is not cosmetic: any `severity: error` turns the badge
yellow with "(errors reported)" on a run whose gates all passed.
"""
import diagnose_log as d


def ids(text):
    return {e["id"]: e for e in d.diagnose(text)}


def test_real_cannot_open_is_counted_per_locus():
    log = "\n".join(
        f"[E::hts_open] cannot open /data/out/{locus}_input.bam: No such file"
        for locus in ("vWA", "TPOX", "FGA")
    )
    got = ids(log)
    assert got["cannot_open"]["severity"] == "error"
    assert got["cannot_open"]["count"] == 3
    assert len(got["cannot_open"]["examples"]) == 3


def test_shell_command_not_found_fires():
    got = ids("bash: line 1: str8rzr: command not found")
    assert got["cmd_not_found"]["examples"] == ["str8rzr"]


def test_docker_exec_not_found_fires():
    got = ids('exec: "GangSTR": executable file not found in $PATH')
    assert got["cmd_not_found"]["examples"] == ["GangSTR"]


def test_not_found_inside_prose_or_usage_does_not_fire():
    assert "cmd_not_found" not in ids("Processing complete: not found any errors")
    assert "cmd_not_found" not in ids("usage: HipSTR --bams: not found means the file list is empty")


def test_help_text_does_not_report_bad_option():
    log = "usage: tool [options]\n  --min-reads N   An invalid option --x will be rejected\n"
    assert "bad_option" not in ids(log)


def test_real_bad_option_fires():
    got = ids("tool: error: unrecognized option '--min-reads'")
    assert got["bad_option"]["examples"] == ["min-reads"]


def test_warning_line_is_a_warning_not_an_error():
    got = ids("WARNING: file /data/in/optional.txt does not exist (optional)")
    assert got["file_not_found"]["severity"] == "warning"


def test_error_among_warnings_stays_an_error():
    log = (
        "WARNING: file /data/in/optional.txt does not exist (optional)\n"
        "ERROR: file /data/in/input.bam does not exist\n"
    )
    assert ids(log)["file_not_found"]["severity"] == "error"


def test_fault_sets_are_disjoint():
    assert not (d.AUTHOR_FIXABLE & d.HARNESS_INCOMPATIBLE)
