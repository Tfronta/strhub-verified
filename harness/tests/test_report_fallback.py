"""What the report says when plan B ran: the build log is split at the marker
the Installs step writes, and every rendering names the environment that ran."""
import report

ENV = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated",
       "fallback": {"dockerfile": "Dockerfile.fallback",
                    "reason": "the published image gymreklab/str-toolkit the README points at"}}


def test_environment_line_names_plan_b_only_when_it_ran():
    assert report._environment_line(ENV) == "ubuntu-22.04 (`Dockerfile`)"
    line = report._environment_line({**ENV, "fallback_used": True})
    assert line.startswith("ubuntu-22.04 (`Dockerfile`); plan B: the published image gymreklab/str-toolkit")
    assert line.endswith("(`Dockerfile.fallback`), after the build from the pinned commit failed")
    html = report._environment_line({**ENV, "fallback_used": True}, code=lambda t: f"<code>{t}</code>")
    assert "<code>Dockerfile.fallback</code>" in html and "`" not in html


def test_primary_build_log_stops_at_the_marker(tmp_path):
    log = tmp_path / "log_build.txt"
    log.write_text("step 1\nfatal error: gsl/gsl_rng.h: No such file or directory\n"
                   f"\n{report.FALLBACK_MARKER} (Dockerfile.fallback) ====\n\n"
                   "fatal error: other.h: No such file or directory\nSuccessfully built\n")
    primary = report._primary_build_log(str(log))
    assert "gsl_rng.h" in primary and "other.h" not in primary
    assert report._primary_build_log(str(tmp_path / "absent.txt")) == ""


def test_install_section_says_in_plain_words_what_ran_when_plan_b_did():
    assert report._install_heading({"fallback_used": True}) == (
        "It did not build from source; the run used the README's ready-made environment")
    assert report._install_heading({}) == "It did not build from source"
    lead = report._install_lead({"fallback_used": True}, ENV)
    assert lead.startswith("STRhub tried to build the tool from its source at the pinned commit")
    assert "The published image gymreklab/str-toolkit the README points at was used instead" in lead
    assert lead.endswith("every gate below ran on it.")
    assert report._install_lead({}, ENV).endswith("Nothing below the Installs gate ran.")


def test_every_rendering_tells_each_reader_what_a_failed_build_means():
    """The mechanism ("plan B: the published image … after the build from the
    pinned commit failed") is the engine's business. A reader is one of three
    people, and each needs the finding in their own terms."""
    rep = {
        "tool": {"name": "GangSTR"}, "level": "content",
        "gates": {"available": True, "installs": True, "runs": True, "io": True, "content": True},
        "source": {"repo": "https://github.com/gymreklab/gangstr", "ref_resolved": "e368b9f"},
        "environment": {**ENV, "fallback_used": True},
        "generated": "2026-09-17T12:48:47+00:00", "scope": report.SCOPE,
        "install_detail": {"passed": True, "fallback_used": True, "faults": ["author"],
                           "diagnostics": [{"id": "autotools_aux_missing", "severity": "error",
                                            "title": "An autotools build is missing its auxiliary file: config.sub",
                                            "suggestion": "run autoreconf -fi", "count": 4}]},
    }
    for text in (report._summary_md(rep, "gangstr"), report._summary_html(rep, "gangstr")):
        assert "What this means" in text
        assert "If you are trying to run it" in text
        assert "The ready-made environment the README points at does work" in text
        assert "If you are reviewing a paper" in text
        assert "not the pinned commit, which is the version a manuscript would cite" in text
        assert "If you maintain it" in text
        assert "Re-verifying after correcting them is free" in text
        assert "What failed" in text and "config.sub" in text
