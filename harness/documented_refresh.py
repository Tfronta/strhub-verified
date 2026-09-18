"""Run the documented instrument for every tool that only has a curated one.

The badge may rest only on a run of the repository's own instructions (or of
a recipe the maintainer submitted). The seven recipes STRhub wrote under
tools/ can never provide that — they are notes — so each of those tools needs
a trial from its repository's URL at the same pinned commit: the recipe the
engine reads off the README and the tree, run and published on the usual
terms, which then takes the alias. docs/PLAN-Documented-Is-The-Badge.md.

Dispatched by the monthly schedule next to the curated runs, and by hand:

    python harness/documented_refresh.py --dispatch --json documented.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from certificate_text import instrument_of  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = "verify.yml"


def curated_tools(root: pathlib.Path = ROOT) -> list[dict]:
    """Every committed recipe that is STRhub's, with what its documented
    counterpart needs: the repository and the pinned commit."""
    out = []
    for m in sorted((root / "tools").glob("*/manifest.yml")):
        try:
            doc = yaml.safe_load(m.read_text()) or {}
        except yaml.YAMLError:
            continue
        if instrument_of(doc) != "curated":
            continue
        src = doc.get("source") or {}
        if not src.get("repo") or not src.get("ref"):
            continue
        out.append({"slug": m.parent.name, "repo": src["repo"], "ref": str(src["ref"]),
                    "version": str((doc.get("tool") or {}).get("version") or "")})
    # One trial per repository and commit: the documented instrument knows
    # nothing of kits or panels (hipstr and hipstr-y, the two STRait Razor
    # kits), so two curated recipes of one commit would only run it twice.
    seen: dict[tuple[str, str], dict] = {}
    for t in out:
        key = (t["repo"].rstrip("/").lower(), t["ref"])
        if key in seen:
            seen[key].setdefault("also_for", []).append(t["slug"])
        else:
            seen[key] = t
    return list(seen.values())


def trial_name(repo: str, ref: str) -> str:
    """The run's `tool` input, the way the web names a trial from a URL."""
    name = re.sub(r"[^a-z0-9.-]+", "-", repo.rstrip("/").split("/")[-1].lower())
    return f"trial-{name}-{ref[:7]}"


def dispatch(tools: list[dict], run=subprocess.run) -> list[dict]:
    """One trial from the URL per curated tool, at its pinned commit. The
    version label rides along so the row reads "v2.0", not a bare sha."""
    done = []
    for t in tools:
        dispatch_id = f"doc_{t['ref'][:7]}_{t['slug']}"[:60]
        cmd = ["gh", "workflow", "run", WORKFLOW,
               "-f", f"tool={trial_name(t['repo'], t['ref'])}", "-f", "mode=trial",
               "-f", f"repo={t['repo']}", "-f", f"ref={t['ref']}",
               "-f", f"dispatch_id={dispatch_id}"]
        if t.get("version") and not t["ref"].startswith(t["version"]):
            cmd += ["-f", f"ref_label={t['version']}"]
        res = run(cmd, capture_output=True, text=True)
        done.append({**t, "dispatch_id": dispatch_id, "dispatched": res.returncode == 0,
                     "error": (res.stderr or "").strip() if res.returncode else ""})
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dispatch", action="store_true", help="start the trials (default: list them)")
    ap.add_argument("--json", default="", help="write what was found/dispatched here")
    args = ap.parse_args()
    tools = curated_tools()
    result = dispatch(tools) if args.dispatch else tools
    for t in result:
        state = ("started" if t.get("dispatched") else "FAILED" if args.dispatch else "would run")
        print(f"{state:9} {t['slug']} <- {t['repo']} @ {t['ref'][:7]}{': ' + t['error'] if t.get('error') else ''}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    return 0 if all(t.get("dispatched", True) for t in result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
