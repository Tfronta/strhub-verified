# Reference datasets (typed library)

STRhub Verified uses these **third-party, open-access** materials only as
fixed inputs for the **external** verification leg (smoke-test that a tool runs
on data other than the author's own example). STRhub Verified is **not** a data
repository or custodian of genomic data.

## Disclaimer

- **No ownership.** STRhub does not claim ownership, custodianship, or
  curation of any dataset listed here. Each entry points to its original source
  and license.
- **No accuracy or casework claim.** Running against these datasets proves
  reproducible execution only — not genotype correctness, representative
  sampling, or fitness for forensic casework.
- **Third-party terms apply.** Users and tool authors remain bound by the terms
  of the upstream providers (NIST, 1000 Genomes / Human Pangenome Reference
  Consortium, etc.).

See each subdirectory's `SOURCE.txt` for provenance, chemistry, and rebuild notes.

## Catalogue

| Type slug | Format | Data location | Source |
|---|---|---|---|
| `illumina-str-fastq` | FASTQ | `datasets/illumina-str-fastq/sample.fastq` (ForenSeq slice; NIST also has PowerSeq) | [NIST mds2-2157](https://data.nist.gov/od/id/mds2-2157) |
| `ont-bam-hg38` | BAM (hg38) | `ont_slices/*.codis.bam` | [1000 Genomes ONT on AWS](https://s3.amazonaws.com/1000g-ont/index.html?prefix=PROCESSED_DATA/ALIGNED_TO_HG38/MINIMAP2_ALIGNED_BAMS/) |

**Scope:** reference datasets cover **STR assays only** (Illumina STR FASTQ and ONT
CODIS BAM). No SNP panels or capillary FSA/HID reference data.

Machine-readable index: `datasets/index.json`. The workflow resolves
`manifest.inputs.type` → compatible dataset (or **N/A** if none).
