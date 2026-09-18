# STRhub Verified: GangSTR (gangstr)

**Result: Runs + Plausible output.** its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

**Verdict: Runs.** The tool installed and its run produced its documented output.

- Source: `https://github.com/gymreklab/gangstr` @ `6ea9b2b8daca51dcab1f0e46210622b94b52ff17`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-15T19:53:01+00:00
- Submitted by: a third party — not the tool's maintainer
- Upstream: The verified commit is the head of `master`.
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35016057251

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## Output content (plausibility evidence)

- Sequence records: **24** (malformed: 0)
- STR loci detected: **24**
- Total reads across calls: **10738** (deepest single sequence: 757)
- STR loci: CSF1PO, D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D1S1656, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D5S818, D6S1043, D7S820, D8S1179, FGA …
- Top markers by read depth: D18S51 (757), D16S539 (618), PentaD (613), D5S818 (589), D6S1043 (585), D7S820 (579)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| External data | yes | PASS | — | Illumina BAM (hg38), NA12878 (autosomal, female) |
| Tool's own example | N/A | N/A | — | — |

## Regions

STRhub supplied the regions BED. The reference dataset is a slice around 24 forensic STR loci, not a whole genome: it carries reads only at those loci.

## Who submitted this

This tool was submitted for verification by somebody other than its maintainer. The maintainer took no part in the run and supplied none of what it used: the command, the environment, and any target regions were chosen by the submitter. Where a maintainer is named above, that names who answers for the software — not who asked for this report, and not an endorsement of it.

## README check (advisory)

Score: **5/5**. Advisory only; does not affect the execution badge.

- PASS install
- PASS command
- PASS input
- PASS output
- PASS dependencies

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

