# Validating repeat catalogs

Use `trgt validate` to validate a given TRGT repeat catalog
relative to a reference genome before running `trgt genotype`. This is
useful when you're developing your own repeat catalogs so issues
get caught early. Every locus is analyzed, confirming that the coordinates are in
bounds, and that the required annotations are present.

## Inputs requirements

- Reference genome (`--genome`): must point to the same FASTA file used during genotyping.
- Repeat catalog (`--repeats`): accepts uncompressed or BGZF-compressed BED files. Each line must follow TRGT’s four-column format:
```chrom  start  end  ID=<ID>;MOTIFS=<motif1,...>;STRUC=<structure>```

## What is validated?

Validation confirms that every contig name exists in the reference FASTA and
that the repeat interval plus any requested flanks remain within sequence
bounds. Whenever a locus fails validation, an error message is printed with
the 1-based line number. Execution continues so you get a full list of issues in
a single pass.

## Example usage

```bash
trgt validate \
  --genome references/hg38.fa \
  --repeats catalogs/hg38_tr_catalog.bed.gz
```
