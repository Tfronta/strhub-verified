"""harness/engine: the gates as one Python runner, a faithful port of the
workflow's bash. Commands go through an executor the tests replace, so what
is checked is WHICH commands run, in what order, under which conditions, and
what the record says about them."""
import json
import pathlib
import subprocess
import sys
import time

import pytest

import report
from engine import record, runner, stages
from engine.executor import Executor

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHA = "a" * 40


def base_plan(**over):
    p = {
        "tool": "x", "ref": SHA, "repo": "https://github.com/o/STRsearch",
        "install_ready": "1", "starts_cmd": "STRsearch --help",
        "example_ready": "0", "example_cmd": "", "cmd": "STRsearch run --out /data/out",
        "dockerdir": "tools/x", "dockerfile": "Dockerfile", "dockerfile_from_repo": "",
        "timeout": "20", "step_timeout": "23", "manifest": "tools/x/manifest.yml",
        "mode": "publish", "input_type": "illumina-bam-hg38",
        "own_ready": "0", "external_ready": "1", "dataset_name": "ds", "fixture_source": "none",
        "supported_loci": "datasets/illumina-bam-hg38/loci.bed",
        "med_fallback_ready": "0", "med_input_type": "", "med_dataset_name": "", "med_supported_loci": "",
    }
    p.update(over)
    return p


class Fake:
    """Records every argv; answers with the scripted exit status per command
    kind (an int, or a callable given the argv and the log path)."""

    def __init__(self, root: pathlib.Path, **rc):
        self.root, self.rc, self.calls = root, rc, []

    @staticmethod
    def kind(argv):
        if argv[0] == "git":
            toks = iter(argv[1:])
            for t in toks:
                if t in ("-C", "-c"):
                    next(toks)
                elif not t.startswith("-"):
                    return "git_" + t
        if argv[0] == "docker":
            return "docker_build"
        if argv[0] == "bash":
            return "run_" + argv[2].removeprefix("strhub_")
        if argv[0] == sys.executable:
            return pathlib.Path(argv[1]).stem
        return argv[0]

    def run(self, argv, *, log=None, timeout=None, cwd=None, env=None):
        self.calls.append(list(argv))
        h = self.rc.get(self.kind(argv), 0)
        rc = h(argv, log) if callable(h) else h
        if argv[0] == "bash":
            # run_container.sh tees the container's output into the log it is given.
            (self.root / argv[4]).parent.mkdir(parents=True, exist_ok=True)
            (self.root / argv[4]).write_text(f"$ {argv[-1]}\n")
        if log:
            with open(log, "a") as f:
                f.write(f"$ {' '.join(argv)}\n")
        return rc

    def output(self, argv, cwd=None):
        return 0, SHA + "\n"

    def kinds(self):
        return [self.kind(c) for c in self.calls]


def stage(rec, name):
    return next(s for s in rec["stages"] if s["stage"] == name)


def go(tmp_path, plan, fake):
    (tmp_path / "work").mkdir(exist_ok=True)
    return runner.run(plan, pathlib.Path("work"), tmp_path, exe=fake, python=sys.executable)


def test_a_failed_available_gate_stops_the_ladder_and_says_so(tmp_path):
    fake = Fake(tmp_path, **{"git_ls-remote": 128})
    rec = go(tmp_path, base_plan(), fake)
    assert stage(rec, "available")["status"] == "failed"
    assert stage(rec, "available")["exit_code"] == 128
    for name in ("installs", "starts", "runs_external"):
        assert stage(rec, name)["status"] == "not_run"
        assert stage(rec, name)["reason"]
    assert "docker_build" not in fake.kinds() and not any(k.startswith("run_") for k in fake.kinds())
    # The checks still look at the (empty) leg, as the workflow's did.
    assert stage(rec, "io_external")["status"] == "failed" or stage(rec, "io_external")["exit_code"] == 0
    assert rec["outcomes"] == {"available": "failure", "installs": "skipped", "runs_own": "skipped",
                               "runs_example": "skipped", "runs_external": "skipped"}
    assert rec["ladder"]["leg"] == "external" and rec["ladder"]["runs"] == "skipped"
    assert (tmp_path / "matrix.json").is_file()


def test_the_order_and_the_conditions_are_the_workflows(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(own_ready="1", example_ready="1", example_cmd="cd /opt/tool && ./run.sh"), fake)
    assert [s["stage"] for s in rec["stages"]] == [
        "available", "installs", "starts",
        "runs_own", "io_own", "content_own",
        "runs_example", "example",
        "runs_external", "io_external", "content_external",
    ]
    assert all(s["status"] == "passed" for s in rec["stages"])
    assert rec["ladder"] == {"leg": "own", "runs": "success", "io": "io_own.json", "content": "content_own.json",
                             "supported_loci": "datasets/illumina-bam-hg38/loci.bed"}
    assert rec["environment_built"] == "primary"
    build = next(c for c in fake.calls if c[:2] == ["docker", "build"])
    assert build == ["docker", "build", "--build-arg", f"STRAITRAZOR_REF={SHA}", "--build-arg", f"TOOL_REF={SHA}",
                     "-f", "tools/x/Dockerfile", "-t", "toolimg:ci", "tools/x"]
    own = next(c for c in fake.calls if c[0] == "bash" and c[2] == "strhub_own")
    assert own[1].endswith("harness/run_container.sh") and own[3:5] == ["20", "work/log_own.txt"]
    assert own[5:5 + len(stages.HARDENING)] == stages.HARDENING
    assert own[-1] == "STRsearch run --out /data/out" and own[-2] == "toolimg:ci"
    assert f"{tmp_path / 'work' / 'in_own'}:/data/in:ro" in own and f"{tmp_path / 'work' / 'out_own'}:/data/out" in own
    assert "--entrypoint" not in own       # the engine's own image: bash -lc is its entrypoint
    assert (tmp_path / "work" / "out_own").stat().st_mode & 0o777 == 0o777
    # No leg runs twice.
    runs = [k for k in fake.kinds() if k.startswith("run_")]
    assert sorted(runs) == ["run_example", "run_external", "run_own", "run_starts"]


def test_a_repository_dockerfile_is_built_at_the_pinned_ref_from_the_directory_it_expects(tmp_path):
    def clone(argv, log):
        src = tmp_path / argv[-1]
        src.mkdir(parents=True)
        (src / "Dockerfile").write_text("FROM python:3\nCOPY ./STRsearch /STRsearch\n")
        return 0
    fake = Fake(tmp_path, git_clone=clone)
    rec = go(tmp_path, base_plan(dockerfile_from_repo="Dockerfile"), fake)
    build = next(c for c in fake.calls if c[:2] == ["docker", "build"])
    assert build[-1] == "work/ctx" and build[build.index("-f") + 1] == "work/ctx/STRsearch/Dockerfile"
    assert fake.kinds()[:7] == ["git_ls-remote", "git_init", "git_fetch", "git_cat-file",
                                "git_clone", "git_checkout", "git_submodule"]
    log = (tmp_path / "work" / "log_build.txt").read_text()
    assert stages.CONTEXT_NOTE % ("Dockerfile", "STRsearch") in log
    # A repository's image has its author's entrypoint: the command still has to reach a shell.
    ext = next(c for c in fake.calls if c[0] == "bash" and c[2] == "strhub_external")
    assert ext[ext.index("--entrypoint") + 1] == "/bin/bash" and ext[-2] == "-lc"
    assert stage(rec, "installs")["status"] == "passed"


def test_a_checkout_that_lands_elsewhere_fails_installs_rather_than_building_the_wrong_commit(tmp_path):
    fake = Fake(tmp_path, git_clone=lambda a, l: (tmp_path / a[-1]).mkdir(parents=True) or 0)
    fake.output = lambda argv, cwd=None: (0, (SHA if argv[-1].endswith("^{commit}") else "b" * 40) + "\n")
    rec = go(tmp_path, base_plan(dockerfile_from_repo="Dockerfile"), fake)
    assert stage(rec, "installs")["status"] == "failed"
    assert "docker_build" not in fake.kinds()
    assert "::error::checked out" in (tmp_path / "work" / "log_build.txt").read_text()


def test_no_install_procedure_means_nothing_is_built_and_the_record_says_why(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(install_ready="0"), fake)
    assert stage(rec, "installs")["status"] == "not_run"
    assert "no install procedure" in stage(rec, "installs")["reason"]
    assert stage(rec, "runs_external")["reason"] == "no image was built"
    assert rec["environment_built"] == ""


def test_the_medical_slice_retry_is_carried_over_as_it_was(tmp_path):
    """Tanda 1 keeps the behaviour; tanda 2 removes it. Until then the record
    has to show BOTH attempts, which the workflow's log never did."""
    work = tmp_path / "work"
    for d in ("in_external", "in_external_med"):
        (work / d).mkdir(parents=True)
    (work / "in_external_med" / "input.bam").write_text("med")

    def run_leg(argv, log):
        out = pathlib.Path(next(a for a in argv if a.endswith(":/data/out")).split(":")[0])
        if argv[2] == "strhub_external_med":
            (out / "called.vcf").write_text("called")
        return 0

    def check_io(argv, log):
        out_dir = tmp_path / argv[3]
        return 0 if (out_dir / "called.vcf").is_file() else 1

    fake = Fake(tmp_path, run_external=run_leg, run_external_med=run_leg, check_io=check_io)
    plan = base_plan(med_fallback_ready="1", med_input_type="illumina-bam-hg38-med",
                     med_dataset_name="ds-med", med_supported_loci="datasets/illumina-bam-hg38-med/loci.bed")
    rec = go(tmp_path, plan, fake)
    ext = stage(rec, "runs_external")
    assert ext["status"] == "passed" and ext["exit_code"] == 0
    assert ext["outputs"]["med_used"] == "1"
    assert ext["outputs"]["retry"]["stage"] == "runs_external_med" and ext["outputs"]["retry"]["promoted"]
    assert rec["med_used"] is True
    assert rec["ladder"]["supported_loci"] == "datasets/illumina-bam-hg38-med/loci.bed"
    assert (work / "out_external" / "called.vcf").is_file() and not (work / "out_external_med").exists()
    assert (work / "in_external" / "input.bam").read_text() == "med" and not (work / "in_external_med").exists()
    promote = next(c for c in fake.calls if "--promote-medical" in c)
    assert promote[-2:] == ["tools/x/manifest.yml", "illumina-bam-hg38-med"]
    assert rec["matrix"][1]["type"] == "illumina-bam-hg38-med" and rec["matrix"][1]["dataset"] == "ds-med"
    content = next(c for c in fake.calls if pathlib.Path(c[1]).stem == "check_content" and "out_external" in c[3])
    assert content[content.index("--panel") + 1] == "datasets/illumina-bam-hg38-med/loci.bed"


def test_without_a_medical_slice_a_failed_external_run_is_run_once(tmp_path):
    fake = Fake(tmp_path, run_external=2)
    rec = go(tmp_path, base_plan(), fake)
    ext = stage(rec, "runs_external")
    assert ext["status"] == "failed" and ext["exit_code"] == 2 and "retry" not in ext["outputs"]
    assert fake.kinds().count("run_external") == 1 and "run_external_med" not in fake.kinds()
    assert rec["outcomes"]["runs_external"] == "failure" and rec["ladder"]["runs"] == "failure"


def test_the_record_is_data_a_reader_can_check(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(), fake)
    record.write(rec, tmp_path / "run_record.json")
    back = record.load(tmp_path / "run_record.json")
    assert back["schema"] == record.SCHEMA
    assert back["plan"] == base_plan() and back["image"] == "toolimg:ci"
    for s in back["stages"]:
        if s["status"] != "not_run":
            assert s["command"] and s["started"] and s["ended"] and s["exit_code"] is not None
        else:
            assert s["reason"] and s["command"] is None


def test_report_takes_its_gate_outcomes_from_the_record(tmp_path):
    rec = {"outcomes": {"available": "success", "installs": "success", "runs_own": "skipped",
                        "runs_example": "failure", "runs_external": "success"},
           "ladder": {"leg": "external", "runs": "success", "io": "io_external.json",
                      "content": "content_external.json", "supported_loci": "datasets/x/loci.bed"},
           "environment_built": "primary"}
    (tmp_path / "run_record.json").write_text(json.dumps(rec))

    class Args:
        available = installs = runs = "fail"; io = "io_result.json"; content = "content_result.json"
        example_runs = "skipped"; environment_built = ""; supported_loci = ""
    a = Args()
    assert report.apply_engine_record(a, str(tmp_path / "run_record.json")) == rec
    assert (a.available, a.installs, a.runs) == ("success", "success", "success")
    assert (a.io, a.content) == ("io_external.json", "content_external.json")
    assert a.example_runs == "failure" and a.environment_built == "primary"
    assert a.supported_loci == "datasets/x/loci.bed"
    # No record: the gates never ran, and every outcome reads as a skipped step's.
    b = Args(); b.available = "pass"
    assert report.apply_engine_record(b, str(tmp_path / "missing.json")) is None
    assert (b.available, b.installs, b.runs, b.example_runs) == ("skipped",) * 4


def test_prepare_writes_the_plan_it_printed(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "harness" / "prepare.py"), "straitrazor",
                          "--work", str(tmp_path / "work"), "--plan-out", str(tmp_path / "plan.json")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    printed = dict(ln.split("=", 1) for ln in out.stdout.splitlines() if "=" in ln)
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan.pop("tool") == "straitrazor"
    assert plan == printed


def test_the_backstop_stops_a_hung_command_and_says_so(tmp_path):
    log = tmp_path / "log.txt"
    t0 = time.monotonic()
    rc = Executor().run(["sleep", "30"], log=log, timeout=1)
    assert rc == 124 and time.monotonic() - t0 < 25
    assert "STRhub: the step backstop stopped `sleep`" in log.read_text()


def test_the_cli_writes_the_record(tmp_path, monkeypatch):
    plan = base_plan(install_ready="0")
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    monkeypatch.setattr(runner, "Executor", lambda: Fake(tmp_path, **{"git_ls-remote": 1}))
    from engine import __main__ as cli
    rc = cli.main(["run", "--plan", str(tmp_path / "plan.json"), "--work", "work",
                   "--root", str(tmp_path), "--record", str(tmp_path / "run_record.json")])
    assert rc == 0
    rec = json.loads((tmp_path / "run_record.json").read_text())
    assert rec["outcomes"]["available"] == "failure" and rec["tool"] == "x"
