"""Propose a verification recipe from a public repository, deterministically.

This is the first step of a trial: what a careful stranger would work out from
the repository alone, before running anything. It reads the file tree and the
README at the pinned ref and answers, with the evidence for each answer:

  build        how the tool is installed (Dockerfile in the repo, conda env,
               pip, make/cmake, cargo, go, or "unknown")
  example_data test inputs shipped in the repository, by kind
  commands     command lines quoted in the README that invoke the tool
  input_type   which STRhub reference dataset the tool most likely takes
  output       the output format the README describes
  readme.gaps  what the README does NOT say, of the things a stranger needs

Nothing here is a judgement about the tool. A gap is a fact about the
documentation, reported so the trial can say "could not determine how to run
this" with the list of what was missing, instead of failing silently. The
model-backed autoconfig fills in what this cannot; this runs first, costs
nothing, and is testable offline against the snapshots in testdata/repos/.

Usage:
  python harness/detect_recipe.py <repo-url> <ref> [--json out.json]
  python harness/detect_recipe.py --offline harness/testdata/repos/hipstr
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

RAW = "https://raw.githubusercontent.com"
API = "https://api.github.com"

README_NAMES = ["README.md", "readme.md", "README.MD", "Readme.md", "README.rst",
                "README.txt", "README"]

# --- build detection ---------------------------------------------------------
# (path, method). First match wins within a tier; tiers are ordered so a
# repository that ships a Dockerfile is built with it, and one that ships a
# conda environment gets conda before pip is considered.
BUILD_FILES = [
    ("Dockerfile", "dockerfile"),
    ("docker/Dockerfile", "dockerfile"),
    ("environment.yml", "conda"),
    ("environment.yaml", "conda"),
    ("pyproject.toml", "pip"),
    ("setup.py", "pip"),
    ("requirements.txt", "pip"),
    ("CMakeLists.txt", "cmake"),
    ("Makefile", "make"),
    ("makefile", "make"),
    ("Cargo.toml", "cargo"),
    ("go.mod", "go"),
    ("package.json", "node"),
]

# --- example data ------------------------------------------------------------
DATA_EXT = {
    "fastq": (".fastq", ".fq", ".fastq.gz", ".fq.gz"),
    "bam": (".bam", ".cram"),
    "vcf": (".vcf", ".vcf.gz"),
    "fasta": (".fa", ".fasta", ".fa.gz", ".fasta.gz"),
    "bed": (".bed",),
    "fsa": (".fsa", ".hid"),
}
DATA_DIRS = re.compile(r"(^|/)(examples?|tests?|testdata|test_data|data|demo|samples?|tutorial|toy)(/|$)",
                       re.IGNORECASE)
# Vendored code is not the tool: htslib's test fasta files are not HipSTR's
# example data, and its scripts are not HipSTR's entry points.
VENDOR_DIRS = re.compile(r"(^|/)(lib|libs|third[_-]?party|vendor|external|deps|node_modules|"
                         r"htslib|submodules?|unused|\.github)(/|$)", re.IGNORECASE)
OUTPUT_DIRS = re.compile(r"output|result", re.IGNORECASE)
CONDA_ENV_FILE = re.compile(r"(^|/)[^/]*(env|environment|conda)[^/]*\.ya?ml$", re.IGNORECASE)

# --- README signals ----------------------------------------------------------
INSTALL_RE = re.compile(
    r"\b(pip3? install|conda (?:install|env create|create)|mamba (?:install|create)|"
    r"micromamba|make\b|cmake\b|cargo (?:build|install)|go (?:build|install)|"
    r"docker (?:build|pull|run)|apt(?:-get)? install|npm install|Rscript|"
    r"install\.packages|python setup\.py install|\./configure)",
    re.IGNORECASE,
)
INPUT_SIGNALS = {
    "bam": re.compile(r"\.bam\b|--bams?\b|\bbam files?\b|\baligned reads\b|\bsamtools\b", re.I),
    "fastq": re.compile(r"\.f(?:ast)?q(?:\.gz)?\b|\bfastq\b|--fastq\b|\braw reads\b", re.I),
    "ont": re.compile(r"\bnanopore\b|\bont\b|\bminimap2\b|\blong[- ]reads?\b|\bR9\.4|\bR10\b|\bguppy\b|\bdorado\b", re.I),
    "illumina": re.compile(r"\billumina\b|\bmiseq\b|\bnextseq\b|\bforenseq\b|\bpowerseq\b|\bshort[- ]reads?\b|\bamplicon\b|\bpaired[- ]end\b", re.I),
    "hg38": re.compile(r"\bhg38\b|\bgrch38\b", re.I),
    "hg19": re.compile(r"\bhg19\b|\bgrch37\b", re.I),
    "ystr": re.compile(r"\by-?strs?\b|\bDYS\d{3}", re.I),
    "snp": re.compile(r"\bsnps?\b|\bisnp\b|\bphenotypic\b|\bancestry\b", re.I),
    "ce": re.compile(r"\.fsa\b|\.hid\b|\bcapillary\b|\belectropherogram\b", re.I),
}
OUTPUT_SIGNALS = [
    ("vcf", re.compile(r"\.vcf(?:\.gz)?\b|\bvcf\b", re.I)),
    ("tsv", re.compile(r"\.tsv\b|\btab[- ]?(?:delimited|separated)\b|\.txt\b", re.I)),
    ("csv", re.compile(r"\.csv\b|\bcomma[- ]separated\b", re.I)),
    ("json", re.compile(r"\.json\b", re.I)),
]
# Words that mean "tell me how to use it" and are not the tool itself.
SHELL_NOISE = {"cd", "ls", "cat", "wget", "curl", "git", "unzip", "tar", "gunzip", "gzip",
               "echo", "export", "source", "sudo", "pip", "pip3", "conda", "mamba",
               "micromamba", "make", "cmake", "docker", "apt", "apt-get", "python", "python3",
               "perl", "Rscript", "bash", "sh", "chmod", "mkdir", "cp", "mv", "rm", "samtools",
               "bwa", "minimap2", "bcftools", "bgzip", "tabix", "zcat", "7z", "head", "tail",
               "awk", "sed", "grep", "sort", "cut", "tee", "xargs", "time"}


def _get(url: str, token: str | None = None, binary: bool = False) -> bytes | str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "strhub-verified/detect_recipe"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed public hosts)
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return data if binary else data.decode("utf-8", "replace")


def repo_slug(repo_url: str) -> str:
    m = re.match(r"^https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", repo_url.strip())
    if not m:
        raise SystemExit(f"::error::not a public GitHub repository URL: {repo_url}")
    return f"{m.group(1)}/{m.group(2)}"


def fetch_tree(slug: str, ref: str, token: str | None) -> dict:
    if ".." in ref.split("/") or ref.startswith("/"):
        raise SystemExit(f"::error::refusing ref {ref!r}")
    raw = _get(f"{API}/repos/{slug}/git/trees/{ref}?recursive=1", token)
    if raw is None:
        raise SystemExit(f"::error::{slug}@{ref}: repository or ref not found")
    t = json.loads(raw)
    return {"tree": [{"path": e["path"], "type": e["type"], "size": e.get("size", 0)} for e in t["tree"]],
            "truncated": bool(t.get("truncated"))}


def fetch_readme(slug: str, ref: str) -> tuple[str, str | None]:
    for name in README_NAMES:
        text = _get(f"{RAW}/{slug}/{ref}/{name}")
        if text is not None:
            return text, name
    return "", None


def load_offline(d: pathlib.Path) -> tuple[dict, str, str]:
    t = json.loads((d / "tree.json").read_text())
    readme = (d / "README.md").read_text() if (d / "README.md").exists() else ""
    return t, readme, t.get("repo", "")


# --- analysis ----------------------------------------------------------------

def detect_build(paths: list[str], readme: str) -> dict:
    found = []
    for path, method in BUILD_FILES:
        if path in paths:
            found.append({"method": method, "file": path})
    # A conda environment file under another name or one directory down
    # (setup/STRspy_2.0.yml) still says how the tool is installed.
    if not any(f["method"] == "conda" for f in found):
        for path in paths:
            if path.count("/") <= 1 and CONDA_ENV_FILE.search(path) and not VENDOR_DIRS.search(path):
                found.append({"method": "conda", "file": path})
                break
    # A Dockerfile the repository ships is the author's own statement of the
    # environment and wins outright. After that the first hit in tier order.
    chosen = found[0] if found else None
    install_lines = [ln.strip() for ln in _code_lines(readme) if INSTALL_RE.search(ln)]
    method = chosen["method"] if chosen else ("readme" if install_lines else "unknown")
    return {
        "method": method,
        "file": chosen["file"] if chosen else None,
        "candidates": found,
        "readme_install_lines": install_lines[:12],
    }


def detect_example_data(tree: list[dict]) -> list[dict]:
    out = []
    for e in tree:
        if e["type"] != "blob" or VENDOR_DIRS.search(e["path"]):
            continue
        p = e["path"]
        low = p.lower()
        for kind, exts in DATA_EXT.items():
            if low.endswith(exts):
                out.append({"path": p, "kind": kind, "size": e.get("size", 0),
                            "in_example_dir": bool(DATA_DIRS.search(p)),
                            # A file under an output/results directory is what the
                            # tool PRODUCES on its example, not what it takes.
                            "looks_like_output": bool(OUTPUT_DIRS.search(p))})
                break
    # Inputs in example-ish directories first, then the rest by size.
    out.sort(key=lambda x: (x["looks_like_output"], not x["in_example_dir"], x["size"]))
    return out[:40]


def _code_lines(readme: str) -> list[str]:
    """Lines inside fenced or indented code blocks of a Markdown/RST README."""
    lines: list[str] = []
    fenced = False
    for ln in readme.splitlines():
        s = ln.rstrip()
        if s.strip().startswith("```") or s.strip().startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            lines.append(s)
        elif s.startswith(("    ", "\t")) and s.strip():
            lines.append(s.strip())
    # Shell prompts, then backslash continuations joined into one command.
    cleaned: list[str] = []
    for ln in lines:
        ln = re.sub(r"^\s*[$>]\s+", "", ln)
        if cleaned and cleaned[-1].endswith("\\"):
            cleaned[-1] = cleaned[-1][:-1].rstrip() + " " + ln.strip()
        else:
            cleaned.append(ln)
    return cleaned


def tool_names(slug: str, tree: list[dict]) -> list[str]:
    """Plausible names of the executable: repo name, plus scripts and binaries in
    the tree that are not obviously helpers."""
    names = set()
    repo = slug.split("/")[-1]
    names.add(repo)
    names.add(repo.lower())
    for e in tree:
        if e["type"] != "blob" or VENDOR_DIRS.search(e["path"]):
            continue
        p = pathlib.PurePosixPath(e["path"])
        if len(p.parts) > 3:
            continue
        stem, suf = p.stem, p.suffix.lower()
        if suf in (".py", ".sh", ".pl", ".R", ".jl") and not stem.startswith(("test", "setup", "__")):
            names.add(p.name)
            names.add(stem)
        if p.parts[0] in ("bin", "scripts") and suf in ("", ".py", ".sh"):
            names.add(p.name)
        # A committed binary at the root (str8rzr): no extension, not a doc.
        if len(p.parts) == 1 and suf == "" and e.get("size", 0) > 20_000:
            names.add(p.name)
    return sorted(n for n in names if len(n) >= 3 and n not in SHELL_NOISE)


#: What may precede the tool's name on a command line and still be "running it".
RUNNERS = {"python", "python3", "python2", "bash", "sh", "perl", "Rscript", "julia", "java", "-jar"}


def _first_program(line: str) -> str | None:
    """Basename of the program a shell line runs, skipping VAR=x prefixes and
    interpreters (`python3 tool.py` runs tool.py)."""
    toks = line.strip().split()
    while toks and re.match(r"^\w+=", toks[0]):
        toks.pop(0)
    while toks and toks[0].split("/")[-1] in RUNNERS:
        toks.pop(0)
    if not toks:
        return None
    return toks[0].split("/")[-1]


def detect_commands(readme: str, names: list[str]) -> list[dict]:
    cands = []
    lower_names = {n.lower() for n in names}
    in_re = re.compile(r"--?(?:bams?|fastq|input|in|reads|i)\b|\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?\b", re.I)
    out_re = re.compile(r"--?(?:out(?:put)?(?:[-_]?\w+)?|o|str-vcf|prefix)\b|\s>\s", re.I)
    for ln in _code_lines(readme):
        text = ln.strip()
        if not text or text.startswith("#"):
            continue
        # "Usage: tool [-h] ..." blocks quote the synopsis, which is still the
        # best statement of how the tool is invoked when nothing else is shown.
        text = re.sub(r"^usage:\s*", "", text, flags=re.I)
        if INSTALL_RE.search(text) and not in_re.search(text):
            continue
        # In a pipeline (`zcat x.fq.gz | str8rzr -c cfg > out`) the tool is the
        # segment named in the tree, or failing that the last one; zcat is not it.
        segments = [seg for seg in re.split(r"\s\|\s", text) if seg.strip()]
        progs = [_first_program(seg) for seg in segments]
        def _named(pr):
            return pr is not None and (pr.lower() in lower_names
                                       or pr.lower().removesuffix(".py").removesuffix(".sh") in lower_names)
        prog = next((pr for pr in progs if _named(pr)), None)
        if prog is None:
            prog = next((pr for pr in reversed(progs) if pr and pr not in SHELL_NOISE), None)
        if prog is None:
            continue
        named = _named(prog)
        has_in, has_out = bool(in_re.search(text)), bool(out_re.search(text))
        # Either the program is one of the repository's own, or the line plainly
        # takes an input and writes an output (a binary the tree did not name).
        if not named and not (has_in and has_out):
            continue
        cands.append({
            "cmd": text,
            "invokes": prog,
            "named_in_tree": named,
            "has_input_flag": has_in,
            "has_output_flag": has_out,
        })
    # Best first: an invocation that names both an input and an output.
    cands.sort(key=lambda c: (not (c["has_input_flag"] and c["has_output_flag"]),
                              not c["has_input_flag"], not c["named_in_tree"]))
    seen, uniq = set(), []
    for c in cands:
        if c["cmd"] not in seen:
            seen.add(c["cmd"]); uniq.append(c)
    return uniq[:10]


def detect_input_type(readme: str, examples: list[dict]) -> dict:
    hits = {k: len(rx.findall(readme)) for k, rx in INPUT_SIGNALS.items()}
    kinds = {e["kind"] for e in examples}
    if "bam" in kinds:
        hits["bam"] += 3
    if "fastq" in kinds:
        hits["fastq"] += 3
    if "fsa" in kinds:
        hits["ce"] += 3
    ranked = []
    if hits["ce"] and hits["ce"] >= max(hits["bam"], hits["fastq"]):
        ranked.append("ce-fsa")
    if hits["bam"] or hits["fastq"]:
        platform = "ont" if hits["ont"] > hits["illumina"] else "illumina"
        if hits["bam"] >= hits["fastq"]:
            ranked.append("ont-bam-hg38" if platform == "ont"
                          else ("illumina-bam-hg38-y" if hits["ystr"] >= 3 else "illumina-bam-hg38"))
            ranked.append("illumina-str-fastq" if platform == "illumina" else "ont-fastq")
        else:
            ranked.append("illumina-str-fastq" if platform == "illumina" else "ont-fastq")
            ranked.append("ont-bam-hg38" if platform == "ont" else "illumina-bam-hg38")
    if hits["snp"] >= 5 and "illumina-snp-fastq" not in ranked:
        ranked.append("illumina-snp-fastq")
    ranked = list(dict.fromkeys(ranked))
    warnings = []
    if hits["hg19"] and not hits["hg38"]:
        warnings.append("README mentions hg19/GRCh37 only; STRhub reference BAMs are hg38")
    if hits["bam"] and hits["fastq"] and abs(hits["bam"] - hits["fastq"]) <= 2:
        warnings.append("README mentions BAM and FASTQ about equally; try both")
    return {"best": ranked[0] if ranked else None, "candidates": ranked, "signals": hits,
            "warnings": warnings}


def detect_output(readme: str, commands: list[dict]) -> dict:
    text = readme + "\n" + "\n".join(c["cmd"] for c in commands)
    scores = [(fmt, len(rx.findall(text))) for fmt, rx in OUTPUT_SIGNALS]
    scores.sort(key=lambda x: -x[1])
    best = scores[0][0] if scores and scores[0][1] else None
    return {"format": best, "signals": dict(scores)}


def readme_gaps(readme_name: str | None, build: dict, commands: list[dict],
                input_type: dict, output: dict, examples: list[dict]) -> dict:
    """What a stranger needs and did not find. Each is a fact about the README,
    phrased for the person who can fix it."""
    gaps = []
    if readme_name is None:
        gaps.append({"item": "readme", "text": "The repository has no README at this ref."})
    if build["method"] == "unknown":
        gaps.append({"item": "install",
                     "text": "No build or install instructions were found: no Dockerfile, "
                             "environment.yml, requirements.txt, setup.py/pyproject.toml, "
                             "Makefile or CMakeLists.txt, and no install command in the README."})
    if not commands:
        gaps.append({"item": "command",
                     "text": "No command line invoking the tool was found in the README's code blocks."})
    elif not any(c["has_input_flag"] for c in commands):
        gaps.append({"item": "command_input",
                     "text": "The README's example commands do not show where the input file goes."})
    if input_type["best"] is None:
        gaps.append({"item": "input",
                     "text": "The README does not say what kind of data the tool takes "
                             "(FASTQ or BAM; Illumina or nanopore; reference build)."})
    if output["format"] is None:
        gaps.append({"item": "output",
                     "text": "The README does not describe the output file or its format."})
    if not examples:
        gaps.append({"item": "example_data",
                     "text": "The repository ships no example input a stranger could run on. "
                             "A trial can still run on STRhub's reference data for the "
                             "detected input type."})
    return {"name": readme_name, "gaps": gaps,
            "sufficient_to_attempt": build["method"] != "unknown" and bool(commands)}


def propose_example(commands: list[dict], tree_paths: list[str], examples: list[dict]) -> dict | None:
    """The manifest `example` block, when the README shows a command that runs on
    data the repository ships. That is the whole condition: a command whose
    input path exists in the tree is one a stranger can run as written."""
    tree = set(tree_paths)
    example_paths = {e["path"] for e in examples}
    for c in commands:
        tokens = [t.strip("'\"<>()") for t in c["cmd"].replace("=", " ").split()]
        refs = [t for t in tokens if t in tree or t.lstrip("./") in tree]
        if any(r.lstrip("./") in example_paths for r in refs):
            return {"cmd": c["cmd"], "cwd": "/opt/tool", "source": "detected",
                    "inputs_in_repo": sorted({r.lstrip("./") for r in refs})}
    return None


def generate_dockerfile(slug: str, ref: str, build: dict) -> str | None:
    """A pinned environment for the methods STRhub can template. None when the
    repository ships its own Dockerfile (used as-is) or nothing was detected."""
    clone = (f"ARG TOOL_REF={ref}\nWORKDIR /opt\n"
             f"RUN git clone https://github.com/{slug}.git tool \\\n"
             f"    && cd tool && git checkout \"${{TOOL_REF}}\" \\\n"
             f"    && git submodule update --init --recursive || true\nWORKDIR /opt/tool\n")
    tail = "ENV PATH=\"/opt/tool:/opt/tool/bin:$PATH\"\nWORKDIR /work\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n"
    head = "# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.\n"
    apt = ("RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
           "        {pkgs} \\\n    && rm -rf /var/lib/apt/lists/*\n")
    m = build["method"]
    if m == "dockerfile":
        return None
    if m == "conda":
        return (head + "FROM mambaorg/micromamba:1.5.8\nUSER root\n"
                + apt.format(pkgs="git ca-certificates") + clone
                + f"RUN micromamba create -y -n tool -f {build['file']} && micromamba clean -a -y\n"
                + "ENV PATH=\"/opt/conda/envs/tool/bin:/opt/tool:$PATH\"\nWORKDIR /work\n"
                + "ENTRYPOINT [\"micromamba\", \"run\", \"-n\", \"tool\", \"/bin/bash\", \"-lc\"]\n")
    if m == "pip":
        install = ("RUN pip install --no-cache-dir -r requirements.txt\n" if build["file"] == "requirements.txt"
                   else "RUN pip install --no-cache-dir .\n")
        return (head + "FROM python:3.11-slim\n" + apt.format(pkgs="git ca-certificates build-essential")
                + clone + install + tail)
    if m in ("make", "cmake"):
        cmd = "RUN make\n" if m == "make" else "RUN cmake . && make\n"
        return (head + "FROM ubuntu:22.04\n"
                + apt.format(pkgs="build-essential cmake git ca-certificates zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev")
                + clone + cmd + tail)
    if m == "cargo":
        return (head + "FROM rust:1.80-slim\n" + apt.format(pkgs="git ca-certificates") + clone
                + "RUN cargo build --release\nENV PATH=\"/opt/tool/target/release:$PATH\"\nWORKDIR /work\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n")
    if m == "go":
        return (head + "FROM golang:1.22\n" + clone + "RUN go build -o /usr/local/bin/tool ./...\n" + tail)
    if m == "readme":
        # Scripts run straight from the clone; the README's install lines are
        # left for the model or the author, since they can be anything.
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs="git ca-certificates python3 python3-pip")
                + clone + tail)
    return None


def detect(slug: str, ref: str, tree_resp: dict, readme: str, readme_name: str | None) -> dict:
    tree = tree_resp["tree"]
    paths = [e["path"] for e in tree]
    build = detect_build(paths, readme)
    examples = detect_example_data(tree)
    names = tool_names(slug, tree)
    commands = detect_commands(readme, names)
    input_type = detect_input_type(readme, examples)
    output = detect_output(readme, commands)
    rd = readme_gaps(readme_name, build, commands, input_type, output, examples)
    return {
        "schema": "strhub-verified/recipe-proposal/1",
        "repo": f"https://github.com/{slug}",
        "ref": ref,
        "tree_truncated": tree_resp.get("truncated", False),
        "build": build,
        "example_data": examples,
        "tool_names": names,
        "commands": commands,
        "input_type": input_type,
        "output": output,
        "readme": rd,
        "example": propose_example(commands, paths, examples),
        "dockerfile": generate_dockerfile(slug, ref, build),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", help="public GitHub repository URL")
    ap.add_argument("ref", nargs="?", help="commit SHA or tag")
    ap.add_argument("--offline", help="directory with tree.json + README.md (tests)")
    ap.add_argument("--json", help="write the proposal here")
    args = ap.parse_args()

    if args.offline:
        tree_resp, readme, repo = load_offline(pathlib.Path(args.offline))
        slug, ref = repo_slug(repo), tree_resp.get("ref", "HEAD")
        readme_name = "README.md" if readme else None
    else:
        if not (args.repo and args.ref):
            ap.error("repo and ref are required unless --offline is given")
        slug, ref = repo_slug(args.repo), args.ref
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        tree_resp = fetch_tree(slug, ref, token)
        readme, readme_name = fetch_readme(slug, ref)

    result = detect(slug, ref, tree_resp, readme, readme_name)
    text = json.dumps(result, indent=2)
    if args.json:
        pathlib.Path(args.json).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
