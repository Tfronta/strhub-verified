# STRhub Verified: AuditProbe (auditprobe-v0-1)

**Result: Available.** the pinned public source exists.

- Source: `https://github.com/Tfronta/strhub-web` @ `main`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-07-24T19:47:21+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/30121607886

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | — | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | — | — | NIST mds2-2157, Illumina STR (ForenSeq slice, donor NTD01) |

## README check (advisory)

Score: **2/5**. Advisory only; does not affect the execution badge.

- PASS install
- — command
- PASS input
- — output
- — dependencies

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

