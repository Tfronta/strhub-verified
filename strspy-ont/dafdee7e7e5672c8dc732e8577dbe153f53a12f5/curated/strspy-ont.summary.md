# STRhub Verified: STRspy (strspy-ont)

**Result: Runs + Expected IO.** it produces a non-empty file in the declared format.

**Verdict: Runs.** The tool installed and its run produced its documented output.

- Source: `https://github.com/unique379r/strspy` @ `dafdee7e7e5672c8dc732e8577dbe153f53a12f5`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-18T13:38:00+00:00
- Upstream: The verified commit is 14 commit(s) behind `main`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35350684894

## Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
bash /opt/strspy/src/STRspy_Normal_v2.0_Args.sh -s /data/in -r yes -t ont -f /opt/strspy/db/STRspy2.0-DB -b /opt/strspy/db/STRspy2.0-DB -l /opt/strspy/db-v2/STRspy_v2.DB.sort.bed -k 0.4 -o /data/out -c /opt/strspy/config/ToolsConfig.txt -d 1
```

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## What the author documents as a known issue

Quoted from the repository's README at the verified commit. STRhub did not establish any of this by running the tool; it is the author's own note about their own software.

**Known bug** (README line 291)

> When using the wrapper ('STRspy_run_v1.0.sh'), One might run into an issue. The parallel version of **STRspy_Parallel_v2.0_Args.sh** is unable to properly connect with "gnu parallel" and exits the workflow without mapping or further analysis steps of the pipeline. Solution to this, the user can choose the Normal version to avoid any crash. ***Tip: Its good practice to use pre-aligned bams for quicker outcomes.***

## Output content (plausibility evidence)

- Sequence records: **6** (malformed: 0)
- STR loci detected: **0**
- Total reads across calls: **0** (deepest single sequence: 0)



## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | yes | 1000 Genomes ONT, hg38 CODIS slice (R10 SUP) |
| Tool's own example | N/A | N/A | — | — |

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

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Install method: [`setup/STRspy_2.0_env.yml`](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/setup/STRspy_2.0_env.yml)
- Run command: [`README.md` line 120](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/README.md#L120) — `USAGE: bash ./STRspy_run_v2.0_Args.sh config/InputConfig.txt config/ToolsConfig.txt`
- Example data: [`db-v2/STRspy_v2.DB.sort.bed`](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/db-v2/STRspy_v2.DB.sort.bed)
- Example data: [`db-v2/optional-create-custom-db/testTwofa/TPOX.fa`](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/db-v2/optional-create-custom-db/testTwofa/TPOX.fa)
- Example data: [`db-v2/optional-create-custom-db/testTwofa/vWA.fa`](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/db-v2/optional-create-custom-db/testTwofa/vWA.fa)
- Known issue: [`README.md` line 291](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/README.md#L291) — `Known bug`
- Documented input: [`README.md` line 44](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/README.md#L44) — `Input either fastq (raw reads usually from ONT) or bam (pre-aligned reads by user)`
- Author's recommendation: [`README.md` line 295](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/README.md#L295) — `***Tip: Its good practice to use pre-aligned bams for quicker outcomes.***`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

Verified automatically, in a clean environment, on the tool's public source at the pinned commit. This is a record of what happened, not an endorsement by the tool's author.

