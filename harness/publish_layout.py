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

Within a commit's directory there are two places (docs/PLAN-Documented-Is-
The-Badge.md): the files at `<slug>/<sha>/` are the run of the repository's
own instructions (or of a recipe its maintainer submitted), which may stand
behind the badge; `<slug>/<sha>/curated/` holds the run of a recipe STRhub
wrote by hand, a note that never does. The alias is the newest commit AMONG
THE RUNS THAT MAY STAND BEHIND THE BADGE; only a tool that has none falls
back to its newest curated run, and its badge then says so.

What holds it (harness/tests/test_publish_layout.py): a newer commit published
later becomes the alias; an older one does not move it; the same commit
re-verified replaces its files; a curated run never displaces a documented
one, at any commit; a root set from before this layout is folded into its
place first, with its commit date fetched when missing, and competes as an
equal; no commit directory is ever deleted.

Usage (the deploy step, from a clone of gh-pages):
    python harness/publish_layout.py <site> --reports reports --slug hipstr
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import upstream  # noqa: E402
from certificate_text import instrument_of_report, BADGE_INSTRUMENTS  # noqa: E402

CURATED_DIR = "curated"
#: A tombstone beside a run's files: the run stays where it is and its URL
#: keeps resolving, but it is no longer a result — never the alias, never
#: the note, and the index lists it as retired with the reason. Written by
#: `retire`, by hand, for a run that can no longer be reproduced (its recipe
#: is gone from tools/) or that was STRhub's fault. Nothing is ever deleted.
TOMBSTONE = "retired.json"

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


def place_of(site: pathlib.Path, slug: str, sha: str, instrument: str) -> pathlib.Path:
    """Where a run of `instrument` at `sha` lives."""
    base = site / slug / sha
    return base if instrument in BADGE_INSTRUMENTS else base / CURATED_DIR


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
    if not report or not sha:
        return None
    dest = place_of(site, slug, sha, instrument_of_report(report))
    if (dest / f"{slug}.json").exists():
        return None
    _move_set(report_files(site, slug), dest)
    _backfill(report, dest / f"{slug}.json", resolve)
    return sha


def settle(site: pathlib.Path, slug: str, sha: str) -> bool:
    """Put a commit's runs where their instrument says. A set published at
    `<slug>/<sha>/` before instruments existed may be a curated run; it moves
    to `curated/` so a documented run of the same commit can land beside it
    instead of over it. Returns True when something moved."""
    base = site / slug / sha
    r = _read(base / f"{slug}.json")
    if not r or instrument_of_report(r) in BADGE_INSTRUMENTS:
        return False
    if (base / CURATED_DIR / f"{slug}.json").exists():
        return False        # a curated run is already there; leave both to be looked at
    _move_set(report_files(base, slug), base / CURATED_DIR)
    return True


def tombstone_of(folder: pathlib.Path) -> dict | None:
    try:
        t = json.loads((folder / TOMBSTONE).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return t if isinstance(t, dict) and t.get("retired") else None


def _with_tombstone(folder: pathlib.Path, r: dict) -> dict:
    """The report as scanned, carrying its tombstone when it has one. The
    file itself is not rewritten: the run is what it was, and the tombstone
    is a separate fact about it."""
    t = tombstone_of(folder)
    return {**r, "retired": t} if t else r


def scan(site: pathlib.Path, slug: str) -> list[tuple[str, str, dict]]:
    """Every run of `slug`: (sha, instrument, report), newest commit first,
    and at one commit the run that may stand behind the badge before the
    curated one. Reads what is there; `settle` is what puts it in place. A
    retired run is listed, with its tombstone under `retired`."""
    found = []
    base = site / slug
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            r = _read(d / f"{slug}.json")
            if r:
                found.append((d.name, instrument_of_report(r), _with_tombstone(d, r)))
            c = _read(d / CURATED_DIR / f"{slug}.json")
            if c:
                found.append((d.name, "curated", _with_tombstone(d / CURATED_DIR, c)))
    # Newest commit first; at one commit, the run that may stand behind the
    # badge before the curated one, whichever was verified later.
    def key(item):
        sha, instrument, r = item
        src = r.get("source") or {}
        committed = src.get("committed") or ""
        return (bool(committed), committed, instrument in BADGE_INSTRUMENTS, r.get("generated") or "")
    found.sort(key=key, reverse=True)
    return found


def alias_source(site: pathlib.Path, slug: str) -> tuple[str, str, dict] | None:
    """The run the root alias copies: the newest commit among the runs that
    may stand behind the badge; failing any, the newest curated run."""
    runs = [r for r in scan(site, slug) if not r[2].get("retired")]
    eligible = [r for r in runs if r[1] in BADGE_INSTRUMENTS]
    return (eligible or runs or [None])[0]


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

    # This run's files, replaced whole: a re-verification of the same commit
    # must not keep a log the new run did not write. Files only — the other
    # instrument's run of the same commit lives in a subdirectory and stays.
    instrument = instrument_of_report(report)
    settle(site, slug, sha)
    target = place_of(site, slug, sha, instrument)
    target.mkdir(parents=True, exist_ok=True)
    for f in report_files(target, slug):
        f.unlink()
    _copy_set(report_files(reports, slug), target)
    _backfill(report, target / f"{slug}.json", resolve)

    alias = write_alias(site, slug)
    return {"slug": slug, "sha": sha, "instrument": instrument,
            "alias": alias[0] if alias else None,
            "alias_instrument": alias[1] if alias else None,
            "versions": [(v_sha, v_inst) for v_sha, v_inst, _ in scan(site, slug)]}


def write_alias(site: pathlib.Path, slug: str) -> tuple[str, str] | None:
    """Point the root `<slug>.*` set at the run the badge may rest on (see
    alias_source), rewritten from scratch so nothing stale survives beside it.
    Every commit is settled first. Returns (sha, instrument) of the alias, or
    None when the slug has no run."""
    base = site / slug
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if d.is_dir():
                settle(site, slug, d.name)
    src = alias_source(site, slug)
    if not src:
        return None
    sha, instrument, _ = src
    for f in report_files(site, slug):
        f.unlink()
    _copy_set(report_files(place_of(site, slug, sha, instrument), slug), site)
    return sha, instrument


def retire(site: pathlib.Path, slug: str, sha: str, instrument: str, reason: str,
           when: str | None = None) -> pathlib.Path:
    """Put a tombstone beside one run and point the alias elsewhere. The
    run's files stay, so its URL keeps resolving; what changes is that it is
    no longer a result the site rests on. Returns the tombstone's path."""
    folder = place_of(site, slug, sha, instrument)
    if not (folder / f"{slug}.json").exists():
        raise SystemExit(f"{folder}: no run of {slug} at {sha[:7]} ({instrument})")
    if not reason.strip():
        raise SystemExit("a retirement needs a reason")
    stone = folder / TOMBSTONE
    stone.write_text(json.dumps({
        "retired": when or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "reason": reason.strip(),
    }, indent=2))
    write_alias(site, slug)
    return stone


def settle_all(site: pathlib.Path) -> list[tuple[str, str, str]]:
    """Every slug on the site: put each commit's runs where their instrument
    says and rewrite the alias by the rule. For the day the rule changes —
    once, by hand, after docs/PLAN-Documented-Is-The-Badge.md — and harmless
    any other day. Returns (slug, alias sha, alias instrument) per slug."""
    out = []
    for d in sorted(site.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and (site / f"{d.name}.json").exists():
            alias = write_alias(site, d.name)
            if alias:
                out.append((d.name, alias[0], alias[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("site", help="a clone of gh-pages")
    ap.add_argument("--reports", default="reports", help="the run's reports/ directory")
    ap.add_argument("--slug", help="the slug the run published as")
    ap.add_argument("--settle-all", action="store_true",
                    help="no run: settle every slug's runs by instrument and rewrite every alias")
    ap.add_argument("--retire", metavar="SHA",
                    help="no run: put a tombstone beside the run of --slug at this commit")
    ap.add_argument("--instrument", default="documented", choices=["documented", "maintainer", "curated"],
                    help="with --retire: which run at that commit")
    ap.add_argument("--reason", default="", help="with --retire: why, for the reader")
    args = ap.parse_args()
    if args.retire:
        if not args.slug:
            ap.error("--slug is required with --retire")
        stone = retire(pathlib.Path(args.site), args.slug, args.retire, args.instrument, args.reason)
        print(f"retired {args.slug} @ {args.retire[:7]} ({args.instrument}): {stone}")
        return 0
    if args.settle_all:
        for slug, sha, instrument in settle_all(pathlib.Path(args.site)):
            print(f"{slug}: alias {sha[:7]} ({instrument})")
        return 0
    if not args.slug:
        ap.error("--slug is required unless --settle-all")
    done = place(pathlib.Path(args.site), pathlib.Path(args.reports), args.slug,
                 resolve=upstream.commit_date)
    where = "" if done["alias"] == done["sha"] and done["alias_instrument"] == done["instrument"] \
        else f" (alias stays at {done['alias'][:7]} {done['alias_instrument']})"
    print(f"{done['slug']} @ {done['sha'][:7]} placed as {done['instrument']}; "
          f"{len(done['versions'])} run(s) known{where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
