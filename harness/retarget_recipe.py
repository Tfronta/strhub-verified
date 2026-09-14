"""Re-point a committed recipe at a newer ref, as a trial recipe.

When a tool publishes a release after it was verified, the honest thing is to
run the same recipe against the new code and show the owner what happened,
without touching the published attestation until they say so. This takes
tools/<slug>/ as it is, swaps the pinned ref in the manifest and in the
Dockerfile's ARG lines, and emits the base64 recipe that a trial dispatch
takes (see verify.yml `recipe`).

Usage:
  python harness/retarget_recipe.py <slug> <new_ref> [--out recipe.b64] [--slug-out]
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

REF_LINE = re.compile(r'^(\s*ref:\s*)["\']?[0-9A-Za-z._/-]+["\']?(\s*(?:#.*)?)$', re.M)
ARG_LINE = re.compile(r'^(ARG\s+\w*_REF=)\S+', re.M)


def retarget(slug: str, new_ref: str) -> dict:
    d = ROOT / "tools" / slug
    if not (d / "manifest.yml").is_file():
        raise SystemExit(f"::error::no committed recipe at tools/{slug}")
    manifest = (d / "manifest.yml").read_text()
    manifest, n_ref = REF_LINE.subn(rf'\g<1>"{new_ref}"\g<2>', manifest, count=1)
    if n_ref != 1:
        raise SystemExit(f"::error::could not find the source.ref line in tools/{slug}/manifest.yml")
    # The slug must not collide with the published one: a trial of a newer ref
    # is a different claim, and the report file is named after it.
    short = new_ref[:7]
    new_slug = f"{slug}-{short}" if short not in slug else slug
    manifest = re.sub(r'^(\s*slug:\s*)["\']?[\w.-]+["\']?\s*$', rf'\g<1>"{new_slug}"', manifest, count=1, flags=re.M)
    manifest = ("# Retargeted by STRhub Verified to a newer upstream ref for a TRIAL. The\n"
                "# recipe is the one that verified the previous ref, unchanged otherwise.\n" + manifest)
    dockerfile = (d / "Dockerfile").read_text()
    dockerfile, _ = ARG_LINE.subn(rf"\g<1>{new_ref}", dockerfile)
    recipe = {"manifest_yml": manifest, "dockerfile": dockerfile}
    bed = d / "assets" / "regions.bed"
    if bed.is_file():
        recipe["regions_bed"] = bed.read_text()
    return {"slug": new_slug, "recipe": recipe,
            "recipe_b64": base64.b64encode(json.dumps(recipe).encode()).decode()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("new_ref")
    ap.add_argument("--out", default="", help="write the base64 recipe here")
    args = ap.parse_args()
    r = retarget(args.slug, args.new_ref)
    if args.out:
        pathlib.Path(args.out).write_text(r["recipe_b64"])
    print(json.dumps({"slug": r["slug"], "bytes": len(r["recipe_b64"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
