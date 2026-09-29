# Repeat definitions

The repeat definition files are BED files containing repeat coordinates and
information about the repeat structure. The first three columns specify the
coordinates of the repeat region. The fourth column contains the following
mandatory fields:

- Repeat identifier (`ID`). The identifier must be globally unique.
- The comma-separated list of repeat motifs (`MOTIFS`) specifying all possible
  motifs that can appear in this region. In particular, each motif present in
  the `STRUC` field must also be present in this field.
- Repeat region structure (`STRUC`) field is required, although it is not
  currently used by TRGT. It is typically set to `STRUC=<TR>`. This field will
  be used in the future versions of the tool for defining population structure
  of complex repeat regions.

For example, consider this definition of tandem repeat:

```bash
chr4  3074876  3074966  ID=HTT;MOTIFS=CAG,CCG;STRUC=<TR>
```

It tells us that the repeat region has coordinates chr4:3074876-3074966.
Its identifier is `HTT`. The region is expected to be composed of tandem
repeats with motifs `CAG` and `CCG`.

Avoid redundant motif sets when defining repeats. For example, motifs `C`, `ACC`,
and `ACCAC` are redundant because the sequence `ACCACC` can be decomposed as either
`ACC⋅ACC` or as `ACCAC⋅C`. In this situation the segmentation algorithm may pick one
decomposition over another simply because of the order in which motifs are
listed. That makes results harder to compare across samples or runs. To avoid
this issue, prefer a minimal, non-overlapping motif set.
