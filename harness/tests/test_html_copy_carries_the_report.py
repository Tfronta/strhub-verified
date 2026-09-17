"""The HTML copy says what the page and the certificate say.

The web linked it as "Full report" while it carried less than the page: no
verdict, no command, no evidence, no notes, six loci and an ellipsis. A copy
that can be opened without STRhub is only worth keeping if it is the report."""
import report

REPORT = {
    "tool": {"name": "HipSTR"},
    "level": "content",
    "gates": {"available": True, "installs": True, "runs": True, "io": True, "content": True},
    "source": {"repo": "https://github.com/tfwillems/HipSTR", "ref_resolved": "12e989b"},
    "environment": {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"]},
    "generated": "2026-09-16T21:14:32+00:00",
    "scope": report.SCOPE,
    "verdict": {"title": "Runs", "reason": "The tool installed and its run produced its documented output."},
    "run": {"cmd": "./HipSTR --bams /data/in/input.bam --str-vcf str_calls.vcf.gz", "cwd": "/opt/tool"},
    "io_detail": {"outputs": [{"path": "**/*.vcf*", "format": "vcf", "resolved": "str_calls.vcf.gz"}]},
    "content_detail": {"outputs": [{"stats": {
        "rows": 3, "distinct_str_loci": 3, "str_loci": ["D18S51", "FGA", "TPOX"],
        "total_reads": 900, "max_sequence_depth": 500,
        "top_loci_by_depth": [["D18S51", 500], ["FGA", 300], ["TPOX", 100]],
        "regions_given": 4, "regions_hit": 3,
    }}]},
    "evidence": [{"claim": "platform_advice", "kind": "readme", "path": "README.md", "line": 435,
                  "text": "We do not recommend running it on PacBio or Oxford Nanopore data, "
                          "as the difference in error profiles will be problematic",
                  "url": "https://github.com/tfwillems/HipSTR/blob/12e989b/README.md#L435"}],
    "needed_beyond_repo": ["Test data: no sample from the repository was used, so a public reference sample stood in."],
    "caveats": {"source": "detect_recipe", "items": ["1 BED path(s) replaced with /data/in/regions.bed."]},
}


def test_the_html_copy_carries_verdict_command_and_output():
    html = report._summary_html(REPORT, "hipstr")
    assert "<b>Verdict: Runs.</b>" in html
    assert "<h2>Command that ran</h2>" in html
    assert "./HipSTR --bams /data/in/input.bam --str-vcf str_calls.vcf.gz" in html
    assert "Output file: <code>str_calls.vcf.gz</code> (VCF)" in html
    assert "Panel loci called: <b>3</b> of 4" in html
    # Every locus with its depth, not six and an ellipsis.
    assert html.count('class="bar"') == 3 and "TPOX" in html and "…" not in html


def test_the_html_copy_carries_evidence_needs_and_notes_whole():
    html = report._summary_html(REPORT, "hipstr")
    assert "Platform advice" in html and "platform_advice" not in html
    assert "as the difference in error profiles will be problematic" in html
    assert "What this run needed beyond the repository" in html
    assert "a public reference sample stood in" in html
    assert "Notes from reading the repository" in html
    assert "/data/in/regions.bed" in html


def test_the_markdown_summary_no_longer_clips_the_evidence():
    md = report._summary_md(REPORT, "hipstr")
    assert "Platform advice:" in md
    assert "as the difference in error profiles will be problematic" in md
    assert "## Command that ran" in md


def test_nothing_is_invented_for_an_older_report():
    older = {k: v for k, v in REPORT.items()
             if k not in ("verdict", "run", "io_detail", "evidence", "needed_beyond_repo", "caveats")}
    html = report._summary_html(older, "hipstr")
    for absent in ("Verdict:", "Command that ran", "Output file", "<h2>Evidence</h2>",
                   "needed beyond the repository", "Notes from reading"):
        assert absent not in html
