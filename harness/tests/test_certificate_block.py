"""The certificate's words travel with the report.

The PDF used to hold its executive summary, its closing lists and its
conclusion as literals of its own; the page could only reword them. Now
report.py writes them into the JSON (certificate_text.certificate_for) and
the PDF prints that block, so a reviewer holding the page and the PDF reads
one text, and this test can hold them to it."""
import json
import pathlib
import subprocess
import sys

import pytest
import yaml

import certificate_text as ct

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _run_report(tmp_path, runs="fail"):
    doc = yaml.safe_load((ROOT / "tools" / "strspy-ont" / "manifest.yml").read_text())
    doc["recipe"] = {"origin": "proposed"}
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(yaml.safe_dump(doc, sort_keys=False))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    res = subprocess.run([sys.executable, str(ROOT / "harness" / "report.py"), "--manifest", str(manifest),
                          "--available", "pass", "--installs", "pass", "--runs", runs,
                          "--io", str(tmp_path / "no-io.json"), "--content", str(tmp_path / "no-content.json"),
                          "--matrix", str(tmp_path / "no-matrix.json"), "--readme", str(tmp_path / "no-readme.json"),
                          "--example", str(tmp_path / "no-example.json"),
                          "--regions-validation", str(tmp_path / "no-regions.json")],
                         cwd=str(ROOT), capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    written = json.loads((ROOT / "reports" / "strspy-ont.json").read_text())
    badge = json.loads((ROOT / "reports" / "strspy-ont.badge.json").read_text())
    md = (ROOT / "reports" / "strspy-ont.summary.md").read_text()
    html = (ROOT / "reports" / "strspy-ont.html").read_text()
    for p in (ROOT / "reports").glob("strspy-ont.*"):
        p.unlink()
    return written, badge, md, html, manifest


def test_the_report_carries_the_certificate_and_the_badge_says_the_same(tmp_path):
    written, badge, md, html, _ = _run_report(tmp_path)
    cert = written["certificate"]
    assert cert["schema"] == ct.CERTIFICATE_SCHEMA
    assert cert["label"] == badge["message"] == "Does not run as documented: stops at run"
    assert cert["reached"] == "Installs"
    assert cert["summary"]["reached"] == "Installs, 2/5 gates passed"
    assert cert["summary"]["why"] == written["verdict"]["reason"]
    assert cert["summary"]["purpose"] == ct.PURPOSE and cert["summary"]["not_evaluated"] == ct.NOT_EVALUATED
    assert cert["out_of_scope"] == ct.OUT_OF_SCOPE and cert["limitations"] == ct.LIMITATIONS
    assert cert["scope"] == {"statement": ct.SCOPE_STATEMENT, "not": ct.SCOPE_NOT, "disclaimer": ct.DISCLAIMER}
    titles = [c["title"] for c in cert["conclusion"]]
    assert titles[:2] == ["Does not run end-to-end", "No output produced"]
    assert any(t.startswith("Verdict: Fails") for t in titles)
    # The copies print the same closing lists.
    for text in (md, html):
        for item in ct.OUT_OF_SCOPE + ct.LIMITATIONS:
            assert item in text


def test_the_certificate_prints_the_block_the_report_carries(tmp_path, monkeypatch):
    # The CI job that gates every run installs no renderer; the PDF half of
    # this test runs where reportlab is, the JSON half everywhere.
    pytest.importorskip("reportlab")
    import generate_pdf
    written, _, _, _, manifest = _run_report(tmp_path)
    # The PDF reads reports/<slug>.json from the working directory.
    reports = tmp_path / "reports"; reports.mkdir()
    (reports / "strspy-ont.json").write_text(json.dumps(written))
    monkeypatch.chdir(tmp_path)
    cfg = generate_pdf.load_config(str(manifest), str(ROOT / "datasets" / "index.json"), publishable=True)
    assert cfg["certificate"]["conclusion"] == written["certificate"]["conclusion"]
    assert cfg["headline"] == written["certificate"]["label"]
    # And what the PDF would derive on its own is the same text: the block is
    # not a second opinion.
    assert [(c["title"], c["body"]) for c in written["certificate"]["conclusion"]] == ct.conclusion_items_for(cfg)
