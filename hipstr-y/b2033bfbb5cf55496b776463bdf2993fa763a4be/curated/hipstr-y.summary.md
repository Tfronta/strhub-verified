# STRhub Verified: hipstr (hipstr-y)

**Not verified as documented.**

## What STRhub had to do to run this tool

STRhub wrote its own recipe for this tool, an environment and a command of its own rather than the repository's instructions, and ran that. Each item below is something a first-time user following the README would have to work out for themselves, and so a recommendation to the author. This run does not change the tool's label: the label is what happens as it is in the repository.

- Runs HipSTR with flags tuned to STRhub's reference slice (--min-reads 5 --use-unpaired --read-qual-trim ! --def-stutter-model --max-str-len 250). Instead of: The README's command, which has none of them. On a BAM slice around the panel loci most mates fall outside the slice and read quality trims most reads; without these flags nearly every locus is skipped.
- Supplies the Y-STR regions BED from STRhub's library. Instead of: A regions file the README leaves to the user.

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
HipSTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa --regions /data/in/regions.bed --str-vcf /data/out/result.vcf.gz --min-reads 5 --use-unpaired --read-qual-trim ! --def-stutter-model --max-str-len 250
```
- Log (own): [`hipstr-y.log-own.txt`](hipstr-y.log-own.txt)
- Log (external): [`hipstr-y.log-external.txt`](hipstr-y.log-external.txt)
- Log (build): [`hipstr-y.log-build.txt`](hipstr-y.log-build.txt)

## Run details

- Source: `https://github.com/tfwillems/HipSTR` @ `b2033bfbb5cf55496b776463bdf2993fa763a4be`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-20T16:54:38+00:00
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35524008276

## Output content (plausibility evidence)

- Sequence records: **13** (malformed: 0)
- STR loci detected: **13**
- Total reads across calls: **2912** (deepest single sequence: 320)
- STR loci: DYS385_2, DYS389I, DYS389II.1, DYS390, DYS391, DYS392, DYS393, DYS438, DYS456, DYS458, DYS635, Y-GATA-A10, Y-GATA-H4
- Top markers by read depth: Y-GATA-H4 (320), DYS389II.1 (298), DYS389I (272), DYS635 (258), DYS385_2 (219), DYS390 (218)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| External data | yes | PASS | — | Illumina BAM (hg38), HG002 (Y-STR, male) |
| Tool's own example | N/A | N/A | — | — |

## Regions

STRhub supplied the regions BED. The reference dataset is a slice around 14 forensic STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Evidence

What this run's configuration rests on, each item at the verified commit. Open any of them to check the claim it supports.
- Install method: [`Makefile`](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/Makefile)
- Run command: [`README.md` line 69](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/README.md#L69): `./HipSTR --bams          run1.bam,run2.bam,run3.bam,run4.bam`
- Example data: [`test/input/chr1_regions.bed`](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/test/input/chr1_regions.bed)
- Example data: [`test/input/chr1_regions_v2.bed`](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/test/input/chr1_regions_v2.bed)
- Example data: [`test/input/1kg.chr1.imputed.vcf.gz`](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/test/input/1kg.chr1.imputed.vcf.gz)
- Documented input: [`README.md` line 69](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/README.md#L69): `./HipSTR --bams          run1.bam,run2.bam,run3.bam,run4.bam`
- Platform advice: [`README.md` line 435](https://github.com/tfwillems/HipSTR/blob/b2033bfbb5cf55496b776463bdf2993fa763a4be/README.md#L435): `We do not recommend running it on PacBio or Oxford Nanopore data, as the difference in error profiles will be problematic`

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

