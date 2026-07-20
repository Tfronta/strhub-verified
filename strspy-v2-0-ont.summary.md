# STRhub Verified: Strspy (strspy-v2-0-ont)

**Result: Runs + Expected IO.** it produces a non-empty file in the declared format.

- Source: `https://github.com/unique379r/strspy` @ `dafdee7e7e5672c8dc732e8577dbe153f53a12f5`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-07-20T19:38:55+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/29772391083

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | yes | 1000 Genomes ONT, hg38 CODIS slice (R10 SUP) |

## Errors reported during the run

The tool reported errors on 9 item(s) during the run.
This does not assess whether the results produced are correct.

| What happened | Times | Affected |
|---|---|---|
| Could not open expected files | 18 | D10S1248, D12S391, D13S317, D5S818, D7S820, D8S1179, FGA, TPOX, vWA |

Structural errors, such as a file that will not open, an unrecognized command-line flag, or an incomplete build, do not depend on the sample: a coverage-limited slice yields fewer reads, but it cannot cause them. These are not attributable to STRhub's reference sample.

We recommend the tool ship its own demo or test data in its official repository, so it can be evaluated against the author's complete data as well as STRhub's slice.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

