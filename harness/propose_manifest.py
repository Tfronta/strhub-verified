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


#: `<BAM/CRAM file with aligned reads>`: what a documented placeholder stands
#: for, read off its own words. Order matters: the first kind that matches wins.
ANGLE_KINDS = [
    ("input", re.compile(r"\b(?:bams?|crams?|fastqs?|fq|reads?|alignments?|aligned)\b", re.I)),
    ("reference", re.compile(r"\b(?:fasta|fa|reference(?! allele)|genome|ref)\b", re.I)),
    ("regions", re.compile(r"\b(?:bed|regions?|loci|locus|repeats?|targets?)\b", re.I)),
    ("catalog", re.compile(r"\b(?:catalog|catalogue|json)\b", re.I)),
    ("outdir", re.compile(r"\b(?:out(?:put)?[ _-]?dir(?:ectory)?|folder|directory|working[ _-]?path)\b", re.I)),
    ("output", re.compile(r"\b(?:out(?:put)?|prefix|vcf|result|report)\b", re.I)),
    ("threads", re.compile(r"\b(?:threads?|cpus?|cores?|processes|procs?|jobs)\b", re.I)),
    ("sample", re.compile(r"\b(?:sample|name|id)\b", re.I)),
]
EXCLUDE_FLAG = re.compile(r"--?[\w-]*(?:exclude|skip|blacklist|mask|ignore)[\w-]*$", re.I)


def _tree_file(tree_paths: list[str], want: re.Pattern) -> str | None:
    """A file the repository ships that matches `want`, hg38 first."""
    hits = [p for p in tree_paths if want.search(p)]
    hits.sort(key=lambda p: (not re.search(r"hg38|grch38|b38", p, re.I), p.count("/"), p))
    return hits[0] if hits else None


def normalize_documented(cmd: str, input_type: str | None, tree_paths: list[str] | None,
                         canonical: str | None, ref_mount: str | None,
                         has_regions: bool, binary_elsewhere: bool = False) -> tuple[str, list[str]]:
    """The parts of a documented command that are not a command yet: usage
    brackets, `<descriptions>`, `path/to/` stand-ins, `a.bam,...` lists and a
    `./tool` that the build put elsewhere. Every change is a note."""
    tree = set(tree_paths or [])
    notes: list[str] = []
    new = cmd.rstrip("\\ ").strip()
    # Optional arguments of a usage synopsis (`[--loci loci.bed]`), innermost
    # first: the documented minimum is what is run.
    if re.search(r"\[\s*-", new):
        before = new

        def optional(m: re.Match) -> str:
            inner = m.group(1)
            # The loci to genotype are optional only in the sense that
            # without them the tool scans the whole genome: straglr's
            # `[--loci loci.bed]` is its genotyping mode. Kept, when STRhub
            # holds a regions file to give it.
            if has_regions and re.search(r"--?(?:loci|regions?|bed|repeats?|targets?)\b", inner, re.I):
                return " " + inner.strip()
            return ""
        while True:
            nxt = re.sub(r"\s*\[([^\[\]]*)\]", optional, new)
            if nxt == new:
                break
            new = nxt
        if new != before:
            notes.append("Optional arguments of the documented usage ([...]) were left out, "
                         "except the loci to genotype.")
    # `x.bam,...` and `a.bam,b.bam,...`: a list of the same kind of file is one file here.
    new = re.sub(r"((?:[\w./<>-]+),(?:[\w./<>-]+,)*)\s*(?:\.\.\.|…)", lambda m: m.group(1).rstrip(","), new)
    new = re.sub(r"\s(?:\.\.\.|…)(?=\s|$)", "", new)
    # `$sample`, `${reference_fasta}`: shell variables standing in for the
    # user's files, as STRling's docs write them. A whole-token variable is
    # resolved by its name like a <description>; inside a file name it is the
    # sample's name.
    def shell_var(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        whole = m.group(0) == m.string[m.start():m.end()] and (
            (m.start() == 0 or m.string[m.start() - 1] in " =") and
            (m.end() == len(m.string) or m.string[m.end()] in " "))
        words = re.sub(r"[_\-]+", " ", name)
        kind = next((k for k, rx in ANGLE_KINDS if rx.search(words)), None)
        if whole and kind == "reference" and ref_mount:
            return ref_mount
        if whole and kind == "input" and canonical:
            return f"/data/in/{canonical}"
        if whole and kind == "outdir":
            return "strhub_out"
        if whole and kind == "threads":
            return "2"
        return "sample"
    if re.search(r"\$(?:\{\w+\}|[A-Za-z_]\w*)", new):
        new = re.sub(r"\$(?:\{(\w+)\}|([A-Za-z_]\w*))", shell_var, new)
        notes.append("Shell variables in the documented command ($sample, $reference_fasta, ...) "
                     "were filled in with STRhub's sample and mounts.")
    # `<description>` placeholders, resolved by what they describe.
    unresolved: list[str] = []

    def angle(m: re.Match) -> str:
        words = m.group(1)
        # The flag it follows says what it is (`--reference <file>`); another
        # placeholder before it says nothing about it.
        before = new[:m.start()].split()
        prev = before[-1] if before and before[-1].startswith("-") else ""
        text = re.sub(r"[_\-/.]+", " ", f"{prev} {words}")
        kind = next((k for k, rx in ANGLE_KINDS if rx.search(text)), None)
        if kind == "input" and canonical:
            return f"/data/in/{canonical}"
        if kind == "reference" and ref_mount:
            return ref_mount
        if kind == "regions" and has_regions:
            return "/data/in/regions.bed"
        if kind == "catalog":
            found = _tree_file(list(tree), re.compile(r"(?:catalog|catalogue)[^/]*\.json$", re.I))
            if found:
                notes.append(f"'<{words}>' resolved to {found}, shipped in the repository.")
                return found
        if kind == "outdir":
            return "strhub_out"
        if kind == "output":
            return "sample"
        if kind == "threads":
            return "2"
        if kind == "sample":
            return "sample"
        unresolved.append(words)
        return m.group(0)
    new = re.sub(r"<([^<>\n]{1,80})>", angle, new)
    if unresolved:
        notes.append("Placeholder(s) STRhub could not resolve: " + ", ".join(f"<{u}>" for u in unresolved) + ".")
    # `/path/to/Tool` and `path/to/samtools`: a program on the PATH. A data file
    # behind `path/to/` is left for the token rules below, and an option whose
    # file STRhub does not hold is dropped, and said.
    toks = new.split()
    out: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        m = re.match(r"^(?:\./)?/?(?:path/to|PATH/TO|your/path|/your/path)/(.+)$", t)
        if m:
            rest = m.group(1)
            base = rest.split("/")[-1]
            if "." not in base or base.endswith((".py", ".sh", ".pl")):
                out.append(base)
                i += 1
                continue
            if not re.search(r"\.(?:bam|cram|f(?:ast)?q|fa|fasta|fna|bed)(?:\.gz)?$", base, re.I):
                if out and out[-1].startswith("-"):
                    notes.append(f"Dropped {out[-1]} {t}: the documentation names that file only as a "
                                 "placeholder and STRhub holds no such file.")
                    out.pop()
                else:
                    notes.append(f"{t} is a placeholder STRhub could not resolve.")
                    out.append(t)
                i += 1
                continue
            out.append(rest)
            i += 1
            continue
        out.append(t)
        i += 1
    new = " ".join(out)
    # An exclusion list is not a regions file: pointing it at the panel would
    # exclude exactly the loci the run is for.
    toks = new.split()
    out = []
    i = 0
    while i < len(toks):
        if EXCLUDE_FLAG.match(toks[i]) and i + 1 < len(toks) and toks[i + 1].lower().endswith(".bed"):
            notes.append(f"Dropped {toks[i]} {toks[i + 1]}: an exclusion list STRhub does not hold.")
            i += 2
            continue
        out.append(toks[i])
        i += 1
    new = " ".join(out)
    new, more = from_the_path(new, tree, binary_elsewhere)
    notes += more
    # An output prefix inside a directory nobody made: STRling's
    # `--output-prefix str-results/$sample` stopped with "couldn't open output
    # file" because its docs run `mkdir -p str-results` a few lines earlier.
    dirs = []
    toks = new.split()
    for i, t in enumerate(toks[:-1]):
        if re.match(r"^--?(?:o|out|output|outdir|out[-_]?dir|output[-_]?dir|output[-_]?prefix|prefix|"
                    r"working[-_]?path|tr-vcf|str-vcf|vcf)$", t, re.I):
            val = toks[i + 1]
            d = val.rsplit("/", 1)[0] if "/" in val.strip("/") else ""
            if d and not val.startswith(("/", "-", "$")) and d not in (".", "..") and d not in dirs:
                dirs.append(d)
    if dirs:
        new = f"mkdir -p {' '.join(dirs)} && {new}"
        notes.append(f"The output directory the command writes into ({', '.join(dirs)}) was created first.")
    return new, notes


def from_the_path(cmd: str, tree: set[str], binary_elsewhere: bool) -> tuple[str, list[str]]:
    """`./trgt` where the build left trgt somewhere else: the same program, from
    the PATH. For the run leg and the example alike: TRGT's own example ran
    `./trgt` in the clone and failed with "No such file", a red that was ours."""
    m = re.match(r"^((?:\w+=\S+\s+)*)\./([\w.+-]+)(\s|$)", cmd)
    if m and binary_elsewhere and tree and m.group(2) not in tree:
        return (f"{m.group(1)}{m.group(2)}{cmd[m.end(2):]}",
                [f"'./{m.group(2)}' run as '{m.group(2)}' from the PATH: the build puts it there, "
                 "not in the directory the documentation runs it from."])
    return cmd, []


#: Build methods whose executables do not land where a README runs them from
#: (`./tool` in the clone): they are put on the PATH instead.
BINARY_ELSEWHERE = {"cargo", "cmake", "go", "autotools", "release_binary", "bioconda",
                    "docker_image", "pip", "make_subdir"}


def rewrite_for_strhub(cmd: str, input_type: str | None, config_files: list[str] | None = None,
                       tree_paths: list[str] | None = None, build_method: str | None = None,
                       docs_text: str = "") -> tuple[str, list[str]]:
    """Point the documented command at STRhub's mounts. Returns (cmd, notes)."""
    ds = datasets_lib.resolve(input_type) if input_type else None
    notes: list[str] = []
    if not ds:
        return cmd, ["No STRhub reference dataset for the detected input type; the run "
                     "leg uses the command as documented."]
    canonical = ds.get("canonical_input")
    ref_mount = (ds.get("reference_genome") or {}).get("mount_path", "/data/ref/hg38.fa") \
        if ds.get("reference_genome") else None
    has_regions = bool(ds.get("regions_library")) or input_type in REQUIRES_REGIONS
    cmd, notes0 = normalize_documented(cmd, input_type, tree_paths, canonical, ref_mount, has_regions,
                                       binary_elsewhere=build_method in BINARY_ELSEWHERE)
    # A reference BAM with no read group, and a tool that names samples by it
    # (HipSTR's family): its documented --bam-samps/--bam-libs name the sample
    # instead. The ONT slices carry no @RG; LongTR stops without one.
    if ds.get("read_groups") is False and docs_text and re.search(r"--bam-samps\b", docs_text) \
            and "--bam-samps" not in cmd:
        sm = ds.get("sample") or "sample"
        cmd = f"{cmd} --bam-samps {sm} --bam-libs {sm}"
        notes0.append(f"The reference BAM carries no read group, so the documented --bam-samps and "
                      f"--bam-libs options name its sample ({sm}).")
    new, notes = resolve_placeholders(cmd, config_files or [], ds.get("kit"))
    notes = notes0 + notes
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


# Which input types add a suffix to a catalogue slug. The autosomal Illumina
# BAM and the Illumina STR FASTQ are the canonical assays and add nothing; a
# Y-STR or a nanopore run is a different claim about the same tool and gets
# its own card. Unlisted types fall back to their last hyphen-segment. Kept
# in step with TYPE_SLUG_SUFFIX in strhub-web/lib/verified/submission.ts.
TYPE_SLUG_SUFFIX = {
    "illumina-bam-hg38": "",
    "illumina-str-fastq": "",
    "illumina-bam-hg38-y": "y",
    "ont-bam-hg38": "ont",
    "ont-fastq": "ont",
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
    # The README's first choice of input is not always one STRhub holds data
    # for: STRspy reads ONT FASTQ or BAM and names FASTQ first, and STRhub has
    # ONT reads only as hg38 BAM slices. A candidate with data beats the best
    # guess without any, since the alternative is a run that never starts.
    limitations: list[str] = []
    it = proposal.get("input_type") or {}
    stmts = it.get("statements") or {}
    input_type_asked = input_type
    if input_type and not datasets_lib.resolve(input_type):
        with_data = next((c for c in it.get("candidates", []) if datasets_lib.resolve(c)), None)
        if with_data:
            input_type = with_data
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
                          f"This run used STRhub's {input_type} reference data.")
        elif it.get("how") == "read":
            docs = stmts.get("inputs") or []
            kinds = " and ".join(i["kind"].upper() for i in docs)
            line = docs[0]["line"] if docs else None
            input_note = (f"Input: the README documents {kinds}"
                          + (f" (line {line})" if line else "")
                          + f"; this run used STRhub's {input_type} reference data.")
            rec = stmts.get("recommendation")
            if rec:
                quote = re.sub(r"[*_`]+", "", rec["text"])[:90]
                input_note += (f" The author recommends {rec['kind'].upper()} "
                               f"(line {rec['line']}: \"{quote}\").")
            if input_type_asked and input_type_asked != input_type:
                input_note += (f" STRhub holds no reference sample as {input_type_asked}, "
                               "so the other documented kind was used.")
        else:
            input_note = (f"Input: no sentence in the README says what the tool takes; "
                          f"{input_type} was tried on the strength of mentions alone.")
            limitations.append("input_type_guessed")
    from_repo = build_info.get("method") == "dockerfile"
    caveat_items: list[str] = []
    dockerfile_fallback_text: str | None = None

    # --- environment
    if from_repo:
        dockerfile_text = (f"# The repository ships its own Dockerfile ({build_info['file']}); the engine\n"
                           "# builds that one with the repository at the pinned ref as context.\n")
        env = {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "repository",
               "from_repo": build_info["file"]}
        cwd = "."
        caveat = f"Environment: the repository's own {build_info['file']} was built as-is."
        fb = build_info.get("fallback") or {}
        if fb and proposal.get("dockerfile_fallback"):
            what = published_environment(fb)
            env["fallback"] = {"dockerfile": "Dockerfile.fallback", "reason": what}
            dockerfile_fallback_text = proposal["dockerfile_fallback"]
            caveat += f" If it does not build, {what} stands in, and the report says so."
        caveat_items.append(caveat)
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

    ssh = build_info.get("ssh_urls_in") or []
    if ssh and not from_repo:
        # Disclosed as what it is: a change to the environment, not to the
        # tool, and a finding for the author at the same time.
        caveat_items.append(f"Environment: {', '.join(ssh[:2])} fetch dependencies over SSH (git@github.com:), "
                            "which needs a GitHub SSH key; STRhub's build fetched them over HTTPS instead.")
    # --- the command
    best = commands[0]["cmd"] if commands else ""
    if input_note:
        caveat_items.append(input_note)
    if not best:
        limitations.append("no_command")
        run_cmd = "true  # no command found in the README; nothing to run"
    else:
        rewritten, notes = rewrite_for_strhub(best, input_type, proposal.get("config_files"),
                                              proposal.get("tree_paths"), build_info.get("method"),
                                              proposal.get("readme_text", ""))
        pre = commands[0].get("prerequisite")
        if pre:
            # The documented step that writes what this command reads runs
            # first, rewritten the same way, and the run stops if it fails.
            pre_cmd, pre_notes = rewrite_for_strhub(pre["cmd"], input_type, proposal.get("config_files"),
                                                    proposal.get("tree_paths"), build_info.get("method"),
                                                    proposal.get("readme_text", ""))
            rewritten = f"{pre_cmd} && {rewritten}"
            notes = [n for n in pre_notes if n not in notes] + notes
            notes.append(f"The documented step before it ({pre['file']}, line {pre['line']}) runs first: "
                         f"it writes {pre['writes']}, which the command reads.")
        caveat_items += notes
        run_cmd = example_wrapper(rewritten, cwd)
        top = commands[0]
        if top.get("origin", "readme") == "readme":
            caveat_items.append("Run command: the README's own command, rewritten to STRhub's mounts; "
                                "everything it created was captured as output.")
        elif top.get("origin") == "wiki":
            caveat_items.append(f"Run command: the one documented on the wiki ({top['file']}, line {top['line']}), "
                                "rewritten to STRhub's mounts; everything it created was captured as output. "
                                "A wiki is not versioned with the code: it was read as it is today.")
        else:
            caveat_items.append(f"Run command: the one documented in {top['file']} (line {top['line']}), "
                                "rewritten to STRhub's mounts; everything it created was captured as output.")
    if best and input_type and datasets_lib.resolve(input_type):
        limitations += check_documented_files(run_cmd, proposal, input_type, caveat_items)
    regions_block = None
    takes_regions = "/data/in/regions.bed" in run_cmd
    if input_type in REQUIRES_REGIONS or (takes_regions and datasets_lib.resolve(input_type or "")
                                          and (datasets_lib.resolve(input_type) or {}).get("regions_library")):
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
            # Whose knowledge picked the layout, said out loud. "The tool is
            # known to read this format" put STRhub's own lookup table in the
            # voice of a fact about somebody's software: nobody read the
            # repository to establish it, which is how the STRspy sentence
            # happened. The table is a fine basis — it just has to be named.
            basis = {
                "tool": f"STRhub records the {fmt} layout for a program of this name",
                "readme": "the layout the README describes",
                "fallback": f"STRhub records no layout for this program, so plain "
                            f"chrom/start/end/name was tried",
            }[how]
            caveat_items.append(
                f"Regions: STRhub's ready-made {fmt} file for the dataset's panel loci ({basis}).")

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
        # Read off the repository, so it may stand behind the badge; a recipe
        # somebody wrote by hand may not (docs/PLAN-Documented-Is-The-Badge.md).
        "recipe": {"origin": "proposed"},
        "report": {"slug": catalogue_slug(name, input_type)},
        "environment": env,
        "run": {"cmd": run_cmd, "timeout_minutes": 20},
        "inputs": ({"type": input_type, **({"regions": regions_block} if regions_block else {})}
                   if input_type else {}),
        "outputs": outputs,
    }
    ex = proposal.get("example")
    if ex and ex.get("cmd"):
        ex_cmd, ex_notes = from_the_path(ex["cmd"], set(proposal.get("tree_paths") or []),
                                         build_info.get("method") in BINARY_ELSEWHERE)
        manifest["example"] = {"cmd": ex_cmd, "cwd": cwd, "source": "detected"}
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

    header = ("# STRhub Verified recipe, PROPOSED from the repository by detect_recipe.\n"
              "# Nobody typed this: every choice is listed under `caveats`, and the report\n"
              "# says so. It is published only if the run's verdict is attributable to the\n"
              "# tool (runs or fails); a verdict that is STRhub's limitation never is.\n")
    return {
        "manifest": manifest,
        "manifest_yml": header + yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=1000),
        "dockerfile": dockerfile_text,
        "dockerfile_fallback": dockerfile_fallback_text,
        "limitations": limitations,
        "readme_gaps": (proposal.get("readme") or {}).get("gaps", []),
    }


#: Flags whose value is a file the tool READS (a reference, a catalog, a
#: motif list, a model), as opposed to one it writes.
INPUT_FILE_FLAG = re.compile(r"^--?(?:r|ref|reference|genome|motifs?|catalog|variant[-_]catalog|loci|regions?|"
                             r"repeats?|db|database|model|library|lib|config|conf|in|input|i|b|bams?|bed|"
                             r"annotation|table|rmsk|microsat)$", re.I)
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
    none of them forensic); or it reads a file nobody holds (vamos's motif
    list, which its README says to download from Zenodo)."""
    from prepare import unwrap_example
    cmd, _ = unwrap_example(run_cmd)
    tree = set(proposal.get("tree_paths") or [])
    shipped = proposal.get("shipped_loci") or {}
    windows = _panel_windows(input_type)
    out: list[str] = []
    toks = cmd.split()
    for i, t in enumerate(toks):
        path = t.strip("'\"").lstrip("./")
        if path in shipped and windows:
            inside = any(c == w[0] and s < w[2] and e > w[1] for c, s, e in shipped[path] for w in windows)
            if not inside:
                caveats.append(f"Loci: {path}, which the command genotypes, lists {len(shipped[path])} "
                               "locus coordinate(s), none inside STRhub's reference sample.")
                out.append("loci_outside_panel")
        prev = toks[i - 1] if i else ""
        if (INPUT_FILE_FLAG.match(prev) and DATA_FILE.search(path) and not t.startswith(("/data/", "-"))
                and path not in tree and "*" not in path):
            caveats.append(f"File: the documented command reads {t} (after {prev}), which is neither in "
                           "the repository nor among STRhub's data.")
            out.append("documented_file_missing")
    return list(dict.fromkeys(out))


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
    ap.add_argument("--ref-label", default="",
                    help="the tag or release the ref was resolved from, shown as the version")
    ap.add_argument("--out-dir", default="", help="also write manifest.yml + Dockerfile here")
    ap.add_argument("--recipe-b64-out", default="", help="write the base64 recipe (prepare --recipe-b64) here")
    args = ap.parse_args()
    proposal = json.loads(pathlib.Path(args.proposal).read_text())
    r = build(proposal, args.slug, args.submitted_by, args.ref_label)
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
    print(json.dumps({"slug": args.slug, "catalogue_slug": r["manifest"]["report"]["slug"],
                      "limitations": r["limitations"],
                      "example": bool(r["manifest"].get("example")),
                      "input_type": r["manifest"].get("inputs", {}).get("type")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
