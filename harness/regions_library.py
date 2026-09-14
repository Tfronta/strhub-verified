"""The regions library: which ready-made regions file a tool gets.

Two questions, both answered from evidence rather than asked of anybody:

  format_for_tool(name, cmd, readme)   which format a tool takes, from what it
                                       is and what its README calls the file
  detect_format(bed_text)              which format a file somebody supplied
                                       is in, from its columns

The first lets a trial pick the library file for a known tool. The second lets
a submitted file be recognised: a 590-locus genome-wide HipSTR reference is
still HipSTR format, and STRhub's 24-locus file in that format is what the
slice can serve, so it stands in.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

FORMATS = {
    "hipstr": {"columns": "chrom start end period ref_copies name [motif]", "tools": ["HipSTR"]},
    "gangstr": {"columns": "chrom start end period motif", "tools": ["GangSTR"]},
    "strsearch": {"columns": "11 columns with flanking sequences", "tools": ["STRsearch"]},
    "bed4": {"columns": "chrom start end name", "tools": []},
}

#: Program names (lower-case) that identify a format outright.
TOOL_FORMATS = {
    "hipstr": "hipstr",
    "gangstr": "gangstr",
    "strsearch": "strsearch",
    "str_search": "strsearch",
    "str_search.py": "strsearch",
    "pipeline.py": "strsearch",
}

MOTIF_RE = re.compile(r"^[ACGTN]{1,12}$", re.I)
INT_RE = re.compile(r"^\d+$")
NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")


def library_path(input_type: str, fmt: str) -> pathlib.Path | None:
    """The committed file for (dataset type, format), or None."""
    index = json.loads((ROOT / "datasets" / "index.json").read_text())
    ds = index["datasets"].get(input_type) or {}
    lib = ds.get("regions_library") or {}
    rel = lib.get(fmt)
    if not rel:
        return None
    p = ROOT / rel
    return p if p.is_file() else None


def available(input_type: str) -> list[str]:
    index = json.loads((ROOT / "datasets" / "index.json").read_text())
    return sorted((index["datasets"].get(input_type) or {}).get("regions_library", {}).keys())


def format_for_tool(tool_name: str = "", cmd: str = "", readme: str = "") -> tuple[str | None, str]:
    """(format, how). `how` is 'tool' when the program name settles it,
    'readme' when the README describes the columns, '' when nothing does."""
    names = {tool_name.lower()}
    for tok in re.split(r"[\s|;&()]+", cmd.lower()):
        names.add(tok.split("/")[-1])
    for n in names:
        if n in TOOL_FORMATS:
            return TOOL_FORMATS[n], "tool"
    text = readme.lower()
    if "hipstr" in text and re.search(r"\bregions?\b", text):
        return "hipstr", "readme"
    if "gangstr" in text and re.search(r"\bregions?\b", text):
        return "gangstr", "readme"
    if re.search(r"5['′]?\s*flank", text) and re.search(r"3['′]?\s*flank", text):
        return "strsearch", "readme"
    return None, ""


def detect_format(bed_text: str) -> str | None:
    """Which library format a supplied file is in, from its data rows."""
    rows = []
    for ln in bed_text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "track", "browser")):
            continue
        rows.append(s.split("\t") if "\t" in s else s.split())
        if len(rows) >= 50:
            break
    if not rows:
        return None
    widths = {len(r) for r in rows}
    if widths == {11}:
        return "strsearch"
    def col(i, pred):
        return all(len(r) > i and pred(r[i]) for r in rows)
    if not (col(1, INT_RE.match) and col(2, INT_RE.match)):
        return None
    if widths <= {5} and col(3, INT_RE.match) and col(4, MOTIF_RE.match):
        return "gangstr"
    if widths <= {6, 7} and col(3, INT_RE.match) and col(4, NUM_RE.match) and col(5, lambda v: not NUM_RE.match(v)):
        return "hipstr"
    if widths <= {3, 4}:
        return "bed4"
    return None
