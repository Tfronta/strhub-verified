# STRhub Verified: STRsearch (strsearch)

**Does not run as documented: stops at install.**

## As it is in the repository

**Step 1, the documented run: As documented, it does not run.** The environment did not build from the declared install steps. That does not mean the tool does not work. It means a third party following the README at this commit did not reach the end.

**Verdict: Fails.** The environment did not build from the declared install steps.

What stopped it, and what can be done:

- The environment did not build from the declared install steps.
  - Yourself: Adjust the install steps and try again.
  - The tool's owner: open an issue, "Documented Dockerfile build fails at pinned commit".

Reached **Available**: the pinned public source exists.

### Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | — | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |
| Starts | — | the installed program answers --help in the built environment |

### It did not build from source

STRhub tried to build the tool from its source at the pinned commit, following the build steps the repository declares, and the build failed. Nothing below the Installs gate ran.

What this means:

- **If you are trying to run it:** A build from source at this commit fails in a clean environment; the cause and a suggested fix are below.
- **If you are reviewing a paper:** Nothing ran, so this says nothing about the software's output. It records that this attempt to build it stopped, and whose side the cause is on.
- **If you maintain it:** The cause could not be classified automatically. The full build output is linked below.

What failed:

| What happened | Times | Suggested fix |
|---|---|---|
| A file the build fetches over HTTP could not be downloaded: usearch | 1 | The URL returned HTTP 404. The upstream download link is no longer valid. |

Full build output: [`strsearch.log-build.txt`](strsearch.log-build.txt)

### Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
python3 /opt/STRsearch/pipeline.py --type paired --num_processors 4 --reads_threshold 30 --stutter_ratio 0.5 from_bam --working_path /data/out --sample sample --sex female --bam /data/in/input.bam --ref_bed /data/in/regions.bed --genotypes /data/out/genotypes.txt --multiple_alleles /data/out/multiple_alleles.txt --qc_matrix /data/out/qc_matrix.txt
```
- Log (build): [`strsearch.log-build.txt`](strsearch.log-build.txt)
- Log (external): [`strsearch.log-external.txt`](strsearch.log-external.txt)

## Run details

- Source: `https://github.com/AnJingwd/STRsearch` @ `c70179b3b175adc82a7314409af06900b3861d61`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-11-08T16:00:00+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/42254219171

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| External data | yes | — | — | Illumina BAM (hg38), NA12878 (autosomal, female) |

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

Executed in a standardized environment following the repository's declared build instructions. Concerns reproducible execution only.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

Verified automatically, in a clean environment, on the tool's public source at the pinned commit. This is a record of what happened, not an endorsement by the tool's author.

