#!/bin/bash
set -euo pipefail

cd ~/Desktop/Proyectos/Validacion-Softwares-NGS/strhub-verified

# Regenerates the committed Illumina BAM slices from public GIAB 300x sources.
# These are plain BAMs (not CRAM), so NO local reference FASTA is needed — only
# samtools and a network connection. Slices stream just the forensic-STR regions.
#
# NOTE: GIAB novoalign BAMs have NO @RG (read groups). HipSTR requires read groups
# (its run.cmd does not pass --bam-samps), so each slice is re-tagged via
# `samtools addreplacerg` with a single sample read group.
#
#   illumina-bam-hg38    -> NA12878.autosomal.bam (HG001, female, 24 autosomal loci)
#   illumina-bam-hg38-y  -> HG002.ystr.bam        (HG002, male, 15 Y-STR loci)

HG001="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/NA12878/NIST_NA12878_HG001_HiSeq_300x/NHGRI_Illumina300X_novoalign_bams/HG001.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam"
HG002="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/AshkenazimTrio/HG002_NA24385_son/NIST_HiSeq_HG002_Homogeneity-10953946/NHGRI_Illumina300X_AJtrio_novoalign_bams/HG002.GRCh38.300x.bam"
PAD=1000

mkdir -p illumina_slices

# ── Autosomal (NA12878 / HG001) ──────────────────────────────────────────────
# Slice regions = HipSTR region intervals padded ±PAD bp to capture flanking reads.
AUTO_REGIONS="tools/hipstr-v0-7/assets/regions.bed"
awk -v p=$PAD 'BEGIN{OFS="\t"}{s=$2-p; print $1, (s<0?0:s), $3+p}' "$AUTO_REGIONS" \
  | sort -k1,1 -k2,2n > /tmp/auto_slice.bed

echo "=== [1/2] NA12878 autosomal: slicing $(grep -c . /tmp/auto_slice.bed) regions from HG001 ==="
samtools view -b -L /tmp/auto_slice.bed "$HG001" \
  | samtools sort -O bam - \
  | samtools addreplacerg -r $'@RG\tID:NA12878\tSM:NA12878\tLB:GIAB300x\tPL:ILLUMINA' \
      -o illumina_slices/NA12878.autosomal.bam -
samtools index illumina_slices/NA12878.autosomal.bam

# ── Y-STR (HG002) ────────────────────────────────────────────────────────────
# Guarded: only rebuilds if the Y regions.bed is complete (18 rows), so a partial
# region set never overwrites the committed HG002.ystr.bam. To complete it, see
# datasets/illumina-bam-hg38-y/README.md.
Y_REGIONS="datasets/illumina-bam-hg38-y/regions.bed"
if [[ -f "$Y_REGIONS" ]] && [[ $(grep -c . "$Y_REGIONS") -ge 18 ]]; then
  awk -v p=$PAD 'BEGIN{OFS="\t"}{s=$2-p; print $1, (s<0?0:s), $3+p}' "$Y_REGIONS" \
    | sort -k1,1 -k2,2n > /tmp/y_slice.bed
  echo "=== [2/2] HG002 Y-STR: slicing $(grep -c . /tmp/y_slice.bed) regions from HG002 ==="
  samtools view -b -L /tmp/y_slice.bed "$HG002" \
    | samtools sort -O bam - \
    | samtools addreplacerg -r $'@RG\tID:HG002\tSM:HG002\tLB:GIAB300x\tPL:ILLUMINA' \
        -o illumina_slices/HG002.ystr.bam -
  samtools index illumina_slices/HG002.ystr.bam
else
  echo "=== [2/2] HG002 Y-STR: SKIPPED ==="
  echo "    $Y_REGIONS has <18 loci. Not rebuilding, to avoid overwriting the"
  echo "    committed HG002.ystr.bam with a partial slice."
  echo "    Complete the region set first: datasets/illumina-bam-hg38-y/README.md"
fi

# ── Result ───────────────────────────────────────────────────────────────────
echo "=== Result ==="
for B in illumina_slices/NA12878.autosomal.bam illumina_slices/HG002.ystr.bam; do
  [[ -f "$B" ]] && printf "  %-32s %8s reads   %s\n" "$B" "$(samtools view -c "$B")" "$(du -h "$B" | cut -f1)"
done
