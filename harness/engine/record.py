"""StageResult and RunRecord: what a run leaves behind, as data.

A stage is one gate or check. Its result says what was run (the exact argv),
how it ended (exit code), where its output went (the log), and when. A stage
that did not run says why. The record carries every stage in the order they
were tried, plus the two derived views report.py needs: the step outcomes in
GitHub's vocabulary and the ladder leg the badge rests on.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib

SCHEMA = "strhub-verified/run-record/1"

PASSED, FAILED, NOT_RUN = "passed", "failed", "not_run"

#: GitHub Actions step outcomes, which report.py already understands.
OUTCOME = {PASSED: "success", FAILED: "failure", NOT_RUN: "skipped"}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclasses.dataclass
class StageResult:
    stage: str
    status: str = NOT_RUN
    command: list[str] | None = None
    exit_code: int | None = None
    log: str | None = None
    started: str | None = None
    ended: str | None = None
    reason: str = ""
    outputs: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def not_run(cls, stage: str, reason: str) -> "StageResult":
        return cls(stage=stage, status=NOT_RUN, reason=reason)

    @classmethod
    def start(cls, stage: str, log: pathlib.Path | str | None = None) -> "StageResult":
        return cls(stage=stage, started=now(), log=str(log) if log else None)

    def finish(self, rc: int, command: list[str] | None = None, **outputs) -> "StageResult":
        self.exit_code = rc
        self.status = PASSED if rc == 0 else FAILED
        if command is not None:
            self.command = list(command)
        self.ended = now()
        self.outputs.update(outputs)
        return self

    @property
    def passed(self) -> bool:
        return self.status == PASSED

    @property
    def outcome(self) -> str:
        return OUTCOME[self.status]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def write(record: dict, path: pathlib.Path | str) -> None:
    pathlib.Path(path).write_text(json.dumps(record, indent=2) + "\n")


def load(path: pathlib.Path | str) -> dict:
    return json.loads(pathlib.Path(path).read_text())
