"""The pre-flight rule: a BED is rejected for reaching too few panel loci, never
for listing loci beyond the slice (a shipped catalog may list dozens)."""
import validate_bed as vb

PANEL = [
    {"chrom": "chr4", "start": 3073876, "end": 3075933, "name": "HTT"},
    {"chrom": "chrX", "start": 147911049, "end": 147913111, "name": "FMR1"},
    {"chrom": "chr9", "start": 27572484, "end": 27574546, "name": "C9orf72"},
]


def row(chrom, start, end):
    return {"chrom": chrom, "start": start, "end": end, "name": f"{chrom}:{start}-{end}"}


def test_intervals_outside_the_panel_do_not_reject():
    bed = [row("chr4", 3074876, 3074933), row("chrX", 147912049, 147912111),
           row("chr1", 100, 200), row("chr2", 300, 400)]
    r = vb.validate(bed, PANEL, min_loci=2)
    assert r["pass"]
    assert r["covered_loci"] == ["FMR1", "HTT"]
    assert r["out_of_panel"] == ["chr1:100-200", "chr2:300-400"]
    assert r["reason"] == ""


def test_too_few_loci_rejects_and_names_the_outside_intervals():
    bed = [row("chr4", 3074876, 3074933), row("chr1", 100, 200)]
    r = vb.validate(bed, PANEL, min_loci=2)
    assert not r["pass"]
    assert "covers 1 supported loci, need at least 2" in r["reason"]
    assert "chr1:100-200" in r["reason"]


def test_too_few_loci_without_outside_intervals_says_only_that():
    r = vb.validate([row("chr4", 3074876, 3074933)], PANEL, min_loci=2)
    assert not r["pass"]
    assert "outside" not in r["reason"]
