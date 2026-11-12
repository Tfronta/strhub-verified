"""Load a manifest with mandatory schema and path validation before use."""
from __future__ import annotations
import json
import pathlib
import sys
import yaml
import _paths

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "manifest.schema.json"


def validate(data: dict) -> dict:
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required; manifest validation cannot be skipped") from exc
    jsonschema.validate(data, json.loads(SCHEMA.read_text()))
    env = data["environment"]
    for value in (env["dockerfile"], env.get("from_repo")):
        if value is not None:
            _paths.relative(value)
    inputs = data.get("inputs") or {}
    for item in (inputs.get("fixture"), inputs.get("regions")):
        if isinstance(item, str):
            _paths.relative(item)
        elif isinstance(item, dict) and "repo" in item:
            _paths.raw_url(item)
        elif isinstance(item, dict) and "path" in item:
            _paths.relative(item["path"])
    return data


def loads(text: str) -> dict:
    return validate(yaml.safe_load(text))


def load(manifest_path: str) -> dict:
    return loads(pathlib.Path(manifest_path).read_text())


if __name__ == "__main__":
    m = load(sys.argv[1])
    print(json.dumps(m, indent=2))


def safe_glob(out, pattern):
    """Glob `pattern` under `out` (the /data/out mount), refusing anything that
    could reach outside it.

    The pattern is author-supplied. Before this existed, `path: "../in_own/*"`
    passed the IO and Content gates by pointing them at the INPUT the harness
    had staged, so a tool that wrote nothing at all could be attested at
    "content". An absolute pattern raised NotImplementedError out of pathlib and
    took the whole step down instead. Both now come back as a refusal the gate
    records, and matches that resolve outside `out` (a symlink the tool left in
    /data/out pointing at /data/in) are dropped.

    Only regular files come back. `**/*`, the default a proposed recipe
    declares, matched the directory a tool writes into before any file in it,
    and the gates then failed to parse a directory.

    Returns (matches, reason). `reason` is None when the pattern is acceptable.
    """
    import pathlib as _pl
    if not pattern or pattern.startswith(("/", "~")):
        return [], "output path must be a glob relative to /data/out, not an absolute path"
    if ".." in _pl.PurePosixPath(pattern).parts:
        return [], "output path must stay under /data/out ('..' is not allowed)"
    out = _pl.Path(out)
    base = out.resolve()
    kept = []
    for m in sorted(out.glob(pattern)):
        if not m.is_file():
            continue
        try:
            m.resolve().relative_to(base)
        except ValueError:
            continue
        kept.append(m)
    return kept, None
