# STRhub Verified — ztest-upload (inventado → slug ztest-upload-v0-7-y (ztest-upload-inventado-slug-ztest-upload-v0-7-y-v0-7-y)

**Result: Installs** — the environment builds from source.

- Source: `https://github.com/tfwillems/HipSTR` @ `b2033bfbb5cf55496b776463bdf2993fa763a4be`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-07-19T18:00:37+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/29697849727

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | — | it executes end-to-end without crashing |
| Runs + Expected IO | — | it produces a non-empty file in the declared format |
| Runs + Plausible output | — | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **0** (malformed: 0)
- STR loci detected: **0**
- Total reads across calls: **0** (deepest single sequence: 0)



## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| STRhub fixture | N/A | N/A | — |
| External data | yes | — | Illumina BAM (hg38) — HG002 (Y-STR, male) |

## Regions

The tool author supplied the regions BED, covering 14 of 14 supported loci. The reference dataset is a slice around 14 forensic STR loci, not a whole genome: it carries reads only at those loci.

## README check (advisory)

Score: **5/5** — advisory only, does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

