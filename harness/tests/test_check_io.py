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


def test_vcf_uncalled_rows_do_not_count_as_called_records(tmp_path):
    """A VCF where every locus row has a missing genotype (./.) because the
    slice held no reads at those coordinates is not a passed IO gate."""
    out = tmp_path / "out"
    out.mkdir()
    vcf = (
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
        "chr4\t3074876\tHTT\tC\t.\t.\tPASS\t.\tGT:DP\t./.:0\n"
        "chrX\t147912050\tFMR1\tC\t.\t.\tPASS\t.\tGT:DP\t.:0\n"
    )
    (out / "calls.vcf").write_text(vcf)
    manifest = tmp_path / "m.yml"
    manifest.write_text(
        "tool: {name: x, version: '1'}\n"
        "source: {repo: 'https://github.com/a/b', ref: abc}\n"
        "environment: {dockerfile: Dockerfile}\n"
        "run: {cmd: x}\n"
        "outputs:\n  - {path: '*.vcf', format: vcf, min_records: 1}\n"
    )
    result = check_io.check(str(manifest), str(out))
    assert result["passed"] is False
    assert result["outputs"][0]["records"] == 0
    assert result["outputs"][0]["uncalled_rows"] == 2

    # When at least one locus has a called genotype (including 0/0), it counts.
    (out / "calls.vcf").write_text(vcf + "chr11\t2171088\tTH01\tA\t.\t.\tPASS\t.\tGT:DP\t0/0:45\n")
    result2 = check_io.check(str(manifest), str(out))
    assert result2["passed"] is True
    assert result2["outputs"][0]["records"] == 1


def test_uncalled_vcf_on_slice_is_strhub_limitation_not_runs_or_fails(tmp_path):
    """A tool that ran to completion and wrote a VCF of uncalled loci (./.) on
    STRhub's slice must be classified as undetermined (basis='strhub',
    step1='ours'), never as 'runs' or 'fails'."""
    import json
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[2]
    manifest = tmp_path / "m.yml"
    manifest.write_text(
        "tool: {name: mahi-mahi, version: '1'}\n"
        "source: {repo: 'https://github.com/nanoporetech/mahi-mahi', ref: abc1234}\n"
        "report: {slug: test-uncalled-vcf}\n"
        "environment: {dockerfile: Dockerfile}\n"
        "run: {cmd: 'mahi-mahi --bam /data/in/input.bam --loci hg38'}\n"
        "outputs:\n  - {path: '*.vcf', format: vcf, min_records: 1}\n"
    )
    io_json = tmp_path / "io.json"
    io_json.write_text(json.dumps({
        "gate": "io",
        "passed": False,
        "outputs": [{"path": "*.vcf", "format": "vcf", "records": 0, "uncalled_rows": 99,
                     "checks": {"confined": True, "exists": True, "non_empty": True,
                                "parses_as_vcf": True, "min_records": False}, "passed": False}],
    }))
    try:
        res = subprocess.run([
            sys.executable, str(root / "harness" / "report.py"),
            "--manifest", str(manifest),
            "--available", "pass",
            "--installs", "pass",
            "--runs", "pass",
            "--io", str(io_json),
            "--content", str(tmp_path / "no-content.json"),
            "--matrix", str(tmp_path / "no-matrix.json"),
            "--readme", str(tmp_path / "no-readme.json"),
            "--example", str(tmp_path / "no-example.json"),
            "--regions-validation", str(tmp_path / "no-regions.json"),
            "--mode", "trial",
        ], cwd=str(root), check=True, capture_output=True, text=True)
        report = json.loads(res.stdout)
        assert report["verdict"]["code"] == "undetermined"
        assert report["verdict"]["basis"] == "strhub"
        assert report["step1"]["code"] == "ours"
    finally:
        for p in (root / "reports").glob("test-uncalled-vcf.*"):
            p.unlink(missing_ok=True)


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
