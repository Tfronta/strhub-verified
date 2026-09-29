"""outputs[].path must not be able to reach outside /data/out."""
import _manifest


def test_relative_globs_match_inside_out(tmp_path):
    (tmp_path / "a.tsv").write_text("x\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.tsv").write_text("y\n")
    m, why = _manifest.safe_glob(tmp_path, "*.tsv")
    assert why is None and [p.name for p in m] == ["a.tsv"]
    m, why = _manifest.safe_glob(tmp_path, "**/*.tsv")
    assert why is None and sorted(p.name for p in m) == ["a.tsv", "b.tsv"]


def test_parent_and_absolute_patterns_are_refused(tmp_path):
    for pattern in ("../x/*", "a/../../x", "/etc/*", "~/x"):
        m, why = _manifest.safe_glob(tmp_path, pattern)
        assert m == [] and why, pattern


def test_symlink_pointing_outside_is_dropped(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.tsv").write_text("s\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "link").symlink_to(outside)
    m, why = _manifest.safe_glob(out, "link/*")
    assert why is None and m == []


def test_the_catch_all_pattern_matches_files_not_the_directory_they_are_in(tmp_path):
    """A proposed recipe declares `**/*`. The tool wrote results/calls.vcf, and
    the first match used to be results/ itself, which no gate can parse."""
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "calls.vcf").write_text("##fileformat=VCFv4.2\n")
    m, why = _manifest.safe_glob(tmp_path, "**/*")
    assert why is None and [p.relative_to(tmp_path).as_posix() for p in m] == ["results/calls.vcf"]
