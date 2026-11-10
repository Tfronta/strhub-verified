"""Put the recipe a trial ran INTO its report artifact.

A trial commits nothing, so the recipe it ran (proposed in CI from the
repository, or dispatched by the web) exists only in the runner's work dir.
The web needs it back for two things: to show a reader what was actually run,
and to let a tool's owner publish exactly the recipe that produced the verdict
they are looking at, instead of retyping it. So it travels next to the report:
reports/<slug>.recipe.json.

Usage:  python harness/attach_recipe.py <tool> --dockerdir <dir> [--proposal recipe_proposal.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tool")
    ap.add_argument("--dockerdir", required=True, help="where manifest.yml and Dockerfile were read from")
    ap.add_argument("--proposal", default="", help="detect_recipe output, when the recipe was proposed")
    ap.add_argument("--procedure-review", default="", help="pre-execution review bound to the effective manifest")
    ap.add_argument("--source-install-dockerfile", default="", help="verified source-installation carrier selected for the build")
    ap.add_argument("--reports", default=str(ROOT / "reports"))
    args = ap.parse_args()

    d = pathlib.Path(args.dockerdir)
    manifest_yml = (d / "manifest.yml").read_text()
    m = yaml.safe_load(manifest_yml)
    slug = (m.get("report") or {}).get("slug") or args.tool
    recipe = {
        "schema": "strhub-verified/recipe/1",
        "slug": slug,
        "manifest_yml": manifest_yml,
        "dockerfile": (d / "Dockerfile").read_text() if (d / "Dockerfile").is_file() else "",
    }
    if (d / "Dockerfile.fallback").is_file():
        recipe["dockerfile_fallback"] = (d / "Dockerfile.fallback").read_text()
    bed = d / "assets" / "regions.bed"
    if bed.is_file():
        recipe["regions_bed"] = bed.read_text()
    if args.proposal and pathlib.Path(args.proposal).is_file():
        try:
            recipe["proposal"] = json.loads(pathlib.Path(args.proposal).read_text())
        except Exception:  # noqa: BLE001
            pass
    if (m.get("environment") or {}).get("source") == "documented":
        import fidelity
        import source_install
        import authorization
        reviewed = json.loads(pathlib.Path(args.procedure_review).read_text()) if args.procedure_review else {}
        install = source_install.installation(recipe.get("proposal") or {}, m)
        if (not authorization.validate(reviewed, m).valid
                or not install.get("ready") or install != reviewed.get("installation")
                or reviewed.get("profile") != fidelity.PROFILE
                or reviewed.get("manifest_sha256") != fidelity.digest(json.dumps(m, sort_keys=True))):
            raise ValueError("cannot attach a source-installation recipe without matching evidence")
        # Retain a submission's descriptor, but never describe it as the file
        # used by CI: the builder independently materialises the cited carrier.
        recipe["submitted_dockerfile"] = recipe["dockerfile"]
        recipe["dockerfile"] = ""
        recipe["source_installation"] = install
        if args.source_install_dockerfile:
            selected = pathlib.Path(args.source_install_dockerfile)
            if selected.is_file():
                text = selected.read_bytes().decode("utf-8")
                if text != install["carrier_dockerfile"]:
                    raise ValueError("selected installation carrier differs from the reviewed transcript")
                recipe["dockerfile"] = text
    out = pathlib.Path(args.reports)
    out.mkdir(exist_ok=True)
    (out / f"{slug}.recipe.json").write_text(json.dumps(recipe, indent=2))
    print(f"attached recipe for {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
