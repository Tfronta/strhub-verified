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
    rc, kv, _ = _run(["strait-razor-powerseq", "--work", str(tmp_path)])
    assert rc == 0
    assert kv["mode"] == "publish"
    assert kv["dockerdir"] == "tools/strait-razor-powerseq"
    assert all("\n" not in v and "\r" not in v for v in kv.values())


def test_trial_recipe_is_materialised_and_regions_staged(tmp_path):
    src = ROOT / "tools" / "hipstr-autosomal"
    manifest = src.joinpath("manifest.yml").read_text()
    # A newline smuggled into a manifest value must not become a second key.
    manifest = manifest.replace('name: hipstr', 'name: "hipstr\\nown_ready=1"')
    # An uploaded regions file, as the web sends one: give the recipe an explicit
    # author-provided regions block (this manifest otherwise stages its assets
    # regions.bed by convention).
    manifest = manifest.replace(
        '  type: "illumina-bam-hg38"\n',
        '  type: "illumina-bam-hg38"\n  regions:\n    path: "tools/hipstr-autosomal/assets/regions.bed"\n    provided_by: author\n',
        1)
    assert "provided_by: author" in manifest
    recipe = {
        "manifest_yml": manifest,
        "dockerfile": src.joinpath("Dockerfile").read_text(),
        "regions_bed": (ROOT / "datasets" / "illumina-bam-hg38" / "regions" / "hipstr.bed").read_text(),
    }
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    rc, kv, err = _run(["hipstr-autosomal", "--work", str(tmp_path), "--recipe-b64", b64])
    assert rc == 0, err
    assert kv["mode"] == "trial"
    assert kv["dockerdir"].endswith("recipe/hipstr-autosomal")
    assert (tmp_path / "recipe" / "hipstr-autosomal" / "Dockerfile").is_file()
    assert kv["regions_source"] == "tool"
    assert kv["regions_missing"] == "0"
    assert (tmp_path / "in_external" / "regions.bed").is_file()
    assert all("\n" not in v for v in kv.values())
    # No plan B declared: the Installs step must not look for one.
    assert kv["dockerfile_fallback"] == ""


def test_trial_recipe_with_a_plan_b_stages_the_fallback_dockerfile(tmp_path):
    src = ROOT / "tools" / "gangstr"
    manifest = src.joinpath("manifest.yml").read_text()
    manifest = manifest.replace("environment:\n", "environment:\n  fallback:\n    dockerfile: Dockerfile.fallback\n    reason: the published image gymreklab/str-toolkit the README points at\n", 1)
    recipe = {"manifest_yml": manifest, "dockerfile": src.joinpath("Dockerfile").read_text(),
              "dockerfile_fallback": "FROM gymreklab/str-toolkit\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n"}
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    rc, kv, err = _run(["gangstr", "--work", str(tmp_path), "--recipe-b64", b64])
    assert rc == 0, err
    assert kv["dockerfile_fallback"] == "Dockerfile.fallback"
    assert (tmp_path / "recipe" / "gangstr" / "Dockerfile.fallback").read_text().startswith("FROM gymreklab/str-toolkit")


def test_a_declared_plan_b_that_is_missing_is_a_warning_not_a_silent_nothing(tmp_path):
    src = ROOT / "tools" / "gangstr"
    manifest = src.joinpath("manifest.yml").read_text()
    manifest = manifest.replace("environment:\n", "environment:\n  fallback:\n    dockerfile: Dockerfile.fallback\n", 1)
    recipe = {"manifest_yml": manifest, "dockerfile": src.joinpath("Dockerfile").read_text()}
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    rc, kv, err = _run(["gangstr", "--work", str(tmp_path), "--recipe-b64", b64])
    assert rc == 0, err
    assert kv["dockerfile_fallback"] == ""
    assert "::warning::fallback Dockerfile declared but not found" in err


def test_garbage_recipe_stops_the_run(tmp_path):
    rc, _, err = _run(["x", "--work", str(tmp_path), "--recipe-b64", "!!not-base64"])
    assert rc != 0 and "::error::" in err
