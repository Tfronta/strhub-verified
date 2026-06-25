# STRhub Verified — GangSTR (gangstr-v2-5)

**Result: Runs + Expected IO** — it produces a non-empty file in the declared format.

- Source: `https://github.com/gymreklab/gangstr` @ `6ea9b2b8daca51dcab1f0e46210622b94b52ff17`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-06-25T12:29:29+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/28170059620

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| External data | yes | PASS | Illumina BAM (hg38) — NA12878 (autosomal, female) |

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

