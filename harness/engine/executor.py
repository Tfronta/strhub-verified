"""Running a command and keeping what it said.

The one place subprocesses are started. `run` streams the command's output to
stdout (the CI log) and, when asked, appends it to a log file — what `| tee -a`
did in the workflow — and returns the exit status. `output` captures a short
answer (a `git rev-parse`). Tests pass a fake with the same two methods.

The backstop timeout is the workflow's `timeout-minutes` on a step: a hung
script, not the tool's run limit, which run_container.sh enforces itself. On
hitting it the process group is stopped and the exit status is 124, the same
status run_container.sh gives a run stopped at its limit.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import signal
import subprocess
import sys
import threading

BACKSTOP_RC = 124


class Executor:
    def run(self, argv: list[str], *, log: pathlib.Path | str | None = None,
            timeout: float | None = None, cwd: pathlib.Path | str | None = None,
            env: dict | None = None) -> int:
        lf = open(log, "a") if log else contextlib.nullcontext(None)
        with lf as f:
            p = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, errors="replace",
                                 start_new_session=True)

            def pump():
                for line in p.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    if f is not None:
                        f.write(line)
                        f.flush()

            t = threading.Thread(target=pump, daemon=True)
            t.start()
            try:
                p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _stop(p)
                t.join(timeout=5)
                line = (f"STRhub: the step backstop stopped `{argv[0]}` after "
                        f"{int(timeout or 0) // 60} minutes.\n")
                sys.stdout.write(line)
                if f is not None:
                    f.write(line)
                return BACKSTOP_RC
            t.join()
            return p.returncode

    def output(self, argv: list[str], *, cwd: pathlib.Path | str | None = None) -> tuple[int, str]:
        res = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace", check=False)
        return res.returncode, res.stdout


def _stop(p: subprocess.Popen) -> None:
    """TERM the whole group, give it 20 seconds, then KILL. The container is
    run_container.sh's to remove: its EXIT trap runs on TERM."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(p.pid, signal.SIGTERM)
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(p.pid, signal.SIGKILL)
        p.wait()
