"""Walk the ladder once, in order, and write the RunRecord.

The order: Available, Installs, Starts, the own leg and its checks, the
example leg and its check, the external leg and its checks, the medical-panel
leg and its checks when one was planned, the matrix. Each stage is conditioned on the ones before it the way the
workflow's `if:` lines conditioned the steps; a stage that does not run is
recorded as such, with its reason, never dropped.
"""
from __future__ import annotations

import pathlib

from . import record, stages
from .executor import Executor
from .record import StageResult
from .stages import Ctx


def _ladder(ctx: Ctx, own: StageResult, ext: StageResult, med: StageResult, legs: list[dict]) -> dict:
    """Which leg the badge rests on. The rule, in the order it is applied:

      1. the author's own fixture, when one was declared;
      2. the external leg on the declared (forensic) input type;
      3. the medical-panel leg, only when both external legs were planned,
         the forensic one produced no documented output and the medical one did.

    Rule 3 is a choice between two results that both exist in the record and
    in the matrix; the report says it was made. It is not a retry: both legs
    ran whatever the first one found."""
    if ctx.ready("own_ready"):
        return {"leg": "own", "runs": own.outcome, "io": "io_own.json", "content": "content_own.json",
                "supported_loci": ctx.plan.get("supported_loci", ""),
                "input_type": ctx.plan.get("input_type", ""), "dataset": ctx.plan.get("dataset_name", "")}
    ladder = {"leg": "external", "runs": ext.outcome, "io": "io_external.json", "content": "content_external.json",
              "supported_loci": ctx.plan.get("supported_loci", ""),
              "input_type": ctx.plan.get("input_type", ""), "dataset": ctx.plan.get("dataset_name", "")}
    by_leg = {l["leg"]: l for l in legs}
    if ctx.ready("med_leg_ready") and not by_leg.get("external", {}).get("io") \
            and by_leg.get("external_med", {}).get("io"):
        ladder = {"leg": "external_med", "runs": med.outcome, "io": "io_external_med.json",
                  "content": "content_external_med.json",
                  "supported_loci": ctx.plan.get("med_supported_loci", ""),
                  "input_type": ctx.plan.get("med_input_type", ""), "dataset": ctx.plan.get("med_dataset_name", ""),
                  "reason": ("the loci this tool genotypes could not be read off its repository, so both "
                             "panels were run; the forensic leg produced no documented output and the "
                             "medical leg did.")}
    return ladder


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
    keep(stages.check_io(ctx, "external", ctx.work / "out_external", "io_external.json"))
    keep(stages.check_content(ctx, "external", ctx.work / "out_external", ctx.work / "in_external",
                              "content_external.json", ctx.plan.get("supported_loci", "")))

    med = keep(stages.runs_external_med(ctx, ins))
    keep(stages.check_io(ctx, "external_med", ctx.work / "out_external_med", "io_external_med.json",
                         ready_key="med_leg_ready"))
    keep(stages.check_content(ctx, "external_med", ctx.work / "out_external_med", ctx.work / "in_external_med",
                              "content_external_med.json", ctx.plan.get("med_supported_loci", ""),
                              ready_key="med_leg_ready"))

    legs = stages.matrix(ctx)
    ladder = _ladder(ctx, own, ext, med, legs)

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
            "runs_external_med": med.outcome,
        },
        "ladder": ladder,
        "environment_built": ins.outputs.get("environment", ""),
        "matrix": legs,
    }
