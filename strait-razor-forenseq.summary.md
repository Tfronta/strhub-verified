# STRhub Verified: STRait Razor (strait-razor-forenseq)

**Result: Runs + Plausible output.** its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci).

**Verdict: Runs.** The tool installed and its run produced its documented output.

- Source: `https://github.com/Ahhgust/STRaitRazor` @ `b618e9345ab40f348b504083ae8de2b39abb60fa`
- Environment: ubuntu-22.04 (`Dockerfile`)
- Generated: 2026-09-19T18:19:36+00:00
- Upstream: The verified commit is the head of `master`.
- Recipe: a recipe STRhub wrote by hand, not read off the repository: a note under the documented result, never the badge
- CI run: https://github.com/Tfronta/strhub-verified/actions/runs/35460767865

## Command that ran

Executed verbatim inside the container, at the pinned commit. Paths under /data are STRhub's mounts: the input sample, the reference genome and the output directory.

```
str8rzr -c /opt/strait-razor/ForenSeqv1.27.config /data/in/sample.fastq > /data/out/sample.allsequences.txt
```

## Gates

| Gate | Status | Meaning |
|---|---|---|
| Available | PASS | the pinned public source exists |
| Installs | PASS | the environment builds from source |
| Runs | PASS | it executes end-to-end without crashing |
| Runs + Expected IO | PASS | it produces a non-empty file in the declared format |
| Runs + Plausible output | PASS | its output looks like plausible genotype-bearing data (declared columns, DNA sequences, integer read counts, and enough recognisable forensic loci) |

## What the author documents as a known issue

Quoted from the repository's README at the verified commit. STRhub did not establish any of this by running the tool; it is the author's own note about their own software.

**known issues** (README line 114)

> There's been one computer architecture (windows 7 + Xeon processor) that's caused some issues with the str8rzr.exe executable. In this case, str8rzr would occassionally crash, and I had to recompile it for that computer (and since then it's been fine). Please let me know if you experience problems-- especially crashes-- it'll let me further diagnose the exact problems therein. str8rzr is written in C/C++ with multithreading support using the pthreads library. This new release couples a new search strategy (see algorithm) coupled with a complete redesign of the code-base used to identify short …

## Output content (plausibility evidence)

- Sequence records: **816** (malformed: 0)
- STR loci detected: **63**  ·  identity SNPs (rsNNNN): **157**  (total panel markers: 220)
- Total reads across calls: **3967** (deepest single sequence: 132)
- STR loci: Amelogenin, CSF1PO, D10S1248, D12S391, D13S317, D16S539, D17S1301, D18S51, D19S433, D1S1656, D20S482, D21S11, D22S1045, D2S1338, D2S441, D3S1358, D4S2408, D5S818 …
- Top markers by read depth: DYS392 (170), DYS438 (117), D6S1043 (111), TH01 (106), DYS389I (97), DYS576 (95)

## Verification matrix

| Leg | Available | Result | Errors reported | Dataset |
|---|---|---|---|---|
| External data | yes | PASS | — | NIST mds2-2157, Illumina STR (ForenSeq slice, donor NTD01) |
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
- Install method: [`Makefile`](https://github.com/Ahhgust/STRaitRazor/blob/b618e9345ab40f348b504083ae8de2b39abb60fa/Makefile)
- Run command: [`README.md` line 123](https://github.com/Ahhgust/STRaitRazor/blob/b618e9345ab40f348b504083ae8de2b39abb60fa/README.md#L123) — `str8rzr -c configFile fastqfile > allsequences.txt`
- Known issue: [`README.md` line 114](https://github.com/Ahhgust/STRaitRazor/blob/b618e9345ab40f348b504083ae8de2b39abb60fa/README.md#L114) — `known issues`
- Documented input: [`README.md` line 19](https://github.com/Ahhgust/STRaitRazor/blob/b618e9345ab40f348b504083ae8de2b39abb60fa/README.md#L19) — `Put str8rzr.exe, batchCstr8.bat, the appropriate config file (Forenseq.config), and all fastq files into this directory.<br>`

## What this run needed beyond the repository

The result above describes a run configured as follows. Anyone repeating it needs the same things.

- A container environment and a command written by STRhub, not taken from the repository's instructions; what they do differently is listed under the recipe.

## What STRhub's recipe does that the repository's instructions do not

This run used a recipe STRhub wrote. Each item below is a departure from the README that a first-time user would have to discover for themselves. The badge rests on the run of the repository's own instructions, not on this one.

- Builds with make (falling back to cmake) and copies str8rzr to /usr/local/bin. — instead of: The README's build steps, which name no install location.
- Picks the ForenSeq kit configuration (ForenSeqv1.27.config) and the STRhub fixture for it. — instead of: A configuration and input the README leaves to the user; the repository ships several kit configurations.

## Scope (read this)

Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

This is **not** a claim that the genotypes are correct, nor that the tool is fit for casework or meets any regulatory standard. Concordance against known truth is out of scope.

Verified automatically, in a clean environment, on the tool's public source at the pinned commit. This is a record of what happened, not an endorsement by the tool's author.

