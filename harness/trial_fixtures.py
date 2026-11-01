"""Trials on disk, so the web's result page can be walked without GitHub.

    python harness/trial_fixtures.py [dir]

Writes one directory per scenario in the layout the site's development-only
fixture reader expects (`VERIFIED_TRIAL_FIXTURE_DIR/<id>/report.json`, see
strhub-web lib/verified/trial.ts::fixtureTrial). Then:

    cd ../strhub-web
    VERIFIED_TRIAL_FIXTURE_DIR=../strhub-verified/.trial-fixtures npx next dev

Nothing is built, dispatched or published: a dev server is refused write access
to the live engine on purpose, and these files never leave the machine.

The point is that the sentences are not written here. Each scenario states only
what a run observed — the gates, the classifier's blocker — and `verdict.decide`
and `certificate_text.step1_says` produce the wording, so what the page shows is
what the engine would say and not a mock of it.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import certificate_text  # noqa: E402
import procedure  # noqa: E402
import verdict as verdict_lib  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / ".trial-fixtures"

GATES_GREEN = {"available": True, "installs": True, "runs": True, "io": True, "content": True}
GATES_RAN_AND_FAILED = {"available": True, "installs": True, "runs": False, "io": False, "content": False}

PROPOSAL = {"schema": "strhub-verified/recipe-proposal/1",
            "readme": {"gaps": [], "sufficient_to_attempt": True}}


def _manifest(cmd, outputs, source="repository", input_type="illumina-bam-hg38"):
    return {"environment": {"source": source}, "run": {"cmd": cmd},
            "inputs": {"type": input_type}, "outputs": [{"path": outputs, "format": "text"}]}


GATES_INSTALL_ONLY = {"available": True, "installs": True, "runs": False, "io": False, "content": False}
GATES_SOURCE_ONLY = {"available": True, "installs": False, "runs": False, "io": False, "content": False}

#: Each scenario is one observation, not one sentence: the install the commit
#: states, the command it cites, what the gates did, and what STRhub was
#: missing. `expect` is the classifier's blocker this scenario is here to show;
#: if the classifier disagrees the script says so and writes nothing, because a
#: fixture that illustrates the wrong message is worse than no fixture.
SCENARIOS = [
    # ── The documented run finished, or ran and stopped ──────────────────
    {
        "id": "tr_runs_hipstr", "expect": "ready",
        "tool": "HipSTR", "version": "v0.6.2",
        "repo": "https://github.com/HipSTR-Tool/HipSTR", "sha": "cd4ba6c",
        "gates": GATES_GREEN, "level": "content",
        "build": "make", "cited": "./HipSTR --bams sample.bam --fasta hg38.fa --regions panel.bed --str-vcf out.vcf.gz",
        "run": "./HipSTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa --regions /data/ref/regions.bed --str-vcf /data/out/out.vcf.gz",
        "outputs": "out.vcf.gz", "limitations": [], "notes": [],
    },
    {
        # Green gates, and the tool's own log reported errors. The headline
        # stays "runs" and turns yellow: it is a fact of the log.
        "id": "tr_runserrors_strspy", "expect": "ready",
        "tool": "STRspy", "version": "v2.0",
        "repo": "https://github.com/unique379r/strspy", "sha": "dafdee7",
        "gates": GATES_GREEN, "level": "io",
        "build": "conda", "cited": "bash STRspy_run_v2.0.sh -i input -o output",
        "run": "bash STRspy_run_v2.0.sh -i /data/in -o /data/out",
        "outputs": "output/Countings", "limitations": [], "notes": [],
        "diagnostics": {"external": [{"id": "cannot_open", "severity": "error",
                                      "title": "The tool could not open a file it needs",
                                      "count": 9, "examples": ["vWA", "TPOX", "FGA"]}]},
    },
    {
        "id": "tr_fails_strspy", "expect": "ready",
        "tool": "STRspy", "version": "v2.0",
        "repo": "https://github.com/unique379r/strspy", "sha": "dafdee7",
        "gates": GATES_RAN_AND_FAILED, "level": "installs",
        "build": "conda", "cited": "bash STRspy_run_v2.0.sh -i input -o output",
        "run": "bash STRspy_run_v2.0.sh -i /data/in -o /data/out",
        "outputs": "output/Countings", "limitations": [], "notes": [],
        "diagnostics": {"external": [{"id": "cannot_open", "severity": "error",
                                      "title": "The tool could not open a file it needs",
                                      "count": 9, "examples": ["vWA", "TPOX", "FGA"]}]},
    },

    # ── A block of the guide is missing: the finding is the commit's ─────
    {
        "id": "tr_nocommand_fdstools", "expect": "no_command",
        "tool": "FDSTools", "version": "v2.0.0",
        "repo": "https://github.com/Jerrythafast/FDSTools", "sha": "8f1a2c4",
        "gates": GATES_SOURCE_ONLY, "level": "available",
        "build": "pip", "cited": "", "run": "", "outputs": "**/*",
        "limitations": ["no_command"], "notes": [],
    },
    {
        # A usage synopsis is not a command. Dropping its optional arguments
        # to make one would be amending the procedure.
        "id": "tr_synopsis_straglr", "expect": "synopsis_trimmed",
        "tool": "straglr", "version": "v1.4.1",
        "repo": "https://github.com/bcgsc/straglr", "sha": "7c2e11d",
        "gates": GATES_SOURCE_ONLY, "level": "available",
        "build": "conda",
        "cited": "straglr.py [--min_support N] [--max_str_len L] <in.bam> <ref.fa> <prefix>",
        "run": "straglr.py /data/in/input.bam /data/ref/hg38.fa /data/out/straglr",
        "outputs": "straglr.tsv", "limitations": [], "notes": [],
    },
    {
        # No output named, so any file the wrapper copied would have counted.
        "id": "tr_nooutput_repeathmm", "expect": "output_unnamed",
        "tool": "RepeatHMM", "version": "v2.0.3",
        "repo": "https://github.com/WGLab/RepeatHMM", "sha": "b4d9f07",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "conda",
        "cited": "python RepeatHMM.py BAMinput --bamfile sample.bam --Onefq2 hg38.fa",
        "run": "python RepeatHMM.py BAMinput --bamfile /data/in/input.bam --Onefq2 /data/ref/hg38.fa",
        "outputs": "**/*", "limitations": [], "notes": [],
    },
    {
        "id": "tr_noinstall_somerepo", "expect": "no_install_procedure",
        "tool": "ExampleTool", "version": "v1.0",
        "repo": "https://github.com/example/example-str", "sha": "a1b2c3d",
        "gates": GATES_SOURCE_ONLY, "level": "available",
        "build": "unknown",
        "cited": "exampletool --in sample.bam --out out.txt",
        "run": "exampletool --in /data/in/input.bam --out /data/out/out.txt",
        "outputs": "out.txt", "limitations": ["install_method_unknown"], "notes": [],
    },
    {
        # A published image is a claim about the image, not about the commit.
        "id": "tr_image_strique", "expect": "published_image",
        "tool": "STRique", "version": "v0.4.2",
        "repo": "https://github.com/giesselmann/STRique", "sha": "e19a55c",
        "gates": GATES_SOURCE_ONLY, "level": "available",
        "build": "docker_image",
        "cited": "docker run giesselmann/strique STRique.py count",
        "run": "STRique.py count --config /data/ref/repeat.config",
        "outputs": "counts.tsv", "limitations": [], "notes": [],
    },
    {
        "id": "tr_missingfile_vamos", "expect": "missing_file",
        "tool": "vamos", "version": "v2.1.3",
        "repo": "https://github.com/ChaissonLab/vamos", "sha": "5f0c2ab",
        "gates": GATES_SOURCE_ONLY, "level": "available",
        "build": "conda",
        "cited": "vamos --contig -b sample.bam -r vntr_motifs.bed -o out.vcf",
        "run": "vamos --contig -b /data/in/input.bam -r /data/ref/regions.bed -o /data/out/out.vcf",
        "outputs": "out.vcf", "limitations": ["documented_file_missing"], "notes": [],
    },

    # ── The limitation is STRhub's: its sample shelf, or its own reader ──
    {
        "id": "tr_oursample_trtools", "expect": "missing_input",
        "tool": "TRTools", "version": "v6.0.1",
        "repo": "https://github.com/gymrek-lab/TRTools", "sha": "3b71e90",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "pip", "cited": "dumpSTR --vcf calls.vcf --out filtered",
        "run": "dumpSTR --vcf calls.vcf --out /data/out/filtered",
        "outputs": "filtered.vcf", "limitations": ["no_reference_dataset"], "notes": [],
    },
    {
        "id": "tr_ourloci_expansionhunter", "expect": "loci_outside_panel",
        "tool": "ExpansionHunter", "version": "v5.0.0",
        "repo": "https://github.com/Illumina/ExpansionHunter", "sha": "c9f1d4e",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "release_binary",
        "cited": "ExpansionHunter --reads sample.bam --reference hg38.fa --variant-catalog variants.json --output-prefix out",
        "run": "ExpansionHunter --reads /data/in/input.bam --reference /data/ref/hg38.fa --variant-catalog /data/ref/variants.json --output-prefix /data/out/out",
        "outputs": "out.vcf", "limitations": ["loci_outside_panel"], "notes": [],
    },
    {
        # Our own reader would add a flag the cited command does not carry.
        "id": "tr_ourflag_longtr", "expect": "flag_injected",
        "tool": "LongTR", "version": "v1.0.2",
        "repo": "https://github.com/gymrek-lab/LongTR", "sha": "d7e8a91",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "make",
        "cited": "LongTR --bams sample.bam --fasta hg38.fa --regions panel.bed --tr-vcf out.vcf.gz",
        "run": "LongTR --bams /data/in/input.bam --fasta /data/ref/hg38.fa --regions /data/ref/regions.bed --tr-vcf /data/out/out.vcf.gz --bam-samps sample",
        "outputs": "out.vcf.gz", "limitations": [], "notes": [],
    },
    {
        # Our own guess at a BED layout. A file appearing would not confirm it.
        "id": "tr_ourbed_strling", "expect": "regions_guessed",
        "tool": "STRling", "version": "v0.5.2",
        "repo": "https://github.com/quinlan-lab/STRling", "sha": "f2c6b83",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "release_binary",
        "cited": "strling call sample.bam sample.bin -o out",
        "run": "strling call /data/in/input.bam /data/out/sample.bin -o /data/out/out",
        "outputs": "out-genotype.txt", "limitations": ["regions_format_guessed"], "notes": [],
    },
    {
        # The command still names the repository's own files, so running it
        # would test our staging, not the reference sample.
        "id": "tr_ourstaging_trgt", "expect": "input_not_substituted",
        "tool": "TRGT", "version": "v1.2.0",
        "repo": "https://github.com/PacificBiosciences/trgt", "sha": "8ad3f52",
        "gates": GATES_INSTALL_ONLY, "level": "installs",
        "build": "release_binary",
        "cited": "trgt genotype --genome hg38.fa --repeats repeats.bed --reads example/sample.bam --output-prefix out",
        "run": "trgt genotype --genome hg38.fa --repeats repeats.bed --reads example/sample.bam --output-prefix out",
        "outputs": "out.vcf.gz", "limitations": [], "notes": [],
    },
]


def _build(s: dict) -> dict:
    proposal = {"build": {"method": s["build"]},
                "commands": ([{"cmd": s["cited"]}] if s["cited"] else [])}
    manifest = _manifest(s["run"], s["outputs"])
    review = procedure.classify(proposal, manifest, s["limitations"], s["notes"])
    diagnostics = s.get("diagnostics", {})
    v = verdict_lib.decide(s["gates"], diagnostics,
                           recipe_proposal={**PROPOSAL, "limitations": s["limitations"]},
                           procedure=review)
    report = {
        "schema": "strhub-verified/1",
        "tool": {"name": s["tool"], "version": s["version"]},
        "source": {"repo": s["repo"], "ref_resolved": s["sha"], "ref": s["sha"]},
        "environment": {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"]},
        "generated": "2026-09-30T16:00:00+00:00",
        "instrument": "documented",
        "recipe": {"origin": "proposed"},
        "level": s["level"],
        "gates": s["gates"],
        "diagnostics": diagnostics,
        "verdict": v,
        "procedure_review": review,
    }
    report["step1"] = certificate_text.step1_says(report)
    return report


def disagreements() -> list[str]:
    """Scenarios whose classifier blocker is not the one they claim to show.

    Kept as a function so a test can hold the fixtures to it: a page that
    illustrates the wrong message would teach the wrong rule."""
    out = []
    for s in SCENARIOS:
        got = _build(s)["procedure_review"].get("blocker")
        if got != s["expect"]:
            out.append(f"{s['id']}: expected {s['expect']}, the classifier says {got}")
    return out


def main() -> None:
    import yaml
    import report as report_mod
    out = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else OUT
    wrong = disagreements()
    if wrong:
        print("Nothing written. These scenarios do not show what they claim:")
        for line in wrong:
            print("  " + line)
        raise SystemExit(1)
    out.mkdir(parents=True, exist_ok=True)
    root = pathlib.Path(__file__).resolve().parent.parent
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    for s in SCENARIOS:
        report = _build(s)
        slug = s["id"]
        report["scope"] = report_mod.SCOPE
        if s["run"]:
            report["run"] = {"cmd": s["run"]}
        d = out / s["id"]
        d.mkdir(exist_ok=True)
        (d / "report.json").write_text(json.dumps(report, indent=2))
        (d / "summary.md").write_text(report_mod._summary_md(report, slug))
        (d / "report.html").write_text(report_mod._summary_html(report, slug))
        manifest_obj = {
            "tool": {"name": s["tool"], "version": s["version"], "contact": f"{s['repo']}/issues"},
            "submission": {"by": "third_party"},
            "source": {"repo": s["repo"], "ref": s["sha"]},
            "recipe": {"origin": "proposed"},
            "report": {"slug": slug},
            "environment": {"dockerfile": "Dockerfile", "os": ["ubuntu-22.04"], "source": "generated"},
            "run": {"cmd": s["run"] or "true", "timeout_minutes": 20},
            "inputs": {"type": "illumina-bam-hg38"},
            "outputs": [{"path": s["outputs"], "format": "text", "min_records": 1}],
        }
        manifest_yml = yaml.safe_dump(manifest_obj, sort_keys=False)
        dockerfile_txt = f"# Proposed environment ({s['build']})\nFROM ubuntu:22.04\nWORKDIR /opt/tool\n"
        (d / "recipe.json").write_text(json.dumps({
            "schema": "strhub-verified/recipe/1",
            "slug": slug,
            "manifest_yml": manifest_yml,
            "dockerfile": dockerfile_txt,
        }, indent=2))
        try:
            import generate_pdf
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                mp = pathlib.Path(tmp) / "manifest.yml"
                mp.write_text(manifest_yml)
                (reports_dir / f"{slug}.json").write_text(json.dumps(report, indent=2))
                cfg = generate_pdf.load_config(str(mp), str(root / "datasets" / "index.json"), publishable=False)
                doc = generate_pdf.SimpleDocTemplate(
                    str(d / "report.pdf"), pagesize=generate_pdf.A4,
                    leftMargin=generate_pdf.ML, rightMargin=generate_pdf.MR,
                    topMargin=generate_pdf.MT, bottomMargin=generate_pdf.MB + 8 * generate_pdf.mm,
                    title=f"STRhub Verified — {cfg['tool_display']}",
                )
                story = generate_pdf.build_cover(cfg) + [generate_pdf.PageBreak()] + generate_pdf.build_body(cfg)
                doc.build(story, canvasmaker=generate_pdf._make_canvas_class(cfg))
                (reports_dir / f"{slug}.json").unlink(missing_ok=True)
        except Exception:
            pass
        step1 = report["step1"]
        print(f"{step1['code']:14s} {s['id']:30s} {step1['headline']}")
        if step1.get("missing_text"):
            print(f"{'':45s} missing: {', '.join(step1['missing_text'])}")
    print(f"\n{len(SCENARIOS)} trials in {out}\n")
    for s in SCENARIOS:
        print(f"  http://localhost:3100/verified/trial/{s['id']}?as=owner")


if __name__ == "__main__":
    main()
