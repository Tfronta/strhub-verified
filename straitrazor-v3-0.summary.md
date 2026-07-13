# STRhub Verified — STRaitRazor (straitrazor-v3-0)

**Result: Runs + Plausible output** — its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

- Source: `https://github.com/Ahhgust/STRaitRazor` @ `b618e9345ab40f348b504083ae8de2b39abb60fa`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-07-13T13:14:08+00:00
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/29252914145

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **816** (malformed: 0)
- STR loci detected: **63**  ·  identity SNPs (rsNNNN): **157**  (total panel markers: 220)
- Total reads across calls: **3967** (deepest single sequence: 132)
- STR loci: Amelogenin, CSF1PO, D10S1248, D12S391, D13S317, D16S539, D17S1301, D18S51, D19S433, D1S1656, D20S482, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D4S2408, D5S818 …
- Top markers by read depth: DYS392 (170), DYS438 (117), D6S1043 (111), TH01 (106), DYS389I (97), DYS576 (95)

## Verification matrix

| Leg | Available | Result | Dataset |
|---|---|---|---|
| STRhub fixture | N/A | N/A | — |
| External data | yes | PASS | NIST mds2-2157 — Illumina STR (ForenSeq slice, donor NTD01) |

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

