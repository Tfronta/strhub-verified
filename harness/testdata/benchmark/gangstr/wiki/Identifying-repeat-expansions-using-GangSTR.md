GangSTR can be used to identify repeat expansions, either using an unbiased genome-wide scan, or targeted to known pathogenic loci. Follow these additional steps for repeat expansion detection:

* When running GangSTR, specify a repeat expansion threshold by specifying a file with thresholds to the `--str-info` option.

This is an example `--str-info` file:

| **chrom** | **pos** | **end** | **thresh** |
| ------| ------| ------| ----- |
| chr1 | 26454 | 26465 | 50 | 
| chr1 | 31556 | 31570 | 20 | 
| chr1 | 35489 | 35504 | 25 |

If working with known pathogenic loci such as Huntington's Disease, it would be appropriate to set the threshold at the known pathogenic repeat length cutoff (for example 40 for HTT).
For unbiased scan, this threshold can be set using either an arbitrary cutoff, or more ideally based on repeat lengths observed in a control population.

* Identify loci with high expansion probabilities.

GangSTR returns the FORMAT field `QEXP`, which gives the posterior probability of no expansion, a heterozygous expansion beyond the threshold, or a homozygous expansion.
You can use your favorite VCF parsing tool to filter on this field, but we recommend [filtering with dumpSTR](https://github.com/gymreklab/GangSTR/wiki/Filtering-GangSTR-output).
The example command below reports only loci with candidate heterozygous expansions:

```
dumpSTR \
  --vcf [GangSTR VCF output] \
  --max-call-DP 1000 \
  --filter-spanbound-only \
  --filter-badCI \
  --expansion-prob-het 0.8 \
  --drop-filtered  		      
```