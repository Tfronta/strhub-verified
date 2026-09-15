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
import regions_library  # noqa: E402
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
        # `--bams run1.bam,run2.bam,run3.bam,run4.bam` is a README showing the
        # flag takes a list; four copies of the same file is not what anyone
        # means, and HipSTR refuses it. One list becomes one file.
        new = re.sub(r"((?:[\w./-]+\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?)(?:,[\w./-]+\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?)+)",
                     lambda m: m.group(1).split(",")[0], new, flags=re.I)
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


def tool_name_as_written(repo: str, proposal: dict) -> str:
    """The repository's own spelling of its name.

    A GitHub path is case-flattened by its owner as often as not
    (`unique379r/strspy`), and a report that renders that is naming the
    project something nobody calls it. The same word usually appears
    correctly cased in the README prose and in the repository's own file
    names; the most frequent such spelling wins, and the path segment is the
    fallback.
    """
    segment = repo.rstrip("/").split("/")[-1]
    pattern = re.compile(re.escape(segment), re.I)
    haystack = proposal.get("readme_text", "") + "\n" + "\n".join(proposal.get("tool_names") or [])
    counts: dict[str, int] = {}
    for m in pattern.finditer(haystack):
        counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    if not counts:
        return segment
    # Ties go to the spelling that is not all-lowercase: "STRspy" over "strspy"
    # when a README uses both, since the flat one is what a URL forces.
    return max(counts, key=lambda w: (counts[w], w != w.lower()))


def build(proposal: dict, slug: str, submitted_by: str = "third_party") -> dict:
    """Return {"manifest": dict, "manifest_yml": str, "dockerfile": str,
    "limitations": [...], "readme_gaps": [...]}."""
    repo, ref = proposal["repo"], proposal["ref"]
    name = tool_name_as_written(repo, proposal)
    build_info = proposal.get("build") or {}
    commands = proposal.get("commands") or []
    input_type = (proposal.get("input_type") or {}).get("best")
    out_fmt = (proposal.get("output") or {}).get("format")
    # The README's first choice of input is not always one STRhub holds data
    # for: STRspy reads ONT FASTQ or BAM and names FASTQ first, and STRhub has
    # ONT reads only as hg38 BAM slices. A candidate with data beats the best
    # guess without any, since the alternative is a run that never starts.
    input_note = None
    if input_type and not datasets_lib.resolve(input_type):
        with_data = next((c for c in (proposal.get("input_type") or {}).get("candidates", [])
                          if datasets_lib.resolve(c)), None)
        if with_data:
            input_note = (f"Input: the README suggests {input_type} first; STRhub has reference "
                          f"data only as {with_data}, which is what the run uses.")
            input_type = with_data
    from_repo = build_info.get("method") == "dockerfile"
    limitations: list[str] = []
    caveat_items: list[str] = []
    dockerfile_fallback_text: str | None = None

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
        if build_info.get("method") == "docker_image":
            caveat_items.append(f"Environment: the published image {build_info.get('image')} the README points "
                                "at; the tool inside it is whatever that image holds, not necessarily the pinned commit.")
        elif build_info.get("method") == "bioconda":
            caveat_items.append(f"Environment: the Bioconda package '{build_info.get('package')}' the README installs; "
                                "its version is the package's, not necessarily the pinned commit.")
        else:
            caveat = (f"Environment: generated by STRhub from the repository's "
                      f"{build_info.get('file') or 'install instructions'} ({build_info.get('method')}), "
                      "at the pinned commit.")
            # Plan B. The pinned commit is what the report names, so it is
            # what gets built first; the published environment the README
            # points at only stands in if that build fails, and the report
            # says which one ran.
            fb = build_info.get("fallback") or {}
            if fb and proposal.get("dockerfile_fallback"):
                what = published_environment(fb)
                env["fallback"] = {"dockerfile": "Dockerfile.fallback", "reason": what}
                dockerfile_fallback_text = proposal["dockerfile_fallback"]
                caveat += f" If that build fails, {what} stands in, and the report says so."
            caveat_items.append(caveat)
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
    if input_note:
        caveat_items.append(input_note)
    if not best:
        limitations.append("no_command")
        run_cmd = "true  # no command found in the README; nothing to run"
    else:
        rewritten, notes = rewrite_for_strhub(best, input_type, proposal.get("config_files"))
        caveat_items += notes
        run_cmd = example_wrapper(rewritten, cwd)
        caveat_items.append("Run command: the README's own command, rewritten to STRhub's mounts; "
                            "everything it created was captured as output.")
    regions_block = None
    if input_type in REQUIRES_REGIONS:
        # The tool needs a regions file. Pick the library format the tool is
        # known to read; failing that, plain BED, flagged so a failed run is
        # read as "the guess may be wrong", never as the tool's fault.
        fmt, how = regions_library.format_for_tool(name, best, proposal.get("readme_text", ""))
        if fmt is None:
            fmt, how = "bed4", "fallback"
            limitations.append("regions_format_guessed")
        if regions_library.library_path(input_type, fmt) is None:
            limitations.append("regions_format_unknown")
        else:
            regions_block = {"library": fmt}
            caveat_items.append(
                f"Regions: STRhub's ready-made {fmt} file for the dataset's panel loci"
                + (" (the tool is known to read this format)." if how == "tool"
                   else " (chosen from the README)." if how == "readme"
                   else " (no known format for this tool; plain chrom/start/end/name was tried)."))

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
        "inputs": ({"type": input_type, **({"regions": regions_block} if regions_block else {})}
                   if input_type else {}),
        "outputs": outputs,
    }
    ex = proposal.get("example")
    if ex and ex.get("cmd"):
        manifest["example"] = {"cmd": ex["cmd"], "cwd": cwd, "source": "detected"}
    # Nothing to run on at all: no STRhub data for the input type and no
    # example in the repository. Every run leg is then N/A, and a verdict read
    # off the gates would call that "fails" — it is nothing of the kind.
    if not (input_type and datasets_lib.resolve(input_type)) and not ex:
        limitations.append("no_reference_dataset")
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
        "dockerfile_fallback": dockerfile_fallback_text,
        "limitations": limitations,
        "readme_gaps": (proposal.get("readme") or {}).get("gaps", []),
    }


def published_environment(fallback: dict) -> str:
    """How the report names a plan-B environment: what it is and where the
    README points."""
    if fallback.get("method") == "docker_image":
        return f"the published image {fallback.get('image')} the README points at"
    if fallback.get("method") == "bioconda":
        return f"the Bioconda package '{fallback.get('package')}' the README installs"
    return "the published environment the README points at"


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
        if r["dockerfile_fallback"]:
            (d / "Dockerfile.fallback").write_text(r["dockerfile_fallback"])
    if args.recipe_b64_out:
        recipe = {"manifest_yml": r["manifest_yml"], "dockerfile": r["dockerfile"]}
        if r["dockerfile_fallback"]:
            recipe["dockerfile_fallback"] = r["dockerfile_fallback"]
        pathlib.Path(args.recipe_b64_out).write_text(base64.b64encode(json.dumps(recipe).encode()).decode())
    print(json.dumps({"slug": args.slug, "limitations": r["limitations"],
                      "example": bool(r["manifest"].get("example")),
                      "input_type": r["manifest"].get("inputs", {}).get("type")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
