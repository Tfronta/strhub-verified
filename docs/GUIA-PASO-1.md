# Step 1: what a commit needs to state so a stranger can run the tool

STRhub Verified tests one thing first, before anything about forensic STR panels:

> At the pinned commit, can a third party install the tool and run it end to end by following
> only what that commit writes, and get the output file the command names?

Nothing is invented to fill a gap. STRhub does not write the install for you, does not add a
flag that your command does not carry, and does not guess a file layout. If a step is missing,
the report says which one, and the run is not attempted. That is why this page exists: it is the
whole contract, and it is four blocks long.

This is not a style guide and it is not a review of your software. A tool can be excellent and
still fail step 1, because step 1 is about the commit, not about the code.

---

## The four blocks

### 1. Installation, copyable

A code block with the commands and the versions. Any one of these is enough:

- the `Dockerfile` in the commit itself, built as it is;
- a release binary that the documentation tells the reader to download;
- the lines of the block: `conda env create -f environment.yml`, `pip install .`, `make`,
  `cmake .. && make`, `cargo build --release`, an install script the block invokes.

```bash
# good: unambiguous, and the file it names is in the tree
conda env create -f environment.yml
conda activate mytool
pip install .
```

What does not count: prose that has to be interpreted (“install the usual dependencies and
compile”), a list of library names without the command that installs them, or a link to an
external wiki. The wiki is not in the commit.

### 2. One command

The command for a single sample, in a code block, with no synopsis brackets.

```bash
# good
mytool --bam sample.bam --ref hg38.fa --regions panel.bed --out sample.vcf

# not a command: this is a usage synopsis
mytool --bam <in.bam> [--regions FILE] [--threads N] ...
```

A synopsis is not a command. Dropping the optional arguments to turn it into one is a change to
your procedure, so STRhub will not do it: it reports that no command was found. If your README
has a synopsis for reference, add a worked example line as well.

### 3. The declared input

The file the command names, plus one line saying what kind of file it is (BAM, CRAM, FASTQ,
other). The file is either in the commit or an explicit placeholder: `<sample.bam>`,
`path/to/sample.bam`, `$BAM`.

If the reference genome or the assembly matters, say which one (hg19, hg38, T2T). If the command
reads a regions or catalog file, say what its columns are, or ship the file.

**The strongest thing you can do here is commit a small example.** A slice of a few megabytes
that the command in block 2 can read turns step 1 into something any user, reviewer or editor can
reproduce in seconds, and it removes STRhub's sample shelf from the equation entirely.

### 4. The declared output

The file the command writes, by name.

```markdown
Writes `sample.vcf` in the output directory.
```

If the documentation does not name an output, STRhub has no way to tell your result from any
stray file the run left behind, so it will not claim the output appeared. A directory name plus
the extension is enough (`out/*.vcf`), as long as it is stated.

---

## What STRhub does with this

It packages exactly the install you declared into a container and runs exactly the command you
wrote, on the files that command names. Packaging your `Makefile` or your `environment.yml` into
an image is wrapping your own instructions, not a second recipe. Adding a dependency you did not
list, rewriting your build, or swapping your input kind for one we happen to hold would be a
different procedure, and a result from it says nothing about your commit, so it is not published
as one.

Three outcomes, and none of them is a judgement about your software:

| Outcome | What it means |
|---|---|
| **As documented, it runs.** | The install ran, the command finished, and the output file you named appeared. Nothing is claimed about genotype accuracy or fitness for casework. |
| **As documented, it does not run.** | The procedure was executed without amendment and stopped. This does not mean the tool does not work. It means a third party following the README at this commit did not reach the end. The log is linked. |
| **A third party cannot tell how to run it.** | Nothing was executed, because one of the four blocks is missing. The report names the block. |

There is also a fourth case that is **ours, not yours**: STRhub may not hold a sample of the kind
your command reads, or may hold slices of other coordinates. The report says so in those words.
It is a limitation of our reference data and it is never reported as your tool failing.

## Trying again

Fix the block the report names, then submit the link again on the new commit. Verification is
pinned to a commit, so a new attempt is a new commit. There is no form where STRhub writes the
missing piece for you, on purpose: the value of the attestation is that nobody filled the gap.

## What step 1 does not say

It does not say the genotypes are correct, that the tool agrees with capillary electrophoresis,
or that it is fit for casework. Those need a truth set, and phase 1 does not have one. Step 1 is
reproducibility of installation and execution, and the report says so on its first page.

Only after step 1 finishes does STRhub run the forensic pipeline (the public hg38 reference
sample over the CODIS and expanded panels, the registered regions file, the content check). If we
cannot do that part, the step 1 result stands on its own.
