# STRhub Verified — GangSTR (gangstr-2-5)

**Result: Installs** — the environment builds from source.

- Source: `https://github.com/gymreklab/gangstr` @ `v2.5`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-06-24T21:37:35+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/28131191634

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| External data | yes | — | Illumina BAM (hg38) — NA12878 (autosomal, female) |

## README check (advisory)

Score: **5/5** — advisory only, does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

