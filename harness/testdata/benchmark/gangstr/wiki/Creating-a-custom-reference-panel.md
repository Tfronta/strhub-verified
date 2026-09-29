This page explains the steps required for creating a custom reference panel for any reference genome. These steps can be modified and run from `scripts/create_ref_panel`. 


# 1 Creating raw reference panel with [Tandem Repeats Finder (TRF)](https://tandem.bu.edu/trf/trf.html)
The first step is to use [TRF](https://tandem.bu.edu/trf/trf.html) to create a raw reference. After installing TRF on your system, use `1_run_TRF.sh` script to create raw reference panel. You can set the following arguments by editing this script:

* `REF_SEP=PATH/TO/CHROM/SEPARATED/REF/`: Directory containing chromosome-separated reference genome. (`chr1.fa chr2.fa chr3.fa etc.`)
* `OUT=PATH/TO/OUT.bed`: Output raw reference panel `bed` file
* `TRF=trf`: Path to TRF executable (if trf is not added to path)
* `THREADS=4`: Number of threads
* `MAX_CHR_NUM=22`: Maximum numbered chromosome (human:22, mouse:19)
* `NON_NUM_CHRS="X,Y"`: Non-numbered chromosomes (chromosomes)
* `TMP=PATH/TO/TMP/`: Path to folder to store temp files

# 2 Trimming reference panel
In this step we trim the reference panel to remove partial motifs at the end of repeat regions, discard regions that are two close to each other, and remove regions that have imperfect repeats. Use `2_trim.sh` script to trim the raw TRF output and create a GangSTR-ready reference panel. You can edit the threshold for discarding close regions by editing this script. Usage:
```
./2_trim.sh {TRF_IN} {OUT_PATH}
    {TRF_IN} path to results from TRF
    {OUT_PATH} path to output file.
```

# 3 Supplementing reference panel (optional)
You can use `3_supplement_bed.sh` to supplement the reference panel bed file with additional loci (disease loci that may have been discarded, codis markers, etc.). You can set the following arguments by editing this script:

* `IN_BED=/PATH/TO/TRIMMED.bed`: Trimmed reference from previous step.
* `OUT_BED=/PATH/TO/TRIMMED_supp.bed`: Output supplemented bed file
* `SUPP_BED1=/PATH/TO/DISEASE.bed`: Path to bed file containing additional loci 1
* `SUPP_BED2=/PATH/TO/DISEASE.bed`: Path to bed file containing additional loci 2
* `SUPP_BED3=/PATH/TO/DISEASE.bed`: Path to bed file containing additional loci 3

More supplement bed files can be added at the end of the following line of the script, separated by comma:
`python scripts/supplement_ref.py $IN_BED $OUT_BED $SUPP_BED1,$SUPP_BED2,$SUPP_BED3`