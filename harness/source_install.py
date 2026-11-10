"""A closed installation transcript, never a tool-specific environment generator.

Profile 1 supports one complete, literal Ubuntu 22.04 installation block:
APT update, noninteractive APT install, and root make. Missing steps, prose
assembly, alternative blocks and other operating systems remain unsupported.
No package, compiler option, environment variable or retry is inferred.
"""
from __future__ import annotations

import hashlib
import json
import re

PROFILE = "strhub-source-install/1"
BASE_IMAGE = "ubuntu:22.04"
HEADING = re.compile(r"^(#{1,6})\s+(?:Install(?:ation)?|Build|Compilation)\s+"
                     r"(?:(?:on|for)\s+)?\(?Ubuntu 22\.04\)?\s*:?\s*$", re.I)
PACKAGE = re.compile(r"[a-z0-9][a-z0-9.+-]*(?::[a-z0-9]+)?(?:=[A-Za-z0-9.+:~_-]+)?\Z")
INSTALL_OPTIONS = {"-y", "--yes", "--no-install-recommends"}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sections(text: str) -> list[dict]:
    """Only an explicitly scoped section; never concatenate separate blocks."""
    lines = text.splitlines()
    sections = []
    fence = None
    for i, line in enumerate(lines):
        marker = re.match(r"^(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]))
            continue
        heading = HEADING.fullmatch(line)
        if not heading:
            continue
        end = i + 1
        section_fence = None
        while end < len(lines):
            row = lines[end]
            if not section_fence and re.match(r"^#{1," + str(len(heading[1])) + r"}\s", row):
                break
            marker = re.match(r"^(`{3,}|~{3,})(.*)$", row)
            if marker:
                if not section_fence:
                    section_fence = (marker[1][0], len(marker[1]))
                elif marker[1][0] == section_fence[0] and len(marker[1]) >= section_fence[1] and not marker[2].strip():
                    section_fence = None
            end += 1
        sections.append({"heading": line, "heading_line": i + 1,
                         "rows": [(n + 1, lines[n]) for n in range(i + 1, end)]})
    return sections


def _commands(section: dict) -> list[dict] | None:
    rows = list(section["rows"])
    while rows and not rows[0][1].strip():
        rows.pop(0)
    while rows and not rows[-1][1].strip():
        rows.pop()
    # No surrounding prose, headings, shell continuations or second block.
    if len(rows) != 5 or rows[0][1] not in ("```sh", "```bash", "```shell") or rows[-1][1] != "```":
        return None
    commands = [{"line": n, "text": raw, "argv": raw.split()} for n, raw in rows[1:-1]]
    update, install, build = [c["argv"] for c in commands]
    if update not in (["apt", "update"], ["apt-get", "update"]) or build != ["make"]:
        return None
    if install[:2] not in (["apt", "install"], ["apt-get", "install"]):
        return None
    options, packages = [], []
    for token in install[2:]:
        if token.startswith("-"):
            if packages or token not in INSTALL_OPTIONS or token in options:
                return None
            options.append(token)
        elif PACKAGE.fullmatch(token):
            packages.append(token)
        else:
            return None
    # Never add -y or pipe 'yes' to make an interactive command fit Docker.
    if len(set(options) & {"-y", "--yes"}) != 1 or not packages:
        return None
    if len(set(packages)) != len(packages) or "make" not in {p.split("=", 1)[0].split(":", 1)[0] for p in packages}:
        return None
    # Recognize only plain commands; quoted words, operators and whitespace
    # transformations are not silently interpreted as the same invocation.
    if any(c["text"] != " ".join(c["argv"]) for c in commands):
        return None
    return commands


def carrier(commands: list[dict]) -> str:
    """A fixed evaluator envelope around the literal, cited argv sequence."""
    lines = ["# Evaluator carrier: strhub-source-install/1; not an upstream Dockerfile.",
             "FROM " + BASE_IMAGE, 'COPY [".", "/opt/tool"]', "WORKDIR /opt/tool"]
    lines += ["RUN " + json.dumps(command["argv"]) for command in commands]
    # A source install has no upstream image entrypoint to replace. This shell
    # transports the independently reviewed command and existing capture wrapper.
    lines.append('ENTRYPOINT ["/bin/bash", "-lc"]')
    return "\n".join(lines) + "\n"


def discover(proposal: dict) -> dict:
    result = {"profile": PROFILE, "ready": False, "method": "make",
              "reason": "No single complete literal installation block is supported by the source-installation profile; no missing steps or dependencies were supplied."}
    if not re.fullmatch(r"[0-9a-f]{40}", str(proposal.get("ref") or "")) or not proposal.get("repo"):
        return result
    if (proposal.get("build") or {}).get("method") != "make" or proposal.get("tree_truncated"):
        return result
    paths = set(proposal.get("tree_paths") or [])
    if paths & {".gitmodules", ".dockerignore", "GNUmakefile"}:
        return result
    makefiles = paths & {"Makefile", "makefile"}
    if len(makefiles) != 1:
        return result
    makefile = next(iter(makefiles))
    text = (proposal.get("upstream_files") or {}).get(makefile)
    if not isinstance(text, str) or not text.strip():
        return result
    sections = []
    for doc in proposal.get("source_documents") or []:
        if doc.get("origin") == "wiki" or not isinstance(doc.get("text"), str) or not doc.get("file"):
            continue
        if "<!--" in doc["text"] or "-->" in doc["text"]:
            continue
        sections += [(doc, section) for section in _sections(doc["text"])]
    if len(sections) != 1:
        return result
    doc, section = sections[0]
    commands = _commands(section)
    if not commands:
        return result
    dockerfile = carrier(commands)
    result.update(ready=True, repo=proposal["repo"], ref=proposal["ref"],
                  source_file=makefile, makefile_sha256=digest(text),
                  base_condition={"image": BASE_IMAGE, "heading": section["heading"],
                                  "line": section["heading_line"], "role": "documented operating-system condition"},
                  citation={"repo": proposal["repo"], "ref": proposal["ref"], "path": doc["file"],
                            "line": commands[0]["line"], "end_line": commands[-1]["line"],
                            "verified": True, "document_sha256": digest(doc["text"])},
                  commands=commands, carrier_dockerfile=dockerfile, carrier_sha256=digest(dockerfile),
                  reason="Transcribe the single cited installation sequence unchanged into a fixed evaluator carrier on its explicitly named operating system; no tool-specific choices or added install commands.")
    return result


def installation(proposal: dict, manifest: dict) -> dict:
    result = discover(proposal)
    expected_env = {"source": "documented", "dockerfile": "Dockerfile", "os": ["ubuntu-22.04"]}
    if manifest.get("environment") != expected_env or manifest.get("source") != {
            "repo": proposal.get("repo"), "ref": proposal.get("ref")}:
        return {"profile": PROFILE, "ready": False, "method": "make",
                "reason": "The effective manifest does not match the cited source-installation plan."}
    return result


def verify_checkout(root, install: dict) -> None:
    """Re-derive the plan from actual source bytes, not a saved ready flag."""
    import _paths
    if not install.get("ready") or install.get("profile") != PROFILE:
        raise ValueError("no proven source installation")
    if any((root / name).exists() or (root / name).is_symlink()
           for name in (".gitmodules", ".dockerignore", "GNUmakefile")):
        raise ValueError("source installation context is outside the supported profile")
    citation = install.get("citation") or {}
    document = _paths.confined(root, citation.get("path"))
    makefile = _paths.confined(root, install.get("source_file"))
    if hashlib.sha256(document.read_bytes()).hexdigest() != citation.get("document_sha256"):
        raise ValueError("upstream evidence differs at pinned checkout: installation document")
    if hashlib.sha256(makefile.read_bytes()).hexdigest() != install.get("makefile_sha256"):
        raise ValueError("upstream evidence differs at pinned checkout: Makefile")
    # Enumerate actual names: on a case-insensitive host both spellings may
    # appear to exist even when the pinned tree contains exactly one file.
    actual_makefiles = [entry.name for entry in root.iterdir() if entry.name in ("Makefile", "makefile")]
    proposal = {"repo": install.get("repo"), "ref": install.get("ref"), "build": {"method": "make"},
                "tree_paths": actual_makefiles,
                "upstream_files": {install["source_file"]: makefile.read_bytes().decode("utf-8")},
                "source_documents": [{"file": citation["path"], "origin": "repo",
                                      "text": document.read_bytes().decode("utf-8")} ]}
    # Compare every field, including command values/order and carrier bytes.
    if discover(proposal) != install:
        raise ValueError("source installation plan does not match its upstream evidence")


def materialise(root, install: dict, destination) -> None:
    verify_checkout(root, install)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(install["carrier_dockerfile"])
    if hashlib.sha256(destination.read_bytes()).hexdigest() != install["carrier_sha256"]:
        raise ValueError("source installation carrier digest mismatch")
