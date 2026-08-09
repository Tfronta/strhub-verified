# STRhub Verified: STRait Razor (strait-razor-b618e93)

**Result: Installs.** the environment builds from source.

- Source: `https://github.com/Ahhgust/STRaitRazor` @ `b618e9345ab40f348b504083ae8de2b39abb60fa`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-08-09T22:39:25+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/31339909338

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **0** (malformed: 0)
- STR loci detected: **0**
- Total reads across calls: **0** (deepest single sequence: 0)



## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | — | yes | NIST mds2-2157, Illumina STR (ForenSeq slice, donor NTD01) |

## Errors reported during the run

The tool reported errors on 1 item(s) during the run.
This does not assess whether the results produced are correct.

| What happened | Times | Affected |
|---|---|---|
| Command not found | 1 | str8rzr |

Structural errors, such as a file that will not open, an unrecognized command-line flag, or an incomplete build, do not depend on the sample: a coverage-limited slice yields fewer reads, but it cannot cause them. These are not attributable to STRhub's reference sample.

We recommend the tool ship its own demo or test data in its official repository, so it can be evaluated against the author's complete data as well as STRhub's slice.

These are corrections to the submission, not limits of the automated environment: fix them and re-verify at no cost. Each row above carries its suggested fix.

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

