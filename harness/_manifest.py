"""Load and (optionally) validate a tool manifest against the JSON schema.

Dependencies are intentionally minimal (pyyaml; jsonschema optional) so the
harness itself is trivially reproducible — the thing doing the certifying must
be more reproducible than the things it certifies.
"""
from __future__ import annotations
import json
import pathlib
import sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "manifest.schema.json"


def load(manifest_path: str) -> dict:
    path = pathlib.Path(manifest_path)
    data = yaml.safe_load(path.read_text())
    try:
        import jsonschema  # optional
        jsonschema.validate(data, json.loads(SCHEMA.read_text()))
    except ImportError:
        pass  # validation is a nicety; absence must not block a run
    except Exception as exc:  # noqa: BLE001
        print(f"::error::manifest failed schema validation: {exc}", file=sys.stderr)
        raise
    return data


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
        try:
            m.resolve().relative_to(base)
        except ValueError:
            continue
        kept.append(m)
    return kept, None
