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
      [--submitted-by third_party] [--out-dir work/proposal]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import datasets as datasets_lib  # noqa: E402
import _manifest  # noqa: E402
from prepare import example_wrapper  # noqa: E402

OUTPUT_GLOB = {
    "vcf": ("**/*.vcf*", "vcf"),
    "tsv": ("**/*.t[sx][vt]", "tsv"),   # .tsv and .txt
    "csv": ("**/*.csv", "csv"),
    "json": ("**/*.json", "json"),
}

def resolve_placeholders(cmd: str, config_files: list[str], kit: str | None) -> tuple[str, list[str]]:
    """No implicit config selection from a kit name or a repository listing."""
    return cmd, []


def normalize_documented(cmd: str, input_type: str | None, tree_paths: list[str] | None,
                         canonical: str | None, ref_mount: str | None,
                         has_regions: bool, binary_elsewhere: bool = False,
                         catalog_from_library: bool = False) -> tuple[str, list[str]]:
    """Retained API: normalization cannot invent a runnable command."""
    return cmd, []


def from_the_path(cmd: str, tree: set[str], binary_elsewhere: bool) -> tuple[str, list[str]]:
    """Executable paths are part of the cited procedure, never rewritten."""
    return cmd, []


BINARY_ELSEWHERE = set()


def rewrite_for_strhub(cmd: str, input_type: str | None, config_files: list[str] | None = None,
                       tree_paths: list[str] | None = None, build_method: str | None = None,
                       docs_text: str = "", library_format: str | None = None) -> tuple[str, list[str]]:
    """Apply only the closed, independently checked substitution profile."""
    import fidelity
    review = fidelity.rewrite(cmd, input_type)
    notes = [f"{item['role']}: {item['original']} -> {item['replacement']}."
             for item in review['substitutions']]
    notes += [f"Evaluator limitation: {item}." for item in review['limitations']]
    return review['command'], notes


TYPE_SLUG_SUFFIX = {
    "illumina-bam-hg38": "",
    "illumina-str-fastq": "",
    "illumina-bam-hg38-y": "y",
    "ont-bam-hg38": "ont",
    "ont-bam-hg38-med": "ont-med",
    "ont-fastq": "ont",
    "pacbio-hifi-bam-hg38": "hifi",
    "illumina-bam-hg38-med": "med",
    "pacbio-hifi-bam-hg38-med": "hifi-med",
    "illumina-snp-fastq": "snp",
    "capillary-fsa": "fsa",
}


def catalogue_slug(name: str, input_type: str | None) -> str:
    """The slug a trial from a URL is filed under if it is published.

    One card per tool and assay, whose version moves as releases do: the
    name, and a suffix only for a non-canonical input type. No version and
    no commit — `hipstr-v0-7` would have lied the day v0.8 was verified, or
    spawned a second card. The committed entries under tools/ follow the same
    rule, so a trial of a tool that is already listed lands on its card and
    refreshes it rather than opening another.
    """
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    suffix = ""
    if input_type:
        mapped = TYPE_SLUG_SUFFIX.get(input_type)
        suffix = mapped if mapped is not None else input_type.split("-")[-1]
    return (f"{base}-{suffix}" if suffix else base) or "tool"


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


def build(proposal: dict, slug: str, submitted_by: str = "third_party",
          ref_label: str = "") -> dict:
    """Return {"manifest": dict, "manifest_yml": str, "dockerfile": str,
    "limitations": [...], "readme_gaps": [...]}.

    `slug` names the run (the artifact, the working directories); the
    manifest's report.slug is the catalogue slug derived below, which is
    where the result is filed if it is published. `ref_label` is the tag or
    release the ref was resolved from, when there was one: that is the version
    a person cites, and the report shows it large; a bare commit shows its
    short SHA.
    """
    repo, ref = proposal["repo"], proposal["ref"]
    name = tool_name_as_written(repo, proposal)
    build_info = proposal.get("build") or {}
    commands = proposal.get("commands") or []
    input_type = (proposal.get("input_type") or {}).get("best")
    out_fmt = (proposal.get("output") or {}).get("format")
    limitations: list[str] = []
    it = proposal.get("input_type") or {}
    stmts = it.get("statements") or {}
    # The input caveat quotes what the README says and states what this run
    # did. Nothing in it is inferred: the kinds, the recommendation and the
    # lines come from read_input_statements, and when nothing was there to
    # read the caveat says the type was guessed — which is a limitation the
    # verdict weighs, not a fact about the tool.
    input_note = None
    if input_type:
        if it.get("how") == "command" and commands:
            top = commands[0]
            kind = "BAM" if "bam" in input_type else "FASTQ"
            input_note = (f"Input: the documented command takes {kind} ({top.get('file') or 'README.md'}, "
                          f"line {top.get('line')}); no sentence says so, so the command is what was read. "
                          f"This plan selects STRhub's {input_type} reference data.")
        elif it.get("how") == "read":
            docs = stmts.get("inputs") or []
            kinds = " and ".join(i["kind"].upper() for i in docs)
            line = docs[0]["line"] if docs else None
            input_note = (f"Input: the README documents {kinds}"
                          + (f" (line {line})" if line else "")
                          + f"; this plan selects STRhub's {input_type} reference data.")
            rec = stmts.get("recommendation")
            if rec:
                quote = re.sub(r"[*_`]+", "", rec["text"])[:90]
                input_note += (f" The author recommends {rec['kind'].upper()} "
                               f"(line {rec['line']}: \"{quote}\").")
        else:
            input_note = (f"Input: no sentence in the README says what the tool takes; "
                          f"{input_type} is only a guess from mentions; it is not authorization to execute.")
            limitations.append("input_type_guessed")
    from_repo = build_info.get("method") == "dockerfile"
    caveat_items: list[str] = []
    import source_install
    source_plan = source_install.discover(proposal) if not from_repo else {"ready": False}

    # --- environment
    if from_repo:
        dockerfile_text = (f"# The repository ships its own Dockerfile ({build_info['file']}); the engine\n"
                           "# builds that one with the repository at the pinned ref as context.\n")
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "repository",
               "from_repo": build_info["file"]}
        cwd = "."
        caveat = f"Environment: the repository's own {build_info['file']} is selected as-is, subject to the evidence check."
        caveat_items.append(caveat)
    elif source_plan["ready"]:
        # One generic transcript: no tool names, prior results or package guesses.
        dockerfile_text = source_plan["carrier_dockerfile"]
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "documented"}
        cwd = "."
        caveat_items.append("Environment: a fixed evaluator carrier transcribes the single complete cited installation block unchanged; its operating system is explicitly named by that block's heading.")
    else:
        # Non-runnable: never infer dependencies, interpreters or library paths.
        dockerfile_text = "# Installation profile not established; must not be built.\nFROM scratch\n"
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated"}
        cwd = "/opt/tool"
        limitations.append("install_method_unknown" if build_info.get("method") == "unknown"
                           else "install_profile_unsupported")
        caveat_items.append("Environment: no proven installation profile; STRhub did not manufacture installation steps.")

    # --- the command
    best = commands[0]["cmd"] if commands else ""
    if input_note:
        caveat_items.append(input_note)
    if not best:
        limitations.append("no_command")
        run_cmd = "true  # no command found in the README; nothing to run"
    else:
        rewritten, notes = rewrite_for_strhub(best, input_type)
        pre = commands[0].get("prerequisite")
        if pre:
            notes.append("Evaluator limitation: a possible prerequisite was discovered but was not automatically chained.")
        caveat_items += notes
        run_cmd = example_wrapper(rewritten, cwd)
        top = commands[0]
        if top.get("origin", "readme") == "readme":
            caveat_items.append("Run command: the README's own command, rewritten to STRhub's mounts; "
                                "the capture wrapper is planned only if the procedure review passes.")
        elif top.get("origin") == "wiki":
            caveat_items.append(f"Run command: the one documented on the wiki ({top['file']}, line {top['line']}), "
                                "rewritten to STRhub's mounts; the capture wrapper is planned only if the procedure review passes. "
                                "A wiki is not versioned with the code: it was read as it is today.")
        else:
            caveat_items.append(f"Run command: the one documented in {top['file']} (line {top['line']}), "
                                "rewritten to STRhub's mounts; the capture wrapper is planned only if the procedure review passes.")
    if best and input_type and datasets_lib.resolve(input_type):
        limitations += check_documented_files(run_cmd, proposal, input_type, caveat_items)
    # --- outputs
    glob, fmt = OUTPUT_GLOB.get(out_fmt or "", ("**/*", "text"))
    outputs = [{"path": glob, "format": fmt, "min_records": 1}]

    # A label that is just the SHA again (the form passes the resolved ref
    # through when nothing better was found) is not a version.
    version = ref_label.strip() if ref_label and not ref.startswith(ref_label.strip()) else ref[:7]
    manifest = {
        "tool": {"name": name, "version": version, "contact": f"{repo.rstrip('/')}/issues"},
        "submission": {"by": submitted_by},
        "source": {"repo": repo, "ref": ref},
        # Discovery origin only. Eligibility requires the pinned procedure
        # review; this label does not establish documented execution.
        "recipe": {"origin": "proposed"},
        "report": {"slug": catalogue_slug(name, input_type)},
        "environment": env,
        "run": {"cmd": run_cmd, "timeout_minutes": 20},
        "inputs": {"type": input_type} if input_type else {},
        "outputs": outputs,
    }
    ex = proposal.get("example")
    if ex and ex.get("cmd"):
        ex_cmd, ex_notes = from_the_path(ex["cmd"], set(proposal.get("tree_paths") or []),
                                         build_info.get("method") in BINARY_ELSEWHERE)
        ex_cwd = "." if from_repo else (ex.get("cwd") or cwd)
        manifest["example"] = {"cmd": ex_cmd, "cwd": ex_cwd, "source": "detected"}
        caveat_items += [f"Example: {n}" for n in ex_notes]
    # Nothing to run on at all: no STRhub data for the input type and no
    # example in the repository. Every run leg is then N/A, and a verdict read
    # off the gates would call that "fails" — it is nothing of the kind.
    if not (input_type and datasets_lib.resolve(input_type)) and not ex:
        limitations.append("no_reference_dataset")
    warnings = (proposal.get("input_type") or {}).get("warnings") or []
    caveat_items += warnings
    if caveat_items:
        manifest["caveats"] = {"source": "detect_recipe", "items": [c[:300] for c in caveat_items[:8]]}
    # Not a manifest field: the schema rejects anything it does not name, and
    # this is a review of the proposal, not a step the container runs.
    import authorization
    reviewed = authorization.prepare_review(proposal, manifest, limitations, caveat_items)

    header = ("# STRhub Verified candidate, proposed by detect_recipe.\n"
              "# Requires pinned upstream evidence and a strict procedure review.\n"
              "# An origin label is not proof; unsupported procedures must not run.\n")
    return {
        "manifest": manifest,
        "manifest_yml": header + yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=1000),
        "dockerfile": dockerfile_text,
        "limitations": limitations,
        "readme_gaps": (proposal.get("readme") or {}).get("gaps", []),
        "procedure": reviewed,
    }


#: Flags whose value is a file the tool READS (a reference, a catalog, a
#: motif list, a model), as opposed to one it writes.
INPUT_FILE_FLAG = re.compile(r"^--?(?:r|ref|reference|genome|motifs?|catalog|variant[-_]catalog|loci|regions?|"
                             r"repeats?|db|database|model|library|lib|config|conf|in|input|i|b|bams?|bed|"
                             r"annotation|table|rmsk|microsat)$", re.I)
LOCI_KEYWORD_FLAG = re.compile(r"^--?(?:loci|regions?|repeats?|catalog|variant[-_]catalog|targets?)$", re.I)
DATA_FILE = re.compile(r"\.(?:tsv|txt|json|bed|csv|pa|model|pkl|tab|gz|ini|cfg|conf|config|fa|fasta)$", re.I)


def _panel_windows(input_type: str) -> list[tuple[str, int, int]]:
    ds = datasets_lib.resolve(input_type) or {}
    rel = ds.get("supported_loci")
    path = datasets_lib.ROOT / rel if rel else None
    if not path or not path.is_file():
        return []
    out = []
    for ln in path.read_text().splitlines():
        f = ln.split("\t")
        if len(f) >= 3 and not ln.startswith("#"):
            out.append((f[0], int(f[1]), int(f[2])))
    return out


def check_documented_files(run_cmd: str, proposal: dict, input_type: str,
                           caveats: list[str]) -> list[str]:
    """What the documented command reads that the run cannot give it.

    Two things make a run say nothing about the tool, and both are knowable
    before running: the loci it genotypes, from a file the repository ships,
    lie outside STRhub's sample (ExpansionHunter's catalog is 31 disease loci,
    none of them forensic); or it reads a file nobody holds, and STRhub has
    nothing in its place (vamos's Zenodo motif list was one, until STRhub
    wrote its panel in vamos's layout)."""
    from prepare import unwrap_example
    cmd, _ = unwrap_example(run_cmd)
    tree = set(proposal.get("tree_paths") or [])
    shipped = proposal.get("shipped_loci") or {}
    windows = _panel_windows(input_type)
    out: list[str] = []
    toks = cmd.split()
    for i, t in enumerate(toks):
        path = t.strip("'\"").lstrip("./")
        prev = toks[i - 1] if i else ""
        if path in shipped and windows:
            inside = any(c == w[0] and s < w[2] and e > w[1] for c, s, e in shipped[path] for w in windows)
            if not inside:
                caveats.append(f"Loci: {path}, which the command genotypes, lists {len(shipped[path])} "
                               "locus coordinate(s), none inside STRhub's reference sample.")
                out.append("loci_outside_panel")
        elif LOCI_KEYWORD_FLAG.match(prev) and not t.startswith(("/data/", "-")) and shipped and windows:
            matching = [sp for sp in shipped if path.lower() in sp.lower()] or list(shipped)
            coords = [pt for sp in matching for pt in shipped[sp]]
            if coords and not any(c == w[0] and s < w[2] and e > w[1] for c, s, e in coords for w in windows):
                caveats.append(f"Loci: {prev} {path} resolves to repository loci ({', '.join(matching[:2])}) "
                               f"with {len(coords)} coordinate(s), none inside STRhub's reference sample.")
                out.append("loci_outside_panel")
        if (INPUT_FILE_FLAG.match(prev) and DATA_FILE.search(path) and not t.startswith(("/data/", "-"))
                and path not in tree and "*" not in path):
            caveats.append(f"File: the documented command reads {t} (after {prev}), which is neither in "
                           "the repository nor among STRhub's data.")
            out.append("documented_file_missing")
        elif "=" in path and not path.startswith("-"):
            k, v = path.split("=", 1)
            v_clean = v.strip("'\"").lstrip("./")
            if (INPUT_FILE_FLAG.match(f"--{k.split('_')[-1]}") and DATA_FILE.search(v_clean)
                    and not v.startswith("/data/") and v_clean not in tree and "*" not in v_clean):
                caveats.append(f"File: the documented command reads {v} (in {t}), which is neither in "
                               "the repository nor among STRhub's data.")
                out.append("documented_file_missing")
    return list(dict.fromkeys(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal", help="detect_recipe.py --json output")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--submitted-by", default="third_party", choices=["maintainer", "third_party"])
    ap.add_argument("--ref-label", default="",
                    help="the tag or release the ref was resolved from, shown as the version")
    ap.add_argument("--out-dir", default="", help="also write manifest.yml + Dockerfile here")
    args = ap.parse_args()
    proposal = json.loads(pathlib.Path(args.proposal).read_text())
    r = build(proposal, args.slug, args.submitted_by, args.ref_label)
    _manifest.loads(r["manifest_yml"])
    # The limitations travel back into the proposal file so the report's verdict
    # can read them alongside the README gaps.
    proposal["limitations"] = r["limitations"]
    proposal["procedure"] = r["procedure"]
    pathlib.Path(args.proposal).write_text(json.dumps(proposal, indent=2))
    if args.out_dir:
        d = pathlib.Path(args.out_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.yml").write_text(r["manifest_yml"])
        (d / "Dockerfile").write_text(r["dockerfile"])
    print(json.dumps({"slug": args.slug, "catalogue_slug": r["manifest"]["report"]["slug"],
                      "limitations": r["limitations"],
                      "example": bool(r["manifest"].get("example")),
                      "input_type": r["manifest"].get("inputs", {}).get("type")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
