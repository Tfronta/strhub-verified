"""Conservative, read-only comparison with a pinned upstream procedure.

This is a closed substitution profile, not a shell equivalence prover. A
construct we cannot establish is an evaluator limitation; it is never repaired.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex

import datasets as datasets_lib

PROFILE = "strhub-upstream-procedure/1"
TOKEN = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"|<[^<>\n]+>|[^\s'\";&|<>()]+|[;&|<>()]+")
INPUT_FLAGS = {"--in", "--input", "--bam", "--bams", "--reads", "--fastq", "-i", "-b"}
REFERENCE_FLAGS = {"--ref", "--reference", "--fasta", "--genome"}
OUTPUT_FLAGS = {"--out", "--output", "--output-prefix", "--out-dir", "-o"}
READ_PATH = re.compile(r"[\w./-]+\.(?:bam|cram|f(?:ast)?q)(?:\.gz)?\Z", re.I)
REF_PATH = re.compile(r"[\w./-]+\.(?:fa|fasta|fna)(?:\.gz)?\Z", re.I)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def literal_lines(text: str) -> list[tuple[int, str]]:
    """Only explicit unquoted shell continuations, never inferred flag lines."""
    result = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        line = re.sub(r"^\$ ", "", line)
        if result and result[-1][1].endswith("\\") and all(result[-1][1].count(q) % 2 == 0 for q in "'\""):
            start, previous = result.pop()
            result.append((start, previous[:-1].rstrip() + " " + line))
        else:
            result.append((number, line))
    return result


def tokens(command: str) -> list[str]:
    matches = list(TOKEN.finditer(command))
    end = 0
    for m in matches:
        if command[end:m.start()].strip():
            raise ValueError("unrecognized shell quoting")
        end = m.end()
    if command[end:].strip():
        raise ValueError("unrecognized shell quoting")
    return [m.group() for m in matches]


def rewrite(command: str, input_type: str | None) -> dict:
    """Only standalone read/reference paths and explicit output placeholders.

    No executable changes, defaults, config selection, region conversion,
    list reduction, synopsis expansion, shell-variable filling or mkdir.
    The original quoting, operators and whitespace are otherwise preserved.
    """
    result = {"profile": PROFILE, "cited": command, "command": command,
              "substitutions": [], "read_bindings": [], "limitations": []}
    if (re.search(r"[$`#\\\n\r*?{}]", command) or re.search(r"\[\s*--?", command)
            or re.search(r"\.\.\.|…", command)):
        result["limitations"].append("shell expansion or synopsis is outside the substitution profile")
        return result
    try:
        toks = tokens(command)
    except ValueError as exc:
        result["limitations"].append(str(exc))
        return result
    ds = datasets_lib.resolve(input_type) if input_type else None
    canonical = (ds or {}).get("canonical_input")
    reference = ((ds or {}).get("reference_genome") or {}).get("mount_path")
    changes = []
    for i, m in enumerate(TOKEN.finditer(command)):
        raw = m.group()
        # Only whole arguments, never a substring of another value or assignment.
        if (m.start() and not command[m.start() - 1].isspace()) or (m.end() < len(command) and not command[m.end()].isspace()):
            continue
        value = raw[1:-1] if len(raw) > 1 and raw[0] == raw[-1] and raw[0] in "'\"" else raw
        previous = toks[i - 1] if i else ""
        target, role = None, None
        angle = value.startswith("<") and value.endswith(">")
        read_placeholder = angle and bool(re.search(r"bam|cram|fastq|reads|input", value, re.I))
        ref_placeholder = angle and bool(re.search(r"fasta|reference|genome", value, re.I))
        if previous in INPUT_FLAGS and canonical and (READ_PATH.fullmatch(value) or read_placeholder):
            kind = lambda path: "fastq" if re.search(r"\.f(?:ast)?q(?:\.gz)?$", path, re.I) else "cram" if re.search(r"\.cram(?:\.gz)?$", path, re.I) else "bam"
            compatible = (not READ_PATH.fullmatch(value) or
                          (kind(value) == kind(canonical) and value.endswith(".gz") == canonical.endswith(".gz")))
            if angle:
                names = re.findall(r"bam|cram|fastq", value, re.I)
                compatible = not names or kind(canonical) in [n.lower() for n in names]
            if compatible:
                target, role = f"/data/in/{canonical}", "read_path"
            else:
                result["limitations"].append("the declared sample does not have the documented read-file kind")
        elif previous in INPUT_FLAGS and "," in value:
            result["limitations"].append("input list cardinality is not changed to fit one available sample")
        elif previous in REFERENCE_FLAGS and reference and (REF_PATH.fullmatch(value) or ref_placeholder):
            if not REF_PATH.fullmatch(value) or value.endswith(".gz") == reference.endswith(".gz"):
                target, role = reference, "reference_path"
            else:
                result["limitations"].append("reference compression was not changed to fit the available file")
        elif previous in OUTPUT_FLAGS and angle and re.search(r"output|prefix|directory", value, re.I):
            target, role = "sample", "output_placeholder"
        elif i and previous not in OUTPUT_FLAGS and READ_PATH.fullmatch(value) and value != f"/data/in/{canonical}":
            result["limitations"].append("a read-file argument is outside the closed input substitution table")
        if target and role == "read_path":
            result["read_bindings"].append({"token": i, "original": raw, "target": target})
        if target and target != value:
            replacement = raw[0] + target + raw[-1] if raw[0] in "'\"" else target
            changes.append((m.start(), m.end(), replacement))
            result["substitutions"].append({"token": i, "original": raw,
                "replacement": replacement, "role": role, "basis": "declared dataset mount" if role != "output_placeholder" else "explicit output-path placeholder"})
    rewritten = command
    for start, end, value in reversed(changes):
        rewritten = rewritten[:start] + value + rewritten[end:]
    result["command"] = rewritten
    if re.search(r"<[^<>]+>|\b(?:configFile|fastqfile)\b", rewritten, re.I):
        result["limitations"].append("unresolved placeholder; no value was invented")
    return result


def cite(proposal: dict, candidate: dict) -> dict:
    """Bind a complete command to its source line, rather than a 300-char quote."""
    source = {"repo": proposal.get("repo"), "ref": proposal.get("ref")}
    out = {"repo": source.get("repo"), "ref": source.get("ref"),
           "path": candidate.get("file"), "line": candidate.get("line"), "verified": False}
    if not re.fullmatch(r"[0-9a-f]{40}", str(source.get("ref") or "")):
        out["reason"] = "upstream ref is not a full immutable commit"
        return out
    for doc in proposal.get("source_documents") or []:
        if doc.get("file") != candidate.get("file") or doc.get("origin") == "wiki":
            continue
        # Unlike discovery, never join separate flag lines or strip a synopsis.
        text = doc.get("text") or ""
        if any(n == candidate.get("line") and line.strip() == candidate.get("cmd")
               for n, line in literal_lines(text)):
            out.update(verified=True, document_sha256=digest(text), command_sha256=digest(candidate["cmd"]))
            return out
    out["reason"] = "the complete command is not established at the cited repository line"
    return out


def installation(proposal: dict, manifest: dict) -> dict:
    """Review an upstream Dockerfile or a separately versioned source transcript.

    A Makefile, package name or release link alone is discovery evidence, not proof
    of every dependency, compiler option and environment setting we might add.
    """
    env, build = manifest.get("environment") or {}, proposal.get("build") or {}
    if env.get("source") == "documented":
        import source_install
        return source_install.installation(proposal, manifest)
    ready = (env.get("source") == "repository" and build.get("method") == "dockerfile"
             and bool(env.get("from_repo")) and env.get("from_repo") == build.get("file")
             and re.fullmatch(r"[0-9a-f]{40}", str(proposal.get("ref") or ""))
             and (manifest.get("source") or {}).get("ref") == proposal.get("ref")
             and (manifest.get("source") or {}).get("repo") == proposal.get("repo"))
    result = {"profile": PROFILE, "ready": False, "method": build.get("method", "unknown"),
            "source_file": env.get("from_repo"),
            "reason": "This evaluator has no proven installation profile for this recipe; no dependencies, compiler options or environment fixes may be supplied by STRhub."}
    if not ready or ".gitmodules" in (proposal.get("tree_paths") or []):
        return result
    content = (proposal.get("upstream_files") or {}).get(env["from_repo"])
    if not isinstance(content, str) or not content.strip():
        return result
    for doc in proposal.get("source_documents") or []:
        if doc.get("origin") == "wiki":
            continue
        for number, line in literal_lines(doc.get("text") or ""):
            try:
                args = shlex.split(line)
            except ValueError:
                continue
            if args[:2] != ["docker", "build"] or any(c in line for c in "$`;&|<>\\\n"):
                continue
            # Root context, optional literal Dockerfile and tag. Unknown build
            # arguments/contexts are limits, never silently dropped or guessed.
            options, i, filename, valid, seen = args[2:], 0, "Dockerfile", True, set()
            while i < len(options) - 1:
                if options[i] not in ("-f", "--file", "-t", "--tag") or i + 1 >= len(options) - 1:
                    valid = False
                    break
                if options[i] in ("-f", "--file"):
                    if "file" in seen:
                        valid = False
                    filename = options[i + 1]
                    seen.add("file")
                else:
                    if "tag" in seen or not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?", options[i + 1]):
                        valid = False
                    seen.add("tag")
                i += 2
            candidate = {"cmd": line.strip(), "file": doc["file"], "line": number}
            citation = cite(proposal, candidate)
            if valid and options[-1:] == ["."] and filename.removeprefix("./") == env["from_repo"] and citation["verified"]:
                result.update(ready=True, citation=citation, documented_command=line.strip(),
                              dockerfile_sha256=digest(content), context=".",
                              reason="Build the cited upstream Dockerfile unchanged, in the documented root context, with no generated installation steps or build-argument overrides.")
                return result
    return result


def image_invocation_supported(proposal: dict, installation_review: dict | None = None) -> bool:
    """Do not replace ENTRYPOINT or add shell options the image did not state."""
    import source_install
    if installation_review and installation_review.get("profile") == source_install.PROFILE:
        return bool(installation_review.get("ready") and source_install.discover(proposal) == installation_review)
    filename = (proposal.get("build") or {}).get("file")
    text = (proposal.get("upstream_files") or {}).get(filename, "")
    # Decline heredocs, alternate escaping and multiple stages rather than
    # mistake text inside RUN (or an earlier stage) for the final entrypoint.
    if "<<" in text or re.search(r"^\s*#\s*escape\s*=", text, re.I | re.M):
        return False
    instructions, pending = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
        else:
            instructions.append(pending + line)
            pending = ""
    entries = [line.split(None, 1)[1] for line in instructions if re.match(r"ENTRYPOINT\s", line, re.I)]
    if pending or len(entries) != 1 or sum(bool(re.match(r"FROM\s", line, re.I)) for line in instructions) != 1:
        return False
    try:
        return json.loads(entries[-1]) == ["/bin/bash", "-lc"]
    except ValueError:
        return False


def verify_checkout(root, review: dict, manifest: dict | None = None) -> None:
    """Check the documents and Dockerfile against the actual pinned checkout."""
    import _paths
    import authorization
    checked = authorization.validate(review, manifest)
    if not checked.valid:
        raise ValueError("no proven procedure for the effective manifest: " + checked.reason)
    review = checked.review
    install = review.get("installation") or {}
    if review.get("profile") != PROFILE or not install.get("ready"):
        raise ValueError("no proven installation profile; Docker must not run")
    import source_install
    if install.get("profile") == source_install.PROFILE:
        source_install.verify_checkout(root, install)
        citations = (review.get("command_review") or {}).get("citations") or []
        checks = [(c.get("path"), c.get("document_sha256")) for c in citations]
    else:
        checks = [(install.get("source_file"), install.get("dockerfile_sha256"))]
        citations = [install.get("citation") or {}] + ((review.get("command_review") or {}).get("citations") or [])
        checks += [(c.get("path"), c.get("document_sha256")) for c in citations]
    for relative, expected in checks:
        if not relative or not expected:
            raise ValueError("incomplete upstream file evidence")
        path = _paths.confined(root, relative)
        # Hash raw bytes; decoding/newline changes must not be disguised.
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"upstream evidence differs at pinned checkout: {relative}")


if __name__ == "__main__":
    import argparse
    import json
    import pathlib
    parser = argparse.ArgumentParser(description="Check upstream evidence before Docker")
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--manifest", required=True, help="actual effective manifest, not a cached contract")
    parser.add_argument("--source-install-dockerfile", help="Materialise only a verified source-installation carrier")
    args = parser.parse_args()
    review = json.loads(pathlib.Path(args.review).read_text())
    import _manifest
    verify_checkout(pathlib.Path(args.checkout), review, _manifest.load(args.manifest))
    if args.source_install_dockerfile:
        import source_install
        source_install.materialise(pathlib.Path(args.checkout), review["installation"],
                                   pathlib.Path(args.source_install_dockerfile))
