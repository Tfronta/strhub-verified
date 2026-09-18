"""index.json lists a tool at its newest commit, and every commit it was
verified at — newest commit first, whatever order they were verified in."""
import json

import build_index
import publish_layout as pl
from test_publish_layout import SLUG, OLD, NEW, _run


def test_the_catalogue_carries_every_commit_newest_first(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG)
    pl.place(site, _run(tmp_path, OLD, "2024-03-10T00:00:00Z", "2026-09-18T00:00:00+00:00"), SLUG)
    cat = build_index.build_catalogue(site)
    assert cat["schema"] == "strhub-verified/index/3"
    (entry,) = cat["tools"]
    # The flat entry is the alias — the newest commit — as every reader expects.
    assert entry["slug"] == SLUG and entry["sha"] == NEW and entry["committed"] == "2026-02-01T00:00:00Z"
    assert entry["report"] == f"{SLUG}.json"
    # The history, in the software's order, each row pointing at its own files.
    assert [v["sha"] for v in entry["versions"]] == [NEW, OLD]
    old = entry["versions"][1]
    assert old["committed"] == "2024-03-10T00:00:00Z" and old["generated"].startswith("2026-09-18")
    assert old["report"] == f"{SLUG}/{OLD}/{SLUG}.json" and old["pdf"] == f"{SLUG}/{OLD}/{SLUG}.pdf"
    assert (site / old["report"]).exists()


def test_a_slug_published_before_the_layout_is_its_own_single_version(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    legacy = _run(tmp_path, NEW, None, "2026-09-01T00:00:00+00:00", name="legacy")
    for f in pl.report_files(legacy, SLUG):
        f.rename(site / f.name)
    (entry,) = build_index.build_catalogue(site)["tools"]
    assert entry["committed"] is None
    assert entry["versions"] == [dict(entry["versions"][0], report=f"{SLUG}.json", page=f"{SLUG}.html", pdf=f"{SLUG}.pdf")]
    assert entry["versions"][0]["sha"] == NEW


def test_commit_directories_are_not_listed_as_tools(tmp_path):
    site = tmp_path / "site"; site.mkdir()
    pl.place(site, _run(tmp_path, NEW, "2026-02-01T00:00:00Z", "2026-09-01T00:00:00+00:00"), SLUG)
    cat = build_index.build_catalogue(site)
    assert cat["count"] == 1 and [t["slug"] for t in cat["tools"]] == [SLUG]
    index_json = json.loads(json.dumps(cat))   # serialisable as written
    assert index_json["tools"][0]["versions"][0]["sha"] == NEW
