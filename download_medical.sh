#!/bin/bash
set -euo pipefail

# Cuts the medical STR slices from the same public sources as the forensic ones:
#
#   illumina-bam-hg38-med       -> illumina_slices/NA12878.medical.bam (GIAB HG001 300x, ±1 kb)
#   pacbio-hifi-bam-hg38-med    -> pacbio_slices/HG002.hifi.medical.bam (GIAB HG002 Revio, ±10 kb)
#
# Loci: datasets/illumina-bam-hg38-med/str_candidates.bed and pacbio_slices/medical_pm10kb.bed,
# both written by harness/build_medical_candidates.py. Plain BAMs streamed over HTTPS through
# their index: only samtools and a network connection are needed, no reference FASTA.
# After cutting, run harness/build_panel.py and harness/build_regions_library.py.

cd "$(dirname "$0")"

HG001="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/NA12878/NIST_NA12878_HG001_HiSeq_300x/NHGRI_Illumina300X_novoalign_bams/HG001.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam"
HG002_HIFI="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/AshkenazimTrio/HG002_NA24385_son/PacBio_HiFi-Revio_20231031/HG002_PacBio-HiFi-Revio_20231031_48x_GRCh38-GIABv3.bam"
PAD=1000
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# ── Illumina (NA12878 / HG001) ───────────────────────────────────────────────
# Same recipe as the autosomal slice in download.sh: candidate tracts ±PAD, sorted,
# re-tagged with one read group (the source BAM has none; HipSTR requires one).
awk -v p=$PAD 'BEGIN{OFS="\t"} !/^#/ {s=$2-1-p; print $1, (s<0?0:s), $3+p}' \
  datasets/illumina-bam-hg38-med/str_candidates.bed | sort -k1,1 -k2,2n > "$tmp/ill.bed"

echo "=== [1/2] NA12878 medical: slicing $(grep -c . "$tmp/ill.bed") regions from HG001 ==="
# -M: the multi-region iterator, which seeks through the index. Without it -L is a
# filter over every record, and the source is a whole 300x genome read over HTTPS.
samtools view -b -M -L "$tmp/ill.bed" "$HG001" \
  | samtools sort -O bam - \
  | samtools addreplacerg -r $'@RG\tID:NA12878\tSM:NA12878\tLB:GIAB300x\tPL:ILLUMINA' \
      -o illumina_slices/NA12878.medical.bam -
samtools index illumina_slices/NA12878.medical.bam

# ── PacBio HiFi (HG002) ──────────────────────────────────────────────────────
# Same recipe as HG002.hifi.codis.bam (datasets/pacbio-hifi-bam-hg38/SOURCE.txt): kinetics
# and signal-to-noise tags dropped, everything else as distributed.
echo "=== [2/2] HG002 HiFi medical: slicing $(grep -c . pacbio_slices/medical_pm10kb.bed) windows ==="
samtools view -b -M -L pacbio_slices/medical_pm10kb.bed -X \
    -x fi -x fp -x ri -x rp -x ip -x pw -x sn \
    -o "$tmp/hifi.raw.bam" "$HG002_HIFI" "$HG002_HIFI.bai"
samtools sort -o pacbio_slices/HG002.hifi.medical.bam "$tmp/hifi.raw.bam"
samtools index pacbio_slices/HG002.hifi.medical.bam

# htslib caches each remote index in the working directory (12 MB and 23 MB);
# they are not part of the dataset and must not be committed.
rm -f "$(basename "$HG001").bai" "$(basename "$HG002_HIFI").bai"

ls -la illumina_slices/NA12878.medical.bam* pacbio_slices/HG002.hifi.medical.bam*
