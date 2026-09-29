"""The regions library: a ready-made file per tool format, recognised both ways."""
import pathlib

import regions_library as rl
import propose_manifest as pm
import detect_recipe as dr

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOS = ROOT / "harness" / "testdata" / "repos"


BAM_TYPES = ("illumina-bam-hg38", "illumina-bam-hg38-y", "ont-bam-hg38")


def test_every_bam_dataset_has_every_format():
    for t in BAM_TYPES:
        assert rl.available(t) == ["bed4", "gangstr", "hipstr", "motif", "strsearch"], t
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
