"""The recipe benchmark: 23 STR tools, pinned, scored against what their
documentation says (harness/testdata/benchmark/). A change to recipe
detection may move tools between columns; it may not lower a total. When a
change raises one, raise the floor here in the same commit."""
import json
import pathlib

import benchmark_recipes as br

#: The totals on 29 September 2026, when this file was written. The engine on
#: main before the work that added the benchmark scored, on the 18 tools it had
#: never seen: install 10, input 12, program 3, clean 7, honest 15, viable 0.
FLOOR = {
    "new": {"install": 17, "input": 17, "program": 13, "clean": 13, "honest": 16, "viable": 9},
    "catalogue": {"install": 4, "input": 5, "program": 5, "clean": 5, "honest": 5, "viable": 4},
}


def test_every_tool_has_a_snapshot_and_a_ground_truth():
    for r in br.rows():
        d = br.BENCH / r["name"]
        assert (d / "tree.json").exists(), r["name"]
        e = json.loads((d / "expected.json").read_text())
        assert e["_about"] and e["program"].get("where") and e["install"]["acceptable_methods"], r["name"]
        assert json.loads((d / "tree.json").read_text())["ref"] == r["sha"], r["name"]


def test_the_benchmark_does_not_go_backwards():
    report = br.run()
    assert report["n"] == 23
    lines = []
    for which, floor in FLOOR.items():
        for metric, n in floor.items():
            got = report["by_set"][which][metric]
            if got < n:
                lines.append(f"{which}.{metric}: {got} < {n}")
    assert not lines, "benchmark regressed:\n" + "\n".join(lines) + "\n\n" + br.table(report)


def test_every_proposed_manifest_is_a_valid_manifest(tmp_path):
    """What a trial of each benchmark tool would run must pass the schema
    report.py validates against, or the trial dies before it can say anything."""
    import _manifest
    for r in br.rows():
        _, recipe = br.propose(r["name"])
        p = tmp_path / f"{r['name']}.yml"
        p.write_text(recipe["manifest_yml"])
        _manifest.load(str(p))
