"""The regions library: a ready-made file per tool format, recognised both ways."""
import pathlib

import regions_library as rl
import propose_manifest as pm
import detect_recipe as dr

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOS = ROOT / "harness" / "testdata" / "repos"


def test_every_bam_dataset_has_every_format():
    for t in ("illumina-bam-hg38", "illumina-bam-hg38-y"):
        assert rl.available(t) == ["bed4", "gangstr", "hipstr", "strsearch"], t
        for fmt in rl.available(t):
            assert rl.library_path(t, fmt) is not None


def test_library_files_are_their_own_format():
    for t in ("illumina-bam-hg38", "illumina-bam-hg38-y"):
        for fmt in rl.available(t):
            assert rl.detect_format(rl.library_path(t, fmt).read_text()) == fmt, (t, fmt)


def test_library_files_cover_the_panel():
    for t in ("illumina-bam-hg38", "illumina-bam-hg38-y"):
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
