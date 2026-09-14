"""Notice when a verified tool publishes a newer release, and try it.

The case this exists for: a tool was verified at v1, its maintainer tagged v2,
and the code the README now describes is not the code the badge is about.
STRspy's v2 kept calling v1 scripts for months and nobody noticed, because
nothing looked. This looks, once a month:

  1. For every repository in the published catalogue, ask GitHub for the
     latest release (or, failing a release, the latest tag).
  2. If its commit is not the one verified, re-run the SAME recipe against it
     as a TRIAL: nothing is published, the owner sees what happened, and the
     attestation stays about the commit it was made for until they confirm.
  3. Say so where the maintainer will see it (an issue on the engine
     repository, updated rather than duplicated).

Reads the catalogue, not tools/: only published tools are refreshed, and one
repository with several published variants gets one lookup.

Usage:
  python harness/upstream_refresh.py --index <url-or-path> [--dispatch] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import retarget_recipe  # noqa: E402
import upstream  # noqa: E402

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_index(where: str) -> dict:
    if where.startswith("http"):
        with urllib.request.urlopen(where, timeout=30) as r:  # noqa: S310 (fixed public host)
            return json.loads(r.read().decode())
    return json.loads(pathlib.Path(where).read_text())


def latest_release(slug: str, token: str | None, get=upstream._get) -> dict | None:
    """{tag, sha, kind} for the newest release, else the newest tag, else None."""
    rel = get(f"/repos/{slug}/releases/latest", token)
    tag = None
    kind = None
    if rel and rel.get("tag_name"):
        tag, kind = rel["tag_name"], "release"
    else:
        tags = get(f"/repos/{slug}/tags?per_page=1", token)
        if isinstance(tags, list) and tags and tags[0].get("name"):
            tag, kind = tags[0]["name"], "tag"
    if not tag:
        return None
    commit = get(f"/repos/{slug}/commits/{tag}", token)
    sha = (commit or {}).get("sha")
    return {"tag": tag, "sha": sha, "kind": kind} if sha else None


def resolve_ref(slug: str, ref: str, token: str | None, get=upstream._get) -> str | None:
    if SHA_RE.match(ref):
        return ref
    commit = get(f"/repos/{slug}/commits/{ref}", token)
    return (commit or {}).get("sha")


def find_newer(index: dict, token: str | None = None, get=upstream._get) -> list[dict]:
    """Tools whose repository has a release or tag newer than the verified ref."""
    out = []
    by_repo: dict[str, list[dict]] = {}
    for t in index.get("tools", []):
        repo = t.get("source_repo")
        slug = upstream.repo_slug(repo or "")
        if slug:
            by_repo.setdefault(slug, []).append(t)
    for repo_slug, tools in by_repo.items():
        latest = latest_release(repo_slug, token, get)
        if not latest:
            continue
        for t in tools:
            verified = resolve_ref(repo_slug, t.get("source_ref", ""), token, get)
            if verified and verified != latest["sha"]:
                out.append({
                    "slug": t["slug"], "repo": t["source_repo"], "verified_ref": t["source_ref"],
                    "verified_sha": verified, "latest_tag": latest["tag"], "latest_sha": latest["sha"],
                    "latest_kind": latest["kind"],
                })
    return out


def dispatch_trials(newer: list[dict], workflow: str = "verify.yml", run=subprocess.run) -> list[dict]:
    """Dispatch one trial per newer release, from the committed recipe. Returns
    what was dispatched (slug of the trial, or the error)."""
    done = []
    for item in newer:
        try:
            r = retarget_recipe.retarget(item["slug"], item["latest_sha"])
        except SystemExit as exc:  # no committed recipe for a published slug
            done.append({**item, "dispatched": False, "error": str(exc)})
            continue
        dispatch_id = f"up_{item['latest_sha'][:7]}_{item['slug']}"[:60]
        cmd = ["gh", "workflow", "run", workflow, "-f", f"tool={r['slug']}", "-f", "mode=trial",
               "-f", f"recipe={r['recipe_b64']}", "-f", f"dispatch_id={dispatch_id}"]
        res = run(cmd, capture_output=True, text=True)
        done.append({**item, "trial_slug": r["slug"], "dispatch_id": dispatch_id,
                     "dispatched": res.returncode == 0,
                     "error": (res.stderr or "").strip() if res.returncode else ""})
    return done


def issue_body(done: list[dict]) -> str:
    lines = ["Upstream releases newer than the verified commit, found by the monthly check. "
             "For each, the committed recipe was re-run against the new commit as a **trial**: "
             "nothing is published until the tool's owner confirms.", "",
             "| Tool | Verified | Newest | Trial |", "|---|---|---|---|"]
    for d in done:
        trial = (f"dispatched as `{d.get('trial_slug')}` (`{d.get('dispatch_id')}`)" if d.get("dispatched")
                 else f"not dispatched: {d.get('error', '')[:120]}")
        lines.append(f"| `{d['slug']}` | `{d['verified_ref'][:12]}` | {d['latest_kind']} `{d['latest_tag']}` "
                     f"(`{d['latest_sha'][:7]}`) | {trial} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="published index.json (URL or path)")
    ap.add_argument("--dispatch", action="store_true", help="dispatch a trial per newer release (needs gh)")
    ap.add_argument("--json", default="", help="write the findings here")
    args = ap.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    newer = find_newer(load_index(args.index), token)
    result = {"newer": newer, "dispatched": []}
    if args.dispatch and newer:
        result["dispatched"] = dispatch_trials(newer)
        result["issue_body"] = issue_body(result["dispatched"])
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
    print(json.dumps({"newer": len(newer), "dispatched": sum(1 for d in result["dispatched"] if d.get("dispatched"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
