Note: this software is still in development, with features still being added and deprecated. Please feel free to report any bugs.

# STRetch

STRetch is a method to detect pathogenic STR expansions from next-gen sequencing data. STRetch uses short read sequencing to detect expansions at all known STR loci and estimate their approximate size. The method adds STR decoy sequences to the reference genome to identify reads originating from a large STR expansion. These reads are then mapped back to the genome using read pair information, and the source locus is assessed for an expansion using a statistical test based on coverage of the STR chromosome. 

STRetch requires paired end reads to work. It is primarily intended for use on
whole genome sequencing data, but can also be run on exome or other targeted
sequencing data, although size estimates should be interpreted with caution.