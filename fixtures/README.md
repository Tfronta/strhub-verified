# Fixtures

A fixture is a **small, fast** test input — just enough to make a tool run
end-to-end. It is NOT a truth set; the project makes no accuracy claim.

## `example/`
A trivial synthetic FASTQ so the pipeline is demonstrable on a fresh clone.
Replace it for real attestations.

## Recommended: NIST Forensic DNA Open Dataset (mds2-2157)
- DOI: https://doi.org/10.18434/M32157
- Why: consent is documented and outsourced to NIST (donor samples acquired
  under NIST Research Protections Office approval), and it covers CE/MPS
  forensic assays (GlobalFiler, ForenSeq Signature Prep, PowerSeq, etc.).
- How: download a single-source FASTQ, **down-sample to a few thousand reads**
  (e.g. `seqtk sample in.fastq 5000 > sample.fastq`), and commit via Git LFS.
  Keep it tiny so CI stays under the runner limits and fast.

## ONT track (later)
mds2-2157 has no long-read data. Use a down-sampled 1000 Genomes ONT sample
for ONT-targeted tools, in a parallel fixture dir.
