"""Whether a finished run goes to the catalogue: one decision, one place.

A failure of the tool is published like a success. It is the finding a paper
reviewer, a user who cannot get the tool running at home, and the tool's owner
all came for, and hiding it would make the catalogue a list of green badges.
What is never published:

  - a pull request's run: it is a check on the engine, not a verification;
  - a trial handed a recipe by whoever dispatched it: that recipe could be
    anything, so its result says nothing about the repository;
  - a run whose verdict is not about the tool (out of scope, or STRhub's own
    infrastructure failed: the verdict's basis is "strhub");
  - a trial from a URL filed under a card that belongs to another repository.
    The slug comes from the repository's NAME, so `someone/HipSTR` would land
    on HipSTR's card, and the alias goes to the newest commit date, which the
    committer sets. The requester still gets the full report as the run's
    artifact; only the card is protected.

Pure, so the policy is testable line by line. The workflow calls `main`.

    python harness/publish_gate.py --report reports/x.json --index published_index.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

PUBLISHED_VERDICTS = ("runs", "fails", "undetermined")


def normalize_repo(url: str) -> str:
    """`https://github.com/Owner/Repo.git/` → `owner/repo`. GitHub names are
    case-insensitive, so the comparison is too."""
    u = (url or "").strip().lower()
    u = re.sub(r"^(?:https?://)?(?:www\.)?github\.com[/:]", "", u)
    u = re.sub(r"^git@github\.com:", "", u)
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def card_owner(index: dict, slug: str) -> str | None:
    """The repository the published card `slug` belongs to, or None if there is
    no such card."""
    for t in (index or {}).get("tools", []):
        if t.get("slug") == slug:
            return t.get("source_repo") or ""
    return None


def decide(report: dict, *, mode: str, url_trial: bool, trial_publish: bool,
           event_name: str, index: dict | None) -> tuple[bool, str]:
    """(publishable, why). `why` is one sentence for the run summary."""
    verdict = report.get("verdict") or {}
    code = verdict.get("code", "")
    if event_name == "pull_request":
        return False, "a pull request's run is a check, never a publication"
    if code not in PUBLISHED_VERDICTS:
        return False, f"verdict '{code or 'none'}' is not a finding about the tool"
    if verdict.get("basis") == "strhub":
        return False, "STRhub's own infrastructure failed; the run has to be repeated"
    if mode == "trial":
        if not url_trial:
            return False, "a trial handed a recipe never publishes"
        if not trial_publish:
            return False, "the dispatch asked for this trial not to be published"
        slug = (report.get("report") or {}).get("slug", "")
        repo = (report.get("source") or {}).get("repo", "")
        if index is None:
            # Fail closed: without the catalogue we cannot tell whose card this is.
            return False, "the published catalogue could not be read to check whose card this is"
        owner = card_owner(index, slug)
        if owner is not None and normalize_repo(owner) != normalize_repo(repo):
            return False, (f"the card '{slug}' belongs to {owner}; a trial of {repo} "
                           "does not publish on it")
    return True, "published"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--index", default="", help="the published index.json, if it could be read")
    args = ap.parse_args(argv)

    report = json.loads(pathlib.Path(args.report).read_text())
    index = None
    ip = pathlib.Path(args.index) if args.index else None
    if ip and ip.is_file():
        try:
            index = json.loads(ip.read_text())
        except ValueError:
            index = None
    env = os.environ
    ok, why = decide(
        report,
        mode=env.get("MODE", "publish"),
        url_trial=env.get("URL_TRIAL") == "true",
        trial_publish=env.get("TRIAL_PUBLISH", "true") != "false",
        event_name=env.get("EVENT_NAME", ""),
        index=index,
    )
    print(f"publishable={'true' if ok else 'false'}")
    print(f"publish_reason={' '.join(why.split())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
