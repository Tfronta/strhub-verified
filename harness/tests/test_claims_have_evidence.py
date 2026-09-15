"""No sentence about somebody else's software ships without a source.

The engine publishes findings about a stranger's repository under STRhub's
name. A heuristic that produces a number is not entitled to speak in the
author's voice, and the two times it did, nothing here caught it: the tests
asserted that a caveat was produced, never that it was true.

This test does the one thing a test can do about truth — it makes an
unsourced claim impossible to add quietly. Every string that speaks in
finding voice must be in harness/claims.py with the evidence it rests on; a
new or reworded one fails here with its fingerprint, and registering it is
the review.
"""
import ast
import hashlib
import pathlib
import re

import claims

HARNESS = pathlib.Path(__file__).resolve().parents[1]
#: Modules whose strings reach a report, a certificate or a page.
SOURCES = ["propose_manifest.py", "report.py", "certificate_text.py",
           "generate_pdf.py", "verdict.py", "check_readme.py", "diagnose_log.py"]

#: Finding voice: an assertion about the tool, its repository, its
#: documentation or its author. Deliberately broad — a false positive costs one
#: register entry, a false negative costs a published falsehood.
FINDING = re.compile(
    r"\b(?:the|this) (?:tool|repository|README|submission|author|maintainer)\b[^.]*?"
    r"\b(?:does not|doesn't|has no|ships|includes|requires|needs|declares|suggests|"
    r"prefers|supports|is|was|documents|provides|lacks)\b"
    r"|\bno (?:command|install method|way to install|sample|example|output file)\b"
    r"|\bwas found in the (?:README|repository)\b"
    r"|\bdoes not include\b|\bships no\b|\bholds no\b", re.I)


def _command_line_help(tree: ast.AST) -> set[int]:
    """Strings passed as argparse `help=`: they reach a maintainer's terminal,
    never a report, and registering them would fill the register with text
    nobody publishes."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                    out.add(id(kw.value))
    return out


def _docstrings(tree: ast.AST) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                out.add(doc)
    return out


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:12]


def _claims_in_sources() -> list[tuple[str, str, str]]:
    """(fingerprint, module, text) for every finding-voice string that ships."""
    found = []
    for name in SOURCES:
        path = HARNESS / name
        tree = ast.parse(path.read_text())
        docs = _docstrings(tree)
        cli_help = _command_line_help(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in cli_help:
                continue
            value = node.value
            # A docstring explains the code to whoever maintains it; it is not
            # published, and several of them quote the very sentences below.
            if value in docs or len(value) < 25 or not FINDING.search(value):
                continue
            found.append((fingerprint(value), name[:-3], " ".join(value.split())))
    return found


def test_every_published_claim_is_registered_with_its_evidence():
    unregistered = [(fp, mod, text) for fp, mod, text in _claims_in_sources()
                    if fp not in claims.REGISTER]
    assert not unregistered, (
        "These sentences assert something about somebody else's software and are "
        "not in harness/claims.py. Add each one with the source it rests on "
        "(tree / readme / log / manifest / gates / run / strhub-table / policy / "
        "advice), or reword it to describe what STRhub did:\n"
        + "\n".join(f'    "{fp}": ("{mod}", ""),  # {text[:100]}' for fp, mod, text in unregistered))


def test_the_register_carries_no_dead_entries():
    live = {fp for fp, _, _ in _claims_in_sources()}
    dead = sorted(fp for fp in claims.REGISTER if fp not in live)
    assert not dead, (
        "Registered claims that no longer appear in the sources — delete them so "
        "the register keeps describing what actually ships: " + ", ".join(dead))


def test_every_entry_names_a_source_we_recognise():
    for fp, (module, source) in claims.REGISTER.items():
        assert source, f"{fp} ({module}) has no evidence source"
        assert source in claims.VALID_SOURCES, f"{fp} ({module}): unknown source {source!r}"


def test_forbidden_phrasings_never_ship():
    """Wordings that put a preference or an absence in the author's mouth.

    Evidence does not rescue these: no reading of a repository establishes what
    its author prefers or intends, and both patterns below were published.
    """
    offences = []
    for _, module, text in _claims_in_sources():
        for pattern, why in claims.FORBIDDEN:
            if re.search(pattern, text, re.I):
                offences.append(f"{module}: {text[:90]!r} — {why}")
    # The register itself is checked too: a forbidden sentence must not be
    # smuggled in by registering it.
    assert not offences, "Forbidden phrasing:\n    " + "\n    ".join(offences)


def test_the_two_sentences_that_shipped_would_be_caught_today():
    """The regression this whole file exists for."""
    for text in ["Input: the README suggests ont-fastq first; STRhub has reference data only as ont-bam-hg38.",
                 "This tool does not include its own demo or test data."]:
        assert FINDING.search(text), text
        assert any(re.search(p, text, re.I) for p, _ in claims.FORBIDDEN), text
        assert fingerprint(text) not in claims.REGISTER, text


def test_strhub_s_own_lookup_table_may_not_speak_as_a_fact_about_the_tool():
    """The five that were left after the audit, and the shape they had.

    Each rested on nothing but STRhub's table of program names, published as a
    property of somebody's software. They are gone, the source that held them
    is refused, and the two phrasings break the build.
    """
    assert "strhub-table" not in claims.VALID_SOURCES
    assert not [fp for fp, (_, src) in claims.REGISTER.items() if src == "strhub-table"]
    for text in ["the tool is known to read this format",
                 "The tool needs a regions file (BED) in its own format."]:
        assert any(re.search(p, text, re.I) for p, _ in claims.FORBIDDEN), text
