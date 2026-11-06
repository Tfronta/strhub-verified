# STRhub Verified: ExpansionHunter (expansionhunter-med)

**Runs as documented.**

## As it is in the repository

**Step 1, the documented run: As documented, it runs.** A third party installed the tool with the steps this commit states and ran the command it writes, and the output file that command names appeared. This says nothing about genotypes or about the forensic panel.

**Verdict: Runs.** The tool installed and its run produced its documented output.

Reached **Runs + Plausible output**: its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |
| Starts | PASS | the installed program answers --help in the built environment |

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
mkdir -p sample && ExpansionHunter --reads /data/in/input.bam --reference /data/ref/hg38.fa --variant-catalog /data/in/regions.json --output-prefix sample
```
- Log (external): [`expansionhunter-med.log-external.txt`](expansionhunter-med.log-external.txt)
- Log (starts): [`expansionhunter-med.log-starts.txt`](expansionhunter-med.log-starts.txt)
- Log (build): [`expansionhunter-med.log-build.txt`](expansionhunter-med.log-build.txt)

## Run details

- Source: `https://github.com/Illumina/ExpansionHunter` @ `9f5db1d4ab72016b2d93330b9792842d71582622`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-11-06T16:19:55+00:00
- Upstream: The verified commit is 8 commit(s) behind `master`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/42250919800

## Output content (plausibility evidence)

- Sequence records: **51** (malformed: 0)
- STR loci detected: **51**
- Total reads across calls: **27496** (deepest single sequence: 1103)
- STR loci: AFF2, AFF3, AR, ARX, ATN1, ATXN1, ATXN10, ATXN2, ATXN3, ATXN7, ATXN8OS, BEAN1, C9orf72, CACNA1A, CBL, CNBP, COMP, CSTB …
- Top markers by read depth: SAMD12 (1103), RAPGEF2 (1015), AFF2 (876), YEATS2 (864), MARCHF6 (855), DAB1 (834)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | — | Illumina BAM (hg38), NA12878, medical STR slice (female) |
| Tool's own example | N/A | N/A | — | — |

## Regions

STRhub supplied the regions BED. The reference dataset is a slice around 51 disease-associated STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **4/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- — output
- PASS dependencies

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Run command: [`docs/03_Usage.md` line 15](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/docs/03_Usage.md#L15): `ExpansionHunter --reads <BAM/CRAM file with aligned reads> \`
- Example data: [`example/input/reference.fa`](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/example/input/reference.fa)
- Example data: [`example/input/variants.bam`](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/example/input/variants.bam)
- Example data: [`example/output/repeats.vcf`](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/example/output/repeats.vcf)
- Example data: [`example/output/repeats_realigned.bam`](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/example/output/repeats_realigned.bam)
- Documented input: [`README.md` line 15](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/README.md#L15): `ExpansionHunter --reads <BAM/CRAM file with aligned reads> \`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, built from the tool's declared install steps rather than from a recipe the repository ships.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's install instructions (release_binary), at the pinned commit.
- Input: the README documents BAM (line 15); this run used STRhub's illumina-bam-hg38-med reference data.
- Panel: the loci file the documented command reads, shipped in the repository, lists coordinates inside STRhub's medical STR slice and none inside the forensic one; this run used the medical slice of the same sample (illumina-bam-hg38-med).
- The output directory the command writes into (sample) was created first.
- 1 input path(s) in the README command replaced with /data/in/input.bam.
- 1 reference FASTA path(s) replaced with /data/ref/hg38.fa.
- Run command: the one documented in docs/03_Usage.md (line 15), rewritten to STRhub's mounts; everything it created was captured as output.
- Regions: STRhub's ready-made eh_catalog file for the dataset's panel loci (STRhub records the eh_catalog layout for a program of this name).

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

