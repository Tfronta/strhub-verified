# illumina-bam-hg38-y — HG002 Y-STR dataset

GIAB **HG002** (NA24385, son) 300x Illumina WGS, GRCh38, sliced around 15 forensic
Y-STR loci (±1000bp flanking). Male sample. Use this dataset to validate
Y-chromosome STR tools.

- BAM: `illumina_slices/HG002.ystr.bam` (~3 MB)
- Coverage: ~96–390x per locus
- Reference: UCSC `hg38.fa` (primary chromosomes identical to the GIAB analysis
  set the BAM was aligned to; all loci on chrY)

## Status — declared, Y leg not yet active

The form lists this dataset (via `datasets/index.json`), but the external Y
verification leg is **not wired**. Today HipSTR's regions come from the per-tool
asset `tools/hipstr-v0-7/assets/regions.bed` (autosomal). To run a real Y leg the
harness must mount **dataset-level** regions (`regions.bed` in this dir). That
change is the "modify harness for 2 samples" task.

## Completing regions.bed

`regions.bed` here currently holds 10 of 18 rows (the ones recoverable from the
HipSTR reference under non-obvious names). Regenerate the complete file from the
source HipSTR reference BED in one shot:

```bash
SRC="/Users/tfronta/Downloads/hg38.hipstr_reference.bed"
Y_NAMES="DYS19/DYS394 DYS389I DYS389II.1 DYS389II.2 DYS390 DYS391 DYS392 DYS393 DYS385_1 DYS385_2 DYS438 DYS448.1 DYS448.2 DYS456 DYS458 DYS635 Y-GATA-A10 Y-GATA-H4"

awk -v names="$Y_NAMES" '
  BEGIN{ n=split(names,a," "); for(i=1;i<=n;i++) set[a[i]]=1 }
  ($6 in set){ print $1"\t"$2"\t"$3"\t"$4"\t"$5"\t"$6"\t"$7 }
' "$SRC" | sort -k1,1 -k2,2n > regions.bed

wc -l regions.bed   # expect 18
```

## HipSTR naming notes

The source BED uses non-forensic names for several loci:
`DYS19/DYS394`, `DYS389II.1`/`DYS389II.2` (split), `DYS385_1`/`DYS385_2` (= a/b),
`DYS448.1`/`DYS448.2` (split), `Y-GATA-H4` (= YGATAH4), `Y-GATA-A10`.
`DYS437` and `DYS439` are absent from the HipSTR reference panel.
