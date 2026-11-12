"""Walk the ladder once, in order, and write the RunRecord.

The order is the workflow's: Available, Installs, Starts, the own leg and its
checks, the example leg and its check, the external leg and its checks, the
matrix. Each stage is conditioned on the ones before it the way the
workflow's `if:` lines conditioned the steps; a stage that does not run is
recorded as such, with its reason, never dropped.
"""
from __future__ import annotations

import pathlib

from . import record, stages
from .executor import Executor
from .record import StageResult
from .stages import Ctx


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

    own = keep(stages.runs_own(ctx, ins))
    keep(stages.check_io(ctx, "own", ctx.work / "out_own", "io_own.json"))
    keep(stages.check_content(ctx, "own", ctx.work / "out_own", ctx.work / "in_own",
                              "content_own.json", ctx.plan.get("supported_loci", "")))

    ex = keep(stages.runs_example(ctx, ins))
    keep(stages.check_example(ctx))

    ext = keep(stages.runs_external(ctx, ins))
    med_used = ext.outputs.get("med_used") == "1"
    supported_loci = ctx.plan.get("med_supported_loci", "") if med_used else ctx.plan.get("supported_loci", "")
    keep(stages.check_io(ctx, "external", ctx.work / "out_external", "io_external.json"))
    keep(stages.check_content(ctx, "external", ctx.work / "out_external", ctx.work / "in_external",
                              "content_external.json", supported_loci))

    legs = stages.matrix(ctx, med_used)

    # The badge ladder follows the author's BYOR "own" leg when present;
    # otherwise it rests on the external typed-dataset leg.
    if ctx.ready("own_ready"):
        ladder = {"leg": "own", "runs": own.outcome, "io": "io_own.json", "content": "content_own.json"}
    else:
        ladder = {"leg": "external", "runs": ext.outcome, "io": "io_external.json", "content": "content_external.json"}
    ladder["supported_loci"] = supported_loci

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
            "runs_own": own.outcome,
            "runs_example": ex.outcome,
            "runs_external": ext.outcome,
        },
        "ladder": ladder,
        "environment_built": ins.outputs.get("environment", ""),
        "med_used": med_used,
        "matrix": legs,
    }
