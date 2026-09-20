# STRhub Verified: GangSTR (gangstr)

**Not verified as documented.**

## What STRhub had to do to run this tool

STRhub wrote its own recipe for this tool, an environment and a command of its own rather than the repository's instructions, and ran that. Each item below is something a first-time user following the README would have to work out for themselves, and so a recommendation to the author. This run does not change the tool's label: the label is what happens as it is in the repository.

- Installs GangSTR 2.5.0 from bioconda, a prebuilt binary. Instead of: cmake .. && make from the source at the pinned commit, as the README documents. The documented build stops in htslib: the repository's CMakeLists runs autoreconf without -i (config.sub/config.guess missing). What ran is bioconda's build of 2.5.0, not this commit's source.
- Supplies the regions BED from STRhub's library and the command-line flags STRhub chose for its reference slice. Instead of: A regions file and a command the README leaves to the user.

With those changes, the run reached **Runs + Plausible output**: its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

**Verdict: Runs.** The tool installed and its run produced its documented output.

## This run, in full

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
GangSTR --bam /data/in/input.bam --ref /data/ref/hg38.fa --regions /data/in/regions.bed --out /data/out/output
```
- Log (own): [`gangstr.log-own.txt`](gangstr.log-own.txt)
- Log (external): [`gangstr.log-external.txt`](gangstr.log-external.txt)
- Log (build): [`gangstr.log-build.txt`](gangstr.log-build.txt)

## Run details

- Source: `https://github.com/gymreklab/gangstr` @ `6ea9b2b8daca51dcab1f0e46210622b94b52ff17`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-20T16:53:24+00:00
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35524008276

## Output content (plausibility evidence)

- Sequence records: **24** (malformed: 0)
- STR loci detected: **24**
- Total reads across calls: **10738** (deepest single sequence: 757)
- STR loci: CSF1PO, D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D1S1656, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D5S818, D6S1043, D7S820, D8S1179, FGA …
- Top markers by read depth: D18S51 (757), D16S539 (618), PentaD (613), D5S818 (589), D6S1043 (585), D7S820 (579)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
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

- A container environment and a command written by STRhub, not taken from the repository's instructions; what they do differently is listed under "What STRhub had to do to run this tool".

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

