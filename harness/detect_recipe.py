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

Beyond the README it reads, at the same ref: the documents and wiki pages the
README links, the build and packaging files, the loci files the repository
ships, what Bioconda holds and the release's assets (gather()). A snapshot
written by snapshot_repo.py freezes all of it for offline tests.

Usage:
  python harness/detect_recipe.py <repo-url> <ref> [--tag v1.2] [--json out.json]
  python harness/detect_recipe.py --offline harness/testdata/benchmark/longtr
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
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
                         r"htslib|submodules?|unused|\.github"
                         # A copy of somebody else's release, named with its
                         # version: vamos ships abPOA-1.4.1/ and spoa-4.1.5/.
                         r"|[A-Za-z][\w]*[-_]v?\d+(?:\.\d+)+)(/|$)", re.IGNORECASE)
OUTPUT_DIRS = re.compile(r"output|result", re.IGNORECASE)
#: Tests, examples and documentation carry build files of their own (a
#: test/CMakeLists.txt) that do not build the tool.
TEST_DIRS = re.compile(r"(^|/)(tests?|testing|examples?|docs?|benchmarks?|test_?data|testdata|demo)(/|$)",
                       re.IGNORECASE)
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


# --- beyond the README ----------------------------------------------------------
# On 24 September 2026, ten of eighteen STR tools the engine had never seen kept
# their usage outside the README: a docs/ folder, the wiki, a Read the Docs
# site. Everything read here is still the repository's own word (or its
# author's, on the wiki and a registry), and each piece says where it came from.

#: Build and packaging files whose CONTENTS say how the tool is built and what
#: its executables are called: console scripts, add_executable, [[bin]].
BUILD_CONTENT_NAMES = {"Makefile", "makefile", "CMakeLists.txt", "setup.py", "setup.cfg",
                       "pyproject.toml", "Cargo.toml", "DESCRIPTION", "configure.ac",
                       "install.sh", "INSTALL.sh", "requirements.txt", "go.mod", "Dockerfile"}
MAX_FILE_BYTES = 200_000
MAX_DOCS = 12
MAX_WIKI = 6

#: Where usage is written when it is not in the README. A link from the README
#: to one of these, inside the repository, is followed.
DOC_EXT = (".md", ".markdown", ".rst", ".txt", ".rmd")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)|href=[\"']([^\"']+)[\"']|<(https?://[^>\s]+)>|`([^`]+)`_")


def build_content_paths(paths: list[str]) -> list[str]:
    """The build and packaging files worth reading, at most two levels down and
    never under vendored code or tests."""
    out = []
    for p in paths:
        pp = pathlib.PurePosixPath(p)
        if len(pp.parts) > 3 or VENDOR_DIRS.search(p) or TEST_DIRS.search(p):
            continue
        if pp.name in BUILD_CONTENT_NAMES or pp.suffix in (".nimble",) \
                or CONDA_ENV_FILE.search(p):
            out.append(p)
    # Shallow first: the root's Makefile is the one the README means.
    out.sort(key=lambda p: (p.count("/"), p))
    return out[:14]


def linked_docs(readme: str, slug: str, paths: set[str]) -> tuple[list[str], list[str]]:
    """In-repository documents and wiki pages the README links to, in the
    order it links them: ([repo paths], [wiki page names])."""
    owner_repo = slug.lower()
    repo_docs: list[str] = []
    wiki: list[str] = []
    for m in MD_LINK.finditer(readme):
        target = next(g for g in m.groups() if g)
        target = target.split("#")[0].strip()
        if not target:
            continue
        low = target.lower()
        w = re.match(rf"https?://github\.com/{re.escape(owner_repo)}/wiki/?([^?#]*)", low)
        if w:
            page = target.split("/wiki", 1)[1].strip("/") or "Home"
            if page not in wiki:
                wiki.append(page)
            continue
        b = re.match(rf"https?://github\.com/{re.escape(owner_repo)}/(?:blob|tree)/[^/]+/(.+)", target, re.I)
        path = b.group(1) if b else (None if re.match(r"^[a-z]+:", target) else target.lstrip("./"))
        if not path:
            continue
        if path in paths and path.lower().endswith(DOC_EXT) and path not in repo_docs:
            repo_docs.append(path)
        elif path.rstrip("/") + "/README.md" in paths and path not in repo_docs:
            repo_docs.append(path.rstrip("/") + "/README.md")
    # A docs/ folder the README never links still holds the usage often
    # enough (ExpansionHunter's docs/03_Usage.md): its top-level pages come
    # after the linked ones, by name.
    # Usage-like names first (STRique's docs/examples/intro.md, MPSproto's
    # doc/MPSproto_tutorial.Rmd), then the rest by name; two levels down.
    usage = re.compile(r"usage|tutorial|example|quick|getting|start|run|install|manual|guide|intro", re.I)
    auto = [p for p in sorted(paths)
            if re.match(r"^(?:docs?|documentation|manual|wiki|vignettes?)/(?:[^/]+/)?[^/]+\.(?:md|rst|rmd)$", p, re.I)
            and p not in repo_docs and not re.search(r"changelog|license|contributing|code_of_conduct|release",
                                                     p, re.I)]
    auto.sort(key=lambda p: (not usage.search(p), p.count("/"), p))
    repo_docs += auto
    return repo_docs[:MAX_DOCS], wiki[:MAX_WIKI]


def fetch_file(slug: str, ref: str, path: str) -> str | None:
    """An optional read: a file that cannot be fetched is a file not read,
    never a failed proposal (the tree and the README are the required ones)."""
    try:
        text = _get(f"{RAW}/{slug}/{ref}/{urllib.parse.quote(path, safe='/')}")
    except Exception:  # noqa: BLE001
        return None
    return text[:MAX_FILE_BYTES] if isinstance(text, str) else None


def fetch_wiki_page(slug: str, page: str) -> str | None:
    """A wiki page, as Markdown. Wikis are not versioned with the code: the
    page is read as it is today, and the proposal says so."""
    for name in (page, page.replace(" ", "-")):
        try:
            text = _get(f"{RAW}/wiki/{slug}/{urllib.parse.quote(name, safe='/')}.md")
        except Exception:  # noqa: BLE001
            return None
        if isinstance(text, str):
            return text[:MAX_FILE_BYTES]
    return None


def packaging(files: dict[str, str]) -> dict:
    """What the packaging declares: {"packages": [...], "executables": [...]}.

    The executables (console scripts, scripts=, add_executable, [[bin]],
    nimble bin) are what a user types, written down more reliably here than
    anywhere else; the package names are what a registry knows the tool by."""
    packages: list[str] = []
    exes: list[str] = []

    def add(lst: list[str], n: str) -> None:
        n = n.strip().strip("'\"")
        if n and n not in lst and PROGRAM_RE.match(n):
            lst.append(n)

    for path, text in files.items():
        base = pathlib.PurePosixPath(path).name
        if base == "setup.py":
            m = re.search(r"console_scripts['\"]?\s*[:=]\s*\[([^\]]*)\]", text)
            if m:
                for entry in re.findall(r"['\"]\s*([\w.+-]+)\s*=", m.group(1)):
                    add(exes, entry)
            m = re.search(r"\bscripts\s*=\s*\[([^\]]*)\]", text)
            if m:
                for sc in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    add(exes, pathlib.PurePosixPath(sc).name)
            m = re.search(r"\bname\s*=\s*['\"]([\w.-]+)['\"]", text)
            if m:
                add(packages, m.group(1))
        elif base == "setup.cfg":
            m = re.search(r"console_scripts\s*=\s*\n((?:[ \t]+.*\n?)+)", text)
            if m:
                for entry in re.findall(r"^\s*([\w.+-]+)\s*=", m.group(1), re.M):
                    add(exes, entry)
            m = re.search(r"^\[metadata\][^\[]*?^name\s*=\s*([\w.-]+)", text, re.M | re.S)
            if m:
                add(packages, m.group(1))
        elif base == "pyproject.toml":
            for sect in re.finditer(r"^\[(?:project\.scripts|tool\.poetry\.scripts)\]\s*\n((?:(?!\[).*\n?)*)", text, re.M):
                for entry in re.findall(r"^\s*['\"]?([\w.+-]+)['\"]?\s*=", sect.group(1), re.M):
                    add(exes, entry)
            m = re.search(r"^\[(?:project|tool\.poetry)\][^\[]*?^name\s*=\s*['\"]([\w.-]+)['\"]", text, re.M | re.S)
            if m:
                add(packages, m.group(1))
        elif base == "Cargo.toml":
            for m in re.finditer(r"^\[\[bin\]\][^\[]*?^name\s*=\s*['\"]([\w.-]+)['\"]", text, re.M | re.S):
                add(exes, m.group(1))
            m = re.search(r"^\[package\][^\[]*?^name\s*=\s*['\"]([\w.-]+)['\"]", text, re.M | re.S)
            if m:
                add(packages, m.group(1))
        elif base == "CMakeLists.txt":
            for m in re.finditer(r"add_executable\s*\(\s*([A-Za-z][\w.+-]*)", text):
                if not re.search(r"test|bench|example", m.group(1), re.I):
                    add(exes, m.group(1))
        elif base == "DESCRIPTION":
            m = re.search(r"^Package:\s*([\w.]+)", text, re.M)
            if m:
                add(packages, m.group(1))
        elif path.endswith(".nimble"):
            add(packages, pathlib.PurePosixPath(path).stem)
            m = re.search(r"^bin\s*=\s*@\[([^\]]*)\]", text, re.M)
            if m:
                for b in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    add(exes, pathlib.PurePosixPath(b).name)
    return {"packages": packages, "executables": exes}


def bioconda_versions(package: str) -> list[str] | None:
    """The versions of a Bioconda package, or None when there is no such
    package (or the registry could not be asked: never a reason to fail)."""
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", package):
        return None
    try:
        raw = _get(f"https://api.anaconda.org/package/bioconda/{package}")
    except Exception:  # noqa: BLE001 — a registry outage is not the tool's
        return None
    if not isinstance(raw, str):
        return None
    try:
        return list(json.loads(raw).get("versions") or [])
    except ValueError:
        return None


def release_assets(slug: str, tag: str, token: str | None) -> dict | None:
    """The assets attached to the release for `tag`, or None."""
    if not tag:
        return None
    try:
        raw = _get(f"{API}/repos/{slug}/releases/tags/{tag}", token)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, str):
        return None
    try:
        r = json.loads(raw)
    except ValueError:
        return None
    return {"tag": tag, "assets": [{"name": a["name"], "size": a.get("size", 0),
                                    "url": a["browser_download_url"],
                                    **({"digest": a["digest"]} if a.get("digest") else {})}
                                   for a in r.get("assets") or []]}


#: Files that define the loci a tool genotypes (ExpansionHunter's variant
#: catalog, a regions BED the docs use): read so a proposal can tell whether
#: those loci are in STRhub's sample at all.
LOCI_FILE = re.compile(r"(?:catalog|catalogue|loci|locus|regions?|repeats?|motifs?)[^/]*\.(?:json|bed|tsv)$", re.I)
MAX_LOCI_FILES = 6
MAX_LOCI_BYTES = 2_000_000


def loci_file_paths(tree: list[dict]) -> list[str]:
    out = [e["path"] for e in tree if e["type"] == "blob" and LOCI_FILE.search(e["path"])
           and not VENDOR_DIRS.search(e["path"]) and 0 < e.get("size", 0) <= MAX_LOCI_BYTES]
    out.sort(key=lambda p: (not re.search(r"hg38|grch38", p, re.I), p.count("/"), p))
    return out[:MAX_LOCI_FILES]


COORD = re.compile(r"\b(chr[0-9XYMT]{1,2}|[0-9]{1,2}|X|Y)[:\t ]+([0-9]{2,10})[-\t ]+([0-9]{2,10})\b")


def shipped_loci(files: dict[str, str], paths: list[str]) -> dict[str, list[list]]:
    """{path: [[chrom, start, end], ...]} for each loci file read."""
    out = {}
    for p in paths:
        text = files.get(p)
        if not text:
            continue
        coords = [[m.group(1) if m.group(1).startswith("chr") else f"chr{m.group(1)}",
                   int(m.group(2)), int(m.group(3))] for m in COORD.finditer(text)]
        coords = [c for c in coords if c[1] < c[2]]
        if coords:
            out[p] = coords[:5000]
    return out


def gather(slug: str, ref: str, tag: str = "", token: str | None = None) -> dict:
    """Everything detect() reads about a repository, fetched at `ref`."""
    tree_resp = fetch_tree(slug, ref, token)
    readme, readme_name = fetch_readme(slug, ref)
    paths = [e["path"] for e in tree_resp["tree"]]
    files = {}
    for p in build_content_paths(paths) + loci_file_paths(tree_resp["tree"]):
        text = fetch_file(slug, ref, p)
        if text is not None:
            files[p] = text
    repo_docs, wiki_pages = linked_docs(readme, slug, set(paths))
    docs = []
    for p in repo_docs:
        text = fetch_file(slug, ref, p)
        if text is not None:
            docs.append({"path": p, "origin": "repo", "text": text})
    # The wiki's own navigation: STRetch's README links the wiki's Home, and
    # the install and run pages hang off its sidebar.
    queue = list(wiki_pages)
    if queue and "_Sidebar" not in queue:
        queue.append("_Sidebar")
    seen_pages: set[str] = set()
    while queue and len(seen_pages) < MAX_WIKI:
        page = queue.pop(0)
        if page in seen_pages:
            continue
        seen_pages.add(page)
        text = fetch_wiki_page(slug, page)
        if text is None:
            continue
        docs.append({"path": f"wiki/{page}", "origin": "wiki", "text": text})
        for m in re.finditer(rf"(?:https?://github\.com/{re.escape(slug)}/wiki/|\]\()([A-Za-z0-9][\w%.-]*)\)?", text):
            target = urllib.parse.unquote(m.group(1)).split("#")[0]
            if target and "." not in target and target not in seen_pages and target not in queue:
                queue.append(target)
    bioconda = {}
    for name in bioconda_candidates(slug, files):
        bioconda[name] = bioconda_versions(name)
    return {"tree_resp": tree_resp, "readme": readme, "readme_name": readme_name,
            "files": files, "docs": docs,
            "published": {"bioconda": bioconda, "release": release_assets(slug, tag, token)},
            "tag": tag}


def bioconda_candidates(slug: str, files: dict[str, str]) -> list[str]:
    """Package names to ask Bioconda about: the repository's name and the
    name its packaging declares, lower-cased. At most three questions."""
    names = [slug.split("/")[-1].lower()]
    for n in packaging(files)["packages"][:2]:
        if n.lower() not in names:
            names.append(n.lower())
    return [re.sub(r"[^a-z0-9._-]", "-", n) for n in names][:3]


def registry_facts(published: dict, tag: str, build: dict) -> dict:
    """{"bioconda": {package: {"versions": n, "latest": v, "has_tag_version": bool}},
    "documented": which of them the docs name}."""
    want = tag.lstrip("vV") if tag else ""
    out = {}
    for pkg, versions in (published.get("bioconda") or {}).items():
        if versions:
            out[pkg] = {"latest": versions[-1], "versions": len(versions),
                        "has_tag_version": bool(want) and want in versions}
    documented = sorted({f.get("package") for f in build.get("candidates", [])
                         if f.get("method") == "bioconda" and f.get("package")})
    return {"bioconda": out, "documented": documented}


def load_snapshot(d: pathlib.Path) -> dict:
    """A snapshot written by snapshot_repo.py, as gather() returns it. Older
    snapshots (testdata/repos/) have only tree.json and README.md."""
    t, readme, _ = load_offline(d)
    files = {}
    fdir = d / "files"
    if fdir.is_dir():
        for p in sorted(fdir.rglob("*")):
            if p.is_file():
                files[p.relative_to(fdir).as_posix()] = p.read_text(errors="replace")
    docs = []
    for sub, origin in (("docs", "repo"), ("wiki", "wiki")):
        ddir = d / sub
        if ddir.is_dir():
            for p in sorted(ddir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(ddir).as_posix()
                    docs.append({"path": rel if origin == "repo" else f"wiki/{rel.removesuffix('.md')}",
                                 "origin": origin, "text": p.read_text(errors="replace")})
    # Keep the order the README linked them in, when the snapshot recorded it.
    order = t.get("docs_order") or []
    if order:
        docs.sort(key=lambda x: order.index(x["path"]) if x["path"] in order else len(order))
    pub = json.loads((d / "published.json").read_text()) if (d / "published.json").exists() else {}
    return {"tree_resp": t, "readme": readme,
            "readme_name": t.get("readme_name") or ("README.md" if readme else None),
            "files": files, "docs": docs,
            "published": {"bioconda": pub.get("bioconda") or {}, "release": pub.get("release")},
            "tag": t.get("tag", "")}


# --- analysis ----------------------------------------------------------------

BIOCONDA_RE = re.compile(r"(?:conda|mamba|micromamba)\s+install\b[^\n]*?-c\s+bioconda[^\n]*?\s([a-z0-9][a-z0-9._-]*)\s*$", re.I)
#: The other ways a README says "install me from Bioconda": the channel
#: before the package, `bioconda::pkg`, or the anaconda.org badge and link.
BIOCONDA_OTHER = re.compile(r"(?:conda|mamba|micromamba)\s+install\b[^\n]*?\bbioconda::([a-z0-9][a-z0-9._-]*)"
                            r"|(?:conda|mamba|micromamba)\s+install\s+(?:-y\s+)?([a-z0-9][a-z0-9._-]*)\s+(?:-c\s+\S+\s+)*-c\s+bioconda\b"
                            r"|anaconda\.org/bioconda/([a-z0-9][a-z0-9._-]*)", re.I)


def bioconda_package(readme: str) -> str | None:
    """The package a README installs from Bioconda, if it says so. The last
    token of the install line is the package in every README seen so far
    (`conda install -c bioconda -c conda-forge gangstr`)."""
    found = bioconda_package_with_line(readme)
    return found[0] if found else None


def bioconda_package_with_line(readme: str) -> tuple[str, int] | None:
    """(package, README line) — the line is the cite."""
    for line_no, ln in _code_lines_numbered(readme):
        # `--file requirements.txt` installs a list, not a package called
        # requirements.txt (vamos).
        if "--file" in ln:
            continue
        m = BIOCONDA_RE.search(ln.strip())
        if m and m.group(1) not in ("bioconda", "conda-forge"):
            return m.group(1), line_no
    for line_no, ln in enumerate(readme.splitlines(), 1):
        if "--file" in ln:
            continue
        m = BIOCONDA_OTHER.search(ln)
        if m:
            pkg = next(g for g in m.groups() if g)
            if pkg.lower() not in ("bioconda", "conda-forge", "recipes", "badges"):
                return pkg.lower(), line_no
    return None


DOCKER_IMAGE_RE = re.compile(
    r"docker\s+(?:pull|run)\s+(?:--?\S+\s+)*([a-z0-9][a-z0-9._/-]*(?::[\w.-]+)?)\b"
    r"|hub\.docker\.com/r/([a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*)", re.I)


def docker_image(readme: str) -> str | None:
    """A Docker image the README tells users to pull. The author's own
    environment, published: as trustworthy as a Dockerfile in the tree."""
    found = docker_image_with_line(readme)
    return found[0] if found else None


def docker_image_with_line(readme: str) -> tuple[str, int] | None:
    """(image, README line) — the line is the cite."""
    for m in DOCKER_IMAGE_RE.finditer(readme):
        img = m.group(1) or m.group(2)
        if img and "/" in img and not img.startswith(("http", "docker.")):
            return img, readme.count("\n", 0, m.start()) + 1
    return None


#: Environments somebody else already built: a Docker image on a registry, a
#: Bioconda package. Whatever runs from one is whatever its publisher last
#: pushed, which need not be the pinned commit the report names.
PUBLISHED_METHODS = ("docker_image", "bioconda")


#: Build files one directory down, when the root has none of the kind:
#: ExpansionHunterDenovo builds from source/, vamos from src/.
SUBDIR_BUILD = re.compile(r"^(?:source|src|cpp|c\+\+|code)/(CMakeLists\.txt|Makefile|makefile)$", re.I)
CONDA_SPEC_LINE = re.compile(r"^[A-Za-z0-9_.-]+=[^=\s]")    # conda's name=version, not pip's name==version
RELEASE_DOC = re.compile(r"/releases\b|\breleases? page\b|\b(?:pre-?built|compiled|static)\s+binar(?:y|ies)\b"
                         r"|\bbinar(?:y|ies)\b[^\n]{0,60}\b(?:release|download)", re.I)
LINUX_ASSET = re.compile(r"linux|x86[_-]64|amd64|x64", re.I)
NOT_LINUX_ASSET = re.compile(r"mac|darwin|osx|windows|win64|\.exe$|\.dmg$|arm64|aarch64|\bsource\b|-src\b|debug", re.I)


def release_binary(release: dict | None, docs_text: str, repo_name: str) -> dict | None:
    """The Linux x86-64 binary the author attached to the release the ref was
    resolved from, when the documentation tells users to download one.
    ExpansionHunter's docs: "A compiled binary ... can be downloaded"."""
    if not release or not RELEASE_DOC.search(docs_text):
        return None
    assets = [a for a in release.get("assets") or [] if not NOT_LINUX_ASSET.search(a["name"])]
    linux = [a for a in assets if LINUX_ASSET.search(a["name"])]
    # A bare binary named for the tool (STRling's `strling`) counts too.
    bare = [a for a in assets if a["name"].lower() == repo_name.lower()]
    pick = (linux or bare or [None])[0]
    if not pick:
        return None
    return {"method": "release_binary", "file": None, "asset": pick["name"], "url": pick["url"],
            "digest": pick.get("digest"), "tag": release.get("tag")}


def detect_build(paths: list[str], readme: str, files: dict[str, str] | None = None,
                 docs_text: str = "", release: dict | None = None, slug: str = "") -> dict:
    files = files or {}
    found = []
    img = docker_image_with_line(readme)
    if img:
        found.append({"method": "docker_image", "file": None, "image": img[0], "readme_line": img[1]})
    pkg = bioconda_package_with_line(readme)
    if pkg:
        found.append({"method": "bioconda", "file": None, "package": pkg[0], "readme_line": pkg[1]})
    pathset = set(paths)
    for path, method in BUILD_FILES:
        if path in pathset:
            found.append({"method": method, "file": path})
    # Autotools: a configure script, or the configure.ac that makes one.
    if "configure.ac" in pathset or "configure" in pathset:
        found.append({"method": "autotools", "file": "configure" if "configure" in pathset else "configure.ac"})
    # One directory down, only when the root has nothing of the kind.
    for p in sorted(paths):
        m = SUBDIR_BUILD.match(p)
        if not m:
            continue
        kind = "cmake" if m.group(1).lower() == "cmakelists.txt" else "make"
        if not any(f["method"] == kind for f in found):
            found.append({"method": kind, "file": p, "dir": p.rsplit("/", 1)[0]})
    if "DESCRIPTION" in pathset and re.search(r"^Package:", files.get("DESCRIPTION", "Package:"), re.M):
        found.append({"method": "r", "file": "DESCRIPTION"})
    nimble = next((p for p in paths if p.endswith(".nimble") and "/" not in p), None)
    if nimble:
        found.append({"method": "nim", "file": nimble})
    for script in ("install.sh", "INSTALL.sh", "setup.sh"):
        if script in pathset:
            found.append({"method": "script", "file": script})
    # A conda environment file under another name or one directory down
    # (setup/STRspy_2.0.yml) still says how the tool is installed.
    if not any(f["method"] == "conda" for f in found):
        for path in paths:
            if path.count("/") <= 1 and CONDA_ENV_FILE.search(path) and not VENDOR_DIRS.search(path) \
                    and not re.search(r"(?:^|[/_.-])(?:dev|devel|test|tests|docs?|ci|build|rtd)(?:[_.-]|$)",
                                      path.rsplit("/", 1)[-1], re.I):
                found.append({"method": "conda", "file": path})
                break
    # requirements.txt written for conda (`htslib=1.17`) and installed with
    # `conda install --file requirements.txt`, as vamos documents: a conda
    # environment, not pip.
    req = files.get("requirements.txt", "")
    req_lines = [ln.strip() for ln in req.splitlines() if ln.strip() and not ln.startswith("#")]
    if req_lines and (sum(1 for ln in req_lines if CONDA_SPEC_LINE.match(ln)) > len(req_lines) / 2
                      or re.search(r"conda\s+install[^\n]*--file\s+requirements\.txt", readme + docs_text)):
        found = [f for f in found if not (f["method"] == "pip" and f["file"] == "requirements.txt")]
        if not any(f["method"] == "conda" for f in found):
            # First among the source builds: it is the environment the make
            # (or pip) step below it builds in, as vamos documents them.
            found.insert(0, {"method": "conda", "file": "requirements.txt", "spec_list": True})
    # A script the documentation says to run to install (STRetch's wiki:
    # `./install.sh`) is the documented install, ahead of an environment file.
    for f in list(found):
        if f["method"] == "script" and re.search(rf"(?:^|\s|\./|bash\s+|sh\s+){re.escape(f['file'])}\b",
                                                  "\n".join(_code_lines(readme + "\n" + docs_text))):
            found.remove(f)
            found.insert(0, {**f, "documented": True})
    rb = release_binary(release, readme + "\n" + docs_text, slug.split("/")[-1])
    if rb:
        found.append(rb)
    # The repository's own Dockerfile wins outright: the author's own statement
    # of the environment, at the pinned ref. Then the binary the author built
    # for this very release, when the documentation says to download it: it
    # IS the pinned commit, compiled by its author. Then anything that BUILDS
    # the pinned commit (conda, pip, cmake, make, ...), in tier order: what the
    # report names is what ran. A published image or Bioconda package comes
    # after: it is the author's environment too, but holds whatever version was
    # last pushed to it. A published one is kept as the FALLBACK for a source
    # build, so a toolchain we guessed wrong does not end the trial (see
    # `fallback`); the report then says which of the two ran.
    # Source builds keep the order they were found in (BUILD_FILES first:
    # an environment.yml at the root before pyproject before CMake before
    # make), so a stray environment file one level down does not outrank the
    # packaging the README documents.
    rank = {"dockerfile": 0, "release_binary": 1, "docker_image": 3, "bioconda": 4}
    found.sort(key=lambda f: rank.get(f["method"], 2))
    chosen = found[0] if found else None
    install_lines = [ln.strip() for ln in _code_lines(readme) if INSTALL_RE.search(ln)]
    method = chosen["method"] if chosen else ("readme" if install_lines else "unknown")
    # The repository's own Dockerfile gets one too: STRsearch ships a Dockerfile
    # AND tells readers to `docker pull` its image. When the Dockerfile does not
    # build, the image the README documents is still the author's word.
    fallback = None
    if chosen and method not in PUBLISHED_METHODS:
        fallback = next((f for f in found if f["method"] in PUBLISHED_METHODS), None)
    # What a source build needs from the environment that no file says: a
    # Makefile that clones its dependencies over SSH (LongTR's spoa) needs a
    # GitHub key nobody has in a fresh environment.
    ssh = sorted(p for p, t in files.items() if re.search(r"git@github\.com:", t))
    # conda plus a build of the tool itself: an environment of dependencies is
    # not the tool (STRling's, STRetch's), and vamos documents `make` in src/.
    then = []
    if chosen and method == "conda":
        m = re.search(r"cd\s+[\w*./-]*?/?(src|source)/?\s*&&\s*make\b", readme + docs_text)
        sub = next((f for f in found if f["method"] == "make" and f.get("dir")), None)
        if m or sub:
            then.append(f"make -C {(sub or {}).get('dir') or m.group(1)}")
        elif any(f["method"] == "pip" for f in found) and re.search(
                r"pip3?\s+install\s+(?:-e\s+)?\.(?:\s|$)|setup\.py\s+install", readme + docs_text):
            # Only when the docs install the package into the environment:
            # straglr's README creates the environment and runs straglr.py
            # from the clone, and a `pip install .` STRhub added failed there.
            then.append("python -m pip install --no-cache-dir .")
        elif any(f["method"] == "make" for f in found):
            then.append("make")
    return {
        "method": method,
        "file": chosen["file"] if chosen else None,
        "dir": chosen.get("dir") if chosen else None,
        "package": chosen.get("package") if chosen else None,
        "image": chosen.get("image") if chosen else None,
        "asset": chosen.get("asset") if chosen else None,
        "url": chosen.get("url") if chosen else None,
        "digest": chosen.get("digest") if chosen else None,
        "tag": chosen.get("tag") if chosen else None,
        "spec_list": bool(chosen.get("spec_list")) if chosen else False,
        "then": then,
        "ssh_urls_in": ssh,
        "readme_line": chosen.get("readme_line") if chosen else None,
        "fallback": fallback,
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
    return [text for _, text in _code_lines_numbered(readme)]


def _code_lines_numbered(readme: str) -> list[tuple[int, str]]:
    """(README line, text) for each command-shaped line in a code block.

    The line is where the command STARTS in the README (1-based), kept through
    the joining below so a report can cite it — a reader who is told "the
    README's own command" must be able to open the README at that command.

    Markdown fences and indented blocks, and reStructuredText literal blocks
    (a paragraph ending in `::`, or `.. code-block::`), which TRTools' README
    and every Sphinx site use and which the Markdown rules missed.
    """
    lines: list[tuple[int, str]] = []
    fenced = False
    rst_block = False       # inside an RST literal block
    rst_open = False        # the previous paragraph opened one
    for no, ln in enumerate(readme.splitlines(), 1):
        s = ln.rstrip()
        stripped = s.strip()
        # A fence is a line of backticks (and an info string), not a line
        # that opens AND closes inline code with them: lusSTR's README starts
        # lines with ```lusstr``` in prose, and each one flipped every block
        # after it inside out.
        if re.match(r"^(?:`{3,}|~{3,})[^`]*$", stripped):
            fenced = not fenced
            continue
        if fenced:
            lines.append((no, s))
            continue
        if rst_block:
            if not stripped:
                continue
            if s[:1] in (" ", "\t"):
                lines.append((no, stripped))
                continue
            rst_block = False
        if rst_open and not stripped:
            rst_block, rst_open = True, False
            continue
        if re.match(r"^\.\.\s+(?:code-block|code|sourcecode|prompt)::", stripped) \
                or (stripped.endswith("::") and not stripped.startswith("..")):
            rst_open = True
            continue
        rst_open = False
        if s.startswith(("    ", "\t")) and stripped:
            lines.append((no, stripped))
    # Shell prompts, then continuations joined into one command: a trailing
    # backslash, or a following line that starts with a flag. READMEs lay a
    # long invocation out one option per line without any backslash (HipSTR,
    # GangSTR), and reading only the first line loses --regions and --out.
    cleaned: list[tuple[int, str]] = []
    for no, ln in lines:
        ln = re.sub(r"^\s*[$>%]\s+", "", ln)
        # `--flag value \  # what it does`: the comment hides the backslash
        # that joins the next line (strkit's `strkit call` example was lost
        # this way). Only an unquoted # after whitespace is a comment.
        m = re.search(r"\s#(?![!/{])", ln)
        if m and ln[:m.start()].count("'") % 2 == 0 and ln[:m.start()].count('"') % 2 == 0:
            ln = ln[:m.start()].rstrip()
        stripped = ln.strip()
        if cleaned and cleaned[-1][1].endswith("\\"):
            cleaned[-1] = (cleaned[-1][0], cleaned[-1][1][:-1].rstrip() + " " + stripped)
        elif cleaned and stripped.startswith("-") and not stripped.startswith("---") \
                and cleaned[-1][1].strip() and not cleaned[-1][1].strip().startswith(("#", "-")) \
                and not cleaned[-1][1].rstrip().endswith(":"):
            # A line ending in a colon ("where:", "Options:") heads an option
            # listing, not a command; joining the flags onto it made STRspy's
            # help text the best "command" in its README.
            cleaned[-1] = (cleaned[-1][0], cleaned[-1][1].rstrip() + " " + stripped)
        else:
            cleaned.append((no, ln))
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


PROGRAM_RE = re.compile(r"^[A-Za-z0-9_][\w.+-]*$")


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


#: Words that follow a program's name in a sentence, not on a command line:
#: "lusSTR is a tool that ..." was taken for an invocation of lusSTR.
PROSE_NEXT = {"is", "are", "was", "were", "can", "could", "will", "would", "should", "must",
              "may", "uses", "use", "allows", "provides", "the", "a", "an", "to", "of", "and",
              "has", "have", "does", "requires", "needs", "takes", "supports", "for", "in",
              "on", "with", "also", "then", "now", "generates", "produces", "outputs",
              "reads", "writes", "accepts", "expects"}
STOPWORDS = {"a", "an", "the", "with", "as", "for", "of", "to", "from", "in", "and", "or",
             "is", "are", "this", "that", "it", "be", "by", "on", "your", "you"}
#: Subcommands that are not the analysis: asking for help, installing,
#: drawing, converting between formats, merging finished results.
HELPER_VERBS = {"help", "gui", "install", "update", "download", "setup", "version",
                "plot", "view", "visualize", "visualise", "viz", "deepdive", "browse",
                "convert", "merge", "join", "compare", "mi", "stats", "summary", "report",
                "format", "sort", "annotate", "filter", "concat"}
#: Subcommands that are the analysis itself.
MAIN_VERBS = {"call", "genotype", "genotyping", "run", "analyze", "analyse", "predict",
              "detect", "profile", "count", "type", "search", "scan", "quantify", "from_bam",
              "from_fastq"}
HELP_ONLY = re.compile(r"^\S+(?:\s+\S+)?\s+(?:-h|--help|-help|help|--version|-v|-V|version)(?:\s+\S+)?\s*$", re.I)
#: An argparse usage line: `tool [-h] {BAMinput,FASTQinput,Scan} ...`. It says
#: which subcommands exist, not how to run one.
SYNOPSIS_CHOICES = re.compile(r"\{[\w-]+(?:,[\w-]+)+\}|\s\.\.\.\s*$|\[-h\]")
#: A script that installs rather than runs: STRetch's wiki opens with `./install.sh`.
INSTALLER = re.compile(r"^(?:install|setup|configure|build|bootstrap|get[-_]deps)(?:\.(?:sh|py|pl))?$", re.I)
#: A program whose NAME says it is a helper (`tandem-genotypes-merge`).
HELPER_NAME = re.compile(r"[-_](?:merge|join|plot|convert|compare|view|viz|stats|summary|install|setup|test)(?:\.\w+)?$", re.I)
IN_FLAG = re.compile(r"--?(?:bams?|crams?|fastqs?|inputs?|in|reads|i|fq|fq1|fq2|reads1|reads2)"
                     r"(?:[-_](?:file|files|dir|bam|bams|fastq))?(?![\w-])"
                     r"|\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?\b"
                     r"|(?<![\w-])[<\[]?\w*(?:fastq|fq|bam|cram|reads|input)\w*[>\]]?(?![\w-])", re.I)
OUT_FLAG = re.compile(r"--?(?:out(?:put)?(?:[-_]?\w+)?|o|str-vcf|tr-vcf|prefix|vcf-out|working_path)(?![\w])"
                      r"|\s>\s", re.I)


def command_sources(readme: str, readme_name: str | None, docs: list[dict] | None) -> list[dict]:
    """Where commands are read from, in the order a stranger reads them: the
    README, then the in-repository documents it links, then the wiki."""
    out = [{"file": readme_name or "README.md", "origin": "readme", "text": readme}]
    for d in docs or []:
        out.append({"file": d["path"], "origin": d["origin"], "text": d["text"]})
    return out


def _subcommand(text: str, prog: str) -> str | None:
    after = text.split(prog, 1)[-1].split()
    return after[0] if after and re.match(r"^[a-z][a-z0-9_-]*$", after[0]) else None


def detect_commands(readme: str, names: list[str], docs: list[dict] | None = None,
                    readme_name: str | None = None, executables: list[str] | None = None) -> list[dict]:
    """Command lines that invoke the tool, best first, each with the file and
    line it was read on."""
    cands = []
    lower_names = {n.lower() for n in names}
    lower_exes = {e.lower() for e in executables or []}
    for rank, src in enumerate(command_sources(readme, readme_name, docs)):
        rst = src["file"].lower().endswith(".rst")
        for line_no, ln in _code_lines_numbered(src["text"]):
            text = ln.strip()
            if not text or text.startswith("#"):
                continue
            # "Usage: tool [-h] ..." blocks quote the synopsis, which is still the
            # best statement of how the tool is invoked when nothing else is shown.
            text = re.sub(r"^usage:\s*", "", text, flags=re.I)
            if INSTALL_RE.search(text) and not IN_FLAG.search(text):
                continue
            # In a pipeline (`zcat x.fq.gz | str8rzr -c cfg > out`) the tool is the
            # segment named in the tree, or failing that the last one; zcat is not it.
            segments = [seg for seg in re.split(r"\s\|\s", text) if seg.strip()]
            progs = [_first_program(seg) for seg in segments]

            def _named(pr):
                if pr is None:
                    return False
                low = pr.lower()
                return (low in lower_names or low in lower_exes
                        or low.removesuffix(".py").removesuffix(".sh") in lower_names)
            prog = next((pr for pr in progs if _named(pr)), None)
            if prog is None:
                prog = next((pr for pr in reversed(progs) if pr and pr not in SHELL_NOISE), None)
            # A program is a word: "where:" heads a help listing and "-s" is an
            # option, and neither runs anything.
            if prog is None or not PROGRAM_RE.match(prog):
                continue
            words = text.split()
            idx = next((i for i, w in enumerate(words) if w.split("/")[-1] == prog), 0)
            nxt = words[idx + 1].lower().strip(",.:;") if idx + 1 < len(words) else ""
            if nxt in PROSE_NEXT and not re.search(r"(?:^|\s)--?\w", text):
                continue
            # A sentence in a list, not a command: "repeatHMM.py BAMinput: with
            # a BAM file as input". Commands do not carry three little words
            # and no option.
            small = sum(1 for w in words if w.lower() in STOPWORDS)
            if small >= 3 and not re.search(r"(?:^|\s)--?\w", text):
                continue
            named = _named(prog)
            has_in, has_out = bool(IN_FLAG.search(text)), bool(OUT_FLAG.search(text))
            # Either the program is one of the repository's own, or the line plainly
            # takes an input and writes an output (a binary the tree did not name).
            if not named and not (has_in and has_out):
                continue
            sub = _subcommand(" ".join(words[idx:]), prog)
            cands.append({
                "cmd": text,
                # Where it was read: the cite for "the documented command", and
                # what a reader opens to check the rewrite against.
                "file": src["file"],
                "origin": src["origin"],
                "line": line_no,
                "invokes": prog,
                "subcommand": sub,
                "named_in_tree": named,
                "entry_point": prog.lower() in lower_exes,
                "has_input_flag": has_in,
                "has_output_flag": has_out,
                "help_only": (bool(HELP_ONLY.match(" ".join(words[idx:]))) or (sub in HELPER_VERBS)
                              or bool(SYNOPSIS_CHOICES.search(text)) or bool(HELPER_NAME.search(prog))
                              or bool(INSTALLER.match(prog))),
                "main_verb": sub in MAIN_VERBS,
                # `zcat x.fq.gz | tool ...` documents a compressed-input variant;
                # the plain invocation is the one to rewrite for STRhub's data.
                "piped": len(segments) > 1,
                "source_rank": rank,
                "rst": rst,
            })
    # Best first: the tool's own program; not a help, drawing or conversion
    # command; the analysis verb when the tool has subcommands; an invocation
    # that names an input and an output; direct rather than behind a pipe;
    # and the README before the documents it links. Ties keep document order.
    # Input and output used to come first, and straglr got a bedtools pipeline
    # and tandem-genotypes its merge helper.
    cands.sort(key=lambda c: (not (c["named_in_tree"] or c["entry_point"]), c["help_only"],
                              not c["main_verb"],
                              # STRhub verifies STR genotyping: a tool's STR
                              # mode before its SNP mode (lusSTR strs / snps).
                              bool(re.search(r"snps?", c.get("subcommand") or "", re.I)),
                              not (c["has_input_flag"] and c["has_output_flag"]),
                              not c["has_input_flag"], c["piped"], c["source_rank"]))
    seen, uniq = set(), []
    for c in cands:
        if c["cmd"] not in seen:
            seen.add(c["cmd"]); uniq.append(c)
    # Only `tool --help` documented is no command at all: running it proves
    # the program starts, not that it does anything (FDSTools' README).
    if uniq and all(c["help_only"] for c in uniq):
        return []
    return uniq[:10]


def attach_prerequisite(commands: list[dict], tree_paths: set[str] | None = None) -> list[dict]:
    """The documented step the chosen command depends on, when there is one.

    STRling's `strling call ... $sample.bin` reads the file its `strling
    extract ... $sample.bin` writes, two lines up in the same document. A file
    the command reads that no input rule covers, named by an earlier command
    of the same program in the same document, is an intermediate: that earlier
    command runs first."""
    if not commands:
        return commands
    top = commands[0]
    reads_ext = re.compile(r"\.(?:bam|cram|sam|f(?:ast)?q|fa|fasta|fna|fai|bed|vcf|json|ini|conf|cfg|config)(?:\.gz)?$", re.I)
    toks = [t.strip("'\"") for t in top["cmd"].split()]
    tree = tree_paths or set()
    # Not the program itself (`pipeline.py`) and not a file the repository
    # ships: an intermediate is something a step WRITES.
    inter = [t for t in toks if re.search(r"\.[A-Za-z0-9]{2,6}$", t) and not reads_ext.search(t)
             and not t.startswith("-") and "/" not in t.strip("./")
             and t.split("/")[-1] != top["invokes"] and t.lstrip("./") not in tree
             and not re.search(r"\.(?:py|sh|pl|r|jl|jar)$", t, re.I)]
    for t in inter:
        for c in commands[1:]:
            if (c["file"] == top["file"] and c["line"] < top["line"] and c["invokes"] == top["invokes"]
                    and c.get("subcommand") != top.get("subcommand") and t in c["cmd"].split()):
                top = {**top, "prerequisite": {"cmd": c["cmd"], "file": c["file"], "line": c["line"],
                                               "subcommand": c.get("subcommand"), "writes": t}}
                return [top] + commands[1:]
    return commands


def prefer_input_kind(commands: list[dict], kind: str | None) -> list[dict]:
    """Among equally good commands, the one that reads the kind of data the
    run will be given: STRsearch documents `from_fastq` and `from_bam`, and a
    BAM went into `--fq1` because from_fastq came first."""
    if not kind or not commands:
        return commands
    want = {"bam": re.compile(r"\bbams?\b|\.bam\b|\bcram|from_bam|--bams?\b", re.I),
            "fastq": re.compile(r"f(?:ast)?q\b|from_fastq|--fq\d?\b", re.I)}.get(kind)
    other = {"bam": want and re.compile(r"f(?:ast)?q\b|from_fastq|--fq\d?\b", re.I),
             "fastq": want and re.compile(r"\bbams?\b|\.bam\b|from_bam|--bams?\b", re.I)}.get(kind)
    if want is None:
        return commands
    def mismatch(c):
        t = c["cmd"]
        return bool(other.search(t)) and not want.search(t)
    head = commands[0]
    peers = [c for c in commands if (c["named_in_tree"] or c["entry_point"]) == (head["named_in_tree"] or head["entry_point"])
             and c["help_only"] == head["help_only"]]
    # A tool with a reads mode and an assembly mode (vamos --read / --contig):
    # STRhub hands it reads.
    def assembly(c):
        return bool(re.search(r"--?(?:contigs?|assembly|asm)\b|\bassembl", c["cmd"], re.I)) \
            and not re.search(r"--?reads?\b", c["cmd"], re.I)
    if mismatch(head) or assembly(head):
        better = next((c for c in peers if not mismatch(c) and not assembly(c)), None)
        if better:
            return [better] + [c for c in commands if c is not better]
    return commands


# --- reading, not counting -----------------------------------------------------
# What the README STATES about input, as opposed to how often it mentions
# things. "The README suggests ont-fastq first" came out of INPUT_SIGNALS: 7
# mentions of fastq against 4 of bam, in a README that documents both and
# recommends BAM outright. A count is evidence about STRhub's guess; a
# sentence is evidence about the tool, and it carries its line.
#
# Word edges are (?<![A-Za-z0-9]) rather than \b so that `from_fastq`,
# `--bam` and `.fastq` all count as the kind they name.
_W = r"(?<![A-Za-z0-9])(?:{})(?![A-Za-z0-9])"
KIND_WORDS = {
    "bam": re.compile(_W.format(r"bams?|crams?|aligned reads|alignments?|pre-aligned"), re.I),
    "fastq": re.compile(_W.format(r"fastqs?|fqs?|raw reads"), re.I),
    "fsa": re.compile(_W.format(r"fsa|hid|electropherograms?"), re.I),
    # Inputs STRhub holds no sample of: genotype calls to post-process, and
    # raw nanopore signal. Read so the proposal can say so, not guess a BAM.
    "vcf": re.compile(_W.format(r"vcfs?|vcf files?"), re.I),
    "signal": re.compile(_W.format(r"fast5|pod5|raw signal|squiggles?"), re.I),
}
#: A sentence that is about what the tool TAKES. Cues, not mentions: "input",
#: "takes", "accepts", "-s input read dir", `--bam <file>`, `from_bam`, a line
#: under an "Input(s)" heading.
INPUT_CUE = re.compile(
    r"\binputs?\b|\btakes?\b|\baccepts?\b|\bread dir\b|\bput\b[^\n]{0,60}\bfiles?\b"
    r"|--(?:bams?|fastq|reads|in|vcfs?|fast5)\b|(?<![A-Za-z0-9])from_(?:bam|fastq)\b"
    r"|\bthe (?:bam|fastq)[- ]files?\b", re.I)
INPUT_HEADING = re.compile(r"^#{1,4}\s*inputs?\b", re.I)
RECOMMEND_CUE = re.compile(r"\btips?:|\brecommend|\bgood practice\b|\bwe suggest\b|\bprefer|"
                           r"\bbest (?:results|practice)\b|\bfaster\b|\bquicker\b", re.I)
AGAINST_CUE = re.compile(r"\b(?:do not|don'?t|not) recommend|\bnot (?:supported|intended|designed) for\b"
                         r"|\bavoid\b|\bshould not be (?:used|run)\b", re.I)
PLATFORM_WORDS = {
    "ont": re.compile(r"\b(?:oxford )?nanopore\b|\bont\b|\bminion\b|\bpromethion\b|\blong[- ]reads?\b", re.I),
    "pacbio": re.compile(r"\bpacbio\b|\bpacific biosciences\b|\bhifi\b", re.I),
    "illumina": re.compile(r"\billumina\b|\bshort[- ]reads?\b|\bmiseq\b|\bnextseq\b|\bforenseq\b|\bpowerseq\b", re.I),
    "ce": re.compile(r"\bcapillary electrophoresis\b|\bgenemapper\b", re.I),
}
#: A sentence that states what the tool is FOR — not one that merely mentions
#: a platform (an author list saying who ran the Illumina sequencing does).
PLATFORM_CUE = re.compile(r"\bdesigned\b|\bintended\b|\btakes?\b|\binputs?\b|\baccepts?\b"
                          r"|\btechnology\b|\bplatforms?\b|\bsequencing data\b|\btailored\b"
                          r"|\bspecifically\b|\boptimi[sz]ed\b|\bbuilt for\b|\bworks (?:with|on)\b"
                          r"|\bsupports?\b|\bfrom (?:\w+ ){0,3}data\b|\bgenotyping\b", re.I)
#: A sentence about where the tool CAME from, not what it is for now:
#: LongTR's README says HipSTR "was initially designed for ... Illumina" and
#: then that LongTR is "tailored ... for long reads". The first read won.
HISTORICAL = re.compile(r"\binitially\b|\boriginally\b|\bpreviously\b|\bwas (?:first )?designed\b"
                        r"|\bmodified version of\b|\bbased on\b|\bderived from\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z*(\[])")


def _sentences(readme: str):
    """(line number, sentence) for every sentence, code blocks included: a
    usage listing says what the tool takes as plainly as prose does. A line
    that packs "designed for Illumina. We do not recommend Nanopore" holds
    two statements, and they must not be read as one."""
    for no, ln in enumerate(readme.splitlines(), 1):
        t = ln.strip()
        if not t or t.startswith(("```", "~~~")):
            continue
        for sent in _SENTENCE.split(t):
            if sent.strip():
                yield no, sent.strip()


def read_input_statements(readme: str) -> dict:
    """What the README says the tool takes, recommends and runs on — each
    with the line it was read on, and nothing ranked.

    Returns {"inputs": [{kind, line, text}], "recommendation": {kind, line,
    text} | None, "platform": [{platform, line, text}], "against":
    [{platform, line, text}], "determined": bool}. `determined` is False when
    no sentence about input was found at all; the caller must then say so
    rather than fall back on a count and present the count as a reading.
    """
    inputs: dict[str, dict] = {}
    recommendation = None
    platform: list[dict] = []
    against: list[dict] = []
    under_input_heading = False
    for no, text in _sentences(readme):
        if re.match(r"^#{1,4}\s", text):
            under_input_heading = bool(INPUT_HEADING.match(text))
        shown = text[:200]
        kinds = [k for k, rx in KIND_WORDS.items() if rx.search(text)]
        if kinds and (INPUT_CUE.search(text) or under_input_heading):
            for k in kinds:
                inputs.setdefault(k, {"kind": k, "line": no, "text": shown})
        if AGAINST_CUE.search(text):
            for pl, rx in PLATFORM_WORDS.items():
                if rx.search(text) and not any(a["platform"] == pl for a in against):
                    against.append({"platform": pl, "line": no, "text": shown})
            continue  # "do not recommend X" is not a recommendation of X
        if kinds and RECOMMEND_CUE.search(text) and recommendation is None:
            recommendation = {"kind": kinds[0], "line": no, "text": shown}
        if PLATFORM_CUE.search(text):
            historical = bool(HISTORICAL.search(text))
            for pl, rx in PLATFORM_WORDS.items():
                if not rx.search(text):
                    continue
                prior = next((p for p in platform if p["platform"] == pl), None)
                if prior is None:
                    platform.append({"platform": pl, "line": no, "text": shown, "historical": historical})
                elif prior["historical"] and not historical:
                    prior.update({"line": no, "text": shown, "historical": False})
    # A platform the author advises against is not one the tool is for, even
    # if some other sentence names it.
    bad = {a["platform"] for a in against}
    platform = [p for p in platform if p["platform"] not in bad]
    # Calls to post-process and raw signal are what the tool reads only when
    # it reads no reads: HipSTR takes an optional phased-SNP VCF beside its BAMs.
    if any(k in inputs for k in ("bam", "fastq", "fsa")):
        for aux in ("vcf", "signal"):
            inputs.pop(aux, None)
        if recommendation and recommendation["kind"] in ("vcf", "signal"):
            recommendation = None
    return {"inputs": list(inputs.values()), "recommendation": recommendation,
            "platform": platform, "against": against, "determined": bool(inputs)}


def _kind_of_type(input_type: str | None) -> str | None:
    """The read container a STRhub input type hands the tool."""
    if not input_type:
        return None
    return "bam" if "bam" in input_type else ("fastq" if "fastq" in input_type else None)


def _type_for(kind: str, platform: str, ystr: bool) -> str | None:
    if kind in ("vcf", "signal"):
        # STRhub holds no genotype calls to post-process and no raw signal. A
        # type that names what the tool reads, so the proposal can say that,
        # instead of handing it Illumina reads.
        return None
    if platform == "pacbio":
        # STRhub's HiFi reads are aligned, in a BAM; there are no unaligned
        # HiFi reads to hand a tool that takes FASTQ.
        return "pacbio-hifi-bam-hg38" if kind == "bam" else None
    if kind == "fsa":
        return "ce-fsa"
    if kind == "bam":
        if platform == "ont":
            return "ont-bam-hg38"
        return "illumina-bam-hg38-y" if ystr else "illumina-bam-hg38"
    if kind == "fastq":
        return "ont-fastq" if platform == "ont" else "illumina-str-fastq"
    return None


def _stated_platform(statements: dict) -> str | None:
    """The platform the documentation says the tool is FOR now. A current
    statement beats a historical one; long reads beat Illumina. When a tool
    states both nanopore and PacBio, either dataset is a faithful reading and
    nanopore is kept first, so a tool already verified on nanopore reads is
    not moved to another dataset by this."""
    plats = [p for p in statements["platform"] if p["platform"] in ("ont", "pacbio", "illumina")]
    current = [p["platform"] for p in plats if not p.get("historical")]
    pool = current or [p["platform"] for p in plats]
    for pl in ("ont", "pacbio", "illumina"):
        if pl in pool:
            return pl
    return None


#: An option, or a redirection, that names what a command WRITES.
_WRITES = re.compile(r"^(?:>>?|--?(?:o|out|output|out[-_]?file|output[-_]?file|prefix|output[-_]?prefix|"
                     r"(?:str|tr)[-_]?vcf|vcf[-_]?out|out(?:put)?[-_]?vcf))$", re.I)


def kind_from_command(cmd: str) -> str | None:
    """What a documented command visibly takes: reads (a .bam/.cram or FASTQ
    path, or a flag that names them) or, failing those, alignments or calls
    it reads rather than writes (LAST's .maf, a .vcf)."""
    if re.search(r"\.(?:bam|cram)\b|--?(?:bams?|crams?)\b|\s-b\s+\S+\.(?:bam|cram)", cmd, re.I):
        return "bam"
    if re.search(r"\.f(?:ast)?q(?:\.gz)?\b|--(?:fastqs?|fq[12]?|reads[12]?)\b", cmd, re.I):
        return "fastq"
    toks = cmd.split()
    for i, t in enumerate(toks):
        if i and _WRITES.match(toks[i - 1]):
            continue
        if re.search(r"\.maf(?:\.gz)?$", t, re.I):
            return "maf"
        if re.search(r"\.vcf(?:\.gz)?$", t, re.I):
            return "vcf"
    return None


def detect_input_type(readme: str, examples: list[dict], docs: list[dict] | None = None,
                      command: str | None = None) -> dict:
    """Which of STRhub's input types the tool can be run as, by READING what
    the README states (read_input_statements) and only failing that by
    counting mentions — and saying which of the two it was.

    The candidates are ordered for STRhub's own use (what to try first), not
    as a claim about the author: the author's recommendation goes first when
    there is one, cited, and the rest in the order the README documents them.
    """
    hits = {k: len(rx.findall(readme)) for k, rx in INPUT_SIGNALS.items()}
    kinds = {e["kind"] for e in examples}
    statements = read_input_statements(readme)
    statements_file = None
    if not statements["determined"]:
        # The README says nothing about input; the documents it links may.
        # Each statement then cites that document, not the README. What the
        # README says the tool is FOR still stands: TRGT's README opens with
        # "from PacBio HiFi data" and its tutorial never says it again.
        for d in docs or []:
            st = read_input_statements(d["text"])
            if st["determined"]:
                readme_platform = statements["platform"]
                statements, statements_file = st, d["path"]
                if readme_platform:
                    statements = {**st, "platform": readme_platform, "platform_file": None}
                break
    ystr = hits["ystr"] >= 3
    warnings: list[str] = []
    if hits["hg19"] and not hits["hg38"]:
        warnings.append("README mentions hg19/GRCh37 only; STRhub reference BAMs are hg38")

    # What the documented command itself takes, when no sentence names reads:
    # vamos's README only says that its helper, tryvamos, reads VCFs, and
    # vamos's own command takes `-b reads.bam`.
    cmd_kind = kind_from_command(command or "")
    only_aux = statements["determined"] and all(i["kind"] in ("vcf", "signal") for i in statements["inputs"])
    not_reads = cmd_kind in ("maf", "vcf")
    if not_reads:
        # The command reads alignments or calls, whatever the README says
        # about the reads upstream of it: tandem-genotypes reads LAST's MAF,
        # and its README's "the read sequences (in fastq or fasta)" is the
        # input of the lastal step before it. Handing it reads would stage a
        # file its command never opens.
        stated = _stated_platform(statements)
        platform = stated or ("ont" if hits["ont"] > hits["illumina"] else "illumina")
        platform_how = "stated" if stated else "counted"
        ranked = []
        how = "command"
    elif cmd_kind and (not statements["determined"] or only_aux):
        stated = _stated_platform(statements)
        platform = stated or ("ont" if hits["ont"] > hits["illumina"] else "illumina")
        platform_how = "stated" if stated else "counted"
        ranked = [t for t in [_type_for(cmd_kind, platform, ystr)] if t]
        how = "command"
    elif statements["determined"]:
        # The platform the README states the tool is for; a count of platform
        # words decides only when no sentence does.
        stated = _stated_platform(statements)
        if stated:
            platform, platform_how = stated, "stated"
        else:
            platform, platform_how = ("ont" if hits["ont"] > hits["illumina"] else "illumina"), "counted"
        documented = [i["kind"] for i in statements["inputs"]]
        rec = statements["recommendation"]
        order = ([rec["kind"]] if rec and rec["kind"] in documented else []) + \
                [k for k in documented if not (rec and k == rec["kind"])]
        ranked = [t for t in (_type_for(k, platform, ystr) for k in order) if t]
        how = "read"
    else:
        # No sentence about input anywhere: the old count, and marked as such
        # so the report can say the type was guessed rather than read.
        if "bam" in kinds:
            hits["bam"] += 3
        if "fastq" in kinds:
            hits["fastq"] += 3
        if "fsa" in kinds:
            hits["ce"] += 3
        platform, platform_how = ("ont" if hits["ont"] > hits["illumina"] else "illumina"), "counted"
        ranked = []
        if hits["ce"] and hits["ce"] >= max(hits["bam"], hits["fastq"]):
            ranked.append("ce-fsa")
        if hits["bam"] or hits["fastq"]:
            first, second = ("bam", "fastq") if hits["bam"] >= hits["fastq"] else ("fastq", "bam")
            ranked += [t for t in (_type_for(first, platform, ystr), _type_for(second, platform, ystr)) if t]
        how = "counted"
    if hits["snp"] >= 5 and "illumina-snp-fastq" not in ranked:
        ranked.append("illumina-snp-fastq")
    ranked = list(dict.fromkeys(ranked))
    # What the documentation says the tool reads when STRhub holds nothing of
    # the kind: the reason a trial cannot run, in the tool's own terms.
    unsupported = None
    if not_reads:
        unsupported = {"kinds": [cmd_kind], "platform": platform}
    elif statements["determined"] and not ranked and how != "command":
        unsupported = {"kinds": [i["kind"] for i in statements["inputs"]], "platform": platform}
    return {"best": ranked[0] if ranked else None, "candidates": ranked, "signals": hits,
            "warnings": warnings, "unsupported": unsupported, "statements_file": statements_file,
            # How the answer was reached, and the sentences it rests on, so a
            # report can cite them — or say that nothing was there to cite.
            "how": how, "platform": platform, "platform_how": platform_how,
            "statements": statements}


#: Files a README names that are never what the tool writes.
NOT_OUTPUT_FILES = re.compile(r"\b(?:requirements|CMakeLists|LICENSE|README|CHANGELOG|NEWS|INSTALL|"
                              r"MANIFEST|environment|setup|package|tsconfig|version)\.(?:txt|json|csv|tsv)\b", re.I)
#: Order among equals: the format the Content gate reads best first.
OUTPUT_PRIORITY = {"vcf": 0, "tsv": 1, "csv": 2, "json": 3}


def detect_output(readme: str, commands: list[dict], docs: list[dict] | None = None) -> dict:
    """The output format the documentation describes: the README, the
    documents it links (ExpansionHunter describes its VCF and JSON outputs in
    docs/05_OutputJsonFiles.md and 06_OutputVcfFiles.md) and the commands. A
    file a README names that is not an output (requirements.txt) is not a
    vote for TSV; that is how ExpansionHunter's VCF was looked for as a table."""
    text = readme + "\n" + "\n".join(d["text"] for d in docs or []) + "\n" + "\n".join(c["cmd"] for c in commands)
    text = NOT_OUTPUT_FILES.sub(" ", text)
    scores = [(fmt, len(rx.findall(text))) for fmt, rx in OUTPUT_SIGNALS]
    scores.sort(key=lambda x: (-x[1], OUTPUT_PRIORITY.get(x[0], 9)))
    best = scores[0][0] if scores and scores[0][1] else None
    # The command writes a file with an extension: that settles it.
    if commands:
        m = re.search(r"(?:--?(?:o|out|output|tr-vcf|str-vcf|vcf)\s+|>\s*)\S+\.(vcf|tsv|csv|json)(?:\.gz)?\b",
                      commands[0]["cmd"], re.I)
        if m:
            best = m.group(1).lower()
    return {"format": best, "signals": dict(scores)}


#: Headings under which an author writes down what they already know is wrong
#: or incomplete. Their own words about their own software: the safest thing a
#: report can carry, and the thing a reader most needs when a run stops.
KNOWN_ISSUE_HEADINGS = re.compile(
    r"known[\s-]*(?:bugs?|issues?|problems?|limitations?)|limitations?|caveats?"
    r"|troubleshooting|gotchas?|warnings?", re.I)


def author_known_issues(readme: str) -> list[dict]:
    """Sections where the author documents a known bug or limitation, quoted.

    STRspy's README has a "Known bug" section saying its wrapper can exit
    without doing any work and that the user should choose the Normal version.
    STRhub read that text (it travels in readme_text) and did nothing with it,
    so a report on a run that died in that very wrapper never mentioned that
    the author had written the problem down. A quote needs no heuristic to
    justify it: it is what the author said, at the ref the report names.
    """
    out: list[dict] = []
    lines = readme.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if not m or not KNOWN_ISSUE_HEADINGS.search(m.group(2)):
            continue
        depth = len(m.group(1))
        body: list[str] = []
        for nxt in lines[i + 1:]:
            h = re.match(r"^(#{1,4})\s+", nxt)
            if h and len(h.group(1)) <= depth:
                break
            body.append(nxt)
        text = " ".join(" ".join(body).split())
        if len(text) < 20:
            continue
        # READMEs write headings with raw HTML in them (STRaitRazor's is
        # "known issues<br>") and with Markdown emphasis; neither is part of
        # the name of the section.
        heading = re.sub(r"<[^>]+>", " ", m.group(2))
        heading = re.sub(r"[*_`#]+", "", heading)
        out.append({
            "heading": " ".join(heading.split()),
            # The line number so a reader can open the README at it, and a
            # bounded quote so a long troubleshooting chapter cannot take over
            # the report.
            "line": i + 1,
            "text": text[:600],
            "truncated": len(text) > 600,
        })
        if len(out) >= 4:
            break
    return out


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
    if input_type["best"] is None and not input_type.get("unsupported"):
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
    reads_ext = DATA_EXT["bam"] + DATA_EXT["fastq"]
    for c in commands:
        tokens = [t.strip("'\"<>(),") for t in c["cmd"].replace("=", " ").split()]
        refs = [t for t in tokens if t in tree or t.lstrip("./") in tree]
        # Every file of reads the command names must be shipped: STRsearch's
        # `from_bam` reads the BAM that its `from_fastq` example WRITES, and
        # run on its own it has nothing to read.
        reads = [t for t in tokens if t.lower().endswith(reads_ext)]
        if any(t not in tree and t.lstrip("./") not in tree for t in reads):
            continue
        if any(r.lstrip("./") in example_paths for r in refs):
            return {"cmd": c["cmd"], "cwd": "/opt/tool", "source": "detected",
                    "inputs_in_repo": sorted({r.lstrip("./") for r in refs})}
    return None


#: What a source build is given besides the toolchain: compilers, the usual
#: C libraries a bioinformatics tool links (htslib's), and git over HTTPS.
BUILD_APT = ("build-essential cmake git ca-certificates curl autoconf automake libtool pkg-config "
             "zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev libssl-dev libncurses-dev")
#: GitHub over HTTPS where a build asks for SSH: a fresh environment has no
#: key, and LongTR's Makefile clones spoa as git@github.com:. The report says
#: so when a build file does it (build.ssh_urls_in).
GIT_HTTPS = ('RUN git config --global url."https://github.com/".insteadOf "git@github.com:" '
             '&& git config --global url."https://".insteadOf "git://"\n')
#: Executables the build produced, on the PATH, wherever it left them
#: (build/install/bin/ExpansionHunter, target/release/trgt, src/vamos).
EXPOSE = ("RUN find /opt/tool -xdev -type f -perm -u+x -newer /tmp/.strhub_built "
          "! -path '*/CMakeFiles/*' ! -path '*/.git/*' ! -name '*.so*' ! -name '*.a' ! -name '*.o' "
          "! -name '*.sh' ! -name '*.py' ! -name 'config.status' ! -name 'libtool' "
          "-exec ln -sf {} /usr/local/bin/ \\;\n")


def keep_path(path: str, extra: str = "") -> str:
    """ENV PATH, and the same PATH for a login shell. The run is `bash -lc`,
    and Debian's /etc/profile (micromamba, python:*-slim, rust, golang)
    resets PATH: straglr's python, in the conda environment, was "not found"
    by the very shell that ran it."""
    exports = f"export PATH={path}:$PATH" + (f"; {extra}" if extra else "")
    return (f"ENV PATH=\"{path}:$PATH\"\n"
            f"RUN echo '{exports}' > /etc/profile.d/zz-strhub-path.sh\n")


def _python_for(files: dict[str, str]) -> str:
    """3.11, or the nearest version pyproject's requires-python admits."""
    text = files.get("pyproject.toml", "") + files.get("setup.cfg", "") + files.get("setup.py", "")
    m = re.search(r"(?:requires-python|python_requires)\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not m:
        return "3.11"
    spec = m.group(1)

    def ok(v: tuple[int, int]) -> bool:
        for part in spec.split(","):
            part = part.strip()
            mm = re.match(r"(>=|<=|==|!=|~=|>|<)\s*(\d+)\.(\d+)", part)
            if not mm:
                continue
            op, want = mm.group(1), (int(mm.group(2)), int(mm.group(3)))
            if (op == ">=" and v < want) or (op == ">" and v <= want) or (op == "<" and v >= want) \
                    or (op == "<=" and v > want) or (op == "==" and v[:2] != want) \
                    or (op == "!=" and v == want) or (op == "~=" and (v < want or v[0] != want[0])):
                return False
        return True
    # 3.11 when the package admits it: the newest that still ships distutils,
    # which NanoRepeat's dependencies import. Picking the newest admitted
    # (3.12) failed a run on STRhub's choice, not the tool's.
    for v in ((3, 11), (3, 10), (3, 12), (3, 9), (3, 8)):
        if ok(v):
            return f"{v[0]}.{v[1]}"
    return "3.11"


def generate_dockerfile(slug: str, ref: str, build: dict, image_layout: bool = False,
                        files: dict[str, str] | None = None) -> str | None:
    """A pinned environment for the methods STRhub can template. None when the
    repository ships its own Dockerfile (used as-is) or nothing was detected.

    `image_layout`: this is plan B for the repository's own Dockerfile. The
    command was written for that image's layout and runs in its WORKDIR, so a
    published image stands in as it is, with nothing cloned and no WORKDIR
    moved."""
    files = files or {}
    # Only the submodule step is tolerated (many repositories have none); a
    # failed clone or checkout must fail the build. Written as `A && B && (C ||
    # true)` on purpose: `A && B && C || true` swallows A and B too, and a build
    # that carried on with an empty /opt/tool then failed at `make` with "no
    # makefile found", which read as the tool's fault.
    clone = (f"ARG TOOL_REF={ref}\nWORKDIR /opt\n"
             f"RUN git clone https://github.com/{slug}.git tool \\\n"
             f"    && cd tool && git checkout \"${{TOOL_REF}}\" \\\n"
             f"    && (git submodule update --init --recursive || true)\nWORKDIR /opt/tool\n"
             "RUN touch /tmp/.strhub_built\n")
    tail = keep_path("/opt/tool:/opt/tool/bin") + "WORKDIR /work\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n"
    head = "# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.\n"
    apt = ("RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
           "        {pkgs} \\\n    && rm -rf /var/lib/apt/lists/*\n")
    m = build["method"]
    if m == "dockerfile":
        return None
    if m == "docker_image" and image_layout:
        return head + f"FROM {build['image']}\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n"
    if m == "docker_image":
        # The image already holds the tool; the clone rides along so the
        # example leg can find the repository's own data.
        return (head + f"FROM {build['image']}\nUSER root\n"
                + "RUN (apt-get update && apt-get install -y --no-install-recommends git ca-certificates "
                "&& rm -rf /var/lib/apt/lists/*) || (apk add --no-cache git ca-certificates) || true\n"
                + clone + "WORKDIR /work\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n")
    if m == "release_binary":
        # The author's own build of this release: downloaded, checked against
        # the digest GitHub records when it records one, unpacked, and its
        # executables put on the PATH. The clone rides along for the example.
        check = ""
        if build.get("digest", "") and str(build["digest"]).startswith("sha256:"):
            check = f" && echo \"{build['digest'][7:]}  /tmp/asset\" | sha256sum -c -"
        name = build["asset"]
        unpack = ("tar -xzf /tmp/asset -C /opt/release" if name.endswith((".tar.gz", ".tgz"))
                  else "tar -xJf /tmp/asset -C /opt/release" if name.endswith(".tar.xz")
                  else "tar -xjf /tmp/asset -C /opt/release" if name.endswith((".tar.bz2", ".tbz2"))
                  else "unzip -q /tmp/asset -d /opt/release" if name.endswith(".zip")
                  else f"cp /tmp/asset /opt/release/{name} && chmod +x /opt/release/{name}")
        return (head + "FROM ubuntu:22.04\n"
                + apt.format(pkgs="git ca-certificates curl unzip xz-utils bzip2 libgomp1 zlib1g libbz2-1.0 liblzma5 libcurl4")
                + clone
                + f"RUN mkdir -p /opt/release && curl -fsSL -o /tmp/asset \"{build['url']}\"{check} \\\n"
                + f"    && {unpack} && rm /tmp/asset\n"
                + "RUN find /opt/release -type f -perm -u+x ! -name '*.so*' -exec ln -sf {} /usr/local/bin/ \\;\n"
                + tail)
    if m == "bioconda":
        return (head + "FROM mambaorg/micromamba:1.5.8\nUSER root\n"
                + apt.format(pkgs="git ca-certificates") + clone
                + f"RUN micromamba install -y -n base -c conda-forge -c bioconda {build['package']} "
                "&& micromamba clean -a -y\n"
                + keep_path("/opt/conda/bin:/opt/tool", "export CONDA_PREFIX=/opt/conda") + "WORKDIR /work\n"
                + "ENTRYPOINT [\"micromamba\", \"run\", \"-n\", \"base\", \"/bin/bash\", \"-lc\"]\n")
    if m == "conda":
        create = (f"RUN micromamba create -y -n tool -c conda-forge -c bioconda --file {build['file']} "
                  if build.get("spec_list") else f"RUN micromamba create -y -n tool -f {build['file']} ")
        # Built against the environment's own libraries: vamos's Makefile
        # includes htslib/sam.h, which conda put under the environment, not
        # where the compiler looks by default.
        # `micromamba run -n tool` leaves CONDA_PREFIX at the root prefix, and
        # vamos's Makefile compiles with -I $(CONDA_PREFIX)/include: it expects
        # the environment activated, so it is declared as such.
        env_paths = ('export CONDA_PREFIX=/opt/conda/envs/tool; '
                     'export CPATH=$CONDA_PREFIX/include:${CPATH:-} LIBRARY_PATH=$CONDA_PREFIX/lib:${LIBRARY_PATH:-} '
                     'LD_LIBRARY_PATH=$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-} PKG_CONFIG_PATH=$CONDA_PREFIX/lib/pkgconfig; ')
        then = "".join(f"RUN micromamba run -n tool bash -lc '{env_paths}{step}'\n" for step in build.get("then") or [])
        # A make or pip step on top of the environment compiles: vamos's
        # Makefile runs cmake for parasail, and the plain image had none.
        pkgs = BUILD_APT if build.get("then") else "git ca-certificates build-essential"
        # ENV_NAME: the micromamba image's own .bashrc activates "the current
        # environment" in every login shell, `base` unless told otherwise,
        # and activating base takes the tool's environment off the PATH. The
        # run is `bash -lc`: straglr's python was "not found" in the very
        # environment it was installed in.
        return (head + "FROM mambaorg/micromamba:1.5.8\nUSER root\n"
                + apt.format(pkgs=pkgs) + GIT_HTTPS + clone
                + create + "&& micromamba clean -a -y\n" + "ENV ENV_NAME=tool\n" + then
                + (EXPOSE if then else "")
                + keep_path("/opt/conda/envs/tool/bin:/opt/tool", "export CONDA_PREFIX=/opt/conda/envs/tool")
                + "WORKDIR /work\n"
                + "ENTRYPOINT [\"micromamba\", \"run\", \"-n\", \"tool\", \"/bin/bash\", \"-lc\"]\n")
    if m == "pip":
        install = ("RUN pip install --no-cache-dir -r requirements.txt\n" if build["file"] == "requirements.txt"
                   else "RUN pip install --no-cache-dir .\n")
        return (head + f"FROM python:{_python_for(files)}-slim\n"
                + apt.format(pkgs="git ca-certificates build-essential zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev")
                + GIT_HTTPS + clone + install + tail)
    if m == "cmake":
        # Out of the source tree, as every CMake project documents it
        # (`mkdir build && cd build && cmake ..`); ExpansionHunterDenovo's
        # source is in source/.
        src = build.get("dir") or "."
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs=BUILD_APT) + GIT_HTTPS + clone
                + f"RUN cmake -S {src} -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2\n"
                + EXPOSE + tail)
    if m == "make":
        where = f" -C {build['dir']}" if build.get("dir") else ""
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs=BUILD_APT) + GIT_HTTPS + clone
                + f"RUN make{where}\n" + EXPOSE + tail)
    if m == "autotools":
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs=BUILD_APT + " libgsl-dev libfftw3-dev") + GIT_HTTPS + clone
                + "RUN ([ -x ./configure ] || autoreconf -i) && ./configure && make\n" + EXPOSE + tail)
    if m == "cargo":
        return (head + "FROM rust:1-bookworm\n"
                + apt.format(pkgs="git ca-certificates cmake clang libclang-dev pkg-config libssl-dev "
                                  "zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev")
                + GIT_HTTPS + clone
                + "RUN cargo build --release\n" + EXPOSE
                + keep_path("/opt/tool/target/release:/usr/local/cargo/bin")
                + "WORKDIR /work\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n")
    if m == "go":
        return (head + "FROM golang:1.22\n" + clone + "RUN go build -o /usr/local/bin/ ./...\n" + tail)
    if m == "r":
        return (head + "FROM rocker/r-ver:4.4.1\n"
                + apt.format(pkgs="git ca-certificates libcurl4-openssl-dev libssl-dev libxml2-dev") + clone
                + "RUN R -q -e 'install.packages(\"remotes\", repos=\"https://cloud.r-project.org\"); "
                  "remotes::install_local(\".\", dependencies=TRUE, upgrade=\"never\")'\n" + tail)
    if m == "nim":
        return (head + "FROM nimlang/nim:2.0.8\n" + apt.format(pkgs="git ca-certificates libhts-dev") + GIT_HTTPS + clone
                + "RUN nimble install -y -d && nimble build -y -d:release\n" + EXPOSE + tail)
    if m == "script":
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs=BUILD_APT + " python3 python3-pip wget unzip")
                + GIT_HTTPS + clone + f"RUN bash {build['file']}\n" + EXPOSE + tail)
    if m == "readme":
        # Scripts run straight from the clone; the README's install lines are
        # left for the model or the author, since they can be anything.
        return (head + "FROM ubuntu:22.04\n" + apt.format(pkgs="git ca-certificates python3 python3-pip")
                + clone + tail)
    return None


def blob_url(slug: str, ref: str, path: str, line: int | None = None) -> str:
    """The file at the pinned ref on GitHub, at a line when there is one."""
    url = f"https://github.com/{slug}/blob/{ref}/{path}"
    return f"{url}#L{line}" if line else url


def wiki_url(slug: str, page: str) -> str:
    return f"https://github.com/{slug}/wiki/{urllib.parse.quote(page)}"


def evidence_for(slug: str, ref: str, readme: str, readme_name: str | None,
                 build: dict, commands: list[dict], examples: list[dict],
                 known_issues: list[dict], input_type: dict | None = None,
                 docs: list[dict] | None = None) -> list[dict]:
    """Every fact the proposal rests on, as data a reader can open.

    Phase B of docs/PLAN-Claims-Need-Evidence.md. The proposal already knew
    where each thing came from — the README line a command was read on, the
    file that says how to install, the paths that count as example data — and
    kept none of it: the report said "the README's own command" and a reader
    had to trust that. Each entry here is one claim, with the file, the line
    when there is one, the text as read, and the URL at the pinned ref, so
    the claim can be checked in one click and challenged when it is wrong.
    """
    readme_lines = readme.splitlines()
    rn = readme_name or "README.md"

    def readme_at(line: int, claim: str, text: str | None = None) -> dict:
        shown = text if text is not None else (readme_lines[line - 1].strip() if 0 < line <= len(readme_lines) else "")
        return {"claim": claim, "kind": "readme", "path": rn, "line": line,
                "text": shown[:300], "url": blob_url(slug, ref, rn, line)}

    out: list[dict] = []
    if build.get("file"):
        out.append({"claim": "install_method", "kind": "tree", "path": build["file"],
                    "text": build["method"], "url": blob_url(slug, ref, build["file"])})
    if build.get("method") in ("docker_image", "bioconda") and build.get("readme_line"):
        out.append(readme_at(build["readme_line"],
                             "published_image" if build["method"] == "docker_image" else "bioconda_package"))
    fb = build.get("fallback") or {}
    if fb.get("readme_line"):
        out.append(readme_at(fb["readme_line"], "fallback_environment"))
    if commands and commands[0].get("line"):
        c = commands[0]
        origin = c.get("origin", "readme")
        if origin == "readme":
            out.append(readme_at(c["line"], "run_command"))
        else:
            # Read in a document the README links (docs/…) or on the wiki: the
            # cite opens THAT file at that line. A wiki page is not versioned
            # with the code, so its URL has no commit in it, and says so.
            text = next((d["text"] for d in docs or [] if d["path"] == c["file"]), "")
            dl = text.splitlines()
            shown = dl[c["line"] - 1].strip() if 0 < c["line"] <= len(dl) else ""
            if origin == "wiki":
                page = c["file"].removeprefix("wiki/")
                out.append({"claim": "run_command", "kind": "wiki", "path": c["file"], "line": c["line"],
                            "text": shown[:300], "url": wiki_url(slug, page)})
            else:
                out.append({"claim": "run_command", "kind": "doc", "path": c["file"], "line": c["line"],
                            "text": shown[:300], "url": blob_url(slug, ref, c["file"], c["line"])})
    for e in examples[:5]:
        out.append({"claim": "example_data", "kind": "tree", "path": e["path"],
                    "text": e.get("kind", ""), "url": blob_url(slug, ref, e["path"])})
    for k in known_issues:
        out.append(readme_at(k["line"], "known_issue", text=k["heading"]))
    # What the README states about input: every documented kind, the
    # author's recommendation, and any platform the author advises against.
    st = (input_type or {}).get("statements") or {}
    seen_lines: set[tuple[str, int]] = set()
    def once(claim: str, line: int, text: str) -> None:
        # Two kinds read off one sentence are one cite, not two rows.
        if (claim, line) not in seen_lines:
            seen_lines.add((claim, line))
            out.append(readme_at(line, claim, text=text))
    for i in st.get("inputs") or []:
        once("documented_input", i["line"], i["text"])
    if st.get("recommendation"):
        r = st["recommendation"]
        once("author_recommendation", r["line"], r["text"])
    for a in st.get("against") or []:
        once("platform_advice", a["line"], a["text"])
    return out


def detect(slug: str, ref: str, tree_resp: dict, readme: str, readme_name: str | None,
           extras: dict | None = None) -> dict:
    """The proposal. `extras` is the rest of what gather() / load_snapshot()
    read: linked documents, build files, what is published elsewhere."""
    extras = extras or {}
    tree = tree_resp["tree"]
    paths = [e["path"] for e in tree]
    docs = extras.get("docs") or []
    files = extras.get("files") or {}
    pkg = packaging(files)
    docs_text = "\n".join(d["text"] for d in docs)
    build = detect_build(paths, readme, files, docs_text,
                         (extras.get("published") or {}).get("release"), slug)
    examples = detect_example_data(tree)
    names = sorted(set(tool_names(slug, tree)) | set(pkg["executables"]))
    commands = detect_commands(readme, names, docs, readme_name, pkg["executables"])
    input_type = detect_input_type(readme, examples, docs, commands[0]["cmd"] if commands else None)
    commands = attach_prerequisite(prefer_input_kind(commands, _kind_of_type(input_type.get("best"))), set(paths))
    output = detect_output(readme, commands, docs)
    rd = readme_gaps(readme_name, build, commands, input_type, output, examples)
    known = author_known_issues(readme)
    # Each known-issue quote carries the URL of the line it was read from.
    for k in known:
        k["url"] = blob_url(slug, ref, readme_name or "README.md", k["line"])
    return {
        "schema": "strhub-verified/recipe-proposal/1",
        "repo": f"https://github.com/{slug}",
        "ref": ref,
        "tree_truncated": tree_resp.get("truncated", False),
        "build": build,
        "example_data": examples,
        "tool_names": names,
        # The tree's paths travel for the rewrite: a documented file the
        # repository ships (a variant catalog) is used from where it is.
        "tree_paths": [e["path"] for e in tree if e["type"] == "blob" and not VENDOR_DIRS.search(e["path"])][:4000],
        # What the packaging declares: the executables a user types and the
        # names a registry knows the tool by.
        "packaging": pkg,
        # The coordinates in the loci files the repository ships, so the
        # proposal can tell whether a catalog's loci are in STRhub's sample.
        "shipped_loci": shipped_loci(files, loci_file_paths(tree)),
        # What is published outside the repository, documented or not: ten of
        # seventeen STR tools are on Bioconda at the exact release, and only
        # two READMEs say so. A fact for the report and for a recipe STRhub
        # writes; never the documented run's environment unless documented.
        "registry": registry_facts(extras.get("published") or {}, extras.get("tag") or "", build),
        # Documents read besides the README, and where each came from. A wiki
        # page is read as it is today: wikis are not versioned with the code.
        "docs_read": [{"path": d["path"], "origin": d["origin"]} for d in docs],
        # Configuration files a README placeholder like `configFile` can resolve
        # to; propose_manifest picks the one matching the dataset's kit.
        "config_files": sorted(e["path"] for e in tree if e["type"] == "blob"
                               and e["path"].count("/") <= 1
                               and e["path"].lower().endswith((".config", ".cfg", ".conf", ".ini"))),
        "commands": commands,
        "input_type": input_type,
        "output": output,
        "readme": rd,
        # The first part of the README travels with the proposal so the regions
        # library can read how the tool describes its regions file. Bounded.
        "readme_text": readme[:20_000],
        # What the author already wrote down as wrong or incomplete. Quoted, so
        # the report carries the author's own words rather than an inference.
        "known_issues": known,
        "readme_name": readme_name,
        # The claims above, each with the file, line and URL it rests on.
        "evidence": evidence_for(slug, ref, readme, readme_name, build, commands, examples, known, input_type,
                                 docs),
        "example": propose_example(commands, paths, examples),
        "dockerfile": generate_dockerfile(slug, ref, build, files=files),
        # Plan B, built only if the one above fails: the published environment
        # the README points at. Same layout (the clone at /opt/tool, bash
        # entrypoint), so the command and the example run unchanged on it.
        "dockerfile_fallback": (generate_dockerfile(slug, ref, build["fallback"],
                                                    image_layout=build["method"] == "dockerfile", files=files)
                                if build.get("fallback") else None),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", help="public GitHub repository URL")
    ap.add_argument("ref", nargs="?", help="commit SHA or tag")
    ap.add_argument("--offline", help="directory with tree.json + README.md (tests)")
    ap.add_argument("--json", help="write the proposal here")
    ap.add_argument("--tag", default="", help="the release tag the ref was resolved from, if any")
    args = ap.parse_args()

    if args.offline:
        src = load_snapshot(pathlib.Path(args.offline))
        slug, ref = repo_slug(src["tree_resp"]["repo"]), src["tree_resp"].get("ref", "HEAD")
    else:
        if not (args.repo and args.ref):
            ap.error("repo and ref are required unless --offline is given")
        slug, ref = repo_slug(args.repo), args.ref
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        src = gather(slug, ref, args.tag, token)

    result = detect(slug, ref, src["tree_resp"], src["readme"], src["readme_name"], extras=src)
    text = json.dumps(result, indent=2)
    if args.json:
        pathlib.Path(args.json).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
