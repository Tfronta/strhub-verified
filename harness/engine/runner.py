"""Walk the ladder once, in order, and write the RunRecord.

The order: Available, Installs, Starts, the example leg and its check, the
external leg and its checks, the matrix. Each stage is conditioned on the
ones before it the way the workflow's `if:` lines conditioned the steps; a
stage that does not run is recorded as such, with its reason, never dropped.
"""
from __future__ import annotations

import pathlib

from . import record, stages
from .executor import Executor
from .record import StageResult
from .stages import Ctx

#: What the attestation used to derive from step outcomes: a failure of
#: STRhub's own evidence checks, which must never read as the tool failing.
EVIDENCE_FAILURES = {
    "installs": "the upstream procedure evidence check before Docker",
    "runs_external": "the mounted dataset provenance check",
}


def _infra_failure(plan: dict, ins: StageResult, ext: StageResult) -> str:
    if plan.get("input_failure"):
        return plan["input_failure"]
    if ins.status == "failed" and ins.outputs.get("source_evidence") != "verified":
        return EVIDENCE_FAILURES["installs"]
    if ext.status == "failed" and ext.outputs.get("input_evidence") != "verified":
        return EVIDENCE_FAILURES["runs_external"]
    return ""


def run(plan: dict, work: pathlib.Path, root: pathlib.Path, exe: Executor | None = None,
        python: str | None = None) -> dict:
    ctx = Ctx(plan=plan, work=pathlib.Path(work), root=pathlib.Path(root), exe=exe or Executor(),
              **({"python": python} if python else {}))
    done: list[StageResult] = []

    def keep(r: StageResult) -> StageResult:
        done.append(r)
        print(f"[engine] {r.stage}: {r.status}" + (f" (exit {r.exit_code})" if r.exit_code is not None else "")
              + (f" — {r.reason}" if r.reason else ""))
        return r

    av = keep(stages.available(ctx))
    ins = keep(stages.installs(ctx, av))
    keep(stages.starts(ctx, ins))
    ex = keep(stages.runs_example(ctx, ins))
    keep(stages.check_example(ctx))
    ext = keep(stages.runs_external(ctx, ins))
    keep(stages.check_io(ctx, ext))
    keep(stages.check_content(ctx, ext))
    legs = stages.matrix(ctx)

    # The badge ladder rests on the external leg; a leg whose mount was not
    # verified never ran, and reads as a skipped step, as it did.
    verified = ext.outputs.get("input_evidence") == "verified"
    ladder = {"leg": "external", "runs": ext.outcome if verified else "skipped",
              "io": "io_external.json", "content": "content_external.json",
              "supported_loci": ctx.plan.get("supported_loci", ""),
              "input_type": ctx.plan.get("input_type", ""), "dataset": ctx.plan.get("dataset_name", "")}

    return {
        "schema": record.SCHEMA,
        "created": record.now(),
        "tool": ctx.plan.get("tool", ""),
        "mode": ctx.plan.get("mode", ""),
        "image": stages.IMAGE,
        "hardening": list(stages.HARDENING),
        "plan": dict(ctx.plan),
        "stages": [r.to_dict() for r in done],
        # Step outcomes in GitHub's vocabulary, what report.py was handed before.
        "outcomes": {
            "available": av.outcome,
            "installs": ins.outcome,
            "runs_example": ex.outcome,
            "runs_external": ext.outcome,
        },
        "evidence": {
            "source": ins.outputs.get("source_evidence", ""),
            "input": ext.outputs.get("input_evidence", ""),
        },
        "infra_failure": _infra_failure(ctx.plan, ins, ext),
        "ladder": ladder,
        "environment_built": ins.outputs.get("environment", ""),
        "matrix": legs,
    }
