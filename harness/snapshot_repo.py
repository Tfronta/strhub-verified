"""Freeze what detect_recipe reads about a repository at a commit.

    python harness/snapshot_repo.py <repo-url> <sha> <out-dir> [--tag v1.2]
    python harness/snapshot_repo.py --benchmark     # every row of testdata/benchmark/repos.tsv

The snapshot is `detect_recipe.gather()` written to disk: tree.json, README.md,
the documents and wiki pages the README links to (docs/, wiki/), the build and
packaging files (files/), and what exists outside the repository
(published.json: Bioconda versions, the release's assets). detect_recipe
--offline reads it back, so a test runs the proposal a trial of that commit
would get, without the network. Files a person wrote next to the snapshot
(expected.json) are left alone.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import detect_recipe as dr  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "harness" / "testdata" / "benchmark"
WRITTEN = ("tree.json", "README.md", "published.json", "docs", "wiki", "files")


def write(out: pathlib.Path, slug: str, sha: str, src: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in WRITTEN:
        p = out / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    t = src["tree_resp"]
    (out / "tree.json").write_text(json.dumps({
        "repo": f"https://github.com/{slug}", "ref": sha, "tag": src.get("tag") or "",
        "readme_name": src.get("readme_name"), "truncated": t.get("truncated", False),
        "docs_order": [d["path"] for d in src["docs"]],
        "tree": t["tree"]}, indent=0))
    if src["readme"]:
        (out / "README.md").write_text(src["readme"])
    for d in src["docs"]:
        base = out / ("wiki" if d["origin"] == "wiki" else "docs")
        rel = d["path"].removeprefix("wiki/") + (".md" if d["origin"] == "wiki" else "")
        f = base / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(d["text"])
    for path, text in src["files"].items():
        f = out / "files" / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    (out / "published.json").write_text(json.dumps(src["published"], indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?")
    ap.add_argument("sha", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--tag", default="")
    ap.add_argument("--benchmark", action="store_true", help="refresh every snapshot in repos.tsv")
    ap.add_argument("--only", default="", help="with --benchmark: comma-separated names")
    args = ap.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    jobs = []
    if args.benchmark:
        only = {n for n in args.only.split(",") if n}
        for ln in (BENCH / "repos.tsv").read_text().splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            name, repo, tag, sha, _set = ln.split("\t")
            if not only or name in only:
                jobs.append((f"https://github.com/{repo}", sha, BENCH / name, tag))
    else:
        if not (args.repo and args.sha and args.out):
            ap.error("repo, sha and out are required without --benchmark")
        jobs.append((args.repo, args.sha, pathlib.Path(args.out), args.tag))
    for repo, sha, out, tag in jobs:
        slug = dr.repo_slug(repo)
        src = dr.gather(slug, sha, tag, token)
        write(out, slug, sha, src)
        print(f"{out.name}: {len(src['tree_resp']['tree'])} paths, readme={src['readme_name']}, "
              f"docs={len(src['docs'])}, files={len(src['files'])}, "
              f"bioconda={ {k: (v[-1] if v else None) for k, v in src['published']['bioconda'].items()} }, "
              f"release_assets={len((src['published']['release'] or {}).get('assets', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
