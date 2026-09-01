# STRhub Verified: Strspy (strspy-v2-0-ont)

**Result: Runs + Expected IO.** it produces a non-empty file in the declared format.

- Source: `https://github.com/unique379r/strspy` @ `dafdee7e7e5672c8dc732e8577dbe153f53a12f5`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-01T11:18:36+00:00
- Submitted by: a third party — not the tool's maintainer
- Upstream: The verified commit is 14 commit(s) behind `main`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/33501209177

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

## Who submitted this

This tool was submitted for verification by somebody other than its maintainer. The maintainer took no part in the run and supplied none of what it used: the command, the environment, and any target regions were chosen by the submitter. Where a maintainer is named above, that names who answers for the software — not who asked for this report, and not an endorsement of it.

## Errors reported during the run

The tool reported errors on 9 item(s) during the run.
This does not assess whether the results produced are correct.

| What happened | Times | Affected |
|---|---|---|
| Could not open expected files | 18 | D10S1248, D12S391, D13S317, D5S818, D7S820, D8S1179, FGA, TPOX, vWA |

Structural errors, such as a file that will not open, an unrecognized command-line flag, or an incomplete build, do not depend on the sample: a coverage-limited slice yields fewer reads, but it cannot cause them. These are not attributable to STRhub's reference sample.

A small test file in the tool's own repository lets a new user run it on their first day and see it working before trusting it with their own data, and it lets a verification run against the author's sample as well as STRhub's slice. Publishing the output that file should produce helps just as much: it shows what the results are meant to look like, which is what a reader needs to tell a correct run from one that merely finished.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

