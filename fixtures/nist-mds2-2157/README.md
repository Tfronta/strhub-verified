# Fixture: NIST Forensic DNA Open Dataset (mds2-2157) — MPS/CE track

Consent-clean fixture for the **MPS/CE track** (Illumina + Ion Torrent forensic
assays). This is the dataset Jonathan King recommended; consent is documented
and outsourced to NIST.

- DOI: 10.18434/M32157 · Landing: https://data.nist.gov/od/id/mds2-2157
- Use scope (NIST): research, training, and educational purposes only; not to be
  used to identify the donor or searched against DNA databases. A smoke-test
  fixture falls squarely within that scope.

## IMPORTANT — data type
Everything in `NGS_Assays/` is **short-read MPS** (Illumina MiSeq / Ion Torrent),
amplicon-based. There is **NO Oxford Nanopore / long-read data** here.
- Use it for MPS tools (e.g. STRait Razor, lusSTR).
- Do NOT use it for ONT tools (e.g. STRspy) — wrong read type. Those use the
  `fixtures/strspy-bam` (1KGP-ONT) fixture instead.

## Download (sequencing reads live in NGS_Assays)
```bash
BASE=https://data.nist.gov/od/ds/ark:/88434/mds2-2157
curl -sL "$BASE/README_Forensic_DNA_Open_Dataset.txt" -o NIST_README.txt

# Pick ONE assay that matches your tool's config:
#   ForenSeq (Illumina MiSeq):
curl -L "$BASE/NGS_Assays/Verogen_ForenSeq_DNA_Signature_Prep_Kit.zip" -o forenseq.zip
#   PowerSeq 46GY (Illumina):
curl -L "$BASE/NGS_Assays/Promega_PowerSeq_46GY.zip" -o powerseq46gy.zip
#   (checksums available by appending .sha256 to any URL)
```

## Build a tiny fixture
```bash
unzip -q powerseq46gy.zip -d powerseq46gy
# Read the bundled README to choose a single-source sample, then down-sample it:
seqkit sample -n 5000 powerseq46gy/<some_single_source>.fastq.gz -o sample.fastq
# place it where the manifest expects:
mkdir -p fixtures/nist-mds2-2157
mv sample.fastq fixtures/nist-mds2-2157/sample.fastq
```

## Match the config to the assay
STRait Razor needs the config that matches the kit:
- ForenSeq reads  -> `ForenSeqv1.27.config`
- PowerSeq reads  -> `PowerSeqv2.31.config`  (what the example manifest uses)

If you switch assays, update `run.cmd` in `tools/strait-razor/manifest.yml`
accordingly (and make sure the Dockerfile installs that config file).
