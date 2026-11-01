"""STRhub's recipe agent: what it takes to run a tool whose documented run does not.

The documented run is the tool as it is: detect_recipe reads the repository,
the engine runs exactly that, and the badge says what happened. When it does
not run, a reviewer or a user still wants to know whether the tool CAN run and
what it took, and the author wants the list of what their documentation leaves
out. That list is the chapter "What STRhub had to do" (recipe.workarounds),
which until now somebody at STRhub had to write by hand, tool by tool.

This writes it. A model reads the repository at the pinned commit (README,
linked documents, build files, any file it asks for, documentation sites the
repository links), proposes a recipe, and every recipe it proposes is run as a
real trial on a runner; it reads what happened and tries again, up to a fixed
number of attempts. It may choose the environment, write the configuration the
documentation tells a user to write, and pass documented options. It may not
change the tool's code: that rule is enforced here, not only asked for. Each
departure from the documented steps is recorded as a workaround, with what
went wrong, and the recipe that ran is what comes out: a curated recipe, a
note under the documented result, never the badge.

    python harness/assist.py --repo https://github.com/o/tool --ref <sha> [--tag v1.2] \\
        [--max-attempts 4] [--out work/assist] [--engine-ref main]

Needs ANTHROPIC_API_KEY (the workflow reads it from the repository's secrets)
and an authenticated GitHub CLI that can dispatch verify.yml.
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402
import datasets as datasets_lib  # noqa: E402
import detect_recipe as dr  # noqa: E402
import propose_manifest as pm  # noqa: E402
import regions_library  # noqa: E402

MODEL = os.environ.get("STRHUB_ASSIST_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("STRHUB_ASSIST_EFFORT", "high")
MAX_TOKENS = 32_000
MAX_REQUESTS = 40
MAX_READS = 60
READ_CAP = 60_000          # characters of one file or page handed to the model
CONTEXT_CAP = 200_000      # characters of documentation in the opening message
RECIPE_MAX_BYTES = 60_000  # prepare.RECIPE_MAX_BYTES

SYSTEM = """\
You make a bioinformatics tool run inside STRhub Verified, a service that checks whether short tandem \
repeat (STR) genotyping tools install and run end to end from their public repository. It does not judge \
accuracy.

The tool's documented instructions were followed literally first, and they did not produce a run. Your job \
is to find the smallest set of changes to HOW the tool is installed and invoked that makes it run on \
STRhub's reference data, and to say exactly what each change is. The list of changes is the finding: it \
tells the tool's author what their documentation leaves out, and tells a user what it takes.

Rules. The first three are enforced by the harness; a recipe that breaks them is rejected before it runs.
1. Never change the tool's source code. No `sed -i`, `patch`, `git apply`, `perl -pi` or redirection into \
the repository's program files. You may: choose the base image, system packages and dependency versions; \
install a dependency the documentation forgets; write or edit a configuration file the documentation tells \
the user to write or edit; pass options the documentation or the program's own --help documents; set \
environment variables; use STRhub's data and regions files.
2. Build the pinned commit. Clone https://github.com/{slug} and check out the pinned ref (declare \
`ARG TOOL_REF=<sha>` and `git checkout "${{TOOL_REF}}"`). Using a published package or image instead is \
allowed only as a stated workaround.
3. The Dockerfile must end with `ENTRYPOINT ["/bin/bash", "-lc"]` (or `["micromamba", "run", "-n", \
"<env>", "/bin/bash", "-lc"]`): the run command is passed to it as one argument.
4. Every departure from the documented steps is a workaround: what the recipe does, instead of which \
documented step (or "not documented"), and why, citing what failed in the trial log or what a file says. \
Keep each field under 300 characters. Do not list things the documentation already says.
5. Prefer the documented route whenever it can work. Do not guess file contents: read the file.

STRhub's runtime contract (fixed, not yours to change):
- The run command executes inside the built image with bash -lc, no network, 6 GB of memory, 2 CPUs, and \
a time limit of run.timeout_minutes (at most 120).
- Inputs are mounted read-only under /data/in; the reference genome is /data/ref/hg38.fa (with .fai). \
Write every output under /data/out (or cd into /data/out first); outputs[].path are globs relative to it.
- Reference data you can choose with inputs.type:
{datasets}
- A regions file for the panel loci is staged when the manifest asks for one with \
`inputs.regions: {{library: <format>}}`: /data/in/regions.bed, or /data/in/regions.json for a JSON \
catalog. Formats: {formats}.

The manifest is YAML with: tool {{name, version}}, source {{repo, ref}} (fixed by the harness), \
environment {{dockerfile: Dockerfile, os: [ubuntu-22.04]}}, run {{cmd, timeout_minutes}}, \
inputs {{type, regions?}}, outputs [{{path, format: vcf|tsv|csv|json|text, min_records}}], and optionally \
caveats. The harness adds recipe {{origin: curated, workarounds}} from your submission; do not write it.

How to work: read what you need (read_file, list_files, fetch_doc), then submit_recipe. Each submission \
is built and run as a real trial, which takes several minutes, and you get back what happened, including \
log tails. You have a limited number of submissions; make each one count. When a trial runs \
(verdict "runs"), call finish with outcome "runs". If you cannot make it run, call finish with outcome \
"gave_up" and say what blocks it. Always end with finish.
"""

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file of the tool's repository at the pinned commit. The path must be in the tree.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path relative to the repository root."}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_files",
        "description": "List the repository's files under a directory prefix ('' for all), at most 300 paths.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"prefix": {"type": "string"}},
            "required": ["prefix"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_doc",
        "description": ("Fetch a documentation page on a site the repository's documentation links to "
                        "(its readthedocs, its project page, its wiki). Returns the page as text."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_recipe",
        "description": ("Submit a recipe. It is validated, then built and run as a real trial, and the result "
                        "comes back. Costs one of your limited attempts when it passes validation."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "manifest_yml": {"type": "string", "description": "The manifest, YAML."},
                "dockerfile": {"type": "string", "description": "The Dockerfile."},
                "workarounds": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "what": {"type": "string"},
                            "instead_of": {"type": "string"},
                            "why": {"type": "string"},
                        },
                        "required": ["what", "instead_of", "why"],
                        "additionalProperties": False,
                    },
                },
                "reasoning": {"type": "string", "description": "What you changed since the last attempt, and why."},
            },
            "required": ["manifest_yml", "dockerfile", "workarounds", "reasoning"],
            "additionalProperties": False,
        },
    },
    {
        "name": "finish",
        "description": "End the session: the tool runs, or you give up and say what blocks it.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string", "enum": ["runs", "gave_up"]},
                "summary": {"type": "string"},
                "recommendations": {"type": "array", "items": {"type": "string"},
                                    "description": "What the author could document or fix, one per item."},
            },
            "required": ["outcome", "summary", "recommendations"],
            "additionalProperties": False,
        },
    },
]

#: Files a recipe may edit in the clone: configuration, never program code.
CONFIG_FILE = re.compile(r"(?:conf|config|settings|param|options)[\w.-]*$|\.(?:conf|cfg|ini|ya?ml|json|txt|config|toml|tsv|csv)$",
                         re.I)
PATCH_CMD = re.compile(r"\bsed\s+(?:-[a-zA-Z]*i[a-zA-Z]*|--in-place)\b[^&;|\n]*|\bpatch\b\s|\bgit\s+apply\b|\bperl\s+-[a-zA-Z]*i",
                       re.I)
CODE_FILE = re.compile(r"[\w./-]+\.(?:py|c|cc|cpp|cxx|h|hpp|hh|r|pl|pm|java|nim|rs|go|jl|sh|bash|js|ts|scala|kt|rb)\b",
                       re.I)


def datasets_text() -> str:
    lines = []
    for t, d in sorted(datasets_lib.load_index().get("datasets", {}).items()):
        lib = sorted((d.get("regions_library") or {}).keys())
        lines.append(f"  - {t}: {d.get('name')}; input /data/in/{d.get('canonical_input')}"
                     + (f"; regions formats: {', '.join(lib)}" if lib else ""))
    return "\n".join(lines)


def formats_text() -> str:
    return "; ".join(f"{k} ({v['columns']})" for k, v in regions_library.FORMATS.items())


def system_prompt(slug: str) -> str:
    return SYSTEM.format(slug=slug, datasets=datasets_text(), formats=formats_text())


# --- the repository, as the model reads it --------------------------------------

class Repo:
    """What the agent can read: the snapshot gather() fetched, and on request
    any file of the tree at the pinned ref and pages on the sites the
    documentation links."""

    def __init__(self, slug: str, ref: str, src: dict, fetch=None, fetch_url=None):
        self.slug, self.ref, self.src = slug, ref, src
        self.paths = [e["path"] for e in src["tree_resp"]["tree"] if e.get("type") == "blob"]
        self._fetch = fetch or (lambda p: dr.fetch_file(slug, ref, p))
        self._fetch_url = fetch_url or _fetch_url
        text = src.get("readme", "") + "\n".join(d["text"] for d in src.get("docs") or [])
        self.hosts = {urllib.parse.urlparse(u).hostname for u in re.findall(r"https?://[^\s)\"'<>\]]+", text)} - {None}
        self.hosts |= {"github.com", "raw.githubusercontent.com"}

    def read(self, path: str) -> str:
        path = path.strip().lstrip("./")
        if path not in self.paths:
            close = [p for p in self.paths if p.endswith("/" + path) or p.split("/")[-1] == path.split("/")[-1]][:5]
            raise ValueError(f"{path} is not in the tree at {self.ref[:7]}" + (f"; did you mean {close}?" if close else ""))
        if path in (self.src.get("files") or {}):
            return self.src["files"][path][:READ_CAP]
        text = self._fetch(path)
        if text is None:
            raise ValueError(f"{path} could not be read")
        return text[:READ_CAP]

    def list(self, prefix: str) -> str:
        prefix = prefix.strip().lstrip("./")
        hits = [p for p in self.paths if p.startswith(prefix)]
        more = f"\n... and {len(hits) - 300} more" if len(hits) > 300 else ""
        return "\n".join(hits[:300]) + more

    def fetch(self, url: str) -> str:
        u = urllib.parse.urlparse(url)
        if u.scheme != "https" or not u.hostname:
            raise ValueError("only https URLs")
        if u.hostname not in self.hosts and not any(u.hostname.endswith("." + h) for h in self.hosts):
            raise ValueError(f"{u.hostname} is not a site the repository's documentation links to "
                             f"(linked: {', '.join(sorted(self.hosts))[:500]})")
        return self._fetch_url(url)[:READ_CAP]


def _fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "strhub-verified/assist"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (allow-listed hosts only)
        raw = r.read(2_000_000).decode("utf-8", "replace")
    if "<html" in raw[:2000].lower():
        # Code blocks survive as text; everything else loses its markup.
        raw = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", raw)
        raw = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|pre|h\d|tr)>", "\n", raw)
        raw = re.sub(r"<[^>]+>", "", raw)
        raw = _html.unescape(raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw


def opening_message(repo: Repo, proposal: dict, documented: dict, max_attempts: int) -> str:
    """The repository and the documented attempt, as one message: the part
    of the conversation that never changes, so it is cached once."""
    src = repo.src
    parts = [f"Tool repository: https://github.com/{repo.slug} at commit {repo.ref}"
             + (f" (release {src.get('tag')})" if src.get("tag") else "") + ".",
             f"README ({src.get('readme_name') or 'none'}):\n<readme>\n{(src.get('readme') or '')[:60_000]}\n</readme>"]
    budget = CONTEXT_CAP - len(parts[1])
    for d in src.get("docs") or []:
        chunk = f"<document path=\"{d['path']}\" origin=\"{d['origin']}\">\n{d['text'][:30_000]}\n</document>"
        if len(chunk) > budget:
            break
        parts.append(chunk)
        budget -= len(chunk)
    for p, t in (src.get("files") or {}).items():
        chunk = f"<file path=\"{p}\">\n{t[:15_000]}\n</file>"
        if len(chunk) > budget:
            break
        parts.append(chunk)
        budget -= len(chunk)
    tree = repo.list("")
    parts.append(f"<tree>\n{tree[:40_000]}\n</tree>")
    parts.append("The documented attempt (read off the repository by STRhub, run literally):\n"
                 f"<manifest>\n{documented['recipe']['manifest_yml']}\n</manifest>\n"
                 f"<dockerfile>\n{documented['recipe']['dockerfile']}\n</dockerfile>\n"
                 f"<result>\n{json.dumps(documented['result'], indent=1)}\n</result>")
    parts.append(f"You have {max_attempts} submissions. Make the tool run on STRhub's data, with as few "
                 "departures from the documentation as possible, and list each one.")
    return "\n\n".join(parts)


# --- recipes --------------------------------------------------------------------

def validate(manifest_yml: str, dockerfile: str, repo: Repo, catalogue_slug: str,
             workarounds: list[dict], tag: str) -> tuple[dict | None, str]:
    """(recipe, "") or (None, why). The recipe is what a trial is handed:
    {manifest_yml, dockerfile, regions_bed?}, with the harness's own fields
    (source, recipe, report slug, submission) set here, not by the model."""
    try:
        m = yaml.safe_load(manifest_yml)
    except yaml.YAMLError as e:
        return None, f"manifest_yml is not valid YAML: {e}"
    if not isinstance(m, dict):
        return None, "manifest_yml must be a YAML mapping"
    for key in ("tool", "environment", "run", "outputs"):
        if key not in m:
            return None, f"manifest_yml has no `{key}`"
    if not (m.get("run") or {}).get("cmd"):
        return None, "run.cmd is empty"
    # Rule 1: no change to the tool's code.
    for ln in dockerfile.splitlines():
        for hit in PATCH_CMD.finditer(ln):
            targets = CODE_FILE.findall(ln[hit.start():])
            code = [t for t in targets if not CONFIG_FILE.search(t)]
            if hit.group(0).lower().startswith(("patch", "git apply")) or code:
                return None, (f"Rule 1: the recipe may not change the tool's source code; this line does: "
                              f"{ln.strip()[:200]}")
        m_redir = re.search(r">>?\s*(\S*\.(?:py|c|cpp|h|r|pl|nim|rs|go|java))\b", ln, re.I)
        if m_redir and "/data/out" not in ln and not CONFIG_FILE.search(m_redir.group(1)):
            return None, f"Rule 1: the recipe may not write into the tool's program files: {ln.strip()[:200]}"
    # Rule 2: the pinned commit.
    if repo.ref not in dockerfile and "TOOL_REF" not in dockerfile:
        return None, f"Rule 2: the Dockerfile must build the pinned commit {repo.ref} (ARG TOOL_REF)"
    # Rule 3: the entrypoint the run command is handed to.
    if not re.search(r'ENTRYPOINT\s*\[\s*"(?:/bin/bash|micromamba)"[^\]]*"-lc"\s*\]', dockerfile):
        return None, 'Rule 3: the Dockerfile must end with ENTRYPOINT ["/bin/bash", "-lc"] (or the micromamba form)'
    for w in workarounds:
        for k in ("what", "instead_of", "why"):
            w[k] = " ".join(str(w.get(k, "")).split())[:300]
    it = (m.get("inputs") or {}).get("type")
    if it and not datasets_lib.resolve(it):
        return None, f"inputs.type {it!r} is not one of STRhub's datasets"
    lib = ((m.get("inputs") or {}).get("regions") or {})
    if isinstance(lib, dict) and lib.get("library") and not regions_library.library_path(it or "", lib["library"]):
        return None, f"no {lib['library']!r} regions file for {it!r}"
    # The harness's fields.
    m["source"] = {"repo": f"https://github.com/{repo.slug}", "ref": repo.ref}
    m["submission"] = {"by": "third_party"}
    m["report"] = {"slug": catalogue_slug}
    m["recipe"] = {"origin": "curated", "workarounds": workarounds}
    m.setdefault("tool", {})
    m["tool"].setdefault("version", tag or repo.ref[:7])
    m["environment"] = {**(m.get("environment") or {}), "dockerfile": "Dockerfile"}
    m["environment"].setdefault("os", ["ubuntu-22.04"])
    header = ("# STRhub Verified recipe, written by STRhub's recipe agent (harness/assist.py) after the\n"
              "# documented instructions did not run. Curated: a note under the documented result,\n"
              "# never the badge. Every departure from the documentation is under recipe.workarounds.\n")
    recipe = {"manifest_yml": header + yaml.safe_dump(m, sort_keys=False, allow_unicode=True, width=1000),
              "dockerfile": dockerfile}
    size = len(json.dumps(recipe))
    if size > RECIPE_MAX_BYTES:
        return None, f"the recipe is {size} bytes; the limit is {RECIPE_MAX_BYTES}"
    # The schema the trial will hold it to, before a trial is spent on it.
    with tempfile.TemporaryDirectory() as d:
        mp = pathlib.Path(d) / "manifest.yml"
        mp.write_text(recipe["manifest_yml"])
        try:
            _manifest.load(str(mp))
        except Exception as e:  # noqa: BLE001 — the schema's message is the answer
            return None, f"the manifest does not pass STRhub's schema: {str(e).splitlines()[0][:400]}"
    return recipe, ""


def summarize(report: dict, logs: dict[str, str], run_url: str) -> dict:
    """What a trial did, for the model: the verdict, the gates, the
    diagnoses, and the tails of the logs that matter."""
    v = report.get("verdict") or {}
    g = report.get("gates") or {}
    out = {"run": run_url, "verdict": v.get("code"), "reason": v.get("reason"), "level": report.get("level"),
           "gates": g}
    inst = report.get("install_detail") or {}
    if inst.get("diagnostics"):
        out["install_diagnostics"] = [f"{i['id']}: {i.get('title')}" for i in inst["diagnostics"]][:6]
    diags = report.get("diagnostics") or {}
    if diags:
        out["run_diagnostics"] = {leg: [f"{i['id']}: {i.get('title')}" for i in issues][:6]
                                  for leg, issues in diags.items()}
    for key in ("io_detail", "content_detail"):
        if report.get(key):
            out[key] = json.dumps(report[key])[:1500]
    if not g.get("installs") and logs.get("build"):
        out["build_log_tail"] = "\n".join(logs["build"].splitlines()[-80:])[-8000:]
    for leg in ("external", "own", "starts"):
        if logs.get(leg) and (not g.get("runs") or not g.get("io")):
            out[f"{leg}_log_tail"] = "\n".join(logs[leg].splitlines()[-60:])[-6000:]
    return out


# --- trials on the runner -------------------------------------------------------

class GitHubTrials:
    """Run a recipe as an unpublished trial of verify.yml and read the result.
    A trial handed a recipe never publishes, whatever it finds."""

    def __init__(self, engine_ref: str = "main", run_id: str = "", poll: float = 30.0, timeout: float = 3600.0):
        self.engine_ref, self.run_id, self.poll, self.timeout = engine_ref, run_id or str(int(time.time())), poll, timeout

    def run(self, recipe: dict, tool: str, attempt: int) -> dict:
        b64 = base64.b64encode(json.dumps(recipe).encode()).decode()
        dispatch_id = f"assist_{self.run_id}_{attempt}"
        subprocess.run(["gh", "workflow", "run", "verify.yml", "--ref", self.engine_ref,
                        "-f", f"tool={tool}", "-f", "mode=trial", "-f", f"recipe={b64}",
                        "-f", "publish=false", "-f", f"dispatch_id={dispatch_id}"], check=True)
        run = self._wait(dispatch_id)
        url = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'Tfronta/strhub-verified')}/actions/runs/{run}"
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["gh", "run", "download", str(run), "-D", d], capture_output=True, text=True)
            reports = [p for p in pathlib.Path(d).rglob("*.json")
                       if not p.name.endswith((".badge.json", ".recipe.json"))]
            if not reports:
                return {"run": url, "verdict": None, "reason": "the trial produced no report (see the run)"}
            report = json.loads(reports[0].read_text())
            logs = {}
            for p in pathlib.Path(d).rglob("*.log-*.txt"):
                logs[p.name.rsplit(".log-", 1)[1].removesuffix(".txt")] = p.read_text(errors="replace")
        return summarize(report, logs, url)

    def _wait(self, dispatch_id: str) -> int:
        deadline = time.time() + self.timeout
        run_id = None
        while time.time() < deadline:
            out = subprocess.run(["gh", "run", "list", "--workflow", "verify.yml", "-L", "50", "--json",
                                  "databaseId,displayTitle,status"], capture_output=True, text=True)
            for r in json.loads(out.stdout or "[]"):
                if f"[{dispatch_id}]" in r["displayTitle"]:
                    run_id = r["databaseId"]
                    if r["status"] == "completed":
                        return run_id
            time.sleep(self.poll)
        raise TimeoutError(f"trial {dispatch_id} did not finish (run {run_id})")


# --- the loop -------------------------------------------------------------------

class Agent:
    def __init__(self, client, trials, repo: Repo, proposal: dict, documented: dict, catalogue_slug: str,
                 tag: str = "", max_attempts: int = 4, model: str = MODEL, log=print):
        self.client, self.trials, self.repo = client, trials, repo
        self.proposal, self.documented, self.slug, self.tag = proposal, documented, catalogue_slug, tag
        self.max_attempts, self.model, self.log = max_attempts, model, log
        self.attempts: list[dict] = []
        self.reads = 0
        self.finish: dict | None = None
        self.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "requests": 0}

    def _request(self, messages: list) -> object:
        # The system prompt and the tools never change within a session, and
        # carry an explicit one-hour breakpoint; the conversation after them
        # is cached by the automatic breakpoint. One hour: a trial takes
        # several minutes between one request and the next.
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system_prompt(self.repo.slug),
                     "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral", "ttl": "1h"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        u = getattr(msg, "usage", None)
        if u is not None:
            self.usage["input"] += getattr(u, "input_tokens", 0) or 0
            self.usage["output"] += getattr(u, "output_tokens", 0) or 0
            self.usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            self.usage["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.usage["requests"] += 1
        return msg

    def _tool(self, name: str, args: dict) -> tuple[str, bool]:
        if name in ("read_file", "list_files", "fetch_doc"):
            self.reads += 1
            if self.reads > MAX_READS:
                return "Read budget exhausted: submit a recipe or finish.", True
            try:
                if name == "read_file":
                    return self.repo.read(args["path"]), False
                if name == "list_files":
                    return self.repo.list(args["prefix"]) or "(nothing under that prefix)", False
                return self.repo.fetch(args["url"]), False
            except Exception as e:  # noqa: BLE001 — a failed read is an answer, not a crash
                return f"Error: {e}", True
        if name == "submit_recipe":
            if len(self.attempts) >= self.max_attempts:
                return "No submissions left. Call finish.", True
            recipe, why = validate(args["manifest_yml"], args["dockerfile"], self.repo, self.slug,
                                   list(args.get("workarounds") or []), self.tag)
            if recipe is None:
                return f"Rejected before running (no attempt used): {why}", True
            n = len(self.attempts) + 1
            self.log(f"attempt {n}: running a trial")
            result = self.trials.run(recipe, f"assist-{self.slug}", n)
            self.attempts.append({"n": n, "recipe": recipe, "workarounds": args.get("workarounds") or [],
                                  "reasoning": args.get("reasoning", ""), "result": result})
            left = self.max_attempts - len(self.attempts)
            head = ("SUCCESS: the tool ran. Call finish with outcome \"runs\"." if result.get("verdict") == "runs"
                    else f"The trial did not run to the end. {left} submission(s) left.")
            return head + "\n" + json.dumps(result, indent=1), False
        if name == "finish":
            self.finish = dict(args)
            return "Finished.", False
        return f"Unknown tool {name}", True

    def run(self) -> dict:
        messages = [{"role": "user", "content": opening_message(self.repo, self.proposal, self.documented,
                                                                  self.max_attempts)}]
        stop = "max_requests"
        for _ in range(MAX_REQUESTS):
            msg = self._request(messages)
            # Appended exactly as it came back (thinking blocks included):
            # the history is never edited, only extended.
            messages.append({"role": "assistant", "content": msg.content})
            if msg.stop_reason == "refusal":
                stop = "refusal"
                break
            uses = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
            if not uses:
                if self.finish is None:
                    messages.append({"role": "user", "content": "Use the tools: submit a recipe, or call finish."})
                    continue
                stop = "finished"
                break
            results = []
            for b in uses:
                if msg.stop_reason == "max_tokens":
                    results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                    "content": "Your response was cut off at the token limit; send it again, shorter."})
                    continue
                text, err = self._tool(b.name, dict(b.input))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": text,
                                **({"is_error": True} if err else {})})
            messages.append({"role": "user", "content": results})
            if self.finish is not None:
                stop = "finished"
                break
        ran = next((a for a in reversed(self.attempts) if (a["result"] or {}).get("verdict") == "runs"), None)
        return {
            "schema": "strhub-verified/assist/1",
            "repo": f"https://github.com/{self.repo.slug}", "ref": self.repo.ref, "slug": self.slug,
            "model": self.model, "stop": stop, "success": ran is not None,
            "finish": self.finish, "attempts": self.attempts, "usage": self.usage,
            "recipe": ran["recipe"] if ran else None,
            "workarounds": ran["workarounds"] if ran else [],
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--max-attempts", type=int, default=4)
    ap.add_argument("--engine-ref", default="main")
    ap.add_argument("--out", default="work/assist")
    args = ap.parse_args()
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise SystemExit("::error::no Anthropic credential: add ANTHROPIC_API_KEY to the repository's secrets")
    import anthropic

    slug = dr.repo_slug(args.repo)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    src = dr.gather(slug, args.ref, args.tag, token)
    proposal = dr.detect(slug, args.ref, src["tree_resp"], src["readme"], src["readme_name"], extras=src)
    built = pm.build(proposal, f"assist-{slug.split('/')[-1].lower()}", ref_label=args.tag)
    catalogue_slug = built["manifest"]["report"]["slug"]
    trials = GitHubTrials(args.engine_ref, os.environ.get("GITHUB_RUN_ID", ""))
    documented_recipe = {"manifest_yml": built["manifest_yml"], "dockerfile": built["dockerfile"]}
    if built.get("dockerfile_fallback"):
        documented_recipe["dockerfile_fallback"] = built["dockerfile_fallback"]
    print("attempt 0: the documented recipe")
    documented = {"recipe": documented_recipe,
                  "result": trials.run(documented_recipe, f"assist-{catalogue_slug}", 0)}
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if documented["result"].get("verdict") == "runs":
        result = {"schema": "strhub-verified/assist/1", "repo": args.repo, "ref": args.ref, "slug": catalogue_slug,
                  "stop": "documented_runs", "success": False, "attempts": [], "documented": documented,
                  "finish": {"outcome": "runs", "summary": "The documented recipe runs; nothing to assist.",
                             "recommendations": []}}
    else:
        agent = Agent(anthropic.Anthropic(), trials, Repo(slug, args.ref, src), proposal, documented,
                      catalogue_slug, args.tag, args.max_attempts)
        result = agent.run()
        result["documented"] = documented
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str))
    if result.get("recipe"):
        d = out / "tools" / catalogue_slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.yml").write_text(result["recipe"]["manifest_yml"])
        (d / "Dockerfile").write_text(result["recipe"]["dockerfile"])
    print(json.dumps({k: result.get(k) for k in ("slug", "stop", "success")} | {"usage": result.get("usage")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
