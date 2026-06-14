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

## Real fixtures already built (two assays)
Two tiny, real fixtures are committed in-tree (5,000 reads each, ~2-4 MB),
both from donor **NTD01** so the assays are directly comparable:

| Tool dir | Assay (Illumina) | Fixture | Config |
|---|---|---|---|
| `tools/strait-razor-PowerSeqv2.31` | Promega PowerSeq 46GY | `tools/strait-razor-PowerSeqv2.31/fixtures/nist-mds2-2157/sample.fastq` | `PowerSeqv2.31.config` |
| `tools/strait-razor-ForenSeqv1.27` | Verogen ForenSeq      | `tools/strait-razor-ForenSeqv1.27/fixtures/nist-mds2-2157/sample.fastq` | `ForenSeqv1.27.config` |

Each fixture dir has a `SOURCE.txt` with exact provenance and the rebuild snippet.

## How they were built (no multi-GB download)
The per-assay zips are huge (PowerSeq 5.8 GB, ForenSeq 7.6 GB) but NIST serves
them from S3 with HTTP range support, so we pull just ONE FASTQ from inside the
zip with `remotezip` and keep only the first 5,000 reads — no full download.

```bash
python -m pip install remotezip   # use a venv if your Python is externally managed
python - <<'PY'
import io
from remotezip import RemoteZip
# PowerSeq 46GY single-source donor NTD01, read 1:
url ="https://data.nist.gov/od/ds/ark:/88434/mds2-2157/NGS_Assays/Promega_PowerSeq_46GY.zip"
name="Promega_PowerSeq_46GY/PowerSeq46GY-SingleSource/PS_NTD01_S1_L001_R1_001.fastq"
with RemoteZip(url) as z, z.open(name) as fh, open("sample.fastq","wb") as w:
    r=io.BufferedReader(fh)
    for _ in range(5000):
        rec=[r.readline() for _ in range(4)]
        if not rec[3]: break
        w.writelines(rec)
PY
```
(For ForenSeq use the zip/member in `tools/strait-razor-ForenSeqv1.27/fixtures/nist-mds2-2157/SOURCE.txt`.)

The classic route still works too — `curl` the whole zip, `unzip`, then
`seqkit sample -n 5000 <single_source>.fastq -o sample.fastq` — it just downloads
several GB you don't need.

## Match the config to the assay
STRait Razor needs the config that matches the kit:
- ForenSeq reads  -> `ForenSeqv1.27.config`
- PowerSeq reads  -> `PowerSeqv2.31.config`  (what the example manifest uses)

If you switch assays, update `run.cmd` in the variant's `manifest.yml`
accordingly (and make sure the Dockerfile installs that config file).
