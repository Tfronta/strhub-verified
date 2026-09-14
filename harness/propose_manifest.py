"""Turn a recipe proposal (detect_recipe.py) into a trial recipe: manifest.yml,
Dockerfile and, when the README's command runs on shipped data, the `example`
block. This is what a trial from a bare URL runs, before any human has typed a
command.

Two legs come out of one proposal:

  example   the README's command, verbatim, on the repository's own data,
            captured by the wrapper (see prepare.example_wrapper). Needs no
            rewriting and no STRhub data. The reviewer's gate.
  run       the same command rewritten to STRhub's reference dataset for the
            detected input type: input tokens become the canonical mount
            (/data/in/input.bam, /data/in/sample.fastq), reference tokens
            /data/ref/hg38.fa, regions tokens /data/in/regions.bed. Outputs are
            not rewritten: the command runs in the clone and whatever it
            creates is captured, so the tool's own output layout is kept.

Everything uncertain is written down: the manifest carries `caveats` with the
rewrites made and the warnings detect_recipe raised, so the report can say
"this is what STRhub guessed" rather than present a guess as the author's
configuration.

Usage:
  python harness/propose_manifest.py proposal.json --slug <slug> \
      [--submitted-by third_party] [--out-dir work/proposal] [--recipe-b64-out work/recipe.b64]
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import datasets as datasets_lib  # noqa: E402
from prepare import example_wrapper  # noqa: E402

INPUT_TOKEN = re.compile(r"(?<![\w/])[\w./-]+\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?\b", re.I)
REF_TOKEN = re.compile(r"(?<![\w/])[\w./-]+\.(?:fa|fasta|fna)(?:\.gz)?\b", re.I)
BED_TOKEN = re.compile(r"(?<![\w/])[\w./-]+\.bed\b", re.I)
OUTPUT_GLOB = {
    "vcf": ("**/*.vcf*", "vcf"),
    "tsv": ("**/*.t[sx][vt]", "tsv"),   # .tsv and .txt
    "csv": ("**/*.csv", "csv"),
    "json": ("**/*.json", "json"),
}
#: Types with a STRhub dataset, and which of them need a regions BED the
#: tool understands (a per-tool format STRhub cannot yet generate for a
#: stranger's tool; see the datasets library plan).
REQUIRES_REGIONS = {"illumina-bam-hg38", "illumina-bam-hg38-y"}


PLACEHOLDER_INPUT = re.compile(r"(?<![\w/.-])[<\[]?\w*(?:fastq|fq|bam|reads|input)\w*[>\]]?(?![\w/.-])", re.I)
PLACEHOLDER_CONFIG = re.compile(r"(?<![\w/.-])[<\[]?\w*config\w*[>\]]?(?![\w/.-])", re.I)


def resolve_placeholders(cmd: str, config_files: list[str], kit: str | None) -> tuple[str, list[str]]:
    """READMEs write `str8rzr -c configFile fastqfile`; a stranger with the
    repository in front of them substitutes a real config from the tree. When
    the dataset names a kit (the NIST sample is ForenSeq), the matching config
    is chosen; otherwise the first one, and the note says so."""
    notes = []
    new = cmd
    if config_files:
        chosen = next((c for c in config_files if kit and kit.lower() in c.lower()), config_files[0])
        new, n = PLACEHOLDER_CONFIG.subn(chosen, new)
        if n:
            notes.append(f"'{cmd.split()[0]}' config placeholder resolved to {chosen}"
                         + (f" (matches the dataset's {kit} kit)." if kit and kit.lower() in chosen.lower()
                            else " (first configuration file in the repository; may not match the data)."))
    return new, notes


def rewrite_for_strhub(cmd: str, input_type: str | None, config_files: list[str] | None = None) -> tuple[str, list[str]]:
    """Point the README's command at STRhub's mounts. Returns (cmd, notes)."""
    ds = datasets_lib.resolve(input_type) if input_type else None
    notes: list[str] = []
    if not ds:
        return cmd, ["No STRhub reference dataset for the detected input type; the run "
                     "leg uses the command as documented."]
    canonical = ds.get("canonical_input")
    new, notes = resolve_placeholders(cmd, config_files or [], ds.get("kit"))
    if canonical:
        new, n = INPUT_TOKEN.subn(f"/data/in/{canonical}", new)
        n2 = 0
        if n == 0:
            new, n2 = PLACEHOLDER_INPUT.subn(f"/data/in/{canonical}", new)
        if n or n2:
            notes.append(f"{n or n2} input {'path' if n else 'placeholder'}(s) in the README command "
                         f"replaced with /data/in/{canonical}.")
    if ds.get("reference_genome"):
        mount = ds["reference_genome"].get("mount_path", "/data/ref/hg38.fa")
        new, n = REF_TOKEN.subn(mount, new)
        if n:
            notes.append(f"{n} reference FASTA path(s) replaced with {mount}.")
    if input_type in REQUIRES_REGIONS or ds.get("supported_loci"):
        new, n = BED_TOKEN.subn("/data/in/regions.bed", new)
        if n:
            notes.append(f"{n} BED path(s) replaced with /data/in/regions.bed.")
    return new, notes


def build(proposal: dict, slug: str, submitted_by: str = "third_party") -> dict:
    """Return {"manifest": dict, "manifest_yml": str, "dockerfile": str,
    "limitations": [...], "readme_gaps": [...]}."""
    repo, ref = proposal["repo"], proposal["ref"]
    name = repo.rstrip("/").split("/")[-1]
    build_info = proposal.get("build") or {}
    commands = proposal.get("commands") or []
    input_type = (proposal.get("input_type") or {}).get("best")
    out_fmt = (proposal.get("output") or {}).get("format")
    from_repo = build_info.get("method") == "dockerfile"
    limitations: list[str] = []
    caveat_items: list[str] = []

    # --- environment
    if from_repo:
        dockerfile_text = (f"# The repository ships its own Dockerfile ({build_info['file']}); the engine\n"
                           "# builds that one with the repository at the pinned ref as context.\n")
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "repository",
               "from_repo": build_info["file"]}
        cwd = "."
        caveat_items.append(f"Environment: the repository's own {build_info['file']} was built as-is.")
    elif proposal.get("dockerfile"):
        dockerfile_text = proposal["dockerfile"]
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated"}
        cwd = "/opt/tool"
        caveat_items.append(f"Environment: generated by STRhub from the repository's "
                            f"{build_info.get('file') or 'install instructions'} ({build_info.get('method')}).")
    else:
        dockerfile_text = ("# No install method was detected; a bare image so the trial can report\n"
                           "# the documentation gap rather than a build error of STRhub's making.\n"
                           "FROM ubuntu:22.04\nRUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates "
                           "&& rm -rf /var/lib/apt/lists/*\n"
                           f"ARG TOOL_REF={ref}\nWORKDIR /opt\nRUN git clone https://github.com/{repo.split('github.com/')[-1]}.git tool "
                           "&& cd tool && git checkout \"${TOOL_REF}\"\nWORKDIR /opt/tool\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n")
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated"}
        cwd = "/opt/tool"
        limitations.append("install_method_unknown")

    # --- the command
    best = commands[0]["cmd"] if commands else ""
    if not best:
        limitations.append("no_command")
        run_cmd = "true  # no command found in the README; nothing to run"
    else:
        rewritten, notes = rewrite_for_strhub(best, input_type, proposal.get("config_files"))
        caveat_items += notes
        run_cmd = example_wrapper(rewritten, cwd)
        caveat_items.append("Run command: the README's own command, rewritten to STRhub's mounts; "
                            "everything it created was captured as output.")
    if input_type in REQUIRES_REGIONS:
        limitations.append("regions_format_unknown")
        caveat_items.append("This input type needs a regions BED in the tool's own format; none was "
                            "generated, so the STRhub-data leg may find no loci. The tool's own example "
                            "leg does not depend on it.")

    # --- outputs
    glob, fmt = OUTPUT_GLOB.get(out_fmt or "", ("**/*", "text"))
    outputs = [{"path": glob, "format": fmt, "min_records": 1}]

    manifest = {
        "tool": {"name": name, "version": ref[:7], "contact": f"{repo.rstrip('/')}/issues"},
        "submission": {"by": submitted_by},
        "source": {"repo": repo, "ref": ref},
        "report": {"slug": slug},
        "environment": env,
        "run": {"cmd": run_cmd, "timeout_minutes": 20},
        "inputs": {"type": input_type} if input_type else {},
        "outputs": outputs,
    }
    ex = proposal.get("example")
    if ex and ex.get("cmd"):
        manifest["example"] = {"cmd": ex["cmd"], "cwd": cwd, "source": "detected"}
    warnings = (proposal.get("input_type") or {}).get("warnings") or []
    caveat_items += warnings
    if caveat_items:
        manifest["caveats"] = {"source": "detect_recipe", "items": [c[:300] for c in caveat_items[:8]]}

    header = ("# STRhub Verified trial recipe, PROPOSED from the repository by detect_recipe.\n"
              "# Nobody typed this: every choice is listed under `caveats`. A trial report\n"
              "# built from it says so, and is never published as an attestation.\n")
    return {
        "manifest": manifest,
        "manifest_yml": header + yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=1000),
        "dockerfile": dockerfile_text,
        "limitations": limitations,
        "readme_gaps": (proposal.get("readme") or {}).get("gaps", []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal", help="detect_recipe.py --json output")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--submitted-by", default="third_party", choices=["maintainer", "third_party"])
    ap.add_argument("--out-dir", default="", help="also write manifest.yml + Dockerfile here")
    ap.add_argument("--recipe-b64-out", default="", help="write the base64 recipe (prepare --recipe-b64) here")
    args = ap.parse_args()
    proposal = json.loads(pathlib.Path(args.proposal).read_text())
    r = build(proposal, args.slug, args.submitted_by)
    # The limitations travel back into the proposal file so the report's verdict
    # can read them alongside the README gaps.
    proposal["limitations"] = r["limitations"]
    pathlib.Path(args.proposal).write_text(json.dumps(proposal, indent=2))
    if args.out_dir:
        d = pathlib.Path(args.out_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.yml").write_text(r["manifest_yml"])
        (d / "Dockerfile").write_text(r["dockerfile"])
    if args.recipe_b64_out:
        recipe = {"manifest_yml": r["manifest_yml"], "dockerfile": r["dockerfile"]}
        pathlib.Path(args.recipe_b64_out).write_text(base64.b64encode(json.dumps(recipe).encode()).decode())
    print(json.dumps({"slug": args.slug, "limitations": r["limitations"],
                      "example": bool(r["manifest"].get("example")),
                      "input_type": r["manifest"].get("inputs", {}).get("type")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
