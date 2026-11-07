"""The Content gate without being told where the columns are.

Only shape is judged: records exist, genotypes were called, the loci the run
was given came back. Nothing here asks whether a genotype is right.
"""
import gzip
import pathlib

import check_content
import content_auto as ca

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "datasets" / "illumina-bam-hg38" / "regions"

VCF_HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tNA12878\n"


def _hipstr_like(regions, called=True):
    """HipSTR writes the region name in ID; POS is the tract start."""
    rows = []
    for chrom, start, end, name in regions:
        gt = "0|1:20" if called else ".:0"
        rows.append(f"{chrom}\t{start}\t{name}\tACGTACGTACGT\tACGTACGT\t.\t.\tSTART={start};END={end}\tGT:DP\t{gt}")
    return VCF_HEADER + "\n".join(rows) + "\n"


def _gangstr_like(regions):
    """GangSTR writes '.' in ID; POS is the tract start, sometimes a base or two off."""
    rows = []
    for i, (chrom, start, end, name) in enumerate(regions):
        rows.append(f"{chrom}\t{start + (i % 3)}\t.\tACGTACGT\tACGT\t.\t.\tEND={end}\tGT:DP:Q\t0/1:33:0.9")
    return VCF_HEADER + "\n".join(rows) + "\n"


PANEL = ROOT / "datasets" / "illumina-bam-hg38" / "loci.bed"


def test_reads_regions_from_every_library_layout():
    # TRGT's layout names the locus inside its fourth column (ID=TH01;MOTIFS=...);
    # a TRGT run on the HiFi slice once reported its loci by that whole string.
    for fmt in ("hipstr", "strsearch", "bed4", "trgt"):
        regs = ca.read_regions(LIB / f"{fmt}.bed")
        assert len(regs) == 24, fmt
        assert {r[3] for r in regs} >= {"TH01", "TPOX", "vWA", "FGA"}, fmt
    # GangSTR's layout carries no names: they come from the panel, by overlap.
    regs = ca.read_regions(LIB / "gangstr.bed")
    assert all(r[3].startswith("chr") for r in regs)
    named = ca.name_regions(regs, PANEL)
    assert {r[3] for r in named} >= {"TH01", "TPOX", "vWA", "FGA"}


def test_hipstr_style_vcf_is_recognised_by_id(tmp_path):
    regions = ca.read_regions(LIB / "hipstr.bed")
    p = tmp_path / "calls.vcf.gz"
    with gzip.open(p, "wt") as fh:
        fh.write(_hipstr_like(regions))
    st = ca.analyze_vcf(p, regions)
    assert st["rows"] == 24 and st["called_genotypes"] == 24
    assert st["regions_hit"] == 24 and "TH01" in st["str_loci"]
    assert st["total_reads"] == 24 * 20
    assert st["depth_source"] == "FORMAT/DP"
    assert all(ca.judge(st, "vcf", 24).values())


def test_gangstr_style_vcf_is_recognised_by_position(tmp_path):
    regions = ca.name_regions(ca.read_regions(LIB / "gangstr.bed"), PANEL)
    p = tmp_path / "out.vcf"
    p.write_text(_gangstr_like(regions))
    st = ca.analyze_vcf(p, regions)
    assert st["regions_hit"] == 24 and st["distinct_str_loci"] == 24
    assert all(ca.judge(st, "vcf", 24).values())


def test_uncalled_genotypes_do_not_pass(tmp_path):
    regions = ca.read_regions(LIB / "hipstr.bed")
    p = tmp_path / "calls.vcf"
    p.write_text(_hipstr_like(regions, called=False))
    checks = ca.judge(ca.analyze_vcf(p, regions), "vcf", 24)
    assert checks["records_present"] and not checks["genotypes_called"]


def test_too_few_of_the_given_loci_do_not_pass(tmp_path):
    regions = ca.read_regions(LIB / "hipstr.bed")
    p = tmp_path / "calls.vcf"
    p.write_text(_hipstr_like(regions[:2]))
    checks = ca.judge(ca.analyze_vcf(p, regions), "vcf", 24)
    assert not checks["given_loci_recognised"]


def test_table_finds_the_locus_sequence_and_count_columns(tmp_path):
    p = tmp_path / "allsequences.txt"
    rows = ["Locus\tLength\tSequence\tFwd\tRev"]
    for locus, n in (("TH01:9", 120), ("TPOX:8", 98), ("vWA:17", 77), ("CSF1PO:12", 60), ("D5S818:11", 55)):
        rows.append(f"{locus}\t{n}\tAATGAATGAATGAATG\t{n}\t{n - 3}")
    p.write_text("\n".join(rows) + "\n")
    st = ca.analyze_table(p, "tsv")
    assert st["locus_column"] == 0 and st["dna_columns"] == [2]
    assert set(st["count_columns"]) >= {3, 4}
    assert st["header_row_dropped"] and st["distinct_str_loci"] == 5
    assert all(ca.judge(st, "tsv", 0).values())


def test_table_with_alleles_only_still_counts(tmp_path):
    p = tmp_path / "profile.csv"
    p.write_text("Marker,Allele1,Allele2\nTH01,6,9.3\nTPOX,8,11\nvWA,16,17\nFGA,21,24\n")
    st = ca.analyze_table(p, "csv")
    assert st["locus_column"] == 0 and st["allele_columns"] == [1, 2] and st["distinct_str_loci"] == 4
    assert all(ca.judge(st, "csv", 0).values())


def test_a_log_file_is_not_genotype_data(tmp_path):
    p = tmp_path / "run.txt"
    p.write_text("Processing chr1\nDone in 3 s\nWrote output\n")
    st = ca.analyze_table(p, "text")
    assert not st.get("locus_column_found")
    assert not ca.judge(st, "text", 0)["locus_column_found"]


def test_gate_runs_auto_when_the_manifest_declares_no_columns(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    regions = ca.name_regions(ca.read_regions(LIB / "gangstr.bed"), PANEL)
    (out / "output.vcf").write_text(_gangstr_like(regions))
    mf = tmp_path / "m.yml"
    mf.write_text(
        "tool: {name: x, version: '1'}\nsource: {repo: 'https://github.com/a/b', ref: abc}\n"
        "environment: {dockerfile: Dockerfile}\nrun: {cmd: x}\n"
        "outputs:\n  - {path: '*.vcf', format: vcf, min_records: 1}\n"
    )
    r = check_content.check(str(mf), str(out), regions_path=str(LIB / "gangstr.bed"), panel_path=str(PANEL))
    assert r["applicable"] and r["passed"]
    assert r["outputs"][0]["mode"] == "auto" and r["outputs"][0]["stats"]["distinct_str_loci"] == 24


def test_declared_table_columns_keep_the_declared_analysis(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.tsv").write_text("TH01:9\t12\tAATG\t5\t5\n")
    mf = tmp_path / "m.yml"
    mf.write_text(
        "tool: {name: x, version: '1'}\nsource: {repo: 'https://github.com/a/b', ref: abc}\n"
        "environment: {dockerfile: Dockerfile}\nrun: {cmd: x}\n"
        "outputs:\n  - path: '*.tsv'\n    format: tsv\n    content: {columns: 5, locus_column: 0, min_distinct_loci: 1}\n"
    )
    r = check_content.check(str(mf), str(out))
    assert "mode" not in r["outputs"][0] and r["passed"]


REAL = pathlib.Path(__file__).resolve().parent.parent / "testdata" / "outputs"


def test_real_hipstr_and_gangstr_vcfs_reach_content():
    """Excerpts of what HipSTR and GangSTR actually wrote for NA12878 with the
    library regions (generated locally; see testdata/outputs/README.md)."""
    if not (REAL / "hipstr.str_calls.vcf").exists():
        return
    hip = ca.analyze_vcf(REAL / "hipstr.str_calls.vcf", ca.read_regions(LIB / "hipstr.bed"))
    assert hip["distinct_str_loci"] >= 20 and hip["called_genotypes"] >= 20
    assert all(ca.judge(hip, "vcf", 24).values())
    gan = ca.analyze_vcf(REAL / "gangstr.output.vcf", ca.name_regions(ca.read_regions(LIB / "gangstr.bed"), PANEL))
    assert gan["regions_hit"] >= 20 and "TH01" in gan["str_loci"]
    assert all(ca.judge(gan, "vcf", 24).values())


def test_a_json_catalog_names_the_loci_like_a_regions_bed(tmp_path):
    """ExpansionHunter is given the panel as a JSON catalog; the content check
    must recognise the same loci in its VCF as it would from a BED."""
    import json
    import content_auto as ca
    cat = tmp_path / "regions.json"
    cat.write_text(json.dumps([{"LocusId": "TH01", "LocusStructure": "(AATG)*",
                                "ReferenceRegion": "chr11:2171087-2171115", "VariantType": "Repeat"}]))
    assert ca.read_regions(cat) == [("chr11", 2171088, 2171115, "TH01")]


def test_expansionhunter_and_trgt_vcf_depths_are_extracted(tmp_path):
    """ExpansionHunter reports ADSP:ADFL:ADIR:LC instead of DP, and TRGT reports SD.
    Both must produce real non-zero read depths per locus."""
    regions = [
        ("chr1", 57367044, 57367119, "DAB1"),
        ("chr9", 69037287, 69037304, "FXN"),
        ("chr4", 3074877, 3074933, "HTT"),
    ]
    vcf = tmp_path / "eh_trgt.vcf"
    vcf.write_text(
        VCF_HEADER
        + "chr1\t57367044\t.\tG\t<STR15>,<STR18>\t.\tPASS\tVARID=DAB1;REPID=DAB1\t"
          "GT:SO:REPCN:REPCI:ADSP:ADFL:ADIR:LC\t1/2:SPANNING/SPANNING:15/18:15-15/18-18:19/15:3/6:0/0:41.2\n"
        + "chr9\t69037287\t.\tG\t<STR9>\t.\tPASS\tTRID=FXN\t"
          "GT:AL:ALLR:SD:MC\t0/1:27,30:27-27,30-30:14,16:9,10\n"
        + "chr4\t3074877\t.\tC\t<STR17>\t.\tPASS\tVARID=HTT;REPID=HTT\t"
          "GT:SO:REPCN:REPCI:ADSP:ADFL:ADIR:LC\t1/1:SPANNING/SPANNING:17/17:17-17/17-17:0/0:0/0:0/0:38.6\n"
    )
    st = ca.analyze_vcf(vcf, regions)
    assert st["called_genotypes"] == 3
    assert st["regions_hit"] == 3
    depth_by_locus = dict(st["top_loci_by_depth"])
    # DAB1: ADSP (19+15) + ADFL (3+6) + ADIR (0+0) = 43
    assert depth_by_locus["DAB1"] == 43
    # FXN: TRGT SD (14+16) = 30
    assert depth_by_locus["FXN"] == 30
    # HTT: ADSP/ADFL/ADIR all 0 -> falls back to round(LC=38.6) = 39
    assert depth_by_locus["HTT"] == 39
    assert st["total_reads"] == 43 + 30 + 39
    assert st["max_sequence_depth"] == 43
    assert st["depth_source"] == "FORMAT/ADSP+ADFL+ADIR, FORMAT/SD, FORMAT/LC"


