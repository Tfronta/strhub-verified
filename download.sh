#!/bin/bash
set -euo pipefail

cd ~/Desktop/Proyectos/Validacion-Softwares-NGS/strhub-verified

REF_FASTA="/Users/tfronta/Downloads/GRCh38_full_analysis_set_plus_decoy_hla.fa"

rm -f illumina_slices/HG00145.codis.bam illumina_slices/HG00145.codis.bam.bai
mkdir -p illumina_slices

BED=~/Desktop/Proyectos/Validacion-Softwares-NGS/datasets/illumina-bam-hg38/codis27_hg38_padded.bed

echo "=== [1/3] Streaming CODIS ±50kb regions from remote CRAM (local reference) ==="
samtools view -b -h \
  --reference "$REF_FASTA" \
  -L "$BED" \
  "https://ftp.sra.ebi.ac.uk/vol1/run/ERR324/ERR3240150/HG00145.final.cram" \
  $(awk '{printf "%s:%s-%s ", $1, $2, $3}' "$BED") \
  | pv -pterb -N "extract" \
  > illumina_slices/HG00145.unsorted.bam

echo
echo "=== [2/3] Sorting ==="
samtools sort -@ 4 -o illumina_slices/HG00145.codis.bam illumina_slices/HG00145.unsorted.bam &
SORT_PID=$!

while kill -0 "$SORT_PID" 2>/dev/null; do
  if [[ -f illumina_slices/HG00145.codis.bam ]]; then
    BYTES=$(stat -f%z illumina_slices/HG00145.codis.bam 2>/dev/null || echo 0)
    printf "\r  Sorting... output: %'d bytes" "$BYTES"
  else
    printf "\r  Sorting... (starting)"
  fi
  sleep 2
done
wait "$SORT_PID"

echo
echo "=== [3/3] Indexing ==="
samtools index illumina_slices/HG00145.codis.bam
rm illumina_slices/HG00145.unsorted.bam

echo "=== Result ==="
echo "Reads: $(samtools view -c illumina_slices/HG00145.codis.bam)"
du -h illumina_slices/HG00145.codis.bam
samtools idxstats illumina_slices/HG00145.codis.bam | awk '$3 > 0 {printf "  %-8s %6d reads\n", $1, $3}'
