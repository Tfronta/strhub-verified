## Quick Start Installation

This is an example of installing STRetch using the install script. 
It assumes **Git** and **Java** are already installed.

The install script also downloads the hg19 genome and annotation files ~8 GB.
It takes approximately 20 minutes (depending on your download speed).

Download STRetch and run the install script:
```
git clone git@github.com:Oshlack/STRetch.git STRetch
cd STRetch
./install.sh
```

Download the test data
```
mkdir test
cd test/
wget -O testdata.zip https://ndownloader.figshare.com/articles/4762489?private_link=cc7347f4637d9a7fe22d
unzip testdata.zip 
rm testdata.zip
```

Run the test data
```
../tools/bin/bpipe run -p EXOME_TARGET="SCA8_region.bed" ../pipelines/STRetch_exome_pipeline.groovy *.fastq.gz
```
(The test data only includes reads from one locus, so runs very quickly, but may produce warning messages about there being no data from many chromosomes - this is fine)

Notes: 
- If you would like to use the included PCR WGS reference set as controls, you will need to edit the "CONTROL" line in `pipeline_config.groovy`.
- To use system versions of any software, simply edit `pipeline_config.groovy` to point to the location of the executables. 
Be aware that using different versions of the tools can results in errors.
- If using STRetch on a cluster, you can use bpipe to send jobs to the queue. You will need to create `STRetch/pipelines/bpipe.config`. See http://docs.bpipe.org/Guides/ResourceManagers/ for instructions, as they will likely differ by cluster.

## Requirements

Operating system: Linux

The installation script requires the following to run (most of of these will already be installed on many systems). The remaining dependancies can be installed automatically.
- Git
- Java (tested on version 1.8)
- bzip2
- unzip

[Bpipe](http://docs.bpipe.org/) - this pipeline software runs the STRetch pipelines

Python 3
- See `environment.yml` for specific packages
- Easiest to install using [Conda](http://conda.pydata.org/docs/using/envs.html):
`conda env create -f environment.yml`
- Then activate the environment with `source activate STR`.
- For some cluster environments you may need to point the pipeline to the
specific version of Python, which would look something like this
`[where you installed conda]/miniconda3/envs/STR/bin/python`

These commandline tools are required, but will already be installed by
environment.yml as part of the python dependencies
- BedTools
- goleft
- mosdepth

Other command line tools
- BWA (requires mem algorithm - tested on version 0.7.12)
- Samtools
- Picard
- [Bazam](https://github.com/ssadedin/bazam) - for extracting reads if starting from bam/cram files

## Reference data

**Quick start for human data:**
You can download a bundle of the pre-indexed hg19 genome with STR decoys and
corresponding bed files [here](https://figshare.com/s/1a39be9282c90c4860cd).

Required reference files:
- Reference genome with STR decoy chromosomes (fasta)
- BWA indices of reference
- .genome file of reference
- STR decoy bed file
- STR positions in genome annotated bed file

All chromosomes names in these files must be in the same sort order.

STRetch requires a reference genome that includes STR decoy chromosomes.
You can generate this by adding concatenating STRdecoys.fasta to the end of
any reference genome in fasta format, and then indexing the result.
For example:
```
$ cat ucsc.hg19.fasta STRdecoys.fasta > ucsc.hg19.STRdecoys.fasta
$ bwa index ucsc.hg19.STRdecoys.fasta
```

STRetch also requires a bed file specifying the position of all STRs in the
reference genome, with two additional columns containing the repeat unit/motif
and the number of repeat units in the reference.

For example:

```chr1	10000	10468	TAACCC	77.2```

This file is produced by extracting the appropriate columns from Tandem Repeats
Finder output.

## Configuring STRetch

`install.sh` will create a text file `STRetch/pipelines/pipeline_config.groovy` (note this file
must be in the same directory as the pipelines).
This will contain system-specific settings, especially paths to the locations
of software and reference files.
There is a template, and several examples provided:
`pipelines/config-examples/pipeline_config_[cluster-name].groovy`.

## Troubleshooting ?

See the [Troubleshooting](Troubleshooting.md) wiki page.

## old STRetch version 0.1.0 - R requirements

R 3 (tested on R version 3.3.1)
- install.packages(c('optparse','plyr','dplyr','tidyr','reshape2'))

Install R packages:
```
R
> install.packages(c('optparse','plyr','dplyr','tidyr','reshape2'))
> q()
```