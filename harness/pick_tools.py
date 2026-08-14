"""Decide which tools a workflow run must verify.

A pull request used to verify `strait-razor-PowerSeqv2.31` whatever it changed,
because the workflow read `github.event.inputs.tool` — which only a dispatch
sets — and fell through to the default. So a PR editing a manifest was checked
by running an unrelated tool, and the one thing the PR touched was never run.
The check was green by construction and told nobody anything.

This picks the tools from the change itself:

  dispatch              the requested tool
  schedule              the SCHEDULE_BATCH least recently verified, so every
                        tool comes round without running all of them monthly
  pull request          every tools/<slug>/ the PR touches, up to MAX_TOOLS
  pull request, none    the default tool, as a canary for a harness, schema or
                        workflow change that no manifest accompanies
  pull request, a sweep the default tool, plus every touched tool named as
                        unverified (see MAX_TOOLS)

Emits `key=value` lines for $GITHUB_OUTPUT and a human note on stderr.

Usage:
  python harness/pick_tools.py --event pull_request --changed changed.txt \
      --default strait-razor-PowerSeqv2.31 >> "$GITHUB_OUTPUT"
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# How many tools one pull request may verify.
#
# Past this, the change is a sweep — a schema migration, a field added to every
# manifest — not a targeted edit to a handful of tools, and one docker build per
# tool would turn a one-line change into an afternoon of CI. Over the cap the run
# falls back to the canary and names every touched tool as unverified, rather
# than verifying an arbitrary six of sixteen: a partial sweep chosen by nothing
# in particular is not evidence about the sweep, but it reads like it.
MAX_TOOLS = 6

# How many tools the monthly re-verification refreshes.
#
# The point of re-verifying an UNCHANGED commit is that the commit is the only
# thing that does not change: a pip pin stops resolving, an apt package leaves
# the base image's repositories, a bioconda build is withdrawn, a repository is
# archived. STRsearch's Dockerfile pinned ubuntu 16.04 and old bioconda builds,
# and stopped building at a commit nobody had touched — which is exactly what a
# badge dated last June would otherwise keep asserting.
#
# So the schedule re-runs whether or not anything upstream moved. What it does
# not do is run everything every month: it takes the few whose published result
# is oldest, so each tool comes round every few months at a bounded cost, and a
# tool verified by hand last week goes to the back of the queue by itself.
#
# It never adds a card to the catalogue. Reports are written per slug and the
# index is rebuilt from the files present, so a re-run replaces a result rather
# than accumulating one.
SCHEDULE_BATCH = 5


def stalest(published: list[dict], root: pathlib.Path, limit: int) -> list[str]:
    """The `limit` published tools whose attestation is oldest, oldest first.

    Reads the catalogue STRhub itself publishes. Entries whose manifest is gone
    are skipped — a slug can outlive the directory that produced it, and there is
    nothing to re-run for those. An entry with no date sorts first: never having
    recorded when it ran is the strongest reason to run it again.
    """
    live = [
        e for e in published
        if isinstance(e, dict) and e.get("slug")
        and (root / "tools" / str(e["slug"]) / "manifest.yml").is_file()
    ]
    live.sort(key=lambda e: (e.get("generated") or ""))
    return [str(e["slug"]) for e in live[:limit]]


def tools_from_paths(paths: list[str], root: pathlib.Path) -> list[str]:
    """Tool slugs whose directory a change touches, in first-seen order.

    A slug is kept only if its manifest still exists in the checked-out tree, so
    a PR that DELETES a tool does not schedule a run against a directory that is
    no longer there.
    """
    slugs: list[str] = []
    for p in paths:
        parts = pathlib.PurePosixPath(p.strip()).parts
        if len(parts) < 3 or parts[0] != "tools":
            continue
        slug = parts[1]
        if slug in slugs:
            continue
        if not (root / "tools" / slug / "manifest.yml").is_file():
            continue
        slugs.append(slug)
    return slugs


def pick(event: str, input_tool: str, changed: list[str], default: str,
         root: pathlib.Path = ROOT,
         published: list[dict] | None = None) -> tuple[list[str], list[str], str]:
    """Return (tools to verify, touched tools left unverified, why)."""
    # A dispatch always wins: somebody asked for a specific tool by name.
    if input_tool.strip():
        return ([input_tool.strip()], [], "requested")

    if event == "schedule":
        batch = stalest(published or [], root, SCHEDULE_BATCH)
        if batch:
            return (batch, [],
                    f"monthly refresh of the {len(batch)} least recently verified")
        # No catalogue to read (first run, or the fetch failed). The default
        # canary is what this event did before, so nothing gets worse.
        return ([default], [], "monthly refresh; no published catalogue to rank")

    if event != "pull_request":
        return ([default], [], "default")

    found = tools_from_paths(changed, root)
    if not found:
        return ([default], [],
                "no tool directory changed; running the default as a canary")
    if len(found) > MAX_TOOLS:
        # The canary is often one of the touched tools itself; it is verified,
        # so it must not also be listed as unverified.
        return ([default], [t for t in found if t != default],
                f"{len(found)} tool directories changed, over the cap of "
                f"{MAX_TOOLS}; running the default as a canary instead")
    return (found, [], f"{len(found)} tool directory/ies changed")


def selftest() -> int:
    """Check the rules against a throwaway tree.

    Run in CI before the real pick, because this file decides whether the check
    below it examines anything at all: if it silently returned the default again,
    every PR would go green exactly as it used to, and nothing downstream would
    notice. No pytest — the harness keeps its dependencies to what a run needs.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for slug in ("alpha", "beta", "canary", "c1", "c2", "c3", "c4", "c5"):
            d = root / "tools" / slug
            d.mkdir(parents=True)
            (d / "manifest.yml").write_text("tool:\n  name: x\n")

        def check(label, got, want):
            if got != want:
                print(f"selftest FAILED: {label}\n  got  {got}\n  want {want}",
                      file=sys.stderr)
                raise SystemExit(1)

        # A dispatch names its tool, whatever the event says.
        check("dispatch",
              pick("workflow_dispatch", "beta", [], "canary", root)[0], ["beta"])

        # The monthly refresh takes the least recently verified, oldest first —
        # the reason it exists is commits that have not changed while the world
        # under them has, so it must never be conditioned on a new commit.
        catalogue = [
            {"slug": "alpha", "generated": "2026-08-01T00:00:00+00:00"},
            {"slug": "c1", "generated": "2026-01-01T00:00:00+00:00"},
            {"slug": "beta", "generated": "2026-05-01T00:00:00+00:00"},
            {"slug": "c2", "generated": None},
            {"slug": "gone", "generated": "2025-01-01T00:00:00+00:00"},
        ]
        got = pick("schedule", "", [], "canary", root, catalogue)[0]
        check("schedule takes the stalest, oldest first, capped",
              got, ["c2", "c1", "beta", "alpha"])
        check("schedule skips a slug whose manifest is gone",
              "gone" in got, False)
        check("schedule with no catalogue falls back to the canary",
              pick("schedule", "", [], "canary", root)[0], ["canary"])
        check("a dispatch still wins over the refresh",
              pick("schedule", "beta", [], "canary", root, catalogue)[0], ["beta"])

        # A PR is answered by what it touches — the whole point of this file.
        check("pr picks the changed tools",
              pick("pull_request", "",
                   ["tools/alpha/manifest.yml", "harness/report.py",
                    "tools/beta/Dockerfile", "tools/alpha/assets/regions.bed"],
                   "canary", root)[0],
              ["alpha", "beta"])
        check("pr with no tool falls back to the canary",
              pick("pull_request", "",
                   ["harness/report.py", "schema/manifest.schema.json"],
                   "canary", root)[0],
              ["canary"])
        check("a deleted tool is not scheduled",
              pick("pull_request", "", ["tools/gone/manifest.yml"], "canary", root)[0],
              ["canary"])
        # A file directly under tools/ belongs to no tool.
        check("a stray file under tools/ picks nothing",
              pick("pull_request", "", ["tools/README.md"], "canary", root)[0],
              ["canary"])

        # A sweep runs the canary and names the rest, with the canary counted once.
        swept = [f"tools/{s}/manifest.yml"
                 for s in ("alpha", "beta", "canary", "c1", "c2", "c3", "c4")]
        tools, dropped, _ = pick("pull_request", "", swept, "canary", root)
        check("a sweep runs the canary", tools, ["canary"])
        check("a sweep names the rest, canary excluded",
              dropped, ["alpha", "beta", "c1", "c2", "c3", "c4"])

    print("pick_tools selftest passed", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="check the rules against a throwaway tree and exit")
    ap.add_argument("--event", required=False,
                    help="github.event_name (pull_request, workflow_dispatch, schedule)")
    ap.add_argument("--input-tool", default="",
                    help="github.event.inputs.tool; empty for non-dispatch events")
    ap.add_argument("--changed", default="",
                    help="file listing the paths a pull request changed, one per line")
    ap.add_argument("--published", default="",
                    help="gh-pages index.json, used by the monthly refresh to rank "
                         "tools by how long ago they were last verified")
    ap.add_argument("--default", required=False,
                    help="tool to fall back on when the event names none")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.event or not args.default:
        ap.error("--event and --default are required unless --selftest is given")

    changed: list[str] = []
    if args.changed:
        p = pathlib.Path(args.changed)
        if p.exists():
            changed = [ln for ln in p.read_text().splitlines() if ln.strip()]

    published: list[dict] = []
    if args.published:
        pp = pathlib.Path(args.published)
        if pp.exists():
            try:
                data = json.loads(pp.read_text())
                published = data.get("tools") or []
            except (OSError, json.JSONDecodeError, AttributeError):
                # Optional input: an unreadable catalogue must not stop a run,
                # it only costs the ranking (see pick()).
                published = []

    tools, dropped, why = pick(
        args.event, args.input_tool, changed, args.default, pathlib.Path(args.root),
        published,
    )

    print(f"tools={json.dumps(tools)}")
    print(f"count={len(tools)}")
    print(f"dropped={json.dumps(dropped)}")

    note = f"Verifying {len(tools)} tool(s): {', '.join(tools)}  ({why})"
    print(note, file=sys.stderr)
    if dropped:
        print(
            f"NOT verified: {', '.join(dropped)}. "
            "Verify any of them with a manual dispatch of this workflow.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
