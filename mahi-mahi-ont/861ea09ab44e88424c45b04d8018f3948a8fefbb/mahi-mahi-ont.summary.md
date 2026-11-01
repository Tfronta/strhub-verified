# STRhub Verified: mahi-mahi (mahi-mahi-ont)

**Runs as documented.**

## As it is in the repository

**Verdict: Runs.** The tool installed and its run produced its documented output.

Reached **Runs + Expected IO**: it produces a non-empty file in the declared format.

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |
| Starts | PASS | the installed program answers --help in the built environment |

### What the author documents as a known issue

Quoted from the repository's README at the verified commit. STRhub did not establish any of this by running the tool; it is the author's own note about their own software.

**Warnings, Precautions, and Limitations** (README line 813)

> ## Warnings and precautions - Use the loci file version that matches the reference genome passed to --ref. - Haplotagged input is recommended. If --bypass-haplotag-check is used, close-in-length alleles may be merged and accuracy may be reduced. - If using non-standard --loci, check the BED file carefully before use. - If a TR region contains sequence that is not actually repetitive, motif decomposition of this unexpected sequence may be effectively nonsensical. The reported length in bases is still meaningful. - Previous versions of mahi-mahi have used different parameters, configurations, an…

**Warnings and precautions** (README line 815)

> - Use the loci file version that matches the reference genome passed to --ref. - Haplotagged input is recommended. If --bypass-haplotag-check is used, close-in-length alleles may be merged and accuracy may be reduced. - If using non-standard --loci, check the BED file carefully before use. - If a TR region contains sequence that is not actually repetitive, motif decomposition of this unexpected sequence may be effectively nonsensical. The reported length in bases is still meaningful. - Previous versions of mahi-mahi have used different parameters, configurations, and filenames. Please refer to…

**Known limitations** (README line 827)

> - When the original BAM contains many non-spanning reads, `DP` can be lower than an allele's `AD` or the sum of `AD`. `DP` measures mean alignment depth over the reference repeat interval, whereas `AD` counts reads selected for allele-length estimation, including selected non-spanning reads. This difference does not by itself indicate an invalid call. - Expansions supported mainly by non-spanning reads may be underestimated and sized less precisely than fully spanned alleles. - Apparent interruptions may be sequencing errors. Visual verification using the read visualisation is recommended. - I…

**Troubleshooting and Support** (README line 891)

> For help, contact Oxford Nanopore Technologies through your usual support channel: [Oxford Nanopore customer support](https://nanoporetech.com/support/customer-support). ## Common checks - Confirm that the reference genome matches the loci file. - Confirm that the BAM or CRAM file is readable and indexed. - Confirm that the sample sex argument is correct. - Confirm that the input BAM is haplotagged unless --bypass-haplotag-check is intentionally being used. ## Common problems and messages | Message or issue | Likely cause | Suggested action | |------------------------|------------------------|…

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
mahi-mahi --bam /data/in/input.bam --ref /data/ref/hg38.fa --loci hg38 --sample SAMPLE --sex XX --out-dir out
```
- Log (external): [`mahi-mahi-ont.log-external.txt`](mahi-mahi-ont.log-external.txt)
- Log (starts): [`mahi-mahi-ont.log-starts.txt`](mahi-mahi-ont.log-starts.txt)
- Log (build): [`mahi-mahi-ont.log-build.txt`](mahi-mahi-ont.log-build.txt)

## Run details

- Source: `https://github.com/nanoporetech/mahi-mahi` @ `861ea09ab44e88424c45b04d8018f3948a8fefbb`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-11-01T14:11:02+00:00
- Upstream: The verified commit is 2 commit(s) behind `main`. That is context, not a fault: a pinned release is often meant to sit behind, and the attestation describes the commit it names.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/41314700506

## Output content (plausibility evidence)

- Sequence records: **99** (malformed: 0)
- STR loci detected: **0**
- Total reads across calls: **0** (deepest single sequence: 0)



## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| STRhub fixture | N/A | N/A | — | — |
| External data | yes | PASS | — | 1000 Genomes ONT, hg38 CODIS slice (R10 SUP) |
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
- Install method: [`pyproject.toml`](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/pyproject.toml)
- Run command: [`README.md` line 230](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L230): `mahi-mahi \`
- Example data: [`src/mahi_mahi/data/str_loci.hg19.bed`](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/src/mahi_mahi/data/str_loci.hg19.bed)
- Example data: [`src/mahi_mahi/data/str_loci.hg38.bed`](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/src/mahi_mahi/data/str_loci.hg38.bed)
- Known issue: [`README.md` line 813](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L813): `Warnings, Precautions, and Limitations`
- Known issue: [`README.md` line 815](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L815): `Warnings and precautions`
- Known issue: [`README.md` line 827](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L827): `Known limitations`
- Known issue: [`README.md` line 891](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L891): `Troubleshooting and Support`
- Documented input: [`README.md` line 55](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md#L55): `-   Aligned BAM or CRAM input.`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- Test data: no sample from the repository was used, so a public reference sample stood in.
- A container environment, built from the tool's declared install steps rather than from a recipe the repository ships.

## Notes from reading the repository

Recorded automatically from the tool's public files when this run was configured. **Not verified by execution**, and not part of the gates above. Useful for what to check by hand.

- Environment: generated by STRhub from the repository's pyproject.toml (pip), at the pinned commit.
- Input: the README documents BAM (line 55); this run used STRhub's ont-bam-hg38 reference data.
- 1 input path(s) in the README command replaced with /data/in/input.bam.
- 1 reference FASTA path(s) replaced with /data/ref/hg38.fa.
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

