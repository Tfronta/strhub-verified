"""The example gate: the README's own command produced something."""
import check_example
import prepare


def _manifest(tmp_path, example):
    mf = tmp_path / "m.yml"
    body = (
        "tool: {name: x, version: '1'}\n"
        "source: {repo: 'https://github.com/a/b', ref: abc}\n"
        "environment: {dockerfile: Dockerfile}\n"
        "run: {cmd: x}\n"
        "outputs:\n  - {path: '*.tsv', format: tsv}\n"
    )
    if example:
        body += "example:\n" + "".join(f"  {k}: {v}\n" for k, v in example.items())
    mf.write_text(body)
    return str(mf)


def test_not_applicable_without_an_example(tmp_path):
    out = tmp_path / "out"; out.mkdir()
    r = check_example.check(_manifest(tmp_path, None), str(out))
    assert r["applicable"] is False and r["passed"] is False


def test_any_created_file_counts_when_nothing_declared(tmp_path):
    out = tmp_path / "out"; (out / "results").mkdir(parents=True)
    (out / "results" / "calls.vcf").write_text("x\n")
    r = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'"}), str(out))
    assert r["passed"] is True and r["produced"] == ["results/calls.vcf"]


def test_empty_files_do_not_count(tmp_path):
    out = tmp_path / "out"; out.mkdir()
    (out / "calls.vcf").write_text("")
    r = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'"}), str(out))
    assert r["passed"] is False


def test_declared_outputs_must_all_be_present(tmp_path):
    out = tmp_path / "out"; out.mkdir()
    (out / "calls.vcf").write_text("x\n")
    ok = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'", "outputs": "['*.vcf']"}), str(out))
    assert ok["passed"] is True
    missing = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'", "outputs": "['*.vcf', 'stats.txt']"}), str(out))
    assert missing["passed"] is False


def test_expected_golden_file_is_compared_but_never_fails(tmp_path):
    out = tmp_path / "out"; (out / "_expected").mkdir(parents=True)
    (out / "calls.vcf").write_text("#h\nchr1 1  A\n")
    (out / "_expected" / "expected.vcf").write_text("chr1\t1\tA\n")
    r = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'", "outputs": "['*.vcf']",
                                                 "expected": "test/expected.vcf"}), str(out))
    assert r["passed"] is True and r["checks"]["matches_expected"] is True
    (out / "calls.vcf").write_text("chr1\t2\tA\n")
    r = check_example.check(_manifest(tmp_path, {"cmd": "'./tool'", "outputs": "['*.vcf']",
                                                 "expected": "test/expected.vcf"}), str(out))
    assert r["passed"] is True and r["checks"]["matches_expected"] is False


def test_wrapper_keeps_the_command_and_its_exit_status():
    w = prepare.example_wrapper("./HipSTR --bams  x.bam\n --out out.vcf", "/opt/tool")
    assert w.startswith("cd '/opt/tool' && touch /tmp/.strhub_mark && ( ./HipSTR --bams x.bam --out out.vcf ); rc=$?;")
    assert w.endswith("exit $rc")
    assert "\n" not in w
