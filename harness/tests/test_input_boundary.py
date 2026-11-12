"""Runner-boundary regressions with inert files; never Docker or STR software."""
import builtins
import json
import pathlib
import sys

import pytest
import yaml
from jsonschema import ValidationError

import _manifest
import _paths
import prepare

CASES = json.loads((pathlib.Path(__file__).parents[1] / "testdata/input_path_cases.json").read_text())


@pytest.mark.parametrize("case", CASES)
def test_manifest_path_contract_matches_web_cases(case):
    for field in ("fixture", "regions", "dockerfile", "from_repo", "fallback"):
        m = manifest()
        if field in ("fixture", "regions"):
            m["inputs"] = {field: case["path"]}
        elif field == "fallback":
            m["environment"]["fallback"] = {"dockerfile": case["path"]}
        else:
            m["environment"][field] = case["path"]
        if case["valid"]:
            _manifest.validate(m)
        else:
            with pytest.raises((ValueError, ValidationError)):
                _manifest.validate(m)


def manifest():
    return {"tool": {"name": "example", "version": "1"},
            "source": {"repo": "https://github.com/example/tool", "ref": "a" * 40},
            "environment": {"dockerfile": "Dockerfile"},
            "run": {"cmd": "not executed"},
            "outputs": [{"path": "result.txt", "format": "text"}]}


def committed(tmp_path, monkeypatch, m=None):
    root = tmp_path / "repo"
    tool = root / "tools" / "example"
    tool.mkdir(parents=True)
    (tool / "manifest.yml").write_text(yaml.safe_dump(m or manifest()))
    (tool / "Dockerfile").write_text("FROM scratch\n")
    monkeypatch.setattr(prepare, "ROOT", root)
    work = tmp_path / "work"
    monkeypatch.setattr(sys, "argv", ["prepare.py", "example", "--work", str(work)])
    return root, tool, work


@pytest.mark.parametrize("value", ["/tmp/sentinel", "../sentinel", "a/../../sentinel", "~/.ssh/key",
                                       "C:\\sentinel", "a\\..\\sentinel", "a\nfile", ".git/config", "."])
def test_fixture_and_regions_reject_unsafe_paths_without_writes(tmp_path, value):
    dest = tmp_path / "staged"
    for fn, args in [(prepare.stage_own, (value, dest)),
                     (prepare.stage_regions, (value, [dest])),
                     (prepare.stage_regions, ({"path": value, "provided_by": "author"}, [dest]))]:
        with pytest.raises(ValueError):
            fn(*args)
        assert not dest.exists()


@pytest.mark.parametrize("kind", ["file", "directory_member", "bam_index"])
def test_fixture_symlink_escape_is_rejected_before_copying(tmp_path, monkeypatch, kind):
    root, _, work = committed(tmp_path, monkeypatch)
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("PRIVATE SENTINEL - NEVER COPY\n")
    data = root / "fixtures"
    data.mkdir()
    if kind == "directory_member":
        (data / "safe.txt").write_text("safe")
        (data / "escape.txt").symlink_to(sentinel)
        fixture = "fixtures"
    else:
        bam = data / "sample.bam"
        if kind == "file":
            bam.symlink_to(sentinel)
        else:
            bam.write_text("fake BAM")
            (data / "sample.bam.bai").symlink_to(sentinel)
        fixture = "fixtures/sample.bam"
    with pytest.raises(ValueError, match="escapes"):
        prepare.stage_own(fixture, work / "in_own")
    assert not work.exists()
    assert sentinel.read_text() == "PRIVATE SENTINEL - NEVER COPY\n"


def test_local_regions_symlink_escape_is_rejected(tmp_path, monkeypatch):
    root, _, work = committed(tmp_path, monkeypatch)
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("not a public BED")
    (root / "regions.bed").symlink_to(sentinel)
    with pytest.raises(ValueError, match="escapes"):
        prepare.stage_regions({"path": "regions.bed", "provided_by": "author"}, [work / "in"])
    assert not work.exists()


@pytest.mark.parametrize("tool", ["../outside", "/tmp/outside", "a/b", ".git"])
def test_tool_identifier_cannot_select_another_root(tmp_path, monkeypatch, tool):
    work = tmp_path / "work"
    monkeypatch.setattr(sys, "argv", ["prepare.py", tool, "--work", str(work), "--trial"])
    with pytest.raises(ValueError, match="safe directory"):
        prepare.main()
    assert not work.exists()


def test_dataset_index_cannot_introduce_an_external_source(tmp_path, monkeypatch):
    _, _, work = committed(tmp_path, monkeypatch)
    monkeypatch.setattr(prepare.datasets_lib, "load_index", lambda: {
        "datasets": {"test": {"data": "../outside.bam", "canonical_input": "input.bam"}}})
    with pytest.raises(ValueError):
        prepare.stage_external("test", work / "in_external")
    assert not work.exists()


def test_missing_validator_cannot_turn_off_manifest_validation(monkeypatch):
    real_import = builtins.__import__
    def absent(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("synthetic missing dependency")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", absent)
    with pytest.raises(RuntimeError, match="validation cannot be skipped"):
        _manifest.validate(manifest())


@pytest.mark.parametrize("kind", ["fixture", "assets", "dockerfile", "destination"])
def test_entire_preparation_checks_all_paths_before_any_download_or_copy(tmp_path, monkeypatch, kind):
    m = manifest()
    m["inputs"] = {"fixture": {"repo": "https://github.com/example/tool", "ref": "a" * 40,
                              "path": "example.bam"}}
    root, tool, work = committed(tmp_path, monkeypatch, m)
    sentinel = tmp_path / "outside"
    sentinel.mkdir()
    (sentinel / "private").write_text("never read")
    if kind == "fixture":
        m["inputs"]["regions"] = "/etc/hosts"
        (tool / "manifest.yml").write_text(yaml.safe_dump(m))
    elif kind == "assets":
        (tool / "assets").symlink_to(sentinel, target_is_directory=True)
    elif kind == "dockerfile":
        (tool / "Dockerfile").unlink()
        (tool / "Dockerfile").symlink_to(sentinel / "private")
    else:
        work.mkdir()
        (work / "in_own").symlink_to(sentinel, target_is_directory=True)
    def forbidden(*args, **kwargs):
        raise AssertionError("download/copy started before input validation")
    monkeypatch.setattr(prepare.urllib.request, "urlretrieve", forbidden)
    monkeypatch.setattr(prepare.shutil, "copy2", forbidden)
    with pytest.raises((ValueError, ValidationError)):
        prepare.main()
    assert not (work / "in_external").exists()
    assert (sentinel / "private").read_text() == "never read"


def test_safe_local_inputs_and_bam_index_still_stage_verbatim(tmp_path, monkeypatch):
    root, _, work = committed(tmp_path, monkeypatch)
    (root / "fixture.bam").write_bytes(b"fake BAM\x00")
    (root / "fixture.bam.bai").write_bytes(b"fake index\x00")
    assert prepare.stage_own("fixture.bam", work / "in_own", "input.bam")
    assert (work / "in_own/input.bam").read_bytes() == b"fake BAM\x00"
    assert (work / "in_own/input.bam.bai").read_bytes() == b"fake index\x00"


def test_remote_url_quotes_literals_without_url_traversal_or_query():
    url = _paths.raw_url({"repo": "https://github.com/example/tool.git", "ref": "release/v1",
                          "path": "examples/a b?x#y.bam"})
    assert url == "https://raw.githubusercontent.com/example/tool/release%2Fv1/examples/a%20b%3Fx%23y.bam"
    with pytest.raises(ValueError):
        _paths.raw_url({"repo": "https://github.com/example/tool", "ref": "main", "path": "../other"})


def test_stale_canonical_file_symlink_cannot_overwrite_another_file(tmp_path, monkeypatch):
    root, _, work = committed(tmp_path, monkeypatch)
    (root / "fixture.bam").write_text("public data")
    dest = work / "in_own"
    dest.mkdir(parents=True)
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("preserve")
    (dest / "input.bam").symlink_to(sentinel)
    with pytest.raises(ValueError):
        prepare.stage_own("fixture.bam", dest, "input.bam")
    assert sentinel.read_text() == "preserve"
