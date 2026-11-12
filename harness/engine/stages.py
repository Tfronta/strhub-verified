"""The gates, one function each: a port, command for command, of the steps
verify.yml ran as bash under the upstream-fidelity profile.

Every function takes the run context and the results it is conditioned on,
and returns a StageResult. The conditions are the workflow's `if:` lines, said
as reasons; the commands are the workflow's commands, argv for argv. Files land
where the workflow put them (logs under <work>/, check results next to the
repository root) so report.py reads the same paths it always did.

What a gate never does: run a thing twice, build a second environment, pick
another dataset, edit the recipe or the clone, or decide anything about the
verdict. Before Docker, the checked-out source is compared with the reviewed
evidence (`harness/fidelity.py`); before a run, the mounted dataset with its
registered bytes (`harness/input_provenance.py`). A check that fails stops the
gate there, with its output in the record, and nothing is tried instead.
"""
from __future__ import annotations

import dataclasses
import os
import pathlib
import shutil
import sys
import tempfile

from .executor import Executor
from .record import StageResult

#: The container runs with every capability dropped, no network, and ceilings
#: on memory, CPU and processes.
HARDENING = [
    "--network", "none",
    "--memory", "6g", "--memory-swap", "6g",
    "--cpus", "2",
    "--pids-limit", "512",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
]
IMAGE = "toolimg:ci"
#: The workflow's `timeout-minutes` on the Starts step.
STARTS_BACKSTOP_MINUTES = 5
#: The literal source-installation transcript profile (harness/source_install.py).
SOURCE_INSTALL_PROFILE = "strhub-source-install/1"
SOURCE_INSTALL_DOCKERFILE = "source-install.Dockerfile"


@dataclasses.dataclass
class Ctx:
    plan: dict
    work: pathlib.Path          # as given (`work`): what the check scripts are told
    root: pathlib.Path          # the engine repository; cwd of every command
    exe: Executor
    python: str = sys.executable
    #: Where the check results and the matrix are written (relative to root,
    #: or absolute): the repository root in CI, a scratch directory locally.
    results: pathlib.Path = pathlib.Path(".")
    #: The image tag and the container-name prefix: fixed in CI, per trial
    #: locally so two trials on one machine do not share them.
    image: str = IMAGE
    container_prefix: str = "strhub"

    def result(self, name: str) -> str:
        return str(self.results / name)

    def result_abs(self, name: str) -> pathlib.Path:
        p = self.results / name
        return p if p.is_absolute() else self.root / p

    @property
    def work_abs(self) -> pathlib.Path:
        # `$PWD/work`: what the container is given to mount.
        return self.work if self.work.is_absolute() else self.root / self.work

    def harness(self, name: str) -> str:
        return str(self.root / "harness" / name)

    @property
    def manifest(self) -> str:
        return self.plan["manifest"]

    @property
    def from_repo(self) -> str:
        return self.plan.get("dockerfile_from_repo") or ""

    def ready(self, key: str) -> bool:
        return str(self.plan.get(key, "")) == "1"


def _say(log: pathlib.Path | None, text: str) -> None:
    """A line of our own, to the CI log and the stage's log file."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    if log is not None:
        with open(log, "a") as f:
            f.write(text + "\n")


def _truncate(path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def _load(path: pathlib.Path):
    import json
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:  # noqa: BLE001
        return None


# --- Gate: Available ---------------------------------------------------------

def available(ctx: Ctx) -> StageResult:
    """The repository answers, and the pinned commit is one IT serves, from its
    own branches or tags. GitHub's API resolves a SHA that exists only in a
    fork, and a report naming this repository must not attest a commit it does
    not hold. Commits and trees only (no blobs), so this stays small."""
    repo, ref = ctx.plan["repo"], ctx.plan["ref"]
    log = _truncate(ctx.work_abs / "log_available.txt")
    st = StageResult.start("available", log)
    argv = ["git", "ls-remote", "--", repo]
    rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
    if rc != 0:
        return st.finish(rc, argv)
    # In a temp dir never cleaned up by hand: git's background maintenance can
    # still be writing into it, and a failed `rm` here once failed the gate and
    # read as the tool's source being unavailable.
    av = pathlib.Path(tempfile.mkdtemp(prefix="strhub-avail-", dir=os.environ.get("RUNNER_TEMP") or None))
    for argv in (
        ["git", "init", "-q", str(av)],
        ["git", "-C", str(av), "-c", "gc.auto=0", "-c", "maintenance.auto=false", "fetch", "-q",
         "--no-auto-gc", "--filter=blob:none", "--tags", "--", repo, "+refs/heads/*:refs/remotes/origin/*"],
    ):
        rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
        if rc != 0:
            return st.finish(rc, argv)
    for spec in (f"{ref}^{{commit}}", f"origin/{ref}^{{commit}}"):
        argv = ["git", "-C", str(av), "cat-file", "-e", spec]
        if ctx.exe.run(argv, log=log, cwd=ctx.root) == 0:
            _say(log, f"pinned ref {ref} is in {repo}")
            return st.finish(0, argv)
    _say(log, f"::error::the pinned ref {ref} is not a commit on any branch or tag of {repo}")
    return st.finish(1, argv)


# --- Gate: Installs (docker build) ------------------------------------------

def installs(ctx: Ctx, available_result: StageResult) -> StageResult:
    """`docker build`, once, of the one environment the review admits: the
    repository's own Dockerfile at the pinned ref, or the literal
    source-installation transcript it cites. Before Docker, the checkout is
    compared with the reviewed evidence; a difference stops the gate with
    `source_evidence: unverified`, which the report counts as STRhub's
    inability to establish the procedure, never as the tool failing."""
    if not available_result.passed:
        return StageResult.not_run("installs", "the pinned source is not available")
    if not ctx.ready("install_ready"):
        return StageResult.not_run("installs", "the review admits no upstream install procedure to build")
    repo, ref = ctx.plan["repo"], ctx.plan["ref"]
    log = _truncate(ctx.work_abs / "log_build.txt")
    st = StageResult.start("installs", log)
    outputs: dict = {"source_evidence": "unverified"}
    profile = ctx.plan.get("installation_profile") or ""
    if not ctx.from_repo and profile != SOURCE_INSTALL_PROFILE:
        _say(log, "::error::no proven upstream installation")
        return st.finish(1, None, **outputs)
    # Obtain the immutable source once for either supported profile. Each
    # command on its own: a failed checkout must not go on to build the
    # default branch under the pinned commit's name.
    name = os.path.basename(repo.removesuffix(".git"))
    ctx_dir = ctx.work / "ctx"
    shutil.rmtree(ctx.root / ctx_dir, ignore_errors=True)
    (ctx.root / ctx_dir).mkdir(parents=True)
    src = ctx_dir / name
    for argv in (["git", "clone", "-q", "--", repo, str(src)],
                 ["git", "-C", str(src), "checkout", "-q", ref]):
        rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
        if rc != 0:
            return st.finish(rc, argv, **outputs)
    rc_w, want = ctx.exe.output(["git", "-C", str(src), "rev-parse", f"{ref}^{{commit}}"], cwd=ctx.root)
    rc_h, head = ctx.exe.output(["git", "-C", str(src), "rev-parse", "HEAD"], cwd=ctx.root)
    if rc_w != 0 or rc_h != 0 or head.strip() != want.strip():
        _say(log, f"::error::checked out {head.strip()}, not {ref}")
        return st.finish(1, ["git", "-C", str(src), "rev-parse", "HEAD"], **outputs)
    review = str(ctx.work / "procedure_review.json")
    context = src
    if ctx.from_repo:
        docker_dir, docker_file = src, ctx.from_repo
        checks = [
            [ctx.python, ctx.harness("_paths.py"), str(src), docker_file],
            [ctx.python, ctx.harness("fidelity.py"), "--checkout", str(src), "--review", review,
             "--manifest", ctx.manifest],
        ]
    else:
        # Re-derive every command from checked source bytes. Never build a
        # submitted or generated descriptor, never select packages by name.
        docker_dir, docker_file = ctx.work_abs, SOURCE_INSTALL_DOCKERFILE
        checks = [
            [ctx.python, ctx.harness("fidelity.py"), "--checkout", str(src), "--review", review,
             "--manifest", ctx.manifest, "--source-install-dockerfile", str(docker_dir / docker_file)],
        ]
    for argv in checks:
        rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
        if rc != 0:
            outputs["failed_check"] = os.path.basename(argv[1])
            return st.finish(rc, argv, **outputs)
    outputs["source_evidence"] = "verified"
    # record_terminal.sh keeps the exact argv and the build's output in
    # work/log_build.txt.terminal, and the output alone in work/log_build.txt.
    argv = ["bash", ctx.harness("record_terminal.sh"), str(ctx.work / "log_build.txt"),
            "docker", "build", "-f", str(docker_dir / docker_file), "-t", ctx.image, str(context)]
    rc = ctx.exe.run(argv, cwd=ctx.root)
    return st.finish(rc, argv, **outputs, **({"environment": "primary"} if rc == 0 else {}))


# --- Starts: the installed program answers --help ---------------------------

def starts(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Outside the ladder, like the example. Only an explicit starts command
    runs here: STRhub does not invent a --help invocation, so a plan without
    one records this stage as not run."""
    if not installs_result.passed:
        return StageResult.not_run("starts", "no image was built")
    cmd = ctx.plan.get("starts_cmd") or ""
    if not cmd:
        return StageResult.not_run("starts", "no explicit starts command: STRhub does not invent a --help invocation")
    log = ctx.work / "log_starts.txt"
    st = StageResult.start("starts", log)
    argv = ["bash", ctx.harness("run_container.sh"), f"{ctx.container_prefix}_starts", "2", str(log),
            *HARDENING, ctx.image, cmd]
    rc = ctx.exe.run(argv, timeout=STARTS_BACKSTOP_MINUTES * 60, cwd=ctx.root)
    check = [ctx.python, ctx.harness("check_starts.py"), "--rc", str(rc), "--log", str(log),
             "--json", ctx.result("starts.json")]
    check_rc = ctx.exe.run(check, cwd=ctx.root)
    # The gate is check_starts's judgement of the log (a program that prints
    # its usage and exits 1 still starts), so the stage's status follows it;
    # the container's own exit status stays in the record as it was.
    judged = _load(ctx.result_abs("starts.json")) or {}
    st.finish(rc, argv, starts_json=ctx.result("starts.json"), check_exit_code=check_rc)
    if judged.get("applicable"):
        st.status = "passed" if judged.get("passed") else "failed"
    return st


# --- Run legs ----------------------------------------------------------------

def _run_leg(ctx: Ctx, name: str, cmd: str, in_dir: pathlib.Path | None,
             out_dir: pathlib.Path, log: pathlib.Path) -> tuple[int, list[str]]:
    """One container run, the reviewed command, on one leg's mounts."""
    out_abs = ctx.root / out_dir if not out_dir.is_absolute() else out_dir
    out_abs.mkdir(parents=True, exist_ok=True)
    # World-writable on purpose. The container runs with every capability
    # dropped, so its root has no CAP_DAC_OVERRIDE and cannot write to a
    # directory the runner user owns (PR #19).
    out_abs.chmod(0o777)
    mounts: list[str] = []
    if in_dir is not None:
        in_abs = ctx.root / in_dir if not in_dir.is_absolute() else in_dir
        mounts += ["-v", f"{in_abs}:/data/in:ro"]
    mounts += ["-v", f"{out_abs}:/data/out"]
    argv = ["bash", ctx.harness("run_container.sh"), f"{ctx.container_prefix}_{name}", str(ctx.plan["timeout"]),
            str(log), *HARDENING, *mounts, ctx.image, cmd]
    # A backstop: run_container.sh stops the container at the manifest's limit
    # and says so in the log; this only catches a hung script.
    rc = ctx.exe.run(argv, timeout=int(ctx.plan["step_timeout"]) * 60, cwd=ctx.root)
    return rc, argv


def runs_example(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Reproduces own example: the cited command on the repository's data,
    inside the image, with nothing from STRhub."""
    if not ctx.ready("example_ready"):
        return StageResult.not_run("runs_example", "no cited example to reproduce")
    if not installs_result.passed:
        return StageResult.not_run("runs_example", "no image was built")
    log = ctx.work / "log_example.txt"
    st = StageResult.start("runs_example", log)
    rc, argv = _run_leg(ctx, "example", ctx.plan["example_cmd"], None, ctx.work / "out_example", log)
    return st.finish(rc, argv)


def check_example(ctx: Ctx) -> StageResult:
    """Example produced its output: check_example.py decides whether what the
    wrapper copied to /data/out is the documented output."""
    if not ctx.ready("example_ready"):
        return StageResult.not_run("example", "no cited example to reproduce")
    st = StageResult.start("example")
    argv = [ctx.python, ctx.harness("check_example.py"), ctx.manifest, str(ctx.work / "out_example"),
            "--json", ctx.result("example.json")]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result=ctx.result("example.json"))


def runs_external(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Runs (external data): the one shared dataset the review admits, run
    once. Before the container starts, input_provenance.py recomputes the
    mount's provenance from Git and the bytes about to be mounted, and
    checks the launch command against the reviewed one; a difference stops
    the leg with `input_evidence: unverified` and no run. This leg has one
    dataset and one attempt: its exit status, output and log are kept as
    they are, whatever they say."""
    if not ctx.ready("external_ready"):
        return StageResult.not_run("runs_external", "no shared dataset was staged for the declared input type")
    if not installs_result.passed:
        return StageResult.not_run("runs_external", "no image was built")
    log = ctx.work / "log_external.txt"
    st = StageResult.start("runs_external", log)
    prov = [ctx.python, ctx.harness("input_provenance.py"), "--work", str(ctx.work),
            "--manifest", ctx.manifest, f"--command={ctx.plan['cmd']}"]
    rc, said = ctx.exe.output(prov, cwd=ctx.root)
    if said.strip():
        _say(None, said.rstrip())
    if rc != 0:
        return st.finish(rc, prov, input_evidence="unverified", provenance=said.strip())
    rc, argv = _run_leg(ctx, "external", ctx.plan["cmd"], ctx.work / "in_external", ctx.work / "out_external", log)
    return st.finish(rc, argv, input_evidence="verified", mounted_inputs=str(ctx.work / "mounted_inputs.json"))


def _verified(ext: StageResult) -> bool:
    return ext.outputs.get("input_evidence") == "verified"


def check_io(ctx: Ctx, ext: StageResult) -> StageResult:
    """Expected IO: non-empty files in the declared formats. Conditioned, as
    the workflow was, on the mount's provenance having been verified: a run
    that never started left nothing to judge."""
    if not _verified(ext):
        return StageResult.not_run("io_external", "the external leg did not run on a verified mount")
    st = StageResult.start("io_external")
    argv = [ctx.python, ctx.harness("check_io.py"), ctx.manifest, str(ctx.work / "out_external"),
            "--json", ctx.result("io_external.json")]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result=ctx.result("io_external.json"))


def check_content(ctx: Ctx, ext: StageResult) -> StageResult:
    """Content: structured, genotype-bearing records against the dataset's panel."""
    if not _verified(ext):
        return StageResult.not_run("content_external", "the external leg did not run on a verified mount")
    st = StageResult.start("content_external")
    argv = [ctx.python, ctx.harness("check_content.py"), ctx.manifest, str(ctx.work / "out_external"),
            "--json", ctx.result("content_external.json"), "--panel", ctx.plan.get("supported_loci", "")]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result=ctx.result("content_external.json"))


# --- The matrix (external + example legs) ------------------------------------

def matrix(ctx: Ctx) -> list[dict]:
    """matrix.json: one row per leg, read by report.py."""
    import json
    ext_io, ext_ct = _load(ctx.result_abs("io_external.json")), _load(ctx.result_abs("content_external.json"))
    legs = [{
        "leg": "external", "label": "External data",
        "available": ctx.ready("external_ready"),
        "type": ctx.plan.get("input_type") or None,
        "dataset": ctx.plan.get("dataset_name") or None,
        "io": bool(ext_io and ext_io.get("passed")),
        "content": bool(ext_ct and ext_ct.get("passed")),
        "passed": bool(ext_io and ext_io.get("passed")),
    }]
    ex = _load(ctx.result_abs("example.json"))
    legs.append({
        "leg": "example", "label": "Tool's own example",
        "available": ctx.ready("example_ready"),
        "io": bool(ex and ex.get("passed")),
        "content": None,
        "passed": bool(ex and ex.get("passed")),
        "matches_expected": (ex or {}).get("checks", {}).get("matches_expected"),
        "produced_count": (ex or {}).get("produced_count"),
    })
    ctx.result_abs("matrix.json").parent.mkdir(parents=True, exist_ok=True)
    ctx.result_abs("matrix.json").write_text(json.dumps(legs, indent=2))
    print(json.dumps(legs, indent=2))
    return legs
