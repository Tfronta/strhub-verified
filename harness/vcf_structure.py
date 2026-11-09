"""Read-only VCF 4.x structural checks, independent of genotype plausibility.

This is a versioned structural profile, not complete VCF conformance or a
reference/genotype correctness check. See docs/VCF-STRUCTURE.md for its scope.
"""
from __future__ import annotations

from dataclasses import dataclass
import gzip
from math import comb, isfinite
import re
import struct

PROFILE = "strhub-vcf-structure/1"
FIXED = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
KEY = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_.]*|1000G)\Z")
FORMAT_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*\Z")
INTEGER = re.compile(r"[-+]?[0-9]+\Z")
FLOAT = re.compile(r"[-+]?(?:[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|inf(?:inity)?|nan)\Z", re.I)
BASES = re.compile(r"[ACGTN]+\Z", re.I)
GT = re.compile(r"[/|]?(?:[0-9]+|\.)(?:[/|](?:[0-9]+|\.))*\Z")


class VCFError(ValueError):
    pass


class UnsupportedVCF(VCFError):
    """A declared feature this evaluator cannot establish, not malformed data."""


@dataclass
class Summary:
    version: str
    records: int = 0
    called_records: int = 0
    uncalled_rows: int = 0
    records_without_gt: int = 0


def read(path) -> str:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        return handle.read()


def require(condition, message):
    if not condition:
        raise VCFError(message)


def fields(text: str, delimiter: str = ",") -> list[str]:
    """Split header attributes, retaining quoted commas and escaped quotes."""
    result, start, quoted, escaped, depth = [], 0, False, False, 0
    for i, c in enumerate(text):
        if escaped:
            escaped = False
        elif c == "\\" and quoted:
            escaped = True
        elif c == '"':
            quoted = not quoted
        elif c == "[" and not quoted:
            depth += 1
        elif c == "]" and not quoted:
            depth -= 1
            require(depth >= 0, "unbalanced metadata list")
        elif c == delimiter and not quoted and depth == 0:
            result.append(text[start:i])
            start = i + 1
    require(not quoted and not escaped and depth == 0, "unterminated quoted metadata or list")
    result.append(text[start:])
    require(all(result), "empty metadata attribute")
    return result


def metadata(line: str, definitions: dict) -> None:
    key, sep, value = line[2:].partition("=")
    require(bool(key and sep and value), "metadata must be ##key=value")
    require(not any(c.isspace() for c in key), "invalid metadata key")
    require(key != "fileformat", "duplicate fileformat declaration")
    if not value.startswith("<"):
        require(key not in ("INFO", "FORMAT", "FILTER", "ALT", "contig"), "structured metadata expected")
        return
    require(value.endswith(">"), "unterminated structured metadata")
    attrs = {}
    for item in fields(value[1:-1]):
        name, eq, val = item.partition("=")
        require(bool(name and eq and val) and name not in attrs, "invalid or duplicate metadata attribute")
        require(not any(c.isspace() for c in name), "invalid metadata attribute name")
        if '"' in val:
            require(re.fullmatch(r'"(?:[^"\\]|\\.)*"', val), "invalid quoted attribute")
        attrs[name] = val
    if key not in ("INFO", "FORMAT", "FILTER", "ALT", "contig"):
        return
    require("ID" in attrs, "metadata ID is required")
    ident = attrs["ID"]
    require(not any(c.isspace() or c in ',<>"' for c in ident), "invalid metadata ID")
    bucket = definitions.setdefault(key, {})
    require(ident not in bucket, "duplicate metadata ID")
    if key in ("INFO", "FORMAT"):
        require((FORMAT_KEY if key == "FORMAT" else KEY).fullmatch(ident), "invalid INFO/FORMAT ID")
        require(all(k in attrs for k in ("Number", "Type", "Description")), "incomplete field declaration")
        number, typ = attrs["Number"], attrs["Type"]
        if number in ("P", "LA", "LR", "LG"):
            raise UnsupportedVCF("local-allele/ploidy cardinality declarations are not supported by this profile")
        require(number in ("A", "R", "G", ".") or bool(re.fullmatch(r"[0-9]+", number)), "invalid Number declaration")
        require(typ in ("Integer", "Float", "Flag", "Character", "String"), "invalid Type declaration")
        require((typ == "Flag") == (number == "0"), "Flag requires Number=0; value fields require nonzero Number")
        require(key != "FORMAT" or typ != "Flag", "FORMAT cannot have Flag type")
        if ident == "GT" and key == "FORMAT":
            require(typ == "String" and number == "1", "GT must be Number=1,Type=String")
    if key in ("INFO", "FORMAT", "FILTER", "ALT"):
        desc = attrs.get("Description", "")
        require(desc.startswith('"') and desc.endswith('"'), "Description must be quoted")
    bucket[ident] = attrs


def typed(value: str, declaration: dict | None, alt_count: int, ploidy=None) -> None:
    values = value.split(",")
    require(all(values), "empty field value; use '.' for missing values")
    if declaration is None:
        return
    typ, number = declaration["Type"], declaration["Number"]
    require(typ != "Flag", "Flag cannot have a value")
    if value == ".":
        return
    expected = int(number) if number.isdecimal() else {"A": alt_count, "R": alt_count + 1}.get(number)
    if number == "G" and ploidy is not None:
        expected = comb(alt_count + ploidy, ploidy)
    if expected is not None:
        require(len(values) == expected, "field value count differs from Number")
    for item in values:
        if item == ".":
            continue
        if typ == "Integer":
            require(INTEGER.fullmatch(item), "invalid Integer value")
            require(-2147483640 <= int(item) <= 2147483647, "Integer outside VCF range")
        elif typ == "Float":
            floating(item)
        elif typ == "Character":
            require(len(item) == 1, "Character value must contain one character")


def floating(value: str) -> None:
    require(FLOAT.fullmatch(value), "invalid Float value")
    if re.fullmatch(r"[-+]?(?:inf(?:inity)?|nan)", value, re.I):
        return
    number = float(value)
    require(isfinite(number), "Float value outside 32-bit range")
    try:
        struct.pack("f", number)
    except OverflowError as exc:
        raise VCFError("Float value outside 32-bit range") from exc


def alternate(allele: str) -> bool:
    if BASES.fullmatch(allele) or allele == "*":
        return True
    if re.fullmatch(r"<[^\s,<>]+>", allele):
        return True
    if (allele.startswith(".") and BASES.fullmatch(allele[1:])) or (allele.endswith(".") and BASES.fullmatch(allele[:-1])):
        return True  # single breakend
    match = re.fullmatch(r"([ACGTNacgtn]*)([\[\]])([^\s\[\]]+):([0-9]+)\2([ACGTNacgtn]*)", allele)
    return bool(match and bool(match[1]) != bool(match[5]))


def record(columns: list[str], definitions: dict, summary: Summary) -> None:
    chrom, pos, ident, ref, alt, qual, filters, info = columns[:8]
    require(chrom != "." and not any(c.isspace() for c in chrom), "CHROM is required and cannot contain whitespace")
    require(INTEGER.fullmatch(pos) and int(pos) >= 0, "POS must be a nonnegative integer")
    require(not any(c.isspace() for c in ident), "ID cannot contain whitespace")
    ids = ident.split(";")
    require(all(ids) and len(ids) == len(set(ids)), "empty or duplicate ID")
    require(ident == "." or "." not in ids, "missing ID cannot be mixed with identifiers")
    require(BASES.fullmatch(ref), "REF must contain A/C/G/T/N bases")
    alts = [] if alt == "." else alt.split(",")
    require(all(alternate(a) for a in alts) and len(alts) == len(set(alts)), "invalid or duplicate ALT allele")
    if qual != ".":
        floating(qual)
    if filters not in (".", "PASS"):
        entries = filters.split(";")
        require(all(e and e not in (".", "0", "PASS") and not any(c.isspace() for c in e) for e in entries)
                and len(entries) == len(set(entries)), "invalid FILTER list")
    if info != ".":
        seen = set()
        for item in info.split(";"):
            key, eq, value = item.partition("=")
            require(KEY.fullmatch(key) and key not in seen, "invalid or duplicate INFO key")
            seen.add(key)
            declaration = definitions.get("INFO", {}).get(key)
            if eq:
                require(value and "=" not in value and all(value.split(",")), "invalid INFO value")
                try:
                    typed(value, declaration, len(alts))
                except VCFError as exc:
                    raise VCFError(f"INFO/{key}: {exc}") from exc
            elif declaration is not None:
                require(declaration["Type"] == "Flag", "INFO value is required")
    summary.records += 1
    if len(columns) == 8 or columns[8] == ".":
        if len(columns) > 8:
            require(all(v == "." for v in columns[9:]), "sample data requires FORMAT keys")
        summary.records_without_gt += 1
        return
    formats = columns[8].split(":")
    require(all(FORMAT_KEY.fullmatch(k) for k in formats) and len(formats) == len(set(formats)), "invalid or duplicate FORMAT key")
    require("GT" not in formats or formats[0] == "GT", "GT must be the first FORMAT key")
    called = False
    for sample in columns[9:]:
        values = sample.split(":")
        require(len(values) <= len(formats) and all(values), "sample has extra or empty FORMAT values")
        ploidy = None
        if formats[0] == "GT":
            require(GT.fullmatch(values[0]), "invalid GT syntax")
            require(summary.version in ("4.4", "4.5") or not values[0].startswith(("/", "|")), "leading GT phasing indicator requires VCF 4.4 or later")
            alleles = re.split(r"[/|]", values[0].lstrip("/|"))
            require(all(a == "." or int(a) <= len(alts) for a in alleles), "GT allele index exceeds ALT count")
            called |= any(a != "." for a in alleles)
            ploidy = len(alleles)
        for key, value in zip(formats, values):
            try:
                typed(value, definitions.get("FORMAT", {}).get(key), len(alts), ploidy)
            except VCFError as exc:
                raise VCFError(f"FORMAT/{key}: {exc}") from exc
    if "GT" in formats:
        summary.called_records += int(called)
        summary.uncalled_rows += int(not called)
    else:
        summary.records_without_gt += 1


def validate(text: str) -> Summary:
    """Consume the entire file. Malformed suffixes cannot hide behind valid rows."""
    lines = text.splitlines(keepends=True)
    require(bool(lines), "missing fileformat declaration")
    first = lines[0].rstrip("\r\n")
    version = re.fullmatch(r"##fileformat=VCFv([0-9]+\.[0-9]+)", first)
    require(version, "first line must declare ##fileformat=VCFv<version>")
    if version[1] not in {f"4.{i}" for i in range(6)}:
        raise UnsupportedVCF("declared VCF version is not supported by this profile")
    summary = Summary(version[1])
    header, definitions = None, {}
    for number, raw in enumerate(lines, 1):
        try:
            require(raw.endswith("\n"), "line must end in LF or CRLF; file may be truncated")
            line = raw[:-2] if raw.endswith("\r\n") else raw[:-1]
            require(not any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in line), "invalid control character")
            if number == 1:
                continue
            require(bool(line), "blank lines are not VCF records")
            if line.startswith("##"):
                require(header is None, "metadata after column header")
                metadata(line, definitions)
            elif line.startswith("#"):
                require(header is None, "unexpected or duplicate column header")
                header = line.split("\t")
                require(header[:8] == FIXED, "eight fixed tab-delimited column names are required")
                require(len(header) == 8 or len(header) >= 10 and header[8] == "FORMAT", "FORMAT needs sample columns")
                samples = header[9:]
                require(all(s and not any(c.isspace() for c in s) for s in samples)
                        and len(samples) == len(set(samples)), "empty or duplicate sample ID")
            else:
                require(header is not None, "data record before column header")
                columns = line.split("\t")
                require(len(columns) == len(header) and all(columns), "record column count differs from header, or contains empty cells")
                record(columns, definitions, summary)
        except VCFError as exc:
            raise type(exc)(f"line {number}: {exc}") from exc
    require(header is not None, "missing #CHROM column header")
    return summary
