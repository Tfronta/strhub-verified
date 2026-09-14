"""The IO gate: present, non-empty, parses, and clears min_records."""
import pathlib

import check_io


def _count(tmp_path, name, text, fmt):
    p = tmp_path / name
    p.write_text(text)
    return check_io._count_records(p, fmt)


def test_blank_lines_are_not_records(tmp_path):
    assert _count(tmp_path, "empty.tsv", "\n\n", "tsv") == 0
    assert _count(tmp_path, "empty.csv", "\n", "csv") == 0


def test_header_only_file_has_zero_records(tmp_path):
    assert _count(tmp_path, "h.tsv", "Locus\tAllele\tReads\n", "tsv") == 0


def test_single_data_row_without_header_is_one_record(tmp_path):
    assert _count(tmp_path, "one.tsv", "TH01:9\tAATG\t120\t118\n", "tsv") == 1


def test_header_over_numeric_columns_is_dropped(tmp_path):
    text = "Locus\tReads\nTH01\t12\nTPOX\t7\n"
    assert _count(tmp_path, "t.tsv", text, "tsv") == 2


def test_all_text_rows_keep_every_row(tmp_path):
    # No numeric column to prove a header, so nothing is dropped.
    text = "TH01\tAATG\nTPOX\tAATG\n"
    assert _count(tmp_path, "t.tsv", text, "tsv") == 2


def test_vcf_counts_non_header_lines(tmp_path):
    text = "##fileformat=VCFv4.2\n#CHROM\tPOS\nchr1\t1\nchr1\t2\n"
    assert _count(tmp_path, "x.vcf", text, "vcf") == 2


def test_gate_refuses_escaping_pattern(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    manifest = tmp_path / "m.yml"
    manifest.write_text(
        "tool: {name: x, version: '1'}\n"
        "source: {repo: 'https://github.com/a/b', ref: abc}\n"
        "environment: {dockerfile: Dockerfile}\n"
        "run: {cmd: x}\n"
        "outputs:\n  - {path: 'link/*', format: tsv, min_records: 1}\n"
    )
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "regions.bed").write_text("chr1\t1\t2\n")
    (out / "link").symlink_to(tmp_path / "in")
    result = check_io.check(str(manifest), str(out))
    assert result["passed"] is False
    assert result["outputs"][0]["checks"] == {"confined": True, "exists": False}
