# STRhub Verified: STRsearch (strsearch)

**Runs from its published image; the pinned commit does not build.**

## As it is in the repository

**Verdict: Runs.** The tool's run produced its documented output, on the published environment the README points at: the build from the pinned commit failed, so what ran is the version that environment holds.

Reached **Runs + Expected IO**: it produces a non-empty file in the declared format.

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |
| Reproduces own example | PASS | the README's own command produced its documented output on the repository's own data |

### It did not build from source; the run used the README's ready-made environment

STRhub tried to build the tool from its source at the pinned commit, following the build steps the repository declares, and the build failed. The published image anjing123/strsearch:latest the README points at was used instead, and every gate below ran on it.

What this means:

- **If you are trying to run it:** A build from source at this commit fails in a clean environment; the cause is below. The ready-made environment the README points at does work: it is what this run used.
- **If you are reviewing a paper:** This result describes the software inside that environment, whatever its publisher last put there, and not the pinned commit, which is the version a manuscript would cite.
- **If you maintain it:** The cause could not be classified automatically. The full build output is linked below.

What failed:

| What happened | Times | Suggested fix |
|---|---|---|
| A download in the build failed: https://drive5.com/cgi-bin/upload3.py?license=2019110501245926689 | 2 | The build fetches that address and did not get the file. If the link is dead or needs a licence, the install steps need a new source for it; if the server was down, trying again will tell. |

Full build output: [`strsearch.log-build.txt`](strsearch.log-build.txt)

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
mkdir -p example && python3 pipeline.py from_bam --working_path example/test_results --sample test --sex male --bam /data/in/input.bam --ref_bed /data/in/regions.bed --genotypes example/test_results/test_genotypes.txt --multiple_alleles example/test_results/test_multiple_alleles.txt --qc_matrix example/test_results/test_qc_matrix.txt
```
- Log (external): [`strsearch.log-external.txt`](strsearch.log-external.txt)
- Log (example): [`strsearch.log-example.txt`](strsearch.log-example.txt)
- Log (build): [`strsearch.log-build.txt`](strsearch.log-build.txt)

## Run details

- Source: `https://github.com/AnJingwd/STRsearch` @ `c70179b3b175adc82a7314409af06900b3861d61`
- Environment: ubuntu-22.04 (`Dockerfile`); plan B: the published image anjing123/strsearch:latest the README points at (`Dockerfile.fallback`), after the build from the pinned commit failed
- Generated: 2026-10-01T12:41:56+00:00
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/36862511780

## Output content (plausibility evidence)

- Sequence records: **35** (malformed: 0)
- STR loci detected: **0**
- Total reads across calls: **0** (deepest single sequence: 0)



## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | — | Illumina BAM (hg38), NA12878 (autosomal, female) |
| Tool's own example | yes | PASS | — | — |

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
- Install method: [`Dockerfile`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/Dockerfile)
- Fallback environment: [`README.md` line 223](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L223): `docker pull anjing123/strsearch:latest`
- Run command: [`README.md` line 107](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L107): `python3 pipeline.py from_bam \`
- Example data: [`example/ref_test.bed`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/ref_test.bed)
- Example data: [`example/test_data/test.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test.bam)
- Example data: [`example/test_data/test_R1.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R1.fastq)
- Example data: [`example/test_data/test_R2.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R2.fastq)
- Example data: [`example/test_output/STRfq/Marker94_reads_test_sortByname.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_output/STRfq/Marker94_reads_test_sortByname.bam)
- Documented input: [`README.md` line 77](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L77): `FASTQ file or BAM-file from singe-end or paird-end sequencing platforms`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment: the build from the pinned commit failed, so the published image anjing123/strsearch:latest the README points at was built instead. What ran is the version that environment holds, not necessarily the pinned commit.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: the repository's own Dockerfile was built as-is. If it does not build, the published image anjing123/strsearch:latest the README points at stands in, and the report says so.
- Input: the README documents BAM and FASTQ (line 77); this run used STRhub's illumina-bam-hg38 reference data.
- The output directory the command writes into (example) was created first.
- 1 input path(s) in the README command replaced with /data/in/input.bam.
- 1 BED path(s) replaced with /data/in/regions.bed.
- Run command: the README's own command, rewritten to STRhub's mounts; everything it created was captured as output.
- Regions: STRhub's ready-made strsearch file for the dataset's panel loci (STRhub records the strsearch layout for a program of this name).
- README mentions hg19/GRCh37 only; STRhub reference BAMs are hg38

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

