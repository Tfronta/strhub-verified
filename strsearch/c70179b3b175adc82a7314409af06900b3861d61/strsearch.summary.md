# STRhub Verified: STRsearch (strsearch)

**Result: Available.** the pinned public source exists.

**Verdict: Fails.** The environment did not build from the declared install steps.

What stopped it, and what can be done:

- The environment did not build from the install steps found in the repository.
  - Yourself: Adjust the install steps (or provide a Dockerfile) and try again.
  - The tool's owner: open an issue, "Build fails from a clean checkout".

- Source: `https://github.com/AnJingwd/STRsearch` @ `c70179b3b175adc82a7314409af06900b3861d61`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-18T20:49:05+00:00
- Upstream: The verified commit is the head of `master`.
- Recipe: the repository's own instructions, read off the README and the tree at the pinned commit
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35393390457

## Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
python3 pipeline.py from_fastq --working_path example/test_results/ --sample test --fq1 /data/in/input.bam --fq2 /data/in/input.bam --ref /data/ref/hg38.fa
```

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | — | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |
| Reproduces own example | — | the README's own command produced its documented output on the repository's own data |

## It did not build from source

STRhub tried to build the tool from its source at the pinned commit, following the build steps the repository declares, and the build failed. Nothing below the Installs gate ran.

What this means:

- **If you are trying to run it:** A build from source at this commit fails in a clean environment; the cause and a suggested fix are below.
- **If you are reviewing a paper:** Nothing ran, so this says nothing about the software's output. It records that this attempt to build it stopped, and whose side the cause is on.
- **If you maintain it:** Every cause identified sits in this run's configuration — the pinned versions, package names or build steps it declared. They are faults in how the tool was set up here rather than in the software. Re-verifying after correcting them is free.

What failed:

| What happened | Times | Suggested fix |
|---|---|---|
| The build referenced a file that is not in the build context | 1 | A COPY/ADD line names a file the build cannot see. The container is built from the tool's directory, and the repository is cloned inside the image — so paths from your own machine are not available. |

Full build output: [`strsearch.log-build.txt`](strsearch.log-build.txt)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | — | — | Illumina BAM (hg38), NA12878 (autosomal, female) |
| Tool's own example | yes | — | — | — |

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
- Run command: [`README.md` line 96](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L96) — `python3 pipeline.py from_fastq \`
- Example data: [`example/ref_test.bed`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/ref_test.bed)
- Example data: [`example/test_data/test.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test.bam)
- Example data: [`example/test_data/test_R1.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R1.fastq)
- Example data: [`example/test_data/test_R2.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R2.fastq)
- Example data: [`example/test_output/STRfq/Marker94_reads_test_sortByname.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_output/STRfq/Marker94_reads_test_sortByname.bam)
- Documented input: [`README.md` line 77](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L77) — `FASTQ file or BAM-file from singe-end or paird-end sequencing platforms`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: the repository's own Dockerfile was built as-is.
- Input: the README documents BAM and FASTQ (line 77); this run used STRhub's illumina-bam-hg38 reference data.
- 2 input path(s) in the README command replaced with /data/in/input.bam.
- 1 reference FASTA path(s) replaced with /data/ref/hg38.fa.
- Run command: the README's own command, rewritten to STRhub's mounts; everything it created was captured as output.
- Regions: STRhub's ready-made strsearch file for the dataset's panel loci (STRhub records the strsearch layout for a program of this name).
- README mentions hg19/GRCh37 only; STRhub reference BAMs are hg38

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

Verified automatically, in a clean environment, on the tool's public source at the pinned commit. This is a record of what happened, not an endorsement by the tool's author.

