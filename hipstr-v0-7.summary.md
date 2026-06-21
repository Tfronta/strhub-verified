# STRhub Verified — hipstr (hipstr-v0-7)

**Result: Runs + Plausible output** — its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

- Source: `https://github.com/tfwillems/HipSTR` @ `b2033bfbb5cf55496b776463bdf2993fa763a4be`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-06-21T20:07:24+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/27915924530

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **1** (malformed: 0)
- STR loci detected: **1**
- Total reads across calls: **0** (deepest single sequence: 0)
- STR loci: PentaE
- Top markers by read depth: PentaE (0)

## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| STRhub fixture | yes | PASS | — |
| External data | yes | PASS | 1000 Genomes Illumina 30x — hg38 CODIS slice |

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

