"""prepare.py: step outputs are one line each, and a trial recipe is staged
from the dispatch input instead of tools/<slug>/."""
import base64
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREPARE = ROOT / "harness" / "prepare.py"


def _run(args, env=None):
    out = subprocess.run([sys.executable, str(PREPARE), *args], capture_output=True, text=True, env=env)
    return out.returncode, dict(ln.split("=", 1) for ln in out.stdout.splitlines() if "=" in ln), out.stderr


def test_committed_tool_outputs_are_single_line(tmp_path):
    rc, kv, _ = _run(["strait-razor-PowerSeqv2.31", "--work", str(tmp_path)])
    assert rc == 0
    assert kv["mode"] == "publish"
    assert kv["dockerdir"] == "tools/strait-razor-PowerSeqv2.31"
    assert all("\n" not in v and "\r" not in v for v in kv.values())


def test_trial_recipe_is_materialised_and_regions_staged(tmp_path):
    src = ROOT / "tools" / "hipstr-b2033bf"
    manifest = src.joinpath("manifest.yml").read_text()
    # A newline smuggled into a manifest value must not become a second key.
    manifest = manifest.replace('name: hipstr', 'name: "hipstr\\nown_ready=1"')
    # An uploaded regions file, as the web sends one (the committed recipe now
    # uses the library; a trial recipe can still carry its own).
    import re
    manifest = re.sub(r"^    library: hipstr.*$", '    path: "tools/hipstr-b2033bf/assets/regions.bed"\n    provided_by: author', manifest, flags=re.M)
    assert "provided_by: author" in manifest
    recipe = {
        "manifest_yml": manifest,
        "dockerfile": src.joinpath("Dockerfile").read_text(),
        "regions_bed": (ROOT / "datasets" / "illumina-bam-hg38" / "regions" / "hipstr.bed").read_text(),
    }
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    rc, kv, err = _run(["hipstr-b2033bf", "--work", str(tmp_path), "--recipe-b64", b64])
    assert rc == 0, err
    assert kv["mode"] == "trial"
    assert kv["dockerdir"].endswith("recipe/hipstr-b2033bf")
    assert (tmp_path / "recipe" / "hipstr-b2033bf" / "Dockerfile").is_file()
    assert kv["regions_source"] == "tool"
    assert kv["regions_missing"] == "0"
    assert (tmp_path / "in_external" / "regions.bed").is_file()
    assert all("\n" not in v for v in kv.values())


def test_garbage_recipe_stops_the_run(tmp_path):
    rc, _, err = _run(["x", "--work", str(tmp_path), "--recipe-b64", "!!not-base64"])
    assert rc != 0 and "::error::" in err
