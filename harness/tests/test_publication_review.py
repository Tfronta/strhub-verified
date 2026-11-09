import copy
import json

import pytest

import build_index
import certificate_text
import publication_review as review
import publish_layout


def fixture(site):
    slug, sha = "example", "a" * 40
    historical = site / slug / sha
    historical.mkdir(parents=True)
    r = {"schema": "strhub-verified/1", "tool": {"name": "Example"},
         "source": {"ref_resolved": sha}, "instrument": "documented",
         "ci_run": "https://github.com/example/repo/actions/runs/1",
         "gates": {"installs": False}, "level": "available",
         "run": {"cmd": "example --input input.bam"}}
    for folder in (site, historical):
        (folder / f"{slug}.json").write_text(json.dumps(r))
        (folder / f"{slug}.log-build.txt").write_text("original log\n")
        (folder / f"{slug}.pdf").write_bytes(b"original pdf")
    rev = {"id": "review-1", "reviewed_at": "2026-11-09T00:00:00Z",
           "reason": "The linked run does not support the published result.",
           "original_report_sha256": review.digest(site / f"{slug}.json"),
           "archive_url": "https://example.com/archive", "review_url": "https://example.com/review",
           "recovered_evidence_note": "A separate trial exists; it is not substituted for this run."}
    return slug, historical, rev


def test_withdrawal_preserves_original_bytes_and_never_fabricates_a_run(tmp_path):
    slug, historical, rev = fixture(tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    r = review.apply(tmp_path, slug, rev)
    archive = tmp_path / "evidence-reviews" / rev["id"] / slug / "original"
    for path, content in before.items():
        assert (archive / path).read_bytes() == content
    for path in historical.iterdir():
        if path.name != "retired.json":
            assert path.read_bytes() == before[path.relative_to(tmp_path)]
    assert publish_layout.tombstone_of(historical)
    assert publish_layout.alias_source(tmp_path, slug) is None
    for key in ("gates", "run", "environment", "install_detail", "logs"):
        assert key not in r
    assert r["ci_run"] is None
    assert not (tmp_path / f"{slug}.log-build.txt").exists()
    assert not (tmp_path / f"{slug}.pdf").exists()  # caller supplies an editorial PDF
    assert certificate_text.headline(r) == ("Evidence insufficient", "lightgrey")
    entry, = build_index.build_catalogue(tmp_path)["tools"]
    assert entry["verdict"] == "undetermined" and entry["record_type"] == "editorial_review"
    assert all(v.get("retired") for v in entry["versions"])
    # Routine alias maintenance cannot resurrect the withdrawn report.
    publish_layout.write_alias(tmp_path, slug)
    assert json.loads((tmp_path / f"{slug}.json").read_text()) == r


def test_changed_publication_is_rejected_before_writing(tmp_path):
    slug, historical, rev = fixture(tmp_path)
    (tmp_path / f"{slug}.json").write_text("changed")
    with pytest.raises(ValueError, match="publication changed"):
        review.apply(tmp_path, slug, rev)
    assert not (tmp_path / "evidence-reviews").exists()
    assert not (historical / "retired.json").exists()


def test_notice_is_independent_of_the_original_execution_claims(tmp_path):
    slug, _, rev = fixture(tmp_path)
    old = json.loads((tmp_path / f"{slug}.json").read_text())
    before = copy.deepcopy(old)
    r = review.notice(old, rev)
    assert old == before
    assert "Editorial correction, not a new verification" in review.render_html(r)
    assert "Command that ran" not in review.render_html(r)
