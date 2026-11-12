"""harness/engine: the gates as one Python runner, a port of the workflow's
bash under the upstream-fidelity profile. Commands go through an executor
the tests replace, so what is checked is WHICH commands run, in what order,
under which conditions, and what the record says about them."""
import json
import pathlib
import subprocess
import sys
import time

import report
from engine import record, runner, stages
from engine.executor import Executor
from engine.record import StageResult

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHA = "a" * 40


def base_plan(**over):
    p = {
        "tool": "x", "ref": SHA, "repo": "https://github.com/o/Tool",
        "procedure_ready": "1", "install_ready": "1", "installation_profile": "",
        "starts_cmd": "", "example_ready": "0", "example_cmd": "",
        "cmd": "tool --reads /data/in/input.bam --output result.vcf",
        "dockerdir": "tools/x", "dockerfile": "Dockerfile", "dockerfile_from_repo": "Dockerfile",
        "timeout": "20", "step_timeout": "23", "manifest": "tools/x/manifest.yml",
        "mode": "publish", "input_type": "illumina-bam-hg38", "own_ready": "0",
        "external_ready": "1", "dataset_name": "ds", "input_failure": "",
        "supported_loci": "datasets/illumina-bam-hg38/loci.bed",
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
        if argv[0] == "bash" and argv[1].endswith("record_terminal.sh"):
            return "docker_build"
        if argv[0] == "bash":
            return "run_" + argv[2].removeprefix("strhub_")
        if argv[0] == sys.executable:
            return pathlib.Path(argv[1]).stem
        return argv[0]

    def _answer(self, argv, log):
        self.calls.append(list(argv))
        h = self.rc.get(self.kind(argv), 0)
        return h(argv, log) if callable(h) else h

    def run(self, argv, *, log=None, timeout=None, cwd=None, env=None):
        rc = self._answer(argv, log)
        if self.kind(argv).startswith("run_"):
            # run_container.sh records into the log it is given.
            (self.root / argv[4]).parent.mkdir(parents=True, exist_ok=True)
            (self.root / argv[4]).write_text(f"$ {argv[-1]}\n")
        if log:
            with open(log, "a") as f:
                f.write(f"$ {' '.join(argv)}\n")
        return rc

    def output(self, argv, cwd=None):
        rc = self._answer(argv, None)
        if self.kind(argv) == "git_rev-parse":
            return 0, SHA + "\n"
        return rc, "" if rc == 0 else "Input provenance could not be established: test\n"

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
    assert stage(rec, "available")["status"] == "failed" and stage(rec, "available")["exit_code"] == 128
    for name in ("installs", "starts", "runs_example", "runs_external", "io_external", "content_external"):
        assert stage(rec, name)["status"] == "not_run" and stage(rec, name)["reason"]
    assert "docker_build" not in fake.kinds() and not any(k.startswith("run_") for k in fake.kinds())
    assert rec["outcomes"] == {"available": "failure", "installs": "skipped",
                               "runs_example": "skipped", "runs_external": "skipped"}
    assert rec["ladder"]["leg"] == "external" and rec["ladder"]["runs"] == "skipped"
    assert rec["infra_failure"] == "" and rec["evidence"] == {"source": "", "input": ""}
    assert (tmp_path / "matrix.json").is_file()


def test_the_order_the_conditions_and_the_commands_are_the_workflows(tmp_path):
    fake = Fake(tmp_path)
    plan = base_plan(example_ready="1", example_cmd="cd . && ./run.sh")
    rec = go(tmp_path, plan, fake)
    assert [s["stage"] for s in rec["stages"]] == [
        "available", "installs", "starts", "runs_example", "example",
        "runs_external", "io_external", "content_external",
    ]
    assert stage(rec, "starts")["status"] == "not_run"       # no --help is invented
    assert all(s["status"] == "passed" for s in rec["stages"] if s["stage"] != "starts")
    # Installs: the clone at the pinned ref, the path and evidence checks, then ONE build.
    assert fake.kinds()[:9] == ["git_ls-remote", "git_init", "git_fetch", "git_cat-file",
                                "git_clone", "git_checkout", "git_rev-parse", "git_rev-parse", "_paths"]
    assert fake.kinds()[9] == "fidelity" and fake.kinds().count("docker_build") == 1
    fid = next(c for c in fake.calls if pathlib.Path(c[1]).stem == "fidelity")
    assert fid[2:] == ["--checkout", "work/ctx/Tool", "--review", "work/procedure_review.json",
                       "--manifest", "tools/x/manifest.yml"]
    build = next(c for c in fake.calls if c[0] == "bash" and c[1].endswith("record_terminal.sh"))
    assert build[2:] == ["work/log_build.txt", "docker", "build", "-f", "work/ctx/Tool/Dockerfile",
                         "-t", "toolimg:ci", "work/ctx/Tool"]
    assert "--build-arg" not in build and "submodule" not in " ".join(fake.kinds())
    assert stage(rec, "installs")["outputs"] == {"source_evidence": "verified", "environment": "primary"}
    # The external leg: provenance first, then one container on the verified mount.
    prov = next(c for c in fake.calls if pathlib.Path(c[1]).stem == "input_provenance")
    assert prov[2:] == ["--work", "work", "--manifest", "tools/x/manifest.yml", f"--command={plan['cmd']}"]
    ext = next(c for c in fake.calls if c[0] == "bash" and c[2] == "strhub_external")
    assert ext[3:5] == ["20", "work/log_external.txt"] and ext[5:5 + len(stages.HARDENING)] == stages.HARDENING
    assert ext[-2:] == ["toolimg:ci", plan["cmd"]] and "--entrypoint" not in ext
    assert f"{tmp_path / 'work' / 'in_external'}:/data/in:ro" in ext and "/data/ref" not in " ".join(ext)
    assert (tmp_path / "work" / "out_external").stat().st_mode & 0o777 == 0o777
    assert stage(rec, "runs_external")["outputs"]["input_evidence"] == "verified"
    content = next(c for c in fake.calls if pathlib.Path(c[1]).stem == "check_content")
    assert content[-2:] == ["--panel", "datasets/illumina-bam-hg38/loci.bed"] and "--regions" not in content
    # No leg runs twice.
    assert sorted(k for k in fake.kinds() if k.startswith("run_")) == ["run_example", "run_external"]
    assert rec["ladder"] == {"leg": "external", "runs": "success", "io": "io_external.json",
                             "content": "content_external.json", "supported_loci": "datasets/illumina-bam-hg38/loci.bed",
                             "input_type": "illumina-bam-hg38", "dataset": "ds"}
    assert rec["environment_built"] == "primary" and rec["infra_failure"] == ""
    assert [l["leg"] for l in rec["matrix"]] == ["external", "example"]


def test_a_source_install_profile_builds_the_verified_carrier_from_work(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(dockerfile_from_repo="", installation_profile=stages.SOURCE_INSTALL_PROFILE), fake)
    fid = next(c for c in fake.calls if pathlib.Path(c[1]).stem == "fidelity")
    carrier = str(tmp_path / "work" / "source-install.Dockerfile")
    assert fid[-2:] == ["--source-install-dockerfile", carrier] and "_paths" not in fake.kinds()
    build = next(c for c in fake.calls if c[1].endswith("record_terminal.sh"))
    assert build[build.index("-f") + 1] == carrier and build[-1] == "work/ctx/Tool"
    assert stage(rec, "installs")["status"] == "passed"


def test_no_proven_installation_is_refused_before_git_and_docker(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(dockerfile_from_repo="", installation_profile=""), fake)
    ins = stage(rec, "installs")
    assert ins["status"] == "failed" and ins["exit_code"] == 1 and ins["command"] is None
    assert ins["outputs"] == {"source_evidence": "unverified"}
    assert "git_clone" not in fake.kinds() and "docker_build" not in fake.kinds()
    assert "no proven upstream installation" in (tmp_path / "work" / "log_build.txt").read_text()
    assert rec["infra_failure"] == "the upstream procedure evidence check before Docker"
    assert stage(rec, "runs_external")["reason"] == "no image was built"


def test_evidence_that_differs_stops_installs_before_docker_and_is_ours(tmp_path):
    fake = Fake(tmp_path, fidelity=lambda a, l: 1)
    rec = go(tmp_path, base_plan(), fake)
    ins = stage(rec, "installs")
    assert ins["status"] == "failed" and ins["outputs"] == {"source_evidence": "unverified", "failed_check": "fidelity.py"}
    assert "docker_build" not in fake.kinds()
    assert rec["infra_failure"] == "the upstream procedure evidence check before Docker"
    assert rec["outcomes"]["installs"] == "failure"


def test_a_build_that_fails_after_verified_evidence_is_the_tools_finding(tmp_path):
    fake = Fake(tmp_path, docker_build=23)
    rec = go(tmp_path, base_plan(), fake)
    ins = stage(rec, "installs")
    assert ins["status"] == "failed" and ins["exit_code"] == 23
    assert ins["outputs"] == {"source_evidence": "verified"} and rec["environment_built"] == ""
    assert rec["infra_failure"] == ""
    assert fake.kinds().count("docker_build") == 1          # built once, nothing instead


def test_an_unverified_mount_never_launches_the_container(tmp_path):
    fake = Fake(tmp_path, input_provenance=1)
    rec = go(tmp_path, base_plan(), fake)
    ext = stage(rec, "runs_external")
    assert ext["status"] == "failed" and ext["exit_code"] == 1
    assert ext["outputs"]["input_evidence"] == "unverified" and "could not be established" in ext["outputs"]["provenance"]
    assert "run_external" not in fake.kinds()
    assert stage(rec, "io_external")["status"] == "not_run" and stage(rec, "content_external")["status"] == "not_run"
    assert rec["ladder"]["runs"] == "skipped" and rec["outcomes"]["runs_external"] == "failure"
    assert rec["infra_failure"] == "the mounted dataset provenance check"


def test_a_failed_run_is_run_once_and_keeps_its_exit_status(tmp_path):
    fake = Fake(tmp_path, run_external=17)
    rec = go(tmp_path, base_plan(), fake)
    ext = stage(rec, "runs_external")
    assert ext["status"] == "failed" and ext["exit_code"] == 17 and ext["outputs"]["input_evidence"] == "verified"
    assert fake.kinds().count("run_external") == 1
    assert stage(rec, "io_external")["status"] in ("passed", "failed")   # the checks still look
    assert rec["ladder"]["runs"] == "failure" and rec["infra_failure"] == ""


def test_the_record_is_data_a_reader_can_check(tmp_path):
    fake = Fake(tmp_path)
    rec = go(tmp_path, base_plan(), fake)
    record.write(rec, tmp_path / "run_record.json")
    back = record.load(tmp_path / "run_record.json")
    assert back["schema"] == record.SCHEMA and back["plan"] == base_plan() and back["image"] == "toolimg:ci"
    for s in back["stages"]:
        if s["status"] != "not_run":
            assert s["started"] and s["ended"] and s["exit_code"] is not None
        else:
            assert s["reason"] and s["command"] is None


def test_report_takes_its_gate_outcomes_and_the_evidence_failure_from_the_record(tmp_path):
    rec = {"outcomes": {"available": "success", "installs": "failure", "runs_example": "skipped",
                        "runs_external": "skipped"},
           "ladder": {"leg": "external", "runs": "skipped", "io": "io_external.json",
                      "content": "content_external.json", "supported_loci": "datasets/x/loci.bed"},
           "environment_built": "", "infra_failure": "the upstream procedure evidence check before Docker"}
    (tmp_path / "run_record.json").write_text(json.dumps(rec))

    class Args:
        available = installs = runs = "fail"; io = "io_result.json"; content = "content_result.json"
        example_runs = "skipped"; environment_built = ""; supported_loci = ""; infra_failure = ""
    a = Args()
    assert report.apply_engine_record(a, str(tmp_path / "run_record.json")) == rec
    assert (a.available, a.installs, a.runs, a.example_runs) == ("success", "failure", "skipped", "skipped")
    assert (a.io, a.content, a.supported_loci) == ("io_external.json", "content_external.json", "datasets/x/loci.bed")
    assert a.infra_failure == "the upstream procedure evidence check before Docker"
    # The workflow's own reason (a step before the gates) wins over the record's.
    b = Args(); b.infra_failure = "the staging of inputs"
    report.apply_engine_record(b, str(tmp_path / "run_record.json"))
    assert b.infra_failure == "the staging of inputs"
    # No record: the gates never ran, and every outcome reads as a skipped step's.
    c = Args(); c.available = "pass"
    assert report.apply_engine_record(c, str(tmp_path / "missing.json")) is None
    assert (c.available, c.installs, c.runs, c.example_runs) == ("skipped",) * 4


def test_starts_is_judged_by_its_check_not_by_the_raw_exit_status(tmp_path):
    def check_starts(argv, log):
        (tmp_path / "starts.json").write_text(json.dumps({"applicable": True, "passed": True}))
        return 0
    fake = Fake(tmp_path, run_starts=1, check_starts=check_starts)
    rec = go(tmp_path, base_plan(starts_cmd="tool --help"), fake)
    st = stage(rec, "starts")
    assert st["status"] == "passed" and st["exit_code"] == 1
    assert "--entrypoint" not in next(c for c in fake.calls if c[0] == "bash" and c[2] == "strhub_starts")


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


def test_the_executor_keeps_what_a_check_said_on_stderr(tmp_path):
    rc, said = Executor().output([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"])
    assert rc == 3 and "out" in said and "err" in said


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
