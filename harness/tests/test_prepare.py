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
    src = ROOT / "tools" / "hipstr"
    manifest = src.joinpath("manifest.yml").read_text()
    # A newline smuggled into a manifest value must not become a second key.
    manifest = manifest.replace('name: hipstr', 'name: "hipstr\\nown_ready=1"')
    # An uploaded regions file, as the web sends one: give the recipe an explicit
    # author-provided regions block (this manifest otherwise stages its assets
    # regions.bed by convention).
    manifest = manifest.replace(
        '  type: "illumina-bam-hg38"\n',
        '  type: "illumina-bam-hg38"\n  regions:\n    path: "tools/hipstr/assets/regions.bed"\n    provided_by: author\n',
        1)
    assert "provided_by: author" in manifest
    recipe = {
        "manifest_yml": manifest,
        "dockerfile": src.joinpath("Dockerfile").read_text(),
        "regions_bed": (ROOT / "datasets" / "illumina-bam-hg38" / "regions" / "hipstr.bed").read_text(),
    }
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    rc, kv, err = _run(["hipstr", "--work", str(tmp_path), "--recipe-b64", b64])
    assert rc == 0, err
    assert kv["mode"] == "trial"
    assert kv["dockerdir"].endswith("recipe/hipstr")
    assert (tmp_path / "recipe" / "hipstr" / "Dockerfile").is_file()
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


def test_the_tools_own_command_comes_back_out_of_the_wrapper():
    """The report names what the gates ran. The wrapper around a README command
    is STRhub's plumbing — marking the time, copying files — and a reader shown
    the whole line cannot tell which part is the tool's."""
    import prepare

    cmd = "./HipSTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa --str-vcf str_calls.vcf.gz"
    wrapped = prepare.example_wrapper(cmd, "/opt/tool")
    assert prepare.unwrap_example(wrapped) == (cmd, "/opt/tool")
    # A committed manifest's command is not wrapped and comes back as it is.
    assert prepare.unwrap_example("  GangSTR --bam in.bam   --out out ") == ("GangSTR --bam in.bam --out out", None)


def test_the_ont_fastq_is_handed_over_uncompressed(tmp_path):
    # Committed gzipped to keep the repository small; staged as plain FASTQ,
    # which every reader takes, under the name the run command uses.
    sys.path.insert(0, str(ROOT / "harness"))
    import prepare
    staged, name = prepare.stage_external("ont-fastq", tmp_path)
    assert staged and "HG00113" in name
    fq = tmp_path / "input.fastq"
    with fq.open() as f:
        head = [next(f) for _ in range(4)]
    assert head[0].startswith("@") and head[2].startswith("+") and len(head[1]) == len(head[3])
    assert sum(1 for _ in fq.open()) == 4 * 864


def test_shipped_example_still_runs_when_strhub_sample_is_not_ready(tmp_path):
    """When the repository ships its own example (example.cmd) and states how to
    install, a STRhub reference-sample limitation (such as loci_outside_panel)
    must only disable the external leg, never the repository's own example leg."""
    src = ROOT / "tools" / "strsearch"
    manifest = src.joinpath("manifest.yml").read_text()
    manifest += "\nexample:\n  cmd: python3 STRsearch.py -i example/test_data/ -c example/STR.configuration.txt -o out/\n  cwd: /opt/tool\n"
    recipe = {"manifest_yml": manifest, "dockerfile": src.joinpath("Dockerfile").read_text()}
    b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({
        "procedure": {"may_say_runs": False, "blocker": "loci_outside_panel"}
    }))
    rc, kv, err = _run(["strsearch", "--work", str(tmp_path), "--recipe-b64", b64, "--proposal", str(proposal)])
    assert rc == 0, err
    assert kv["external_ready"] == "0"
    assert kv["install_ready"] == "1"
    assert kv["example_ready"] == "1"

    # When no install procedure exists at all, nothing builds so example_ready is 0.
    proposal.write_text(json.dumps({
        "procedure": {"may_say_runs": False, "blocker": "no_install_procedure"}
    }))
    rc2, kv2, err2 = _run(["strsearch", "--work", str(tmp_path), "--recipe-b64", b64, "--proposal", str(proposal)])
    assert rc2 == 0, err2
    assert kv2["install_ready"] == "0"
    assert kv2["example_ready"] == "0"
