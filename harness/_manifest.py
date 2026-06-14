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
