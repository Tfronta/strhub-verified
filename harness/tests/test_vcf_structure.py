import gzip
import json
import pathlib
import sys

import pytest
import yaml

import check_io
import report as report_module
import vcf_structure as vcf

FIXED = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"
SITE = "chr1\t10\t.\tA\tC\t.\tPASS\t."
HEADER = "##fileformat=VCFv4.2\n" + FIXED + "\n"
GT_HEADER = "##fileformat=VCFv4.2\n" + FIXED + "\tFORMAT\tSAMPLE\n"
VALID = HEADER + SITE + "\n"
ROOT = pathlib.Path(__file__).resolve().parents[2]


def gate(tmp_path, files, **spec):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data if isinstance(data, bytes) else data.encode())
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump({
        "tool": {"name": "vcf-boundary", "version": "1"},
        "source": {"repo": "https://github.com/example/tool", "ref": "a" * 40},
        "environment": {"dockerfile": "Dockerfile"}, "run": {"cmd": "not executed"},
        "outputs": [{"path": "*", "format": "vcf", "min_records": 1, **spec}],
    }))
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    result = check_io.check(str(manifest), str(out))
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}
    return result, manifest


@pytest.mark.parametrize("text", [
    "This is not a VCF file\n", "Usage: program --input x --output result.vcf\n", "ERROR failed to open input\n",
    "", "\n" + VALID, SITE + "\n", "##fileformat=VCFv4.2\n" + SITE + "\n",
    "##fileformat=VCFv4.2\n#CHROM\tPOS\nchr1\t10\n", HEADER + SITE,  # truncated final line
    HEADER + SITE.replace("\t", " ") + "\n", HEADER + SITE + "\t\n",
    HEADER + SITE + "\nERROR late failure\n", HEADER + SITE + "\n\n", HEADER + SITE + "\n##source=late\n",
    HEADER + FIXED + "\n", "##fileformat=VCFv4.2\n##fileformat=VCFv4.2\n" + FIXED + "\n",
    "##fileformat=VCFv4.2\n" + FIXED + "\tFORMAT\n", GT_HEADER + SITE + "\n",
    "##fileformat=VCFv4.2\n" + FIXED + "\tFORMAT\tA\tA\n",
    HEADER + SITE.replace("chr1", ".") + "\n", HEADER + SITE.replace("chr1", "chr 1") + "\n",
    HEADER + SITE.replace("\t10\t", "\twrong\t") + "\n", HEADER + SITE.replace("\t10\t", "\t-1\t") + "\n",
    HEADER + SITE.replace("\tA\t", "\tR\t") + "\n", HEADER + SITE.replace("\tC\t", "\tC,\t") + "\n",
    HEADER + SITE.replace("\tC\t", "\t.,C\t") + "\n", HEADER + SITE.replace("\tC\t", "\t<DEL\t") + "\n",
    HEADER + SITE.replace("\t.\tPASS", "\twrong\tPASS") + "\n",
    HEADER + SITE.replace("PASS", "PASS;q10") + "\n", HEADER + SITE.replace("PASS", "0") + "\n",
    HEADER + SITE[:-1] + "A=1;A=2\n", HEADER + SITE[:-1] + "A=\n", HEADER + SITE[:-1] + "A=x=y\n",
    GT_HEADER + SITE + "\tGT:DP\t0/1:\n", GT_HEADER + SITE + "\tGT:GT\t0/1:0/1\n",
    GT_HEADER + SITE + "\tDP:GT\t10:0/1\n", GT_HEADER + SITE + "\tGT\t0/x\n",
    GT_HEADER + SITE + "\tGT\t0/2\n", GT_HEADER + SITE + "\tGT\t0/1:10\n",
    GT_HEADER + SITE + "\tGT\t|0/1\n", GT_HEADER + SITE + "\t.\t0/1\n",
    GT_HEADER + SITE + "\tGT:X\t0/1:a,,b\n",
])
def test_malformed_files_never_pass_io(tmp_path, text):
    result, _ = gate(tmp_path, {"calls.vcf": text})
    entry = result["outputs"][0]
    assert result["passed"] is False
    assert entry["checks"]["parses_as_vcf"] is False
    assert entry["validation_status"] == "invalid"
    assert entry.get("parse_error")


@pytest.mark.parametrize("gt,called", [("0/1", 1), ("0|1", 1), ("0", 1), ("1/0/1", 1),
                                        ("./1", 1), ("0/0", 1), (".", 0), ("./.", 0), (".|.", 0)])
def test_calls_and_records_are_independent(tmp_path, gt, called):
    result, _ = gate(tmp_path, {"calls.vcf": GT_HEADER + SITE + "\tGT:DP\t" + gt + "\n"})
    entry = result["outputs"][0]
    assert entry["checks"]["parses_as_vcf"] is True
    assert entry["checks"]["min_records"] is True
    assert entry["records"] == 1
    assert entry["called_records"] == called and entry["uncalled_rows"] == 1 - called
    assert result["passed"] is bool(called)


@pytest.mark.parametrize("alt", ["C", "c,g", ".", "*", "<DEL>", "<CNV:TR>", "<NON_REF>", "<*>",
                                 "A]chr2:20]", "A[chr2:20[", "]chr2:20]A", "[chr2:20[A", ".A", "A."])
def test_sites_only_and_structural_alleles_are_supported(alt):
    summary = vcf.validate(HEADER + SITE.replace("\tC\t", "\t" + alt + "\t") + "\n")
    assert summary.records == summary.records_without_gt == 1


def test_header_only_is_a_valid_vcf_but_not_a_record():
    assert vcf.validate(HEADER).records == 0


def test_crlf_and_new_phasing_syntax():
    text = GT_HEADER.replace("4.2", "4.5") + SITE + "\tGT\t|0/1/1\n"
    assert vcf.validate(text.replace("\n", "\r\n")).called_records == 1


@pytest.mark.parametrize("typ,number,value", [("Integer", "1", "word"), ("Integer", "1", "2147483648"),
                                           ("Float", "1", "word"), ("Float", "1", "1e1000"), ("Integer", "2", "1"),
                                           ("Integer", "A", "1,2"), ("Flag", "0", ".")])
def test_declared_info_types_and_cardinalities_are_enforced(typ, number, value):
    header = f'##fileformat=VCFv4.2\n##INFO=<ID=X,Number={number},Type={typ},Description="test">\n' + FIXED + "\n"
    with pytest.raises(vcf.VCFError, match="INFO/X"):
        vcf.validate(header + SITE[:-1] + "X=" + value + "\n")


@pytest.mark.parametrize("sample", ["0/1:word", "0/1:1,2"])
def test_declared_format_type_is_checked(sample):
    header = '##fileformat=VCFv4.2\n##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Depth">\n' + FIXED + "\tFORMAT\tS\n"
    with pytest.raises(vcf.VCFError, match="FORMAT/DP"):
        vcf.validate(header + SITE + "\tGT:DP\t" + sample + "\n")


@pytest.mark.parametrize("value", ["1e-12", "-3.5", "NaN", "-Inf", "+Infinity", "."])
def test_vcf_float_literals_and_missing_values_are_supported(value):
    header = '##fileformat=VCFv4.2\n##INFO=<ID=X,Number=1,Type=Float,Description="test">\n' + FIXED + "\n"
    assert vcf.validate(header + SITE[:-1] + "X=" + value + "\n").records == 1


@pytest.mark.parametrize("meta", [
    '##INFO=<ID=X,Number=1,Type=Integer,Description="unclosed>',
    '##INFO=<ID=X,Number=1,Type=Integer,Description="a"b"c">',
    '##INFO=<ID=X,Number=1,Type=Potato,Description="test">',
    '##INFO=<ID=X,Number=potato,Type=Integer,Description="test">',
    '##INFO=<ID=X,ID=X,Number=1,Type=Integer,Description="test">',
    '##FORMAT=<ID=GT,Number=2,Type=Integer,Description="test">',
])
def test_malformed_structured_metadata_is_rejected(meta):
    with pytest.raises(vcf.VCFError):
        vcf.validate("##fileformat=VCFv4.2\n" + meta + "\n" + FIXED + "\n" + SITE + "\n")


def test_metadata_lists_do_not_split_into_spurious_attributes():
    assert vcf.validate("##fileformat=VCFv4.3\n##META=<ID=Assay,Values=[A,B]>\n" + FIXED + "\n" + SITE + "\n").records == 1


def test_declared_new_cardinality_is_an_evaluator_limit(tmp_path):
    text = '##fileformat=VCFv4.5\n##FORMAT=<ID=X,Number=LA,Type=Integer,Description="local alleles">\n' + FIXED + "\n" + SITE + "\n"
    result, _ = gate(tmp_path, {"calls.vcf": text})
    assert result["outputs"][0]["validation_status"] == "unsupported"
    assert not result["passed"]


def test_multiallelic_genotype_likelihood_count_and_quoted_metadata():
    header = ('##fileformat=VCFv4.2\n##FORMAT=<ID=PL,Number=G,Type=Integer,Description="A comma, and an escaped \\"quote\\"">\n'
              + FIXED + "\tFORMAT\tS1\tS2\n")
    row = SITE.replace("\tC\t", "\tC,G\t") + "\tGT:PL\t0/2:1,2,3,4,5,6\t./.:.\n"
    assert vcf.validate(header + row).called_records == 1
    with pytest.raises(vcf.VCFError):
        vcf.validate(header + row.replace("1,2,3,4,5,6", "1,2"))


@pytest.mark.parametrize("data", [b"not gzip", gzip.compress(VALID.encode())[:-5], VALID.encode() + b"\xff\n"])
def test_corrupt_compression_or_encoding_is_recorded_as_failure(tmp_path, data):
    result, _ = gate(tmp_path, {"calls.vcf.gz": data}, must_contain=["chr1"])
    assert result["passed"] is False
    assert result["outputs"][0]["checks"]["parses_as_vcf"] is False


def test_gzip_stream_including_concatenated_bgzf_style_members(tmp_path):
    data = gzip.compress(HEADER.encode()) + gzip.compress((SITE + "\n").encode())
    result, _ = gate(tmp_path, {"calls.vcf.gz": data})
    assert result["passed"] is True


def test_every_matching_file_is_validated_without_changing_any_bytes(tmp_path):
    result, _ = gate(tmp_path, {"a.vcf": VALID, "z.vcf": "ERROR hidden behind a valid first file\n"})
    entry = result["outputs"][0]
    assert result["passed"] is False
    assert len(entry["files"]) == 2
    assert entry["files"][0]["passed"] and not entry["files"][1]["passed"]


def test_min_records_applies_to_each_declared_file(tmp_path):
    result, _ = gate(tmp_path, {"a.vcf": VALID, "b.vcf": HEADER})
    assert result["outputs"][0]["checks"]["parses_as_vcf"] is True
    assert result["outputs"][0]["checks"]["min_records"] is False


def test_historical_output_files_are_checked_without_repairs():
    folder = ROOT / "harness/testdata/outputs"
    hipstr = folder / "hipstr.str_calls.vcf"
    gangstr = folder / "gangstr.output.vcf"
    before = {p: p.read_bytes() for p in (hipstr, gangstr)}
    assert vcf.validate(vcf.read(hipstr)).records == 23
    with pytest.raises(vcf.VCFError, match="FORMAT/REPCI: field value count"):
        vcf.validate(vcf.read(gangstr))
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("text,expected,extra", [("ERROR not a VCF\n", "fails", False),
                                              (VALID.replace("4.2", "9.9"), "undetermined", False),
                                              (VALID.replace("4.2", "9.9"), "undetermined", True)])
def test_report_cannot_certify_invalid_or_unsupported_vcf(tmp_path, text, expected, extra, monkeypatch, capsys):
    io, manifest = gate(tmp_path, {"calls.vcf": text}, path="*.vcf")
    if extra:
        m = yaml.safe_load(manifest.read_text())
        m["outputs"].append({"path": "notes.txt", "format": "text"})
        manifest.write_text(yaml.safe_dump(m))
        (tmp_path / "out/notes.txt").write_text("independent valid output\n")
        io = check_io.check(str(manifest), str(tmp_path / "out"))
    (tmp_path / "io.json").write_text(json.dumps(io))
    # Even an independently passing plausibility check cannot override IO.
    (tmp_path / "content.json").write_text('{"passed": true}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(report_module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["report.py", "--manifest", str(manifest),
                                     "--available", "pass", "--installs", "pass", "--runs", "pass",
                                     "--io", "io.json", "--content", "content.json", "--mode", "trial"])
    assert report_module.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"]["code"] == expected
    assert not report["gates"]["io"]
