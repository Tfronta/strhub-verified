# STRhub Verified: GangSTR (gangstr)

**Runs as documented.**

## As it is in the repository

**Verdict: Runs.** The tool's run produced its documented output, on the published environment the README points at: the build from the pinned commit failed, so what ran is the version that environment holds.

Reached **Runs + Plausible output**: its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

### It did not build from source; the run used the README's ready-made environment

STRhub tried to build the tool from its source at the pinned commit, following the build steps the repository declares, and the build failed. The published image gymreklab/str-toolkit the README points at was used instead, and every gate below ran on it.

What this means:

- **If you are trying to run it:** A build from source at this commit fails in a clean environment; the cause is below. The ready-made environment the README points at does work: it is what this run used.
- **If you are reviewing a paper:** This result describes the software inside that environment, whatever its publisher last put there, and not the pinned commit, which is the version a manuscript would cite.
- **If you maintain it:** Every cause identified sits in this run's configuration: the pinned versions, package names or build steps it declared. They are faults in how the tool was set up here rather than in the software. Re-verifying after correcting them is free.

What failed:

| What happened | Times | Suggested fix |
|---|---|---|
| An autotools build is missing its auxiliary file: config.sub | 4 | The configure script needs 'config.sub', which `autoreconf -i` (or `automake --add-missing`) copies in from the automake package. The build runs autoconf without installing those files; running `autoreconf -fi` before `./configure` in that step fixes it. |

Full build output: [`gangstr.log-build.txt`](gangstr.log-build.txt)

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
GangSTR --bam /data/in/input.bam --ref /data/ref/hg38.fa --regions /data/in/regions.bed --out outprefix
```
- Log (external): [`gangstr.log-external.txt`](gangstr.log-external.txt)
- Log (build): [`gangstr.log-build.txt`](gangstr.log-build.txt)

## Run details

- Source: `https://github.com/gymreklab/gangstr` @ `6ea9b2b8daca51dcab1f0e46210622b94b52ff17`
- Environment: ubuntu-22.04 (`Dockerfile`); plan B: the published image gymreklab/str-toolkit the README points at (`Dockerfile.fallback`), after the build from the pinned commit failed
- Generated: 2026-09-20T16:54:13+00:00
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35524020158

## Output content (plausibility evidence)

- Sequence records: **24** (malformed: 0)
- STR loci detected: **24**
- Total reads across calls: **11603** (deepest single sequence: 800)
- STR loci: CSF1PO, D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D1S1656, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D5S818, D6S1043, D7S820, D8S1179, FGA …
- Top markers by read depth: D18S51 (800), D7S820 (684), D16S539 (656), D5S818 (641), PentaD (621), D6S1043 (609)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | — | Illumina BAM (hg38), NA12878 (autosomal, female) |
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
- Install method: [`CMakeLists.txt`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/CMakeLists.txt)
- Fallback environment: [`README.md` line 18](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/README.md#L18): `A Docker with GangSTR plus the dumpSTR filtering tool installed is available at [gymreklab/str-toolkit](https://hub.docker.com/r/gymreklab/str-toolkit) from Docker hub.`
- Run command: [`README.md` line 101](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/README.md#L101): `GangSTR --bam file.bam`
- Example data: [`test/HTT.bed`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/test/HTT.bed)
- Example data: [`test/alignment/nc190_25.sorted.bam`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/test/alignment/nc190_25.sorted.bam)
- Example data: [`test/alignment/nc10_25.sorted.bam`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/test/alignment/nc10_25.sorted.bam)
- Example data: [`test/alignment/nc30_15.sorted.bam`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/test/alignment/nc30_15.sorted.bam)
- Example data: [`experimental/supplement_bed/hg38_codis.bed`](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/experimental/supplement_bed/hg38_codis.bed)
- Documented input: [`README.md` line 6](https://github.com/gymreklab/gangstr/blob/6ea9b2b8daca51dcab1f0e46210622b94b52ff17/README.md#L6): `GangSTR takes aligned reads (BAM) and a set of repeats in the reference genome as input and outputs a VCF file containing genotypes for each locus.`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment: the build from the pinned commit failed, so the published image gymreklab/str-toolkit the README points at was built instead. What ran is the version that environment holds, not necessarily the pinned commit.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's CMakeLists.txt (cmake), at the pinned commit. If that build fails, the published image gymreklab/str-toolkit the README points at stands in, and the report says so.
- Input: the README documents BAM (line 6); this run used STRhub's illumina-bam-hg38 reference data.
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

