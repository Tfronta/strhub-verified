# STRhub Verified: STRsearch (strsearch-c70179b)

**Result: Runs + Plausible output.** its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

- Source: `https://github.com/AnJingwd/STRsearch` @ `c70179b3b175adc82a7314409af06900b3861d61`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-08-14T11:39:58+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/31797047624

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

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

## Regions

The submitter supplied the regions BED, covering 24 of 24 supported loci. The reference dataset is a slice around 24 forensic STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- A regions configuration file, supplied with the submission rather than taken from the repository.
- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, supplied with the submission.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- --ref_bed expects an 11-column STR configuration file (chr/start/end/period/.../flanking sequences), not a plain BED.
- Example coordinates and reference are hg19 (ucsc.hg19.fasta, ref_test.bed); an hg38-aligned BAM needs an hg38 STR config file.
- usearch is required but licensed; the Dockerfile fetches it from a personal license URL, which no other user can reach.
- The from_fastq mode needs a bwa-indexed reference (.amb/.ann/.bwt/.pac/.sa); only hg38.fa and .fai are mounted, so use from_bam.
- The Dockerfile assumes code lives in a ./STRsearch subdirectory, but conf.py, pipeline.py and scripts/ are at the repository root.
- The Dockerfile pins ubuntu:16.04, Miniconda 4.3.31 and old bioconda builds (samtools 1.7, bedtools 2.17.0); these pins no longer resolve.
- --sex is required by from_bam; the example uses male, which affects Y-locus handling.

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

