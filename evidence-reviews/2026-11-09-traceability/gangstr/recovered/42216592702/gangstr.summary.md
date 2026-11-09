# STRhub Verified: gangstr (gangstr)

**Does not run as documented: stops at install.**

## As it is in the repository

**Step 1, the documented run: As documented, it does not run.** The environment did not build from the declared install steps. That does not mean the tool does not work. It means a third party following the README at this commit did not reach the end. Fix the documentation, or the step that broke, and try the link again on the new commit.

**Verdict: Fails.** The environment did not build from the declared install steps.

What stopped it, and what can be done:

- The environment did not build from the install steps found in the repository.
  - Yourself: Adjust the install steps (or provide a Dockerfile) and try again.
  - The tool's owner: open an issue, "Build fails from a clean checkout".

Reached **Available**: the pinned public source exists.

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | — | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

### It did not build from source

STRhub tried to build the tool from its source at the pinned commit, following the build steps the repository declares, and the build failed. Nothing below the Installs gate ran.

What this means:

- **If you are trying to run it:** A build from source at this commit fails in a clean environment; the cause and a suggested fix are below.
- **If you are reviewing a paper:** Nothing ran, so this says nothing about the software's output. It records that this attempt to build it stopped, and whose side the cause is on.
- **If you maintain it:** Every cause identified sits in this run's configuration: the pinned versions, package names or build steps it declared. They are faults in how the tool was set up here rather than in the software. Re-verifying after correcting them is free.

What failed:

| What happened | Times | Suggested fix |
|---|---|---|
| An autotools build is missing its auxiliary file: config.sub | 2 | The configure script needs 'config.sub', which `autoreconf -i` (or `automake --add-missing`) copies in from the automake package. The build runs autoconf without installing those files; running `autoreconf -fi` before `./configure` in that step fixes it. |

Full build output: [`gangstr.log-build.txt`](gangstr.log-build.txt)

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
mkdir -p outprefix && GangSTR --bam /data/in/input.bam --ref /data/ref/hg38.fa --regions /data/in/regions.bed --out outprefix
```
- Log (build): [`gangstr.log-build.txt`](gangstr.log-build.txt)

## Run details

- Source: `https://github.com/gymreklab/gangstr` @ `e368b9f4dbf7ab7585036a5ff2e68480d0623c80`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-11-06T12:21:35+00:00
- Upstream: The verified commit is 2 commit(s) behind `master`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/42216592702

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | — | — | Illumina BAM (hg38), NA12878 (autosomal, female) |
| Tool's own example | N/A | N/A | — | — |

## Regions

STRhub supplied the regions BED. The reference dataset is a slice around 24 forensic STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Install method: [`CMakeLists.txt`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/CMakeLists.txt)
- Fallback environment: [`README.md` line 18](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/README.md#L18): `A Docker with GangSTR plus the dumpSTR filtering tool installed is available at [gymreklab/str-toolkit](https://hub.docker.com/r/gymreklab/str-toolkit) from Docker hub.`
- Run command: [`README.md` line 92](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/README.md#L92): `GangSTR --bam file.bam`
- Example data: [`test/HTT.bed`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/test/HTT.bed)
- Example data: [`test/alignment/nc190_25.sorted.bam`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/test/alignment/nc190_25.sorted.bam)
- Example data: [`test/alignment/nc10_25.sorted.bam`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/test/alignment/nc10_25.sorted.bam)
- Example data: [`test/alignment/nc30_15.sorted.bam`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/test/alignment/nc30_15.sorted.bam)
- Example data: [`experimental/supplement_bed/hg38_codis.bed`](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/experimental/supplement_bed/hg38_codis.bed)
- Documented input: [`README.md` line 6](https://github.com/gymreklab/gangstr/blob/e368b9f4dbf7ab7585036a5ff2e68480d0623c80/README.md#L6): `GangSTR takes aligned reads (BAM) and a set of repeats in the reference genome as input and outputs a VCF file containing genotypes for each locus.`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, built from the tool's declared install steps rather than from a recipe the repository ships.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's CMakeLists.txt (cmake), at the pinned commit. If that build fails, the published image gymreklab/str-toolkit the README points at stands in, and the report says so.
- Input: the README documents BAM (line 6); this run used STRhub's illumina-bam-hg38 reference data.
- The output directory the command writes into (outprefix) was created first.
- 1 input path(s) in the README command replaced with /data/in/input.bam.
- 1 reference FASTA path(s) replaced with /data/ref/hg38.fa.
- 1 BED path(s) replaced with /data/in/regions.bed.
- Run command: the README's own command, rewritten to STRhub's mounts; everything it created was captured as output.
- Regions: STRhub's ready-made gangstr file for the dataset's panel loci (STRhub records the gangstr layout for a program of this name).

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

