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

## ONT track — `ont-bam-hg38`

mds2-2157 has no long-read data. ONT tools use the typed dataset **`ont-bam-hg38`**
(see `datasets/ont-bam-hg38/` + `ont_slices/`).

- **Source:** [1000 Genomes ONT on AWS](https://s3.amazonaws.com/1000g-ont/index.html?prefix=PROCESSED_DATA/ALIGNED_TO_HG38/MINIMAP2_ALIGNED_BAMS/) (open access)
- **Chemistry:** ONT R10, basecalling model SUP
- **Slices:** pre-built CODIS ±10 kb extracts in `ont_slices/*.codis.bam` (already in-repo)
- **Default CI file:** `ont_slices/HG00113.codis.bam` (+ `.bai`)
- **Disclaimer:** see `datasets/README.md` — STRhub is not the data provider
