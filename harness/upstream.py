"""How far the verified commit has fallen behind the repository it came from.

An attestation is pinned to a commit, and stays true about that commit forever:
"this installed and ran on this date" is not made false by later work. But the
reader is usually holding a manuscript that cites a version, and their real
question is whether the thing we verified is the thing they are looking at. A
report that cannot answer it leaves them to compare SHAs by hand.

Two answers matter, and only one of them is a number:

  behind_by   how many commits have landed on the default branch since. Context,
              not a verdict — a tool 200 commits behind may be perfectly current
              for the release the paper cites.

  ref_exists  whether the pinned commit is still reachable at all. A force-push,
              a deleted branch or a vanished repository strands an attestation
              against something nobody can fetch, and THAT is a finding: the
              central claim of the badge is that anyone can go and check.

Costs one or two API calls and no CI. Every failure returns None, and the report
then says nothing: a guess about how current somebody's software is would be
worse than the silence it replaces.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request

API = "https://api.github.com"
TIMEOUT = 15


def repo_slug(repo_url: str) -> str | None:
    """owner/name from a GitHub URL, or None if it is not one."""
    m = re.match(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_url.strip())
    return m.group(1) if m else None


def _get(path: str, token: str | None) -> dict | None:
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "strhub-verified")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        # 404 is an answer — the caller distinguishes "gone" from "unknown".
        if exc.code == 404:
            return {"__status__": 404}
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def check(repo_url: str, ref: str, token: str | None = None) -> dict | None:
    """Where the pinned ref sits relative to the repository's default branch."""
    slug = repo_slug(repo_url)
    if not slug or not ref.strip():
        return None
    token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    repo = _get(f"/repos/{slug}", token)
    if repo is None:
        return None
    checked = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if repo.get("__status__") == 404:
        # The repository itself is gone or private. Reported, because "the public
        # source exists" is the first thing the badge claims.
        return {"checked": checked, "repo_exists": False, "ref_exists": False}

    branch = repo.get("default_branch") or "main"
    cmp_ = _get(f"/repos/{slug}/compare/{ref.strip()}...{branch}", token)
    if cmp_ is None:
        return None
    if cmp_.get("__status__") == 404:
        return {"checked": checked, "repo_exists": True, "ref_exists": False,
                "default_branch": branch}

    return {
        "checked": checked,
        "repo_exists": True,
        "ref_exists": True,
        "default_branch": branch,
        # "identical" | "behind" | "ahead" | "diverged", from GitHub's own
        # comparison of the pinned ref against the branch head.
        "status": cmp_.get("status"),
        # ahead_by, not behind_by. The comparison is base=our ref, head=the
        # branch, so GitHub's "ahead" counts how far the BRANCH has moved past
        # us — which is precisely how far we are behind it.
        "behind_by": cmp_.get("ahead_by", 0),
    }


def note(up: dict | None) -> str:
    """One sentence for a reader, or "" when there is nothing to say."""
    if not up:
        return ""
    if not up.get("repo_exists"):
        return ("The public repository is no longer reachable at the URL this "
                "attestation was made from. Nothing here can be re-checked "
                "against the source, which is the first thing the badge claims.")
    if not up.get("ref_exists"):
        return ("The pinned commit is no longer reachable in the repository — a "
                "force-push, a deleted branch or a rewritten history. The result "
                "below still describes what ran, but nobody can fetch that "
                "source to repeat it.")
    behind = up.get("behind_by") or 0
    branch = up.get("default_branch", "the default branch")
    if behind <= 0:
        return f"The verified commit is the head of `{branch}`."
    return (f"The verified commit is {behind} commit(s) behind `{branch}`. That "
            "is context, not a fault: a pinned release is often meant to sit "
            "behind, and the attestation describes the commit it names.")
