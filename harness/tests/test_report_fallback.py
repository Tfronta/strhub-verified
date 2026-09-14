"""What the report says when plan B ran: the build log is split at the marker
the Installs step writes, and every rendering names the environment that ran."""
import report

ENV = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated",
       "fallback": {"dockerfile": "Dockerfile.fallback",
                    "reason": "the published image gymreklab/str-toolkit the README points at"}}


def test_environment_line_names_plan_b_only_when_it_ran():
    assert report._environment_line(ENV) == "ubuntu-22.04 (`Dockerfile`)"
    line = report._environment_line({**ENV, "fallback_used": True})
    assert line.startswith("ubuntu-22.04 (`Dockerfile`) — plan B: the published image gymreklab/str-toolkit")
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


def test_install_section_is_about_the_pinned_commit_when_plan_b_ran():
    assert report._install_heading({"fallback_used": True}) == "Why the pinned commit did not build"
    assert report._install_heading({}) == "Why the environment did not build"
    lead = report._install_lead({"fallback_used": True}, ENV)
    assert "gymreklab/str-toolkit" in lead and "every gate below ran on it" in lead
    assert report._install_lead({}, ENV).endswith("nothing below the Installs gate ran.")
