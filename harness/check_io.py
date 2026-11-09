"""IO gate: does the tool produce the output it claims, in the declared format?

This is the line that keeps the project on the executability side and off the
concordance side. We check that files exist, are non-empty, parse as the
declared format, and clear a minimum record count (to catch exit-0-but-empty
silent failures). We do NOT check whether the values are biologically correct.

Usage:  python harness/check_io.py <manifest.yml> <output_dir> [--json io_result.json]
Exit:   0 if all required checks pass, 1 otherwise.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _manifest  # noqa: E402
import vcf_structure  # noqa: E402


def _read_text(path: pathlib.Path) -> str:
    if path.suffix == ".gz" or path.name.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace").read()
    return path.read_text(errors="replace")


def _vcf_file(path: pathlib.Path, out: pathlib.Path, spec: dict) -> dict:
    result = {"resolved": str(path.relative_to(out)), "checks": {"non_empty": path.stat().st_size > 0},
              "records": 0, "called_records": 0, "uncalled_rows": 0, "records_without_gt": 0}
    try:
        text = vcf_structure.read(path)
        summary = vcf_structure.validate(text)
        result.update(vars(summary))
        result["validation_status"] = "valid"
        result["checks"]["parses_as_vcf"] = True
        result["checks"]["min_records"] = summary.records >= spec.get("min_records", 1)
        # Keep the existing policy for all-missing GT output, but record that
        # independently of format validity and the number of data rows.
        result["checks"]["has_called_genotypes"] = summary.uncalled_rows == 0 or summary.called_records > 0
        if spec.get("must_contain"):
            missing = [s for s in spec["must_contain"] if s not in text]
            result["checks"]["must_contain"] = not missing
            if missing:
                result["missing"] = missing
    except (vcf_structure.VCFError, OSError, EOFError, UnicodeError, ValueError) as exc:
        result["validation_status"] = "unsupported" if isinstance(exc, vcf_structure.UnsupportedVCF) else "invalid"
        result["checks"]["parses_as_vcf"] = False
        result["checks"]["min_records"] = False
        result["parse_error"] = str(exc)
    result["passed"] = all(result["checks"].values())
    return result


def _vcf_outputs(matches: list[pathlib.Path], out: pathlib.Path, spec: dict) -> dict:
    files = [_vcf_file(path, out, spec) for path in matches]
    keys = set().union(*(f["checks"] for f in files))
    result = {"resolved": files[0]["resolved"], "files": files,
              "validation_profile": vcf_structure.PROFILE,
              "checks": {key: all(f["checks"].get(key, False) for f in files) for key in sorted(keys)},
              "passed": all(f["passed"] for f in files)}
    for key in ("records", "called_records", "uncalled_rows", "records_without_gt"):
        result[key] = sum(f[key] for f in files)
    statuses = {f["validation_status"] for f in files}
    result["validation_status"] = "invalid" if "invalid" in statuses else "unsupported" if "unsupported" in statuses else "valid"
    errors = [f"{f['resolved']}: {f['parse_error']}" for f in files if f.get("parse_error")]
    if errors:
        result["parse_error"] = "; ".join(errors)
    return result


def _count_records(path: pathlib.Path, fmt: str) -> int:
    if fmt == "vcf":
        return vcf_structure.validate(vcf_structure.read(path)).records
    text = _read_text(path)
    if fmt == "json":
        obj = json.loads(text)
        return len(obj) if isinstance(obj, (list, dict)) else 1
    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        rows = [r for r in csv.reader(text.splitlines(), delimiter=delim)
                if any(cell.strip() for cell in r)]
        return len(rows) - (1 if _has_header(rows) else 0)
    return sum(1 for ln in text.splitlines() if ln.strip())  # text


def _looks_numeric(cell: str) -> bool:
    try:
        float(cell.strip())
        return True
    except ValueError:
        return False


def _has_header(rows: list[list[str]]) -> bool:
    """Whether row 0 of a CSV/TSV is a header rather than a record.

    This used to be assumed: every CSV/TSV lost its first row, and blank lines
    counted as records. So a file holding nothing but two newlines cleared
    `min_records: 1`, and a one-row headerless TSV failed it. Both are the
    exact opposite of what the gate is for.

    Evidence-based instead: a header is a first row with a non-numeric cell in a
    column where the rows below are numeric (a label over a count), or, when it
    is the only row, one with no digits at all. A single row that carries a
    number is a record, not a heading.
    """
    if not rows:
        return False
    first = rows[0]
    if len(rows) == 1:
        return not any(ch.isdigit() for cell in first for ch in cell)
    body = rows[1:]
    for c, cell in enumerate(first):
        if _looks_numeric(cell):
            continue
        below = [r[c] for r in body if c < len(r) and r[c].strip()]
        if below and all(_looks_numeric(v) for v in below):
            return True
    return False


def check(manifest_path: str, out_dir: str) -> dict:
    m = _manifest.load(manifest_path)
    out = pathlib.Path(out_dir)
    checks = []
    ok = True

    for spec in m["outputs"]:
        matches, refused = _manifest.safe_glob(out, spec["path"])
        entry = {"path": spec["path"], "format": spec["format"], "checks": {}}

        # A pattern that could leave /data/out is refused outright, and the
        # refusal is recorded so the report can say why the gate did not pass.
        entry["checks"]["confined"] = refused is None
        if refused is not None:
            entry["error"] = refused
            entry["passed"] = ok = False
            checks.append(entry)
            continue

        present = bool(matches)
        entry["checks"]["exists"] = present
        if not present:
            entry["passed"] = ok = False
            checks.append(entry)
            continue

        if spec["format"] == "vcf":
            validated = _vcf_outputs(matches, out, spec)
            entry.update({k: v for k, v in validated.items() if k != "checks"})
            entry["checks"].update(validated["checks"])
            ok = ok and entry["passed"]
            checks.append(entry)
            continue

        f = matches[0]
        entry["resolved"] = str(f.relative_to(out))
        nonempty = f.stat().st_size > 0
        entry["checks"]["non_empty"] = nonempty

        try:
            n = _count_records(f, spec["format"])
            parses = True
        except Exception as exc:  # noqa: BLE001
            n, parses = 0, False
            entry["parse_error"] = str(exc)
        entry["checks"]["parses_as_" + spec["format"]] = parses
        entry["records"] = n
        entry["checks"]["min_records"] = n >= spec.get("min_records", 1)

        if spec.get("must_contain"):
            blob = _read_text(f)
            missing = [s for s in spec["must_contain"] if s not in blob]
            entry["checks"]["must_contain"] = not missing
            if missing:
                entry["missing"] = missing

        entry["passed"] = all(entry["checks"].values())
        ok = ok and entry["passed"]
        checks.append(entry)

    return {"gate": "io", "passed": ok, "outputs": checks}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("output_dir")
    ap.add_argument("--json", default="io_result.json")
    args = ap.parse_args()

    result = check(args.manifest, args.output_dir)
    pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
