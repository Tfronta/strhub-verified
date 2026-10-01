"""The regions library: a ready-made file per tool format, recognised both ways."""
import pathlib

import regions_library as rl
import propose_manifest as pm
import detect_recipe as dr

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOS = ROOT / "harness" / "testdata" / "repos"


BAM_TYPES = ("illumina-bam-hg38", "illumina-bam-hg38-y", "ont-bam-hg38", "pacbio-hifi-bam-hg38",
             # Not a BAM, but read by tools that align it to hg38 and take the same regions.
             "ont-fastq")


def test_every_bam_dataset_has_every_format():
    for t in BAM_TYPES:
        assert rl.available(t) == ["bed4", "eh_catalog", "gangstr", "hipstr", "motif", "strsearch", "trgt"], t
        for fmt in rl.available(t):
            assert rl.library_path(t, fmt) is not None


def test_library_files_are_their_own_format():
    for t in BAM_TYPES:
        for fmt in rl.available(t):
            assert rl.detect_format(rl.library_path(t, fmt).read_text()) == fmt, (t, fmt)


def test_library_files_cover_the_panel():
    for t in BAM_TYPES:
        panel = {ln.split("\t")[3] for ln in (ROOT / "datasets" / t / "loci.bed").read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")}
        names = {ln.split("\t")[3] for ln in rl.library_path(t, "bed4").read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")}
        bases = names | {n.split(".")[0] for n in names}
        for p in panel:
            assert p in bases or any(part in bases for part in p.split("/")), (t, p)


def test_a_big_hipstr_reference_is_still_hipstr_format():
    big = "\n".join(f"chr1\t{i * 1000}\t{i * 1000 + 40}\t4\t10.0\tLOCUS{i}\tACGT" for i in range(600))
    assert rl.detect_format(big) == "hipstr"


def test_format_is_read_off_the_program_name():
    assert rl.format_for_tool("GangSTR", "GangSTR --bam x") == ("gangstr", "tool")
    assert rl.format_for_tool("x", "./HipSTR --bams a --regions r") == ("hipstr", "tool")
    assert rl.format_for_tool("STRsearch", "python3 pipeline.py from_bam") == ("strsearch", "tool")
    assert rl.format_for_tool("mystr", "mystr -i x") == (None, "")


def _proposal(name):
    tree, readme, repo = dr.load_offline(REPOS / name)
    return dr.detect(dr.repo_slug(repo), tree["ref"], tree, readme, "README.md")


def test_proposal_picks_the_library_file_for_known_tools(tmp_path):
    for name, fmt in (("hipstr", "hipstr"), ("gangstr", "gangstr"), ("strsearch", "strsearch")):
        r = pm.build(_proposal(name), f"{name}-trial")
        assert r["manifest"]["inputs"].get("regions") == {"library": fmt}, name
        assert "regions_format_unknown" not in r["limitations"]
        assert any("ready-made" in c for c in r["manifest"]["caveats"]["items"])


def test_the_long_read_tools_get_the_motif_in_column_four():
    """LongTR, straglr, NanoRepeat and strkit each read the repeat motif from
    column 4 and refuse anything else there: a locus name (bed4) or a period
    (hipstr, gangstr). By program name, and by a README that lays it out."""
    for prog in ("LongTR", "straglr.py", "nanoRepeat.py", "strkit"):
        assert rl.format_for_tool(prog, prog)[0] == "motif", prog
    assert rl.format_for_tool("sometool", "", "`--loci`: 4 column BED format: chromosome start end repeat")[0] == "motif"
    assert rl.format_for_tool("sometool", "", "CHROM | START | END | MOTIF | NAME")[0] == "motif"
    for t in BAM_TYPES:
        rows = [ln.split("\t") for ln in rl.library_path(t, "motif").read_text().splitlines() if ln.strip()]
        assert rows and all(len(r) == 4 and r[3].isalpha() and r[3].isupper() for r in rows), t


def test_the_ont_panel_is_the_codis_loci_inside_its_slices():
    """Derived by coordinates from the Illumina panel: the ONT slices are the
    CODIS loci ±10 kb, at the same hg38 positions."""
    names = [ln.split("\t")[3] for ln in rl.library_path("ont-bam-hg38", "bed4").read_text().splitlines() if ln.strip()]
    assert len(names) == 20 and {"TH01", "vWA", "FGA", "D21S11", "TPOX"} <= set(names)


def test_the_hifi_slice_has_the_same_windows_and_so_the_same_panel_as_ont():
    """The PacBio HiFi slice was cut with the ONT windows; the two derived
    libraries differ only in the file they name."""
    assert (ROOT / "pacbio_slices" / "codis_pm10kb.bed").read_text() == \
        (ROOT / "ont_slices" / "codis_pm10kb.bed").read_text()
    for fmt in rl.available("ont-bam-hg38"):
        assert rl.library_path("pacbio-hifi-bam-hg38", fmt).read_text() == \
            rl.library_path("ont-bam-hg38", fmt).read_text(), fmt


def test_the_manifest_schema_accepts_every_library_format():
    """A format added to the library and not to the schema published nothing:
    report.py rejected every trial that used it (motif, on 29 September)."""
    import json
    schema = json.loads((ROOT / "schema" / "manifest.schema.json").read_text())
    text = json.dumps(schema)
    import re
    enums = [json.loads(m) for m in re.findall(r'"enum": (\[[^\]]*"bed4"[^\]]*\])', text)]
    assert enums, "the regions library enum is not in the schema"
    for t in BAM_TYPES:
        for fmt in rl.available(t):
            assert all(fmt in e for e in enums), (fmt, enums)


def test_expansionhunter_gets_a_catalog_of_the_panel_and_trgt_its_repeat_definitions():
    """The loci to genotype, in the shape each tool takes them: HipSTR a
    regions BED, ExpansionHunter a JSON variant catalog, TRGT a BED of
    repeat definitions. Same loci, same coordinates (0-based where the format
    is), recognised back by detect_format."""
    import json
    assert rl.format_for_tool("ExpansionHunter", "ExpansionHunter --reads x")[0] == "eh_catalog"
    assert rl.format_for_tool("trgt", "trgt genotype")[0] == "trgt"
    for t in BAM_TYPES:
        hip = [ln.split("\t") for ln in rl.library_path(t, "hipstr").read_text().splitlines() if ln.strip()]
        cat = json.loads(rl.library_path(t, "eh_catalog").read_text())
        assert [c["LocusId"] for c in cat] == [h[5] for h in hip], t
        for c, h in zip(cat, hip):
            assert c["ReferenceRegion"] == f"{h[0]}:{int(h[1]) - 1}-{h[2]}"
            assert c["LocusStructure"] == f"({h[6]})*"
        assert rl.detect_format(rl.library_path(t, "eh_catalog").read_text()) == "eh_catalog"
        trgt = rl.library_path(t, "trgt").read_text().splitlines()
        assert len(trgt) == len(hip) and all("MOTIFS=" in ln and "STRUC=" in ln for ln in trgt)


def test_a_json_catalog_is_staged_as_regions_json(tmp_path):
    import prepare
    legs = [tmp_path / "in_own", tmp_path / "in_external"]
    src = prepare.stage_regions({"library": "eh_catalog"}, legs, "illumina-bam-hg38")
    assert src == "strhub"
    for leg in legs:
        assert (leg / "regions.json").is_file() and not (leg / "regions.bed").exists()
