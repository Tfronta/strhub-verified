# VCF structural validation

IO now validates VCF text with the versioned profile
`strhub-vcf-structure/1`. Counting non-comment lines is not parsing VCF.
No tool is executed, no file is rewritten, and no tool-specific exception is
used to make an output pass.

The companion web view lists every inspected VCF, its structural status and
separate row/call counts. It does not turn an unvalidated file's placeholder
zero into an observed count, and does not reinterpret legacy `records` values.
VCF evidence remains visible when plausibility statistics are unavailable.

The profile is based on the [VCF specifications](https://samtools.github.io/hts-specs/),
read at [hts-specs commit 510c107ba89aa13113818c9e4fa3071283cb7f7b](https://github.com/samtools/hts-specs/tree/510c107ba89aa13113818c9e4fa3071283cb7f7b).
The VCF 4.1 text was also checked when reviewing the historical output fixtures.

## Checks and limits

- The first line must declare a supported VCF 4.0-4.5 version; metadata precedes
  one mandatory, tab-delimited header with the eight fixed column names.
- FORMAT requires sample columns. Sample names and FORMAT keys cannot be
  duplicated. Every data record must have exactly the header's column count,
  with nonempty cells and LF or CRLF line endings.
- Fixed fields validate chromosome presence, integer position (including
  telomeric position 0), REF bases, ALT syntax, Float QUAL, FILTER lists and
  INFO key/value syntax. Symbolic alleles, paired/single breakends, sites-only
  records, missing values and lowercase bases are supported.
- Structured metadata is checked for balanced quoting/lists, required field
  attributes and duplicate IDs. Declared INFO/FORMAT types and cardinalities
  are checked for fixed Number, A and R; Number=G is checked when sample ploidy
  can be obtained from GT. Floats support the specified infinity/NaN literals.
- GT syntax, ordering within FORMAT and allele indexes are checked, including
  haploid, polyploid, phased and partially missing calls. Leading phasing
  indicators require VCF 4.4 or later. Missing trailing sample fields are allowed.
- Files are read in strict UTF-8, preserving line endings. Plain VCF and gzip
  streams (including concatenated members as used by BGZF) are decoded in full.
  Corrupt/truncated gzip, invalid encoding or malformed data suffixes fail.

This is a **structural profile, not full VCF conformance certification**. It does
not check coordinate ordering/contiguity, identifier uniqueness across records,
the reference assembly, biological truth, mate relationships, all reserved-tag
semantics or every version-specific semantic rule. Undeclared tag values have
no inferred type; only their syntax is checked. Number=G cardinality without
known ploidy is not established. It does not certify BGZF indexes or require
a tabix index to read a gzip stream. It uses the Python standard library and
adds no installation dependency to the evaluator or tools.

Declared versions beyond the supported range and local-allele/ploidy Number
declarations P/LA/LR/LG are reported as `validation_status: unsupported`.
They cannot pass IO, and the report attributes the inability to determine
validity to the evaluator. Invalid syntax is reported as `invalid`, with a
file/line/field diagnostic when available. No repair or retry is attempted.

## Records and calls

For VCF outputs, `records` is the total number of structurally valid data rows.
`called_records` counts rows with GT and at least one non-missing allele,
`uncalled_rows` counts rows whose GT values are all missing, and
`records_without_gt` counts rows with no GT field. These categories are separate
from `parses_as_vcf`.

`min_records` applies to data rows. The existing policy of refusing an all-missing
GT output remains, now as the separate `has_called_genotypes` check. A sites-only
VCF does not invent genotype calls. A header-only VCF is structurally valid but
has zero records. A failure due only to uncalled GT output is not presented as
proof that the reference slice lacked reads; the report states that the cause
was not established.

Every file matched by the declared VCF glob is checked independently. All must
pass their checks; `files` carries individual results and top-level counts sum
the successfully validated files. `resolved` retains the first path for older
readers. A valid first file cannot hide a second malformed file. Broad patterns
that also match index files are not silently narrowed; the contract will expose
those mismatches instead of rewriting a recipe to obtain a success.

## Evidence and regression tests

The audit's arbitrary-text example now fails `parses_as_vcf`. Tests also cover
malformed headers/columns/types, declared cardinalities, GT bounds, unsupported
features, gzip/encoding errors, late error text, multiple matched files and
end-to-end report decisions. A passing plausibility check cannot override a
failed IO format check.

Historical fixtures are read byte-for-byte and remain unchanged. HipSTR's
stored excerpt passes this profile (23 records, 22 with calls). GangSTR's stored
excerpt is rejected at FORMAT/REPCI: its Number=1 String declaration differs
from the comma-separated value count. RC and ENCLREADS show the same kind of
discrepancy. This is a result of this profile, not a new execution or a claim
that GangSTR cannot run. The fixture, tool and recipe are not patched.

Run the repository checks:

For this change, 454 engine tests, 626 web tests, TypeScript, 15 shared BED
cases and the picker self-test passed. All tests read outputs or use synthetic
files; they do not launch STR tools or repair their procedures.

```bash
python3 -m pytest harness/tests -q
python3 harness/test_validate_bed.py
python3 harness/pick_tools.py --selftest
```
