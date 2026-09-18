"""Fold the pre-consolidation catalogue into the per-commit layout. Run once.

Before one slug per tool (PR #33), a run was published as `<name>-<version>`
or `<name>-<sha>`: `hipstr-v0-7`, `hipstr-b2033bf`, `straitrazor-v3-0`. They
are still on gh-pages, each as a root set with its own index entry, some of
them the same commit twice, none with the date its commit was made. Tanda 3 of
docs/PLAN-Version-History.md: each becomes `<slug>/<sha>/` under the slug the
tool is filed under TODAY (the one its committed recipe under tools/ declares,
or the one a trial from its URL would be filed under), two sets of one commit
become one, the commit date is fetched, and the root aliases are rewritten to
the newest commit of each slug. The old root files are gone afterwards; the
web's history folds them by heuristic until then and needs nothing after.

The mapping is a table, not a guess: every legacy slug on gh-pages is named
here with where it goes. A slug on the site that this table does not know is
reported and left alone.

Dry run by default. To apply, from a fresh clone of gh-pages, AFTER the deploy
step publishes by commit (PR #39 merged):

    git clone --branch gh-pages https://github.com/Tfronta/strhub-verified site
    GH_TOKEN=... python harness/migrate_layout.py site            # the plan
    GH_TOKEN=... python harness/migrate_layout.py site --apply    # do it
    python harness/build_index.py site --out site/index.html
    (cd site && git add -A && git status && git commit -m "migrate: per-commit layout" && git push)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import publish_layout as pl  # noqa: E402
import upstream  # noqa: E402

#: legacy slug on gh-pages -> the slug the same verification is filed under
#: today. `straitrazor` is what a trial of Ahhgust/STRaitRazor from its URL is
#: filed under (catalogue_slug of the name as the README writes it); the two
#: kit recipes under tools/ keep their own slugs, because a kit is a different
#: verification.
LEGACY = {
    "gangstr-v2-5": "gangstr",
    "hipstr-v0-7": "hipstr",
    "hipstr-b2033bf": "hipstr",
    "hipstr-v0-7-y": "hipstr-y",
    "hipstr-b2033bf-y": "hipstr-y",
    "strait-razor-ForenSeqv1.27": "strait-razor-forenseq",
    "strait-razor-PowerSeqv2.31": "strait-razor-powerseq",
    "strait-razor-b618e93": "straitrazor",
    "straitrazor-v3-0": "straitrazor",
    "strsearch-c70179b": "strsearch",
    "strspy-v2-0-ont": "strspy-ont",
}

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
#: The old naming: a version (`-v0-7`, dots written as dashes) or a short sha
#: after the name, with or without an assay suffix (`-y`, `-ont`) after it.
OLD_NAMING = re.compile(r"-(?:v\d+(?:-\d+)*|[0-9a-f]{7,40})(?:-[a-z]+)?$")


def legacy_slugs(site: pathlib.Path) -> list[str]:
    """The table's slugs that are on the site, as root sets, in name order."""
    found = []
    for p in sorted(site.glob("*.json")):
        if p.name.endswith(".badge.json") or p.name == "index.json":
            continue
        if pl._read(p) and p.stem != LEGACY.get(p.stem, p.stem):
            found.append(p.stem)
    return found


def unknown_slugs(site: pathlib.Path) -> list[str]:
    """Root reports in the old naming that the table does not know: reported,
    never touched. A bare tool slug (`hipstr`) is not one of these."""
    out = []
    for p in sorted(site.glob("*.json")):
        if p.name.endswith(".badge.json") or p.name == "index.json" or not pl._read(p):
            continue
        slug = p.stem
        if slug in LEGACY:
            continue
        if OLD_NAMING.search(slug):
            out.append(slug)
    return out


def _prefer(a: tuple[str, dict], b: tuple[str, dict]) -> tuple[str, dict]:
    """Of two sets for one commit, the one to keep: a version that is a tag
    over a bare sha (it says more), then the later verification, then more
    logs. Deterministic, so the plan reads the same every time."""
    def key(item):
        slug, r = item
        version = (r.get("tool") or {}).get("version") or ""
        return (not SHA_RE.match(version.lower()), r.get("generated") or "",
                len(r.get("logs") or {}), slug)
    return max(a, b, key=key)


def _retitle(folder: pathlib.Path, legacy: str, target: str) -> None:
    """Rename a set's files from the legacy stem to the target's, and every
    reference the files make to each other: the log names inside the JSON,
    the links and the slug in the HTML copy and the summary. The PDF is left
    as it was written: it names the legacy permalink, and rewriting a binary
    is not a thing to do to a certificate."""
    for f in pl.report_files(folder, legacy):
        f.rename(folder / (target + f.name[len(legacy):]))
    report_path = folder / f"{target}.json"
    report = json.loads(report_path.read_text())
    logs = report.get("logs") or {}
    for leg, name in list(logs.items()):
        if name.startswith(f"{legacy}."):
            logs[leg] = target + name[len(legacy):]
    report_path.write_text(json.dumps(report, indent=2))
    for name in (f"{target}.html", f"{target}.summary.md"):
        p = folder / name
        if p.exists():
            text = p.read_text()
            text = text.replace(f"{legacy}.", f"{target}.")
            text = text.replace(f"<code>{legacy}</code>", f"<code>{target}</code>")
            text = text.replace(f"({legacy})", f"({target})")
            p.write_text(text)


def plan(site: pathlib.Path) -> list[dict]:
    """What would happen, one line per legacy slug, in the order they are
    listed. Two sets of one commit under one target are one verification:
    the one _prefer keeps moves, the other is dropped."""
    entries = []
    for legacy in legacy_slugs(site):
        report = pl._read(site / f"{legacy}.json")
        entries.append((legacy, LEGACY[legacy], pl.sha_of(report) or "", report))

    winners: dict[tuple[str, str], tuple[str, dict]] = {}
    for legacy, target, sha, report in entries:
        if not sha:
            continue
        key = (target, sha)
        winners[key] = _prefer(winners[key], (legacy, report)) if key in winners else (legacy, report)

    steps = []
    for legacy, target, sha, report in entries:
        if not sha:
            steps.append({"legacy": legacy, "action": "skip", "why": "no pinned commit"})
        elif (site / target / sha).is_dir():
            steps.append({"legacy": legacy, "target": target, "sha": sha, "action": "drop",
                          "why": f"{target}/{sha[:7]} is already published by commit"})
        elif winners[(target, sha)][0] != legacy:
            steps.append({"legacy": legacy, "target": target, "sha": sha, "action": "drop",
                          "why": f"the same commit as {winners[(target, sha)][0]}, which is kept"})
        else:
            steps.append({"legacy": legacy, "target": target, "sha": sha, "action": "move"})
    return steps


def migrate(site: pathlib.Path, resolve: pl.Resolver | None = None, apply: bool = False) -> dict:
    """Carry the plan out (when `apply`), then fold every touched slug's root
    set and rewrite its alias. Returns the plan, the slugs touched and what
    was left alone."""
    steps = plan(site)
    unknown = unknown_slugs(site)
    touched: list[str] = []
    if apply:
        for s in steps:
            if s["action"] == "move":
                dest = site / s["target"] / s["sha"]
                pl._move_set(pl.report_files(site, s["legacy"]), dest)
                _retitle(dest, s["legacy"], s["target"])
                report = pl._read(dest / f"{s['target']}.json")
                if report:
                    pl._backfill(report, dest / f"{s['target']}.json", resolve)
                if s["target"] not in touched:
                    touched.append(s["target"])
            elif s["action"] == "drop":
                for f in pl.report_files(site, s["legacy"]):
                    f.unlink()
        # A slug already filed under its own name (`hipstr` today) has a root
        # set and no directory; it joins the layout like any legacy set does,
        # and the alias of every slug touched is rewritten to its newest commit.
        for target in sorted(set(touched) | set(_bare_root_slugs(site, unknown))):
            pl.fold_root(site, target, resolve)
            pl.write_alias(site, target)
            if target not in touched:
                touched.append(target)
    return {"steps": steps, "touched": touched, "unknown": unknown}


def _bare_root_slugs(site: pathlib.Path, unknown: list[str]) -> list[str]:
    """Root sets whose slug is already the one they are filed under."""
    return [p.stem for p in sorted(site.glob("*.json"))
            if not p.name.endswith(".badge.json") and p.name != "index.json"
            and pl._read(p) and p.stem not in LEGACY and p.stem not in unknown]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("site", help="a fresh clone of gh-pages")
    ap.add_argument("--apply", action="store_true", help="carry the plan out (default: print it)")
    args = ap.parse_args()
    site = pathlib.Path(args.site)
    done = migrate(site, resolve=upstream.commit_date, apply=args.apply)
    for s in done["steps"]:
        where = f" -> {s['target']}/{s['sha'][:7]}" if s.get("target") else ""
        why = f"  ({s['why']})" if s.get("why") else ""
        print(f"{s['action']:5} {s['legacy']}{where}{why}")
    for slug in done["unknown"]:
        print(f"left  {slug}  (not in the table; looks like the old naming — add it and run again)")
    if args.apply:
        print(f"applied; aliases rewritten for: {', '.join(sorted(done['touched'])) or '-'}")
        print("now: python harness/build_index.py <site> --out <site>/index.html, review, commit, push")
    else:
        print("dry run; nothing changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
