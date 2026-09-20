# STRhub Verified: STRspy (strspy-ont)

**Does not run as documented: stops at run.**

## As it is in the repository

**Verdict: Fails.** The tool exited with an error before producing its documented output.

What stopped it, and what can be done:

- The tool was installed but exited with an error when run.
  - Yourself: Adjust the command and try again.
  - The tool's owner: open an issue, "Documented command fails on a public reference sample".

Reached **Installs**: the environment builds from source.

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

### What the author documents as a known issue

Quoted from the repository's README at the verified commit. STRhub did not establish any of this by running the tool; it is the author's own note about their own software.

**Known bug** (README line 291)

> When using the wrapper ('STRspy_run_v1.0.sh'), One might run into an issue. The parallel version of **STRspy_Parallel_v2.0_Args.sh** is unable to properly connect with "gnu parallel" and exits the workflow without mapping or further analysis steps of the pipeline. Solution to this, the user can choose the Normal version to avoid any crash. ***Tip: Its good practice to use pre-aligned bams for quicker outcomes.***

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
bash ./STRspy_run_v2.0_Args.sh config/InputConfig.txt config/ToolsConfig.txt
```
- Log (external): [`strspy-ont.log-external.txt`](strspy-ont.log-external.txt)
- Log (build): [`strspy-ont.log-build.txt`](strspy-ont.log-build.txt)

## Run details

- Source: `https://github.com/unique379r/strspy` @ `e069e19c304720f92587199f66c9e18360e944ef`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-20T12:51:51+00:00
- Upstream: The verified commit is 14 commit(s) behind `main`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35511749337

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | — | — | 1000 Genomes ONT, hg38 CODIS slice (R10 SUP) |
| Tool's own example | N/A | N/A | — | — |

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Install method: [`setup/STRspy_2.0_env.yml`](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/setup/STRspy_2.0_env.yml)
- Run command: [`README.md` line 120](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/README.md#L120): `USAGE: bash ./STRspy_run_v2.0_Args.sh config/InputConfig.txt config/ToolsConfig.txt`
- Example data: [`db-v2/STRspy_v2.DB.sort.bed`](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/db-v2/STRspy_v2.DB.sort.bed)
- Example data: [`db-v2/optional-create-custom-db/testTwofa/TPOX.fa`](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/db-v2/optional-create-custom-db/testTwofa/TPOX.fa)
- Example data: [`db-v2/optional-create-custom-db/testTwofa/vWA.fa`](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/db-v2/optional-create-custom-db/testTwofa/vWA.fa)
- Known issue: [`README.md` line 291](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/README.md#L291): `Known bug`
- Documented input: [`README.md` line 44](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/README.md#L44): `Input either fastq (raw reads usually from ONT) or bam (pre-aligned reads by user)`
- Author's recommendation: [`README.md` line 295](https://github.com/unique379r/strspy/blob/e069e19c304720f92587199f66c9e18360e944ef/README.md#L295): `***Tip: Its good practice to use pre-aligned bams for quicker outcomes.***`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, built from the tool's declared install steps rather than from a recipe the repository ships.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's setup/STRspy_2.0_env.yml (conda), at the pinned commit.
- Input: the README documents BAM and FASTQ (line 44); this run used STRhub's ont-bam-hg38 reference data. The author recommends BAM (line 295: "Tip: Its good practice to use pre-aligned bams for quicker outcomes.").
- Run command: the README's own command, rewritten to STRhub's mounts; everything it created was captured as output.

## Out of scope

This report does not evaluate any of the following:

- Genotype correctness or accuracy
- Concordance against known truth sets
- Sensitivity, specificity, or stutter performance
- Allele calling accuracy or forensic casework suitability
- Regulatory compliance or ISO accreditation
- Multi-laboratory or multi-dataset reproducibility

## Limitations

- Single reference dataset per input type
- Single containerized environment (Docker / ubuntu-22.04)
- No truth-set comparison or ground-truth genotypes
- No accuracy or concordance assessment
- No forensic validation of results
- Short-read limitations apply (very long STR alleles may not span reads)

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

Verified automatically, in a clean environment, on the tool's public source at the pinned commit. This is a record of what happened, not an endorsement by the tool's author.

