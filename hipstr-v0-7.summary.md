# STRhub Verified — hipstr (hipstr-v0-7)

**Result: Runs + Plausible output** — its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

- Source: `https://github.com/tfwillems/HipSTR` @ `b2033bfbb5cf55496b776463bdf2993fa763a4be`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-06-22T13:36:19+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/27956541776

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **23** (malformed: 0)
- STR loci detected: **23**
- Total reads across calls: **0** (deepest single sequence: 0)
- STR loci: CSF1PO, D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D1S1656, D22S1045, D2S1338, D2S441, D3S1358, D5S818, D6S1043, D7S820, D8S1179, FGA, PentaD …
- Top markers by read depth: D1S1656 (0), D10S1248 (0), TH01 (0), vWA (0), D12S391 (0), D13S317 (0)

## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| STRhub fixture | yes | PASS | — |
| External data | yes | PASS | Illumina BAM (hg38) — NA12878 (autosomal, mujer) |

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

