# STRhub Verified: STRsearch (strsearch)

**Not verified as documented.**

## What STRhub had to do to run this tool

STRhub wrote its own recipe for this tool, an environment and a command of its own rather than the repository's instructions, and ran that. Each item below is something a first-time user following the README would have to work out for themselves, and so a recommendation to the author. This run does not change the tool's label: the label is what happens as it is in the repository.

- Builds the environment on ubuntu 22.04 at the version floors the README declares (bwa, samtools, bamToFastq, seqtk). Instead of: The repository's own Dockerfile: ubuntu 16.04 with exact pins and Miniconda 4.3.31. The pinned stack no longer resolves.
- Fills in conf.py with the paths of the installed tools. Instead of: conf.py as shipped, with 'YOUR PATH/...' placeholders the user is to replace.
- Leaves usearch out. Instead of: usearch, which conf.py names. Licensed and unobtainable; only --assemble_pairs reaches it, and this run does not use it.
- Supplies an hg38 regions configuration in STRsearch's eleven-column layout, with flanking sequences, written by STRhub. Instead of: The repository's example, which is hg19 and covers five markers. No hg38 configuration ships with the repository.

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
python3 /opt/STRsearch/pipeline.py --type paired --num_processors 4 --reads_threshold 30 --stutter_ratio 0.5 from_bam --working_path /data/out --sample sample --sex female --bam /data/in/input.bam --ref_bed /data/in/regions.bed --genotypes /data/out/genotypes.txt --multiple_alleles /data/out/multiple_alleles.txt --qc_matrix /data/out/qc_matrix.txt
```
- Log (external): [`strsearch.log-external.txt`](strsearch.log-external.txt)
- Log (build): [`strsearch.log-build.txt`](strsearch.log-build.txt)

## Run details

- Source: `https://github.com/AnJingwd/STRsearch` @ `c70179b3b175adc82a7314409af06900b3861d61`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-20T16:53:08+00:00
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35524008276

## Output content (plausibility evidence)

- Sequence records: **388** (malformed: 0)
- STR loci detected: **24**
- Total reads across calls: **2401** (deepest single sequence: 51)
- STR loci: CSF1PO, D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D1S1656, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D5S818, D6S1043, D7S820, D8S1179, FGA …
- Top markers by read depth: vWA (241), D21S11 (187), FGA (164), D19S433 (131), SE33 (125), D18S51 (123)

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
- Install method: [`Dockerfile`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/Dockerfile)
- Run command: [`README.md` line 96](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L96): `python3 pipeline.py from_fastq \`
- Example data: [`example/ref_test.bed`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/ref_test.bed)
- Example data: [`example/test_data/test.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test.bam)
- Example data: [`example/test_data/test_R1.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R1.fastq)
- Example data: [`example/test_data/test_R2.fastq`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_data/test_R2.fastq)
- Example data: [`example/test_output/STRfq/Marker94_reads_test_sortByname.bam`](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/example/test_output/STRfq/Marker94_reads_test_sortByname.bam)
- Documented input: [`README.md` line 77](https://github.com/AnJingwd/STRsearch/blob/c70179b3b175adc82a7314409af06900b3861d61/README.md#L77): `FASTQ file or BAM-file from singe-end or paird-end sequencing platforms`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, supplied with the submission.

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

