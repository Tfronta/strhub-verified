"""Where a run's files go on gh-pages, and which commit a tool's alias points at.

The unit published is a tool AT A COMMIT, not a tool. Every run lands in its
own directory, `<slug>/<sha>/`, with its files under the names the run wrote
them (so the HTML copy's relative links and the log names inside the JSON keep
working); the root `<slug>.*` set — what the web, the badge and shields read —
is an alias of the NEWEST commit among those directories, newest by the date
the commit was made, not by when it was verified.

That one rule is what lets anyone verify any commit from the form. Before it,
a slug was one file, and a run that published wrote over whatever was there:
someone verifying the first commit of STRspy v2 from strhub.app would have
replaced the current attestation with a two-year-old one. Now it lands below.
See docs/PLAN-Version-History.md.

What holds it (harness/tests/test_publish_layout.py): a newer commit published
later becomes the alias; an older one does not move it; the same commit
re-verified replaces its directory; a root set from before this layout is
folded into its directory first, with its commit date fetched when missing,
and competes as an equal; no commit directory is ever deleted.

Usage (the deploy step, from a clone of gh-pages):
    python harness/publish_layout.py <site> --reports reports --slug hipstr
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import upstream  # noqa: E402

#: How a report is looked up under its directory: the same stem the run wrote.
Resolver = Callable[[str, str], "str | None"]


def report_files(folder: pathlib.Path, slug: str) -> list[pathlib.Path]:
    """Every file of one run: `<slug>.json`, `.html`, `.pdf`, `.badge.json`,
    `.summary.md`, `.log-*.txt`. Not the recipe attachment, which the web reads
    out of the run's artifact and which is committed under tools/ when it
    publishes; and not another slug that happens to share a prefix
    (`hipstr-y.json` does not start with `hipstr.`)."""
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.name.startswith(f"{slug}.")
        and not p.name.endswith(".recipe.json")
    )


def _read(path: pathlib.Path) -> dict | None:
    try:
        r = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return r if isinstance(r, dict) and r.get("schema") == "strhub-verified/1" else None


def sha_of(report: dict) -> str | None:
    src = report.get("source") or {}
    return src.get("ref_resolved") or src.get("ref") or None


def rank(report: dict) -> tuple:
    """Newest first when sorted descending. A report that knows when its commit
    was made outranks one that does not; among those that do, the commit date
    decides; the verification date only breaks ties (a re-verified commit is
    the same commit)."""
    src = report.get("source") or {}
    committed = src.get("committed") or ""
    return (bool(committed), committed, report.get("generated") or "")


def _backfill(report: dict, path: pathlib.Path, resolve: Resolver | None) -> None:
    """Give a report its commit date when it has none and GitHub can say.
    Written back, so it is asked once."""
    if not resolve or (report.get("source") or {}).get("committed"):
        return
    repo = (report.get("source") or {}).get("repo") or ""
    sha = sha_of(report) or ""
    when = resolve(repo, sha) if repo and sha else None
    if when:
        report.setdefault("source", {})["committed"] = when
        path.write_text(json.dumps(report, indent=2))


def _move_set(files: list[pathlib.Path], dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.move(str(f), str(dest / f.name))


def _copy_set(files: list[pathlib.Path], dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(str(f), str(dest / f.name))


def fold_root(site: pathlib.Path, slug: str, resolve: Resolver | None = None) -> str | None:
    """A root set from before this layout becomes the directory of its commit.

    It was the newest at the time, and it must compete on its commit date
    like any other — so the date is fetched if the report predates it. Nothing
    is done when its directory already exists (the root is then the alias
    this module wrote, not a stranded set). Returns the sha folded, or None."""
    root_json = site / f"{slug}.json"
    report = _read(root_json) if root_json.exists() else None
    sha = sha_of(report) if report else None
    if not report or not sha or (site / slug / sha).is_dir():
        return None
    _move_set(report_files(site, slug), site / slug / sha)
    _backfill(report, site / slug / sha / f"{slug}.json", resolve)
    return sha


def scan(site: pathlib.Path, slug: str) -> list[tuple[str, dict]]:
    """Every commit of `slug` with its report, newest commit first."""
    found = []
    base = site / slug
    if base.is_dir():
        for d in sorted(base.iterdir()):
            r = _read(d / f"{slug}.json") if d.is_dir() else None
            if r:
                found.append((d.name, r))
    found.sort(key=lambda item: rank(item[1]), reverse=True)
    return found


def place(site: pathlib.Path, reports: pathlib.Path, slug: str,
          resolve: Resolver | None = None) -> dict:
    """Land one run and point the alias at the newest commit. Returns what was
    done: the run's sha, the alias's sha, and every commit known, newest first."""
    run_json = reports / f"{slug}.json"
    report = _read(run_json)
    if not report:
        raise SystemExit(f"{run_json}: not an attestation report")
    sha = sha_of(report)
    if not sha:
        raise SystemExit(f"{run_json}: no pinned commit (source.ref_resolved)")

    fold_root(site, slug, resolve)

    # This run's directory, replaced whole: a re-verification of the same
    # commit must not keep a log the new run did not write.
    target = site / slug / sha
    if target.is_dir():
        shutil.rmtree(target)
    _copy_set(report_files(reports, slug), target)
    _backfill(report, target / f"{slug}.json", resolve)

    newest_sha = write_alias(site, slug)
    return {"slug": slug, "sha": sha, "alias": newest_sha,
            "versions": [v_sha for v_sha, _ in scan(site, slug)]}


def write_alias(site: pathlib.Path, slug: str) -> str | None:
    """Point the root `<slug>.*` set at the newest commit's directory,
    rewritten from scratch so nothing stale survives beside it. Returns the
    commit the alias now names, or None when the slug has no directory."""
    versions = scan(site, slug)
    if not versions:
        return None
    newest_sha = versions[0][0]
    for f in report_files(site, slug):
        f.unlink()
    _copy_set(report_files(site / slug / newest_sha, slug), site)
    return newest_sha


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("site", help="a clone of gh-pages")
    ap.add_argument("--reports", default="reports", help="the run's reports/ directory")
    ap.add_argument("--slug", required=True, help="the slug the run published as")
    args = ap.parse_args()
    done = place(pathlib.Path(args.site), pathlib.Path(args.reports), args.slug,
                 resolve=upstream.commit_date)
    moved = "" if done["alias"] == done["sha"] else f" (alias stays at {done['alias'][:7]}: a newer commit)"
    print(f"{done['slug']} @ {done['sha'][:7]} placed; {len(done['versions'])} commit(s) known{moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
