"""The pinned commit's date rides on the compare call the report already makes,
and can be fetched on its own for a report published before it was recorded."""
import upstream

REPO = "https://github.com/tfwillems/HipSTR"
SHA = "12e989be4a8f9ab59f0c4c5da3784b82018cac82"


def _fake_get(responses):
    def get(path, token):
        for prefix, body in responses:
            if path.startswith(prefix):
                return body
        return {"__status__": 404}
    return get


def test_check_carries_the_committer_date_of_the_pinned_ref(monkeypatch):
    monkeypatch.setattr(upstream, "_get", _fake_get([
        ("/repos/tfwillems/HipSTR/compare/", {
            "status": "behind", "ahead_by": 1,
            "base_commit": {"sha": SHA, "commit": {
                "author": {"date": "2024-05-01T10:00:00Z"},
                "committer": {"date": "2024-05-02T09:30:00Z"}}}}),
        ("/repos/tfwillems/HipSTR", {"default_branch": "master"}),
    ]))
    up = upstream.check(REPO, SHA, token="t")
    assert up["behind_by"] == 1 and up["default_branch"] == "master"
    assert up["committed"] == "2024-05-02T09:30:00Z"   # the committer's, as GitHub shows it


def test_check_says_nothing_about_a_date_it_does_not_have(monkeypatch):
    monkeypatch.setattr(upstream, "_get", _fake_get([
        ("/repos/tfwillems/HipSTR/compare/", {"status": "identical", "ahead_by": 0}),
        ("/repos/tfwillems/HipSTR", {"default_branch": "master"}),
    ]))
    assert "committed" not in upstream.check(REPO, SHA, token="t")


def test_commit_date_on_its_own_for_a_report_that_predates_it():
    get = _fake_get([(f"/repos/tfwillems/HipSTR/commits/{SHA}",
                      {"sha": SHA, "commit": {"committer": {"date": "2024-05-02T09:30:00Z"}}})])
    assert upstream.commit_date(REPO, SHA, token="t", get=get) == "2024-05-02T09:30:00Z"
    assert upstream.commit_date(REPO, "0" * 40, token="t", get=get) is None
    assert upstream.commit_date("not a github url", SHA, token="t", get=get) is None
