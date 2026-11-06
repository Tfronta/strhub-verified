# STRhub Verified: TRGT (trgt-hifi-med)

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
| Reproduces own example | PASS | the README's own command produced its documented output on the repository's own data |

### What the author documents as a known issue

Quoted from the repository's README at the verified commit. STRhub did not establish any of this by running the tool; it is the author's own note about their own software.

**Active development warning** (README line 18)

> Please note that TRGT is still under active development. We anticipate some changes to the input and output file formats of TRGT.

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
mkdir -p sample && trgt genotype --genome /data/ref/hg38.fa --repeats /data/in/regions.bed --reads /data/in/input.bam --output-prefix sample
```
- Log (example): [`trgt-hifi-med.log-example.txt`](trgt-hifi-med.log-example.txt)
- Log (starts): [`trgt-hifi-med.log-starts.txt`](trgt-hifi-med.log-starts.txt)
- Log (build): [`trgt-hifi-med.log-build.txt`](trgt-hifi-med.log-build.txt)

## Run details

- Source: `https://github.com/PacificBiosciences/trgt` @ `b21c6217eeaef9a080205932fe29f730dc00e31f`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-11-06T16:14:18+00:00
- Upstream: The verified commit is the head of `main`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/42250070770

## Output content (plausibility evidence)

- Sequence records: **51** (malformed: 0)
- STR loci detected: **51**
- Total reads across calls: **2143** (deepest single sequence: 73)
- STR loci: AFF2, AFF3, AR, ARX, ATN1, ATXN1, ATXN10, ATXN2, ATXN3, ATXN7, ATXN8OS, BEAN1, C9orf72, CACNA1A, CBL, CNBP, COMP, CSTB …
- Top markers by read depth: NUTM2B-AS1 (73), RAPGEF2 (67), STARD7 (60), AFF3 (60), DAB1 (58), SAMD12 (56)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | — | GIAB HG002 PacBio HiFi (Revio), hg38 medical STR slice |
| Tool's own example | yes | PASS | — | — |

## Regions

STRhub supplied the regions BED. The reference dataset is a slice around 51 disease-associated STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Run command: [`docs/tutorial.md` line 39](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/docs/tutorial.md#L39): `./trgt genotype --genome example/reference.fasta \`
- Example data: [`example/repeat.bed`](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/example/repeat.bed)
- Example data: [`example/reference.fasta`](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/example/reference.fasta)
- Example data: [`example/sample.bam`](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/example/sample.bam)
- Example data: [`repeats/pathogenic_repeats.hg38.bed`](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/repeats/pathogenic_repeats.hg38.bed)
- Example data: [`repeats/repeat_catalog.hg38.bed`](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/repeats/repeat_catalog.hg38.bed)
- Known issue: [`README.md` line 18](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/README.md#L18): `Active development warning`
- Documented input: [`README.md` line 9](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/README.md#L9): `It is now possible to add a fail reads BAM as a separate aligned BAM in addition to the primary `--reads` BAM.`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, built from the tool's declared install steps rather than from a recipe the repository ships.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's install instructions (release_binary), at the pinned commit.
- Input: the README documents BAM (line 9); this run used STRhub's pacbio-hifi-bam-hg38-med reference data.
- Panel: the loci file the documented command reads, shipped in the repository, lists coordinates inside STRhub's medical STR slice and none inside the forensic one; this run used the medical slice of the same sample (pacbio-hifi-bam-hg38-med).
- './trgt' run as 'trgt' from the PATH: the build puts it there, not in the directory the documentation runs it from.
- The output directory the command writes into (sample) was created first.
- 1 input path(s) in the README command replaced with /data/in/input.bam.
- 1 reference FASTA path(s) replaced with /data/ref/hg38.fa.
- 1 BED path(s) replaced with /data/in/regions.bed.

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

