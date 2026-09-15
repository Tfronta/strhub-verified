"""The certificate may not say the opposite of the report it renders.

A PDF is the artefact that circulates on its own — detached from the page, the
log and the verdict. Its conclusion used to be four fixed paragraphs asserting
success with the numbers interpolated, so a run that stopped at Installs was
certified as "installs and executes without error ... generated a structurally
valid output file", with "0 loci" as the only hint.
"""
import certificate_text


def _cfg(**over):
    cfg = {
        "gates": {"available": True, "installs": True, "runs": False, "io": False, "content": False},
        "verdict": {"title": "Fails", "reason": "The tool exited with an error before producing its documented output."},
        "tool_display": "STRspy dafdee7", "tool_name": "STRspy",
        "declared_format": "TSV", "dataset": {"name": "ONT slice"},
        "stats": {}, "datasets": [{"leg": "external", "available": True, "passed": False}],
        "is_trial": True, "fallback_used": False,
    }
    cfg.update(over)
    return cfg


def _conclusion(cfg):
    return [f"{t} :: {b}" for t, b in certificate_text.conclusion_items_for(cfg)]


def test_a_run_that_stopped_is_not_certified_as_running():
    text = " ".join(_conclusion(_cfg()))
    assert "Does not run end-to-end" in text
    assert "No output produced" in text
    assert "executes without error" not in text
    assert "generated a structurally valid" not in text
    assert "Verdict: Fails" in text


def test_a_build_that_failed_says_so_instead_of_blaming_the_run():
    cfg = _cfg(gates={"available": True, "installs": False, "runs": False, "io": False, "content": False})
    assert "Does not install" in " ".join(_conclusion(cfg))


def test_output_without_content_claims_only_what_the_gate_established():
    cfg = _cfg(gates={"available": True, "installs": True, "runs": True, "io": True, "content": False})
    text = " ".join(_conclusion(cfg))
    assert "Produces output in the declared format" in text
    assert "genotype calls across" not in text


def test_a_passing_run_still_reports_its_evidence():
    cfg = _cfg(
        gates={"available": True, "installs": True, "runs": True, "io": True, "content": True},
        verdict={"title": "Runs", "reason": "The tool installed and its run produced its documented output."},
        stats={"distinct_str_loci": 24, "max_sequence_depth": 800, "top_loci_by_depth": [["D18S51", 800]]},
    )
    text = " ".join(_conclusion(cfg))
    assert "Runs end-to-end" in text and "executes without error" in text
    assert "24 target forensic STR loci" in text and "800 at D18S51" in text
    assert "Verdict: Runs" in text


def test_absence_of_test_data_is_claimed_only_on_evidence():
    # "This tool does not include its own demo or test data" was printed for
    # every tool. STRsearch ships 35 files including example/test_data/test.bam.
    nobody_looked = certificate_text.test_data_item(_cfg(), "ONT slice")
    assert nobody_looked[0] == "Reference input"
    assert "does not include" not in nobody_looked[1] and "ships no" not in nobody_looked[1]

    ships = certificate_text.test_data_item(
        _cfg(repo_test_data={"known": True, "present": True, "count": 35}), "ONT slice")
    assert "ships example data (35 file(s))" in ships[1]

    ships_none = certificate_text.test_data_item(
        _cfg(repo_test_data={"known": True, "present": False, "count": 0}), "ONT slice")
    assert ships_none[0] == "No bundled demo data" and "ships no test or demo data" in ships_none[1]
