"""The gates, one function each. A faithful port of the steps verify.yml ran.

Every function takes the run context and the results it is conditioned on,
and returns a StageResult. The conditions are the workflow's `if:` lines, said
as reasons; the commands are the workflow's commands, argv for argv. Files land
where the workflow put them (logs under <work>/, check results next to the
repository root) so report.py reads the same paths it always did.

What a gate must never do: run a thing twice, edit the recipe directory or the
clone, or decide anything about the verdict. The one carried-over exception is
the forensic→medical slice retry in `runs_external`, kept exactly as it was for
tanda 1 and marked for removal.
"""
from __future__ import annotations

import dataclasses
import os
import pathlib
import re
import shutil
import sys
import tempfile

from .executor import Executor
from .record import StageResult

#: The container runs with every capability dropped, no network, and ceilings
#: on memory, CPU and processes. Unquoted on purpose in the workflow: a list.
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

#: The line the Installs gate writes when a repository's Dockerfile is built
#: from the directory that holds the clone (see `installs`).
CONTEXT_NOTE = "==== STRhub: %s copies ./%s, so it is built from the directory that holds the clone ===="


@dataclasses.dataclass
class Ctx:
    plan: dict
    work: pathlib.Path          # as given (`work`): what the check scripts are told
    root: pathlib.Path          # the engine repository; cwd of every command
    exe: Executor
    python: str = sys.executable

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

    @property
    def entry(self) -> tuple[list[str], list[str]]:
        """A repository's own Dockerfile has whatever entrypoint its author
        chose; the engine's images end in `ENTRYPOINT ["/bin/bash", "-lc"]`.
        For the former the entrypoint is overridden so the command still
        reaches a shell."""
        if self.from_repo:
            return ["--entrypoint", "/bin/bash"], ["-lc"]
        return [], []

    @property
    def ref_mount(self) -> list[str]:
        ref = self.work_abs / "ref"
        return ["-v", f"{ref}:/data/ref:ro"] if ref.is_dir() else []

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

def _copies_clone_by_name(dockerfile: pathlib.Path, name: str) -> bool:
    """A Dockerfile that copies the repository by its own name (`COPY
    ./STRsearch /STRsearch`) is written for the parent directory as context."""
    pat = re.compile(r"^[ \t]*(COPY|ADD)([ \t]+--[^ \t]+)*[ \t]+(\./)?" + re.escape(name) + r"(/|[ \t])",
                     re.IGNORECASE | re.MULTILINE)
    try:
        return bool(pat.search(dockerfile.read_text(errors="replace")))
    except OSError:
        return False


def installs(ctx: Ctx, available_result: StageResult) -> StageResult:
    """`docker build` from the recipe's Dockerfile, or from the repository's own
    at the pinned ref. Nothing to build from a ref the repository does not
    hold, or when the commit states no install procedure at all."""
    if not available_result.passed:
        return StageResult.not_run("installs", "the pinned source is not available")
    if str(ctx.plan.get("install_ready", "1")) == "0":
        return StageResult.not_run("installs", "the commit states no install procedure a third party can execute")
    repo, ref = ctx.plan["repo"], ctx.plan["ref"]
    log = _truncate(ctx.work_abs / "log_build.txt")
    st = StageResult.start("installs", log)
    docker_dir = pathlib.Path(ctx.plan["dockerdir"])
    docker_file = ctx.plan["dockerfile"]
    context = docker_dir
    if ctx.from_repo:
        # The repository ships its own Dockerfile: build THAT, at the pinned
        # ref. The author's own statement of the environment, taken at its
        # word. Cloned under the repository's own name, because some
        # Dockerfiles are built from the directory ABOVE the clone.
        name = os.path.basename(repo.removesuffix(".git"))
        ctx_dir = ctx.work / "ctx"
        shutil.rmtree(ctx.root / ctx_dir, ignore_errors=True)
        (ctx.root / ctx_dir).mkdir(parents=True)
        src = ctx_dir / name
        # Each command on its own: a failed checkout must not go on to build
        # the default branch under the pinned commit's name.
        for argv in (["git", "clone", "-q", "--", repo, str(src)],
                     ["git", "-C", str(src), "checkout", "-q", ref]):
            rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
            if rc != 0:
                return st.finish(rc, argv)
        rc_w, want = ctx.exe.output(["git", "-C", str(src), "rev-parse", f"{ref}^{{commit}}"], cwd=ctx.root)
        rc_h, head = ctx.exe.output(["git", "-C", str(src), "rev-parse", "HEAD"], cwd=ctx.root)
        if rc_w != 0 or rc_h != 0 or head.strip() != want.strip():
            _say(log, f"::error::checked out {head.strip()}, not {ref}")
            return st.finish(1, ["git", "-C", str(src), "rev-parse", "HEAD"])
        ctx.exe.run(["git", "-C", str(src), "submodule", "update", "--init", "--recursive", "-q"],
                    log=log, cwd=ctx.root)   # || true
        docker_dir, docker_file, context = src, ctx.from_repo, src
        # Only when the clone has no file or directory of that name itself:
        # strkit's `COPY strkit strkit` copies its own package directory.
        if not (ctx.root / src / name).exists() and _copies_clone_by_name(ctx.root / src / docker_file, name):
            context = ctx_dir
            _say(log, CONTEXT_NOTE % (docker_file, name))
            _say(log, "")
    argv = ["docker", "build",
            "--build-arg", f"STRAITRAZOR_REF={ref}",
            "--build-arg", f"TOOL_REF={ref}",
            "-f", str(docker_dir / docker_file),
            "-t", IMAGE,
            str(context)]
    rc = ctx.exe.run(argv, log=log, cwd=ctx.root)
    return st.finish(rc, argv, **({"environment": "primary"} if rc == 0 else {}))


# --- Starts: the installed program answers --help ---------------------------

def starts(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Outside the ladder, like the example: the one fact a reviewer can use
    when the README says nothing runnable. Two minutes, the same isolation."""
    if not installs_result.passed:
        return StageResult.not_run("starts", "no image was built")
    cmd = ctx.plan.get("starts_cmd") or ""
    if not cmd:
        return StageResult.not_run("starts", "no program to ask for --help")
    log = ctx.work / "log_starts.txt"
    st = StageResult.start("starts", log)
    entry, entry_args = ctx.entry
    argv = ["bash", ctx.harness("run_container.sh"), "strhub_starts", "2", str(log),
            *HARDENING, *entry, IMAGE, *entry_args, cmd]
    rc = ctx.exe.run(argv, timeout=STARTS_BACKSTOP_MINUTES * 60, cwd=ctx.root)
    check = [ctx.python, ctx.harness("check_starts.py"), "--rc", str(rc), "--log", str(log), "--json", "starts.json"]
    check_rc = ctx.exe.run(check, cwd=ctx.root)
    return st.finish(rc, argv, starts_json="starts.json", check_exit_code=check_rc)


# --- Run legs ----------------------------------------------------------------

def _run_leg(ctx: Ctx, name: str, cmd: str, in_dir: pathlib.Path | None,
             out_dir: pathlib.Path, log: pathlib.Path) -> tuple[int, list[str]]:
    """One container run, the author's command, on one leg's mounts."""
    out_abs = ctx.root / out_dir if not out_dir.is_absolute() else out_dir
    out_abs.mkdir(parents=True, exist_ok=True)
    # World-writable on purpose. The container runs with every capability
    # dropped, so its root has no CAP_DAC_OVERRIDE and cannot write to a
    # directory the runner user owns (PR #19).
    out_abs.chmod(0o777)
    entry, entry_args = ctx.entry
    mounts: list[str] = []
    if in_dir is not None:
        in_abs = ctx.root / in_dir if not in_dir.is_absolute() else in_dir
        mounts += ["-v", f"{in_abs}:/data/in:ro"]
    mounts += ["-v", f"{out_abs}:/data/out"]
    mounts += ctx.ref_mount
    argv = ["bash", ctx.harness("run_container.sh"), f"strhub_{name}", str(ctx.plan["timeout"]), str(log),
            *HARDENING, *entry, *mounts, IMAGE, *entry_args, cmd]
    # A backstop: run_container.sh stops the container at the manifest's limit
    # and says so in the log; this only catches a hung script.
    rc = ctx.exe.run(argv, timeout=int(ctx.plan["step_timeout"]) * 60, cwd=ctx.root)
    return rc, argv


def runs_own(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Gate · Runs (own data): the author's BYOR fixture. The badge ladder
    uses THIS leg when it exists."""
    if not ctx.ready("own_ready"):
        return StageResult.not_run("runs_own", "no fixture of the author's own was declared")
    if not installs_result.passed:
        return StageResult.not_run("runs_own", "no image was built")
    log = ctx.work / "log_own.txt"
    st = StageResult.start("runs_own", log)
    rc, argv = _run_leg(ctx, "own", ctx.plan["cmd"], ctx.work / "in_own", ctx.work / "out_own", log)
    return st.finish(rc, argv)


def runs_example(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Reproduces own example: the README's command on the repository's data,
    inside the image, with nothing from STRhub."""
    if not ctx.ready("example_ready"):
        return StageResult.not_run("runs_example", "the recipe declares no documented example to reproduce")
    if not installs_result.passed:
        return StageResult.not_run("runs_example", "no image was built")
    log = ctx.work / "log_example.txt"
    st = StageResult.start("runs_example", log)
    rc, argv = _run_leg(ctx, "example", ctx.plan["example_cmd"], None, ctx.work / "out_example", log)
    return st.finish(rc, argv)


def _io_probe(ctx: Ctx, out_dir: pathlib.Path, json_path: pathlib.Path) -> bool:
    argv = [ctx.python, ctx.harness("check_io.py"), ctx.manifest, str(out_dir), "--json", str(json_path)]
    return ctx.exe.run(argv, cwd=ctx.root) == 0


def runs_external(ctx: Ctx, installs_result: StageResult) -> StageResult:
    """Runs (external data): STRhub's typed reference dataset.

    CARRIED OVER FOR TANDA 1, TO BE REMOVED IN TANDA 2: the forensic→medical
    slice retry. If the forensic slice produces no called records and a medical
    slice of the same platform was staged, the identical command is run again
    on it; if that passes, the retry's outputs and log REPLACE the first
    attempt's, the manifest is rewritten in place (inputs.type, report.slug, a
    caveat) and the exit status is set to 0. The record keeps both attempts.
    """
    if not ctx.ready("external_ready"):
        return StageResult.not_run("runs_external", "no reference dataset of the kind this tool reads is held")
    if not installs_result.passed:
        return StageResult.not_run("runs_external", "no image was built")
    log = ctx.work / "log_external.txt"
    st = StageResult.start("runs_external", log)
    out_dir, in_dir = ctx.work / "out_external", ctx.work / "in_external"
    rc, argv = _run_leg(ctx, "external", ctx.plan["cmd"], in_dir, out_dir, log)
    outputs: dict = {}
    io_ok = rc == 0 and _io_probe(ctx, out_dir, ctx.work / "io_forensic_probe.json")
    med_in = ctx.work / "in_external_med"
    if not io_ok and ctx.ready("med_fallback_ready") and (ctx.root / med_in).is_dir():
        med_type = ctx.plan.get("med_input_type", "")
        _say(None, f"Forensic slice produced no called records (rc={rc}); retrying identical command "
                   f"on medical STR slice ({med_type})...")
        med_out, med_log = ctx.work / "out_external_med", ctx.work / "log_external_med.txt"
        rc_med, argv_med = _run_leg(ctx, "external_med", ctx.plan["cmd"], med_in, med_out, med_log)
        retry = {"stage": "runs_external_med", "command": argv_med, "exit_code": rc_med,
                 "log": str(med_log), "promoted": False}
        if rc_med == 0 and _io_probe(ctx, med_out, ctx.work / "io_med_probe.json"):
            shutil.rmtree(ctx.root / out_dir)
            (ctx.root / med_out).rename(ctx.root / out_dir)
            (ctx.root / med_log).rename(ctx.root / log)
            shutil.rmtree(ctx.root / in_dir)
            (ctx.root / med_in).rename(ctx.root / in_dir)
            ctx.exe.run([ctx.python, ctx.harness("prepare.py"), "--promote-medical", ctx.manifest, med_type],
                        cwd=ctx.root)
            retry["promoted"] = True
            outputs["med_used"] = "1"
            rc = 0
        outputs["retry"] = retry
    return st.finish(rc, argv, **outputs)


# --- Checks on what a leg left behind --------------------------------------

def check_io(ctx: Ctx, leg: str, out_dir: pathlib.Path, json_name: str) -> StageResult:
    """Expected IO: non-empty files in the declared formats. Conditioned on the
    leg being staged, not on its run having passed: an empty directory is a
    result too, and the check says so."""
    stage = f"io_{leg}"
    if not ctx.ready(f"{leg}_ready"):
        return StageResult.not_run(stage, f"the {leg} leg was not staged")
    st = StageResult.start(stage)
    argv = [ctx.python, ctx.harness("check_io.py"), ctx.manifest, str(out_dir), "--json", json_name]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result=json_name)


def check_content(ctx: Ctx, leg: str, out_dir: pathlib.Path, in_dir: pathlib.Path,
                  json_name: str, supported_loci: str) -> StageResult:
    """Content: the loci this leg was given are a regions BED, or a JSON
    catalog (ExpansionHunter's) staged as regions.json."""
    stage = f"content_{leg}"
    if not ctx.ready(f"{leg}_ready"):
        return StageResult.not_run(stage, f"the {leg} leg was not staged")
    st = StageResult.start(stage)
    reg = in_dir / "regions.bed"
    if not (ctx.root / reg).is_file():
        reg = in_dir / "regions.json"
    argv = [ctx.python, ctx.harness("check_content.py"), ctx.manifest, str(out_dir), "--json", json_name,
            "--regions", str(reg), "--panel", supported_loci]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result=json_name)


def check_example(ctx: Ctx) -> StageResult:
    """Example produced its output: check_example.py decides whether what the
    wrapper copied to /data/out is the documented output."""
    if not ctx.ready("example_ready"):
        return StageResult.not_run("example", "the recipe declares no documented example to reproduce")
    st = StageResult.start("example")
    argv = [ctx.python, ctx.harness("check_example.py"), ctx.manifest, str(ctx.work / "out_example"),
            "--json", "example.json"]
    return st.finish(ctx.exe.run(argv, cwd=ctx.root), argv, result="example.json")


# --- The matrix (own + external + example legs) ------------------------------

def _load(path: pathlib.Path):
    try:
        import json
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:  # noqa: BLE001
        return None


def matrix(ctx: Ctx, med_used: bool) -> list[dict]:
    """matrix.json: one row per leg, read by report.py."""
    import json
    root = ctx.root
    own_io, own_ct = _load(root / "io_own.json"), _load(root / "content_own.json")
    fixture_source = ctx.plan.get("fixture_source") or "strhub"
    legs = [{
        "leg": "own", "label": "Your data" if fixture_source == "tool" else "STRhub fixture",
        "available": ctx.ready("own_ready"),
        "io": bool(own_io and own_io.get("passed")),
        "content": bool(own_ct and own_ct.get("passed")),
        "passed": bool(own_io and own_io.get("passed")),
        "fixture_source": fixture_source,
    }]
    ext_io, ext_ct = _load(root / "io_external.json"), _load(root / "content_external.json")
    legs.append({
        "leg": "external", "label": "External data",
        "available": ctx.ready("external_ready"),
        "type": (ctx.plan.get("med_input_type") if med_used else ctx.plan.get("input_type")) or None,
        "dataset": (ctx.plan.get("med_dataset_name") if med_used else ctx.plan.get("dataset_name")) or None,
        "io": bool(ext_io and ext_io.get("passed")),
        "content": bool(ext_ct and ext_ct.get("passed")),
        "passed": bool(ext_io and ext_io.get("passed")),
    })
    ex = _load(root / "example.json")
    legs.append({
        "leg": "example", "label": "Tool's own example",
        "available": ctx.ready("example_ready"),
        "io": bool(ex and ex.get("passed")),
        "content": None,
        "passed": bool(ex and ex.get("passed")),
        "matches_expected": (ex or {}).get("checks", {}).get("matches_expected"),
        "produced_count": (ex or {}).get("produced_count"),
    })
    (root / "matrix.json").write_text(json.dumps(legs, indent=2))
    print(json.dumps(legs, indent=2))
    return legs
