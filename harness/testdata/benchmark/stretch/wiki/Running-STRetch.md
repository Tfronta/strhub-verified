## Quick start

Run the WGS pipeline:

```STRetch/tools/bin/bpipe run STRetch/pipelines/STRetch_wgs_pipeline.groovy sample1_L001_R1.fastq.gz sample1_L001_R2.fastq.gz sample2_L001_R1.fastq.gz sample2_L001_R2.fastq.gz …```

All reads are assumed to be paired end with filenames ending in
`_R1.fastq.gz` and `_R2.fastq.gz`.
Multiple samples can be run in the same command and will be processed in
parallel and their STR variation compared to find outliers. 

If you would like to use the included PCR WGS reference set as controls, you will need to edit the "CONTROL" line in `pipeline_config.groovy`. Otherwise by default STRetch will use all the other samples in your set as controls.

## STRetch pipelines

STRetch provides three pipelines, depending on what type of sequencing you are doing and what format your data is in.

For all pipelines, if you analyse multiple samples together you can look for outliers in your set of samples.

### Whole genome sequencing starting from fastq files: _STRetch_wgs_pipeline.groovy_

This pipeline maps all paired-end reads against a reference genome containing STR-decoy chromosomes. It then uses reads mapping to the STR-decoy chromosomes to detect large STR expansions.

On a single sample:

`STRetch/tools/bin/bpipe run STRetch/pipelines/STRetch_wgs_pipeline.groovy sample_L001_R1.fastq.gz sample_L001_R2.fastq.gz`

On multiple samples:

`STRetch/tools/bin/bpipe run STRetch/pipelines/STRetch_wgs_pipeline.groovy sample1_L001_R1.fastq.gz sample1_L001_R2.fastq.gz sample2_L001_R1.fastq.gz sample2_L001_R2.fastq.gz …`

### Whole genome sequencing starting from mapped bam/cram files: _STRetch_wgs_bam_pipeline.groovy_

This pipeline takes a position sorted mapped bam file and extracts reads from it likely to contain STR sequence. Specifically, all reads mapping to any STRs, flanking sequence, and unmapped reads. These reads are then mapped against a new reference genome containing STR-decoy chromosomes and the pipeline continues much as the standard STRetch WGS pipeline.

`STRetch/tools/bin/bpipe run -p input_regions=all_STRs_in_genome.bed STRetch/pipelines/STRetch_wgs_bam_pipeline.groovy sample1.bam sample2.bam`

<!--
or 

`STRetch/tools/bin/bpipe run -p input_regions=all_STRs_in_genome.bed -p CRAM_REF=reference_genome.fasta STRetch/pipelines/STRetch_wgs_bam_pipeline.groovy sample1.cram sample2.cram`

If using cram input files, make sure to set `CRAM_REF=reference_genome.fasta` in `pipeline_config.groovy` to the reference genome used to create the cram files.
-->

`all_STRs_in_genome.bed` is a bed file defining the positions of *all STRs* in the genome, for example `hg19.simpleRepeat_period1-6.dedup.sorted.bed`. **WARNING:** using a bed file that only specifies some STRs may cause STRetch to miss expansions, this file must include all STRs in the genome. It must match the reference genome used to produce the bam file, but doesn’t have to match the reference genome used for the rest of the pipeline. This be file must not contain two STRs at the same position (this does occur in some genome annotations, see [Reference data](Reference-data) for more details)

You can additionally run multiple instances of BWA in parallel to speed up the read extraction and mapping time. To do this, set the `bwa_parallelism` parameter. For example `-p bwa_parallelism=12` would run BWA 12 times in parallel for each sample.

### Exome or other targeted sequencing, starting from fastq files: _STRetch_exome_pipeline.groovy_

Note that because STRetch assumes uniform coverage when estimate STR allele sizes, the exome pipeline will likely not produce accurate size estimate. It can be used to find check if samples are outliers at a given STR locus. This pipeline requires that all samples run together should have been sequenced using the same technology, for example the same exome kit. 

Note: for exome samples, the exome target region must be set in the
`pipeline_config.groovy` and is assumed to be the same for all samples.

`EXOME_TARGET="target_region.bed"`

`STRetch/tools/bin/bpipe run STRetch/pipelines/STRetch_exome_pipeline.groovy sample1_L001_R1.fastq.gz sample1_L001_R2.fastq.gz sample2_L001_R1.fastq.gz sample2_L001_R2.fastq.gz …`

### Exome or other targeted sequencing, starting from BAM/CRAM files: _STRetch_exome_bam_pipeline.groovy_

Please see notes above about running STRetch on exome data from BAM/CRAM files. In particular, it's important to set `EXOME_TARGET` and `input_regions` correctly.

`STRetch/tools/bin/bpipe run STRetch/pipelines/STRetch_exome_bam_pipeline.groovy sample1.bam sample2.bam …`

## Running STRetch in a cluster environment and more advanced bpipe options

You can also use the bpipe `-n` parameter to limit concurrency. Please see the [Bpipe documentation](http://docs.bpipe.org/Commands/run/). `-n` is the number of threads, and STRetch is set to use 8 threads per sample for alignment by default, so if you set `-n` to less than 8 it will simply sit there and not run.
In general, it's not necessary to set `-n`. Bpipe will not try to use more resources than are available. The exception to that is when you want to submit a large number of jobs to a cluster, in which case setting '-n' to a large number is generally the best strategy. For more information on using Bpipe to submit STRetch jobs directly to your cluster, please see the [Bpipe resource manager documentation](http://docs.bpipe.org/Guides/ResourceManagers/).

Any setting in `pipeline_config.groovy` can also be set at the command line using the `-p VARIABLE="content"` structure. For example:
`bpipe run -p EXOME_TARGET="SCA8_region.bed" -p input_regions="STR_regions.bed" pipeline.groovy inputdata`

## Making your own custom control data

If you have a set of samples you would like to use as controls for future samples, simply run all samples using the STRetch pipeline, then re-run the `estimateSTR.py` script in the same working directory with the `--emit` option, like so:

`STRetch/tools/bin/python STRetch/scripts/estimateSTR.py --model STRetch/scripts/STRcov.model.csv --locus_counts *.locus_counts --STR_counts *.STR_counts --median_cov *.median_cov --emit my_controls.tsv`

When running STRetch with your new samples, edit the file `STRetch/pipelines/pipeline_config.groovy`:

`CONTROL="my_controls.tsv"`
