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


def test_apt_installing_libsigsegv_is_not_a_crash():
    # A toolchain install lists this package seven times in a build log; it is
    # not a segfault, and read as one it hid the real cause of a failed build.
    log = ("#6 6.855   librhash0 librtmp1 libsasl2-2 libsigsegv2 libssh-4\n"
           "#6 17.02 Unpacking libsigsegv2:amd64 (2.13-1ubuntu3) ...\n"
           "#6 20.56 Setting up libsigsegv2:amd64 (2.13-1ubuntu3) ...\n")
    assert "segfault" not in ids(log)
    assert ids("Program received signal SIGSEGV, Segmentation fault.")["segfault"]["count"] == 1
    assert "segfault" in ids("./GangSTR: Segmentation fault (core dumped)")


def test_autotools_missing_aux_files_is_named_with_the_file():
    log = ("#10 31.91 configure.ac: error: required file 'config.sub' not found\n"
           "#10 31.91 configure.ac: error: required file 'config.guess' not found\n"
           "make[2]: *** [CMakeFiles/htslib.dir/build.make:124: htslib-update] Error 1\n")
    got = ids(log)
    assert got["autotools_aux_missing"]["count"] == 2
    assert got["autotools_aux_missing"]["examples"] == ["config.sub", "config.guess"]
    assert "autoreconf" in got["autotools_aux_missing"]["suggestion"]


def test_a_build_that_runs_autoconf_without_install_is_the_repositorys_to_fix():
    # GangSTR's CMakeLists runs plain `autoreconf` on htslib 1.11, which needs
    # `autoreconf -i`; the step is the repository's own and the fix is one flag.
    # Unclassified, the report said "the cause could not be classified", which
    # told the maintainer nothing.
    log = ("#10 33.43 configure.ac: error: required file 'config.sub' not found\n"
           "#10 33.44 configure.ac: error: required file 'config.guess' not found\n"
           "#10 33.44 configure.ac:   try running autoreconf --install\n")
    assert "autotools_aux_missing" in ids(log)
    assert d.fault_of("autotools_aux_missing") == "author"
    assert "Re-verifying after correcting them is free" in d.install_fault_sentence(["author"])
