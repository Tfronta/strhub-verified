"""The one-off migration: the pre-consolidation slugs become commit
directories under the slug each tool is filed under today, one commit
published twice becomes one, dates are fetched, aliases point at the newest
commit, and nothing the table does not name is touched."""
import json
import pathlib

import build_index
import migrate_layout as ml
import publish_layout as pl

# The catalogue as gh-pages holds it on 2026-09-18: slug -> (name, version, sha, types, logs, generated)
B2033 = "b2033bf000000000000000000000000000000000"
E12E9 = "12e989b000000000000000000000000000000000"
B618 = "b618e93000000000000000000000000000000000"
SITE = {
    "gangstr-v2-5": ("GangSTR", "v2.5", "6ea9b2b" + "0" * 33, ["illumina-bam-hg38"], ["build", "external", "own"], "2026-09-15T10:00:00+00:00"),
    "hipstr-b2033bf": ("hipstr", "b2033bf", B2033, ["illumina-bam-hg38"], ["build", "external"], "2026-09-15T12:00:00+00:00"),
    "hipstr-b2033bf-y": ("hipstr", "b2033bf", B2033, ["illumina-bam-hg38-y"], ["build", "external"], "2026-09-15T12:00:00+00:00"),
    "hipstr-v0-7": ("hipstr", "v0.7", B2033, ["illumina-bam-hg38"], ["build", "external", "own"], "2026-09-15T11:00:00+00:00"),
    "hipstr-v0-7-y": ("hipstr", "v0.7", B2033, ["illumina-bam-hg38-y"], ["build", "external", "own"], "2026-09-15T11:00:00+00:00"),
    "hipstr": ("HipSTR", "12e989b", E12E9, ["illumina-bam-hg38"], ["build", "external"], "2026-09-16T21:14:32+00:00"),
    "strait-razor-ForenSeqv1.27": ("STRait Razor", "v3", B618, ["illumina-str-fastq"], ["build"], "2026-09-15T09:00:00+00:00"),
    "strait-razor-PowerSeqv2.31": ("STRait Razor", "v3", B618, ["illumina-str-fastq"], ["build"], "2026-09-15T09:00:00+00:00"),
    "strait-razor-b618e93": ("STRait Razor", "b618e93", B618, ["illumina-str-fastq"], ["build"], "2026-09-15T13:00:00+00:00"),
    "straitrazor-v3-0": ("STRaitRazor", "v3.0", B618, ["illumina-str-fastq"], ["build"], "2026-09-15T08:00:00+00:00"),
    "strsearch-c70179b": ("STRsearch", "c70179b", "c70179b" + "0" * 33, ["illumina-bam-hg38"], ["build", "external"], "2026-09-15T10:00:00+00:00"),
    "strspy-v2-0-ont": ("STRspy", "v2.0", "dafdee7" + "0" * 33, ["ont-bam-hg38"], ["build", "external"], "2026-09-15T10:00:00+00:00"),
}
DATES = {B2033: "2019-09-04T00:00:00Z", E12E9: "2026-02-01T00:00:00Z", B618: "2020-01-01T00:00:00Z"}


def _site(tmp_path, extra=None):
    site = tmp_path / "site"
    site.mkdir()
    for slug, (name, version, sha, types, logs, generated) in {**SITE, **(extra or {})}.items():
        r = {"schema": "strhub-verified/1", "tool": {"name": name, "version": version}, "level": "content",
             "source": {"repo": "https://github.com/x/" + name.lower().replace(" ", ""), "ref": sha, "ref_resolved": sha},
             "generated": generated, "gates": {}, "scope": "x",
             "datasets": [{"leg": "external", "type": types[0], "available": True, "passed": True}],
             "logs": {leg: f"{slug}.log-{leg}.txt" for leg in logs}}
        if slug == "hipstr":   # the one set that came from a trial from the URL
            r["caveats"] = {"source": "detect_recipe", "items": ["x"]}
        (site / f"{slug}.json").write_text(json.dumps(r))
        (site / f"{slug}.html").write_text(
            f"<title>STRhub Verified · {name} ({slug})</title><li>Variant: <code>{slug}</code></li>"
            f'<a href="{slug}.json">{slug}.json</a> <a href="{slug}.log-build.txt">log</a>')
        (site / f"{slug}.summary.md").write_text(f"# STRhub Verified: {name} ({slug})\n")
        (site / f"{slug}.pdf").write_bytes(b"%PDF " + slug.encode())
        (site / f"{slug}.badge.json").write_text("{}")
        for leg in logs:
            (site / f"{slug}.log-{leg}.txt").write_text(f"{slug} {leg}")
    return site


def _resolve(repo, sha):
    return DATES.get(sha, "2021-06-01T00:00:00Z")


def test_the_plan_names_every_legacy_slug_and_keeps_one_set_per_commit(tmp_path):
    steps = {s["legacy"]: s for s in ml.plan(_site(tmp_path))}
    assert set(steps) == set(ml.LEGACY)
    assert steps["hipstr-v0-7"]["action"] == "move" and steps["hipstr-v0-7"]["target"] == "hipstr"
    # The tag-labelled set is kept over the bare-sha one of the same commit.
    assert steps["hipstr-b2033bf"]["action"] == "drop" and "hipstr-v0-7" in steps["hipstr-b2033bf"]["why"]
    assert steps["hipstr-v0-7-y"]["action"] == "move" and steps["hipstr-b2033bf-y"]["action"] == "drop"
    assert steps["straitrazor-v3-0"]["action"] == "move" and steps["strait-razor-b618e93"]["action"] == "drop"
    # Two kits at one commit are two verifications: both move, to their own slugs.
    assert steps["strait-razor-ForenSeqv1.27"]["action"] == "move" and steps["strait-razor-ForenSeqv1.27"]["target"] == "strait-razor-forenseq"
    assert steps["strait-razor-PowerSeqv2.31"]["action"] == "move" and steps["strait-razor-PowerSeqv2.31"]["target"] == "strait-razor-powerseq"


def test_a_dry_run_changes_nothing(tmp_path):
    site = _site(tmp_path)
    before = sorted(p.relative_to(site).as_posix() for p in site.rglob("*"))
    ml.migrate(site, resolve=_resolve, apply=False)
    assert sorted(p.relative_to(site).as_posix() for p in site.rglob("*")) == before


def test_applying_lays_every_tool_out_by_commit_with_aliases_on_the_newest(tmp_path):
    site = _site(tmp_path)
    done = ml.migrate(site, resolve=_resolve, apply=True)
    assert done["unknown"] == []
    # Every legacy root set is gone; every tool has its directories and its alias.
    for legacy in ml.LEGACY:
        assert not list(site.glob(f"{legacy}.*")), legacy
    assert sorted(done["touched"]) == ["gangstr", "hipstr", "hipstr-y", "strait-razor-forenseq",
                                       "strait-razor-powerseq", "straitrazor", "strsearch", "strspy-ont"]
    # Hand-written recipes land under curated/; the one trial from the URL at its commit's root.
    assert (site / "hipstr" / B2033 / "curated" / "hipstr.json").exists()
    assert (site / "hipstr" / E12E9 / "hipstr.json").exists()      # the bare root set, folded in
    assert (site / "hipstr-y" / B2033 / "curated" / "hipstr-y.json").exists()
    assert (site / "straitrazor" / B618 / "curated" / "straitrazor.json").exists()
    # The alias is the newest commit AMONG THE RUNS THAT MAY STAND BEHIND THE BADGE:
    # hipstr's documented run at 12e989b, not the later-verified curated v0.7.
    alias = json.loads((site / "hipstr.json").read_text())
    assert alias["source"]["ref_resolved"] == E12E9 and alias["source"]["committed"] == DATES[E12E9]
    assert alias["caveats"]["source"] == "detect_recipe"
    # A tool with only curated runs keeps a curated alias, marked as such.
    y = json.loads((site / "hipstr-y.json").read_text())
    assert y["source"]["ref_resolved"] == B2033 and pl.instrument_of_report(y) == "curated"


def test_moved_sets_are_renamed_inside_and_out(tmp_path):
    site = _site(tmp_path)
    ml.migrate(site, resolve=_resolve, apply=True)
    d = site / "hipstr" / B2033 / "curated"
    assert sorted(p.name for p in d.iterdir()) == [
        "hipstr.badge.json", "hipstr.html", "hipstr.json", "hipstr.log-build.txt",
        "hipstr.log-external.txt", "hipstr.log-own.txt", "hipstr.pdf", "hipstr.summary.md"]
    r = json.loads((d / "hipstr.json").read_text())
    assert r["logs"] == {"build": "hipstr.log-build.txt", "external": "hipstr.log-external.txt", "own": "hipstr.log-own.txt"}
    assert r["tool"]["version"] == "v0.7"                       # the kept set, not the bare-sha one
    assert r["source"]["committed"] == DATES[B2033]              # fetched
    html = (d / "hipstr.html").read_text()
    assert 'href="hipstr.json"' in html and 'href="hipstr.log-build.txt"' in html
    assert "<code>hipstr</code>" in html and "(hipstr)" in html and "hipstr-v0-7" not in html
    assert "(hipstr)" in (d / "hipstr.summary.md").read_text()
    # The dropped duplicate's files are gone, not moved.
    assert not (d / "hipstr-b2033bf.json").exists() and not list(site.glob("hipstr-b2033bf.*"))


def test_the_index_afterwards_lists_only_todays_slugs_with_their_history(tmp_path):
    site = _site(tmp_path)
    ml.migrate(site, resolve=_resolve, apply=True)
    cat = build_index.build_catalogue(site)
    assert sorted(t["slug"] for t in cat["tools"]) == ["gangstr", "hipstr", "hipstr-y", "strait-razor-forenseq",
                                                       "strait-razor-powerseq", "straitrazor", "strsearch", "strspy-ont"]
    hipstr = next(t for t in cat["tools"] if t["slug"] == "hipstr")
    assert [(v["sha"], v["instrument"]) for v in hipstr["versions"]] == [(E12E9, "documented"), (B2033, "curated")]
    assert hipstr["versions"][1]["version"] == "v0.7" and hipstr["versions"][1]["committed"] == DATES[B2033]
    assert hipstr["versions"][1]["report"] == f"hipstr/{B2033}/curated/hipstr.json"
    assert hipstr["instrument"] == "documented"
    assert next(t for t in cat["tools"] if t["slug"] == "strspy-ont")["instrument"] == "curated"


def test_a_slug_the_table_does_not_know_is_reported_and_left_alone(tmp_path):
    site = _site(tmp_path, extra={"newtool-v9-9": ("NewTool", "v9.9", "f" * 40, ["illumina-bam-hg38"], ["build"], "2026-09-17T00:00:00+00:00")})
    done = ml.migrate(site, resolve=_resolve, apply=True)
    assert done["unknown"] == ["newtool-v9-9"]
    assert (site / "newtool-v9-9.json").exists() and not (site / "newtool-v9-9").exists()


def test_running_it_twice_is_harmless(tmp_path):
    site = _site(tmp_path)
    ml.migrate(site, resolve=_resolve, apply=True)
    snapshot = sorted(p.relative_to(site).as_posix() for p in site.rglob("*"))
    done = ml.migrate(site, resolve=_resolve, apply=True)
    assert done["steps"] == []
    assert sorted(p.relative_to(site).as_posix() for p in site.rglob("*")) == snapshot


def test_a_deploy_after_the_migration_lands_beside_the_migrated_commits(tmp_path):
    """The layout the migration leaves is the one publish_layout keeps: a new
    run of hipstr at an older commit lands below and moves nothing."""
    site = _site(tmp_path)
    ml.migrate(site, resolve=_resolve, apply=True)
    run = tmp_path / "reports"; run.mkdir()
    older = "0" * 40
    (run / "hipstr.json").write_text(json.dumps({
        "schema": "strhub-verified/1", "tool": {"name": "HipSTR", "version": "v0.6"}, "level": "runs",
        "instrument": "documented",
        "source": {"repo": "https://github.com/x/hipstr", "ref": older, "ref_resolved": older, "committed": "2018-01-01T00:00:00Z"},
        "generated": "2026-09-19T00:00:00+00:00", "gates": {}, "scope": "x"}))
    (run / "hipstr.html").write_text("x")
    done = pl.place(site, run, "hipstr", resolve=_resolve)
    assert done["alias"] == E12E9 and done["alias_instrument"] == "documented"
    assert done["versions"] == [(E12E9, "documented"), (B2033, "curated"), (older, "documented")]
