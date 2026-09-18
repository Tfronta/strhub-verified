"""The alias points at the newest commit, whatever order things were verified in.

A slug used to be one file that every publishing run wrote over, so verifying
an old commit from the form would have replaced the current attestation with
an older one. Now every run lands in `<slug>/<sha>/` and the root set is an
alias of the newest commit — newest by when the commit was made."""
import json
import pathlib

import publish_layout as pl

SLUG = "hipstr"
REPO = "https://github.com/tfwillems/HipSTR"
OLD, NEW, NEWER = "a" * 40, "b" * 40, "c" * 40


def _report(sha, committed, generated, level="content"):
    r = {"schema": "strhub-verified/1", "tool": {"name": "HipSTR"}, "level": level,
         "source": {"repo": REPO, "ref": sha, "ref_resolved": sha},
         "generated": generated, "gates": {}, "scope": "x",
         "logs": {"external": f"{SLUG}.log-external.txt"}}
    if committed:
        r["source"]["committed"] = committed
    return r


def _run(tmp_path, sha, committed, generated, logs=("external",), name="reports"):
    """A run's reports/ directory, as the workflow leaves it."""
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    for f in d.iterdir():
        f.unlink()
    (d / f"{SLUG}.json").write_text(json.dumps(_report(sha, committed, generated)))
    (d / f"{SLUG}.html").write_text(f"<html>{sha}</html>")
    (d / f"{SLUG}.pdf").write_bytes(b"%PDF " + sha.encode())
    (d / f"{SLUG}.badge.json").write_text("{}")
    (d / f"{SLUG}.summary.md").write_text(f"# {sha}")
    for leg in logs:
        (d / f"{SLUG}.log-{leg}.txt").write_text(f"log {leg} {sha}")
    (d / f"{SLUG}.recipe.json").write_text("{}")          # never published
    (d / "hipstr-y.json").write_text(json.dumps(_report(sha, committed, generated)))  # another slug
    return d


def _alias_sha(site):
    return json.loads((site / f"{SLUG}.json").read_text())["source"]["ref_resolved"]


def test_a_run_lands_in_its_commits_directory_and_becomes_the_alias(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    done = pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG)
    assert done == {"slug": SLUG, "sha": NEW, "alias": NEW, "versions": [NEW]}
    assert (site / SLUG / NEW / f"{SLUG}.json").exists()
    assert (site / SLUG / NEW / f"{SLUG}.log-external.txt").read_text() == f"log external {NEW}"
    assert _alias_sha(site) == NEW
    assert (site / f"{SLUG}.pdf").read_bytes().endswith(NEW.encode())
    # The recipe attachment and the other slug's file stayed out.
    assert not (site / SLUG / NEW / f"{SLUG}.recipe.json").exists()
    assert not (site / "hipstr-y.json").exists() and not (site / SLUG / NEW / "hipstr-y.json").exists()


def test_an_older_commit_published_later_lands_below_and_does_not_move_the_alias(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG)
    # Verified LATER, but a commit made two years EARLIER.
    done = pl.place(site, _run(tmp_path, OLD, "2024-03-10T00:00:00Z", "2026-09-18T00:00:00+00:00"), SLUG)
    assert done["alias"] == NEW and done["versions"] == [NEW, OLD]
    assert _alias_sha(site) == NEW
    assert (site / SLUG / OLD / f"{SLUG}.json").exists()


def test_a_newer_commit_published_later_takes_the_alias(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG)
    done = pl.place(site, _run(tmp_path, NEWER, "2026-08-01T00:00:00Z", "2026-09-18T00:00:00+00:00"), SLUG)
    assert done["alias"] == NEWER and done["versions"] == [NEWER, NEW]
    assert _alias_sha(site) == NEWER
    assert (site / f"{SLUG}.html").read_text() == f"<html>{NEWER}</html>"


def test_the_same_commit_reverified_replaces_its_directory_whole(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00+00:00", logs=("own", "external")), SLUG)
    assert (site / SLUG / NEW / f"{SLUG}.log-own.txt").exists() and (site / f"{SLUG}.log-own.txt").exists()
    done = pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00", logs=("external",)), SLUG)
    assert done["versions"] == [NEW]
    # A log the new run did not write is gone from the directory AND the alias.
    assert not (site / SLUG / NEW / f"{SLUG}.log-own.txt").exists()
    assert not (site / f"{SLUG}.log-own.txt").exists()
    assert json.loads((site / f"{SLUG}.json").read_text())["generated"].startswith("2026-09")


def test_a_root_set_from_before_the_layout_is_folded_in_and_dated(tmp_path):
    """What is on gh-pages today: one flat set per slug, no directory, and a
    report that never recorded when its commit was made. It was the newest at
    the time; it has to compete as one, so its date is fetched once."""
    site = tmp_path / "site"; site.mkdir()
    legacy = _run(tmp_path, NEW, None, "2026-09-01T00:00:00+00:00", name="legacy")
    for f in pl.report_files(legacy, SLUG):
        f.rename(site / f.name)
    asked = []

    def resolve(repo, sha):
        asked.append((repo, sha))
        return "2026-02-01T00:00:00Z"

    # An OLDER commit arrives after the layout change.
    done = pl.place(site, _run(tmp_path, OLD, "2024-03-10T00:00:00Z", "2026-09-18T00:00:00+00:00"), SLUG, resolve=resolve)
    assert asked == [(REPO, NEW)]
    assert done["alias"] == NEW and done["versions"] == [NEW, OLD]
    folded = json.loads((site / SLUG / NEW / f"{SLUG}.json").read_text())
    assert folded["source"]["committed"] == "2026-02-01T00:00:00Z"
    assert _alias_sha(site) == NEW


def test_a_report_without_a_commit_date_ranks_below_every_dated_one(tmp_path):
    """No GitHub to ask (the resolver returns nothing): a dated commit wins,
    and the undated one is still kept and listed."""
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, None, "2026-09-18T00:00:00+00:00"), SLUG, resolve=lambda repo, sha: None)
    done = pl.place(site, _run(tmp_path, OLD, "2024-03-10T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG, resolve=lambda repo, sha: None)
    assert done["versions"] == [OLD, NEW] and done["alias"] == OLD


def test_no_commit_directory_is_ever_deleted(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    for sha, when in ((OLD, "2024-03-10T00:00:00Z"), (NEW, "2026-02-01T00:00:00Z"), (NEWER, "2026-08-01T00:00:00Z")):
        pl.place(site, _run(tmp_path, sha, when, "2026-09-18T00:00:00+00:00"), SLUG)
    assert sorted(p.name for p in (site / SLUG).iterdir()) == sorted([OLD, NEW, NEWER])
    assert [s for s, _ in pl.scan(site, SLUG)] == [NEWER, NEW, OLD]


def test_a_run_that_is_not_a_report_is_refused(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / f"{SLUG}.json").write_text(json.dumps({"schema": "strhub-verified/index/2"}))
    try:
        pl.place(site, bad, SLUG)
    except SystemExit as exc:
        assert "not an attestation report" in str(exc)
    else:
        raise AssertionError("an index was accepted as a run")
