import yaml

import check_example


def contract(tmp_path, **example):
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump({
        "tool": {"name": "boundary", "version": "1"},
        "source": {"repo": "https://github.com/example/tool", "ref": "a" * 40},
        "environment": {"dockerfile": "Dockerfile"}, "run": {"cmd": "not executed"},
        "outputs": [{"path": "*.txt", "format": "text"}],
        "example": {"cmd": "not executed", **example},
    }))
    return str(manifest)


def test_external_output_symlink_is_not_counted_as_created_output(tmp_path):
    outside = tmp_path / "private"
    outside.write_text("private sentinel")
    out = tmp_path / "out"
    out.mkdir()
    (out / "result.txt").symlink_to(outside)
    result = check_example.check(contract(tmp_path), str(out))
    assert result["passed"] is False
    assert result["produced_count"] == 0


def test_golden_input_symlink_cannot_read_a_runner_file(tmp_path, monkeypatch):
    outside = tmp_path / "private"
    outside.write_text("private sentinel")
    out = tmp_path / "out"
    (out / "_expected").mkdir(parents=True)
    (out / "_expected/golden.txt").symlink_to(outside)
    (out / "result.txt").write_text("public output")
    def forbidden(*args):
        raise AssertionError("outside golden file was read")
    monkeypatch.setattr(check_example, "_normalised", forbidden)
    result = check_example.check(contract(tmp_path, outputs=["result.txt"], expected="golden.txt"), str(out))
    assert result["checks"]["matches_expected"] is None
    assert "_expected/golden.txt" not in result["produced"]
