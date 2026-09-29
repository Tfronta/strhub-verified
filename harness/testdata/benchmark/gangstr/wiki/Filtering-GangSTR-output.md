GangSTR VCF files can be filtered using `dumpSTR`, which is packaged as part of our [STRTools](http://github.com/gymreklab/STRTools) suite.
DumpSTR outputs an annotated VCF file with locus-level filters returned in the FILTER column and call-level filters returned in a FILTER field in the FORMAT for each sample. Filtered genotypes are set to no call.

Different filter settings are recommended for different applications.

## General filters (Level 1 filters)

The following filters are recommended in almost all applications to remove poor quality loci and unreliable calls:

Call-level filters:
* `--filter-spanbound-only`: Flags loci where only spanning and/or bounding reads were identified. If no FRR or enclosing reads are found, it is an indication that reads could not be reliably aligned in or near the repeat region.
* `--filter-badCI`: Flags loci where the maximum likelihood genotype estimates are outside of the bootstrap confidence interval. This indicates that genotype calls are unstable and likely not reliable.
* `--max-call-DP 1000`: Flags loci where an unusually large number of informative read pairs were identified. If your data is targeted and has very high coverage, you may need to adjust the threshold accordingly.
* `--min-call-DP 20`: Flags loci with less than 20 total reads used to make the call.

Locus-level filters:
* We recommend using `--filter-regions filter_files/hg19_segmentalduplications.bed.gz --filter-regions-names SEGDUP` to filter loci overlapping annotated segmental duplications in the reference genome, as mapping is unreliable.

## Stringent quality filtering for precise repeat length estimation (Level 2A filters)

For applications where precise repeat length estimation is required (e.g. genotyping the CODIS forensics STRs, Y-STR genotyping, association testing), we recommend the additional filters (beyond level 1):

* `--min-call-Q 0.9`: Flags loci where the repeat length could not be precisely estimated at repeat unit resolution.
* `--min-call-DP 50`: Flags loci without a sufficient number of read pairs to accurately estimate repeat length.

If a large cohort is available, we additionally recommend the locus level filters:
* `-min-locus-hwep 0.01`: Flags loci with genotype frequencies unexpected based on Hardy Weinberg Equilibrium.

## Identifying candidate repeat expansions (Level 2B filters)

For identifying candidate repeat expansions, we recommend the additional filters (beyond level 1):

* `--expansion-prob-het 0.8`: Keeps loci with a posterior probability of a heterozygous expansion beyond a specified threshold greater than 80%. Apply this for autosomal dominant disorders.
* `--expansion-prob-hom 0.8`: Keeps loci with a posterior probability of a homozygous expansion beyond a specified threshold greater than 80%. Apply this for autosomal recessive disorders.
* `--min-call-DP 50`: Flags loci without a sufficient number of read pairs to accurately estimate expansion probability.

See [Identifying repeat expansions](https://github.com/gymreklab/GangSTR/wiki/Identifying-repeat-expansions-using-GangSTR) for more info.