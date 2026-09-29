## Final results

**sample.STRs.tsv** contains STRetch results for all STR loci with any assigned reads in that sample (not all results are significant). If there are no reads assigned to a locus, that locus will not be reported.

**STRs.tsv** contains all STRetch results for all STR loci all samples in that batch with any assigned reads in any sample. If reads are only assigned for a given locus in in one sample, the other samples with show 0 reads.

Both files have the same columns, with one line per locus per sample.

**Columns:**  
chrom  
start  
end  
sample  
repeatunit  
reflen - number of repeat units in the reference   
locuscoverage - number of STR reads assigned to that locus  
outlier - z score testing for outliers  
p_adj - adjusted p value, is this locus significantly expanded relative to other samples? (p values have already been adjusted for multiple testing using the Benjamini-Hochberg method)  
bpInsertion - estimated size of allele in bp inserted relative to the reference  
repeatUnits - estimated total size of allele in repeat units

The STR allele size estimates are only based on the reads in that sample, not the control information. The control is only used to calculate the outlier z scores and corresponding p values, asking the question: is the allele in this sample significantly longer than other samples? If you run a single sample, you simply get no values for the outlier z scores and p values.

## Intermediate files

### sample.STR_counts

Number of reads mapping to each STR decoy chromosome. All STR decoy chromosomes are listed.

**Columns:**  
Chromosome  
Start of chromosome (i.e. always 0)  
End of chromosome (i.e. length of the chromosome -1)  
Number of reads mapping to that chromosome  

### sample.locus_counts

Counts the number of reads than are assigned to each STR locus. The file consists of only those loci for which there are any assigned reads. Each line is an STR as defined in the reference annotation, along with the count of reads for that locus.

**Columns:**  
Chromosome  
Start  
End  
repeat unit  
Number of repeat units in the reference genome  
Number of reads assigned to the locus  

### sample.median_cov

Estimated median coverage over the whole genome, or specified target region for that sample.