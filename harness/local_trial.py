"""Run a trial locally from any GitHub repository URL and write the full
artifact directory expected by strhub-web (`report.json`, `recipe.json`,
`summary.md`, `report.html`, `report.pdf`).

Works for both the 23 benchmark tools and any brand-new public GitHub
repository (via `detect_recipe.gather` or `git clone --filter=blob:none` when
`api.github.com` is unreachable or rate-limited).

Usage:
  python3 harness/local_trial.py --repo https://github.com/owner/tool \
      [--ref <sha_or_tag>] [--ref-label v1.0] --out-dir .trial-fixtures/tr_xxx
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmark_recipes as br  # noqa: E402
import detect_recipe as dr  # noqa: E402
import propose_manifest as pm  # noqa: E402
import _manifest  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def resolve_ref_git(slug: str, ref: str = "") -> tuple[str, str, str]:
    """Resolve (sha, label, how) for `https://github.com/<slug>` via git ls-remote."""
    url = f"https://github.com/{slug}.git"
    res = subprocess.run(
        ["git", "ls-remote", url, "HEAD", "refs/heads/*", "refs/tags/*"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"Repository not found or unreachable: {url}")
    head_sha = ""
    heads: dict[str, str] = {}
    tags: list[tuple[str, str]] = []
    for line in res.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        sha, name = parts[0].strip(), parts[1].strip()
        if name == "HEAD":
            head_sha = sha
        elif name.startswith("refs/heads/"):
            heads[name.removeprefix("refs/heads/")] = sha
        elif name.startswith("refs/tags/"):
            tname = name.removeprefix("refs/tags/")
            if tname.endswith("^{}"):
                tname = tname[:-3]
                tags = [(k, v) for k, v in tags if k != tname]
            tags.append((tname, sha))

    want = (ref or "").strip()
    if want:
        if re.fullmatch(r"[0-9a-fA-F]{40}", want):
            return want.lower(), want[:7], "given"
        for tname, sha in tags:
            if tname == want or tname.lstrip("vV") == want.lstrip("vV"):
                return sha, tname, "given"
        if want in heads:
            return heads[want], want, "given"
        for sha in list(heads.values()) + [s for _, s in tags] + ([head_sha] if head_sha else []):
            if sha.startswith(want.lower()):
                return sha, want[:7], "given"
        return want, want[:7], "given"

    if tags:
        tname, sha = tags[-1]
        return sha, tname, "tag"
    if head_sha:
        branch = next((b for b, s in heads.items() if s == head_sha), "HEAD")
        return head_sha, branch, "head"
    raise RuntimeError(f"Could not resolve a commit for {slug}")


def gather_via_git(slug: str, ref: str, tag: str = "") -> dict:
    """Gather the exact structure `detect_recipe.gather()` returns, using a
    blobless shallow fetch (`--depth 1 --filter=blob:none`) so even huge
    repositories take ~1 second."""
    tmp_root = ROOT / ".tmp"
    tmp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(tmp_root)) as tmp:
        clone_dir = pathlib.Path(tmp) / "repo"
        empty_tpl = pathlib.Path(tmp) / "tpl"
        clone_dir.mkdir()
        empty_tpl.mkdir()
        url = f"https://github.com/{slug}.git"
        subprocess.run(
            ["git", "-C", str(clone_dir), "init", "--bare", "-q", f"--template={empty_tpl}"],
            check=True, timeout=15,
        )
        target_ref = ref or "HEAD"
        subprocess.run(
            ["git", "-C", str(clone_dir), "fetch", "-q", "--depth", "1", "--filter=blob:none", url, target_ref],
            check=True, timeout=30,
        )
        resolved_sha = subprocess.run(
            ["git", "-C", str(clone_dir), "rev-parse", "FETCH_HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        ls_tree = subprocess.run(
            ["git", "-C", str(clone_dir), "ls-tree", "-r", "FETCH_HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout
        tree_entries = []
        paths = []
        path_set = set()
        for line in ls_tree.splitlines():
            if "\t" not in line:
                continue
            meta, path = line.split("\t", 1)
            mparts = meta.split()
            obj_type = mparts[1] if len(mparts) > 1 else "blob"
            tree_entries.append({"path": path, "type": obj_type, "size": 1000 if obj_type == "blob" else 0})
            if obj_type == "blob":
                paths.append(path)
                path_set.add(path)

        def read_blob(rel_path: str) -> str | None:
            if rel_path not in path_set:
                return None
            txt = dr.fetch_file(slug, resolved_sha, rel_path)
            if txt is not None:
                return txt
            res = subprocess.run(
                ["git", "-C", str(clone_dir), "show", f"FETCH_HEAD:{rel_path}"],
                capture_output=True, timeout=20, check=False,
            )
            if res.returncode != 0:
                return None
            return res.stdout.decode("utf-8", "replace")[:dr.MAX_FILE_BYTES]

        readme, readme_name = "", None
        for rname in dr.README_NAMES:
            txt = read_blob(rname)
            if txt is not None:
                readme = txt
                readme_name = rname
                break

        files: dict[str, str] = {}
        for rel in dr.build_content_paths(paths) + dr.loci_file_paths(tree_entries):
            txt = read_blob(rel)
            if txt is not None:
                files[rel] = txt

        repo_docs, _wiki_pages = dr.linked_docs(readme, slug, path_set)
        docs = []
        for rel in repo_docs:
            txt = read_blob(rel)
            if txt is not None:
                docs.append({"path": rel, "origin": "repo", "text": txt})

        return {
            "tree_resp": {"repo": f"https://github.com/{slug}", "ref": resolved_sha, "tree": tree_entries, "truncated": False},
            "readme": readme,
            "readme_name": readme_name,
            "files": files,
            "docs": docs,
            "published": {"bioconda": {}, "release": None},
            "tag": tag,
        }


def _find_benchmark_snapshot(slug: str) -> pathlib.Path | None:
    want = slug.lower()
    for spec in br.rows():
        if spec["repo"].lower() == want:
            d = br.BENCH / spec["name"]
            if (d / "tree.json").is_file():
                return d
    return None


def _parse_kv_output(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def upstream_build_command(manifest: dict, review: dict, checkout: pathlib.Path, tag: str) -> list[str]:
    """Resolve only the cited upstream build; never build the proposed stub."""
    import fidelity
    import _paths
    import authorization
    if not authorization.validate(review, manifest).valid:
        raise ValueError("no proven upstream installation for this effective manifest")
    if (not (review.get("installation") or {}).get("ready")
            or review.get("manifest_sha256") != fidelity.digest(json.dumps(manifest, sort_keys=True))):
        raise ValueError("no proven upstream installation for this manifest")
    source = manifest["source"]
    subprocess.run(["git", "clone", "--no-checkout", "--", source["repo"], str(checkout)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", source["ref"]], check=True, capture_output=True, text=True)
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    if head != source["ref"]:
        raise ValueError("checkout is not the cited immutable commit")
    fidelity.verify_checkout(checkout, review, manifest)
    import source_install
    if review["installation"].get("profile") == source_install.PROFILE:
        path = checkout.parent / "source-install.Dockerfile"
        source_install.materialise(checkout, review["installation"], path)
    else:
        path = _paths.confined(checkout, manifest["environment"]["from_repo"])
    return ["docker", "build", "-f", str(path), "-t", tag, str(checkout)]


def build_local_trial(repo_url: str, ref: str, ref_label: str, out_dir: pathlib.Path,
                      prefer_offline: bool = False, run_docker: bool = False) -> dict:
    slug = dr.repo_slug(repo_url)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    snap = _find_benchmark_snapshot(slug)

    src = None
    if snap is not None and (prefer_offline or not ref or ref == json.loads((snap / "tree.json").read_text()).get("ref")):
        src = dr.load_snapshot(snap)
        ref = src["tree_resp"].get("ref", ref or "HEAD")
        if not ref_label:
            ref_label = src.get("tag", "")
    else:
        if not ref or not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
            resolved_sha, resolved_label, _ = resolve_ref_git(slug, ref)
            ref = resolved_sha
            if not ref_label:
                ref_label = resolved_label
        try:
            src = dr.gather(slug, ref, ref_label, token)
        except Exception:
            src = gather_via_git(slug, ref, ref_label)

    proposal = dr.detect(slug, ref, src["tree_resp"], src["readme"], src["readme_name"], extras=src)
    run_slug = f"trial-{slug.split('/')[-1].lower()}-{ref[:7]}"
    built = pm.build(proposal, run_slug, submitted_by="third_party", ref_label=ref_label)
    _manifest.loads(built["manifest_yml"])
    proposal["limitations"] = built["limitations"]
    proposal["procedure"] = built["procedure"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        work_dir = tmp_path / "work"
        prop_dir = work_dir / "proposal"
        prop_dir.mkdir(parents=True)
        manifest_path = prop_dir / "manifest.yml"
        dockerfile_path = prop_dir / "Dockerfile"
        manifest_path.write_text(built["manifest_yml"])
        dockerfile_path.write_text(built["dockerfile"])
        if built.get("dockerfile_fallback"):
            (prop_dir / "Dockerfile.fallback").write_text(built["dockerfile_fallback"])

        proposal_json = tmp_path / "recipe_proposal.json"
        proposal_json.write_text(json.dumps(proposal, indent=2))

        # --- Step 1: Pre-flight (prepare.py) ---
        prep_res = subprocess.run(
            [sys.executable, str(ROOT / "harness" / "prepare.py"), run_slug, "--work", str(work_dir),
             "--trial", "--proposal", str(proposal_json)],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        )
        preflight = _parse_kv_output(prep_res.stdout)

        proc = json.loads((work_dir / "procedure_review.json").read_text())
        may_run = bool(proc.get("may_say_runs"))

        log_ext = tmp_path / "log_external.txt"
        log_build = tmp_path / "log_build.txt"
        log_ex = tmp_path / "log_example.txt"
        io_json = tmp_path / "io_external.json"
        content_json = tmp_path / "content_external.json"
        example_json = tmp_path / "no-example.json"

        avail_flag = "pass"
        installs_flag = "fail"
        runs_flag = "skipped"
        example_flag = "skipped"
        infra_failure = preflight.get("input_failure", "")
        if preflight.get("install_ready") != "1" or (not may_run and preflight.get("example_ready") != "1"):
            log_build.write_text(
                f"==== STRhub Verified local evaluation ====\n"
                f"Repository: https://github.com/{slug} @ {ref}\n"
                f"Procedure classifier blocker: {proc.get('blocker')}\n"
                f"Reason: {proc.get('reason')}\n"
            )
        elif run_docker:
            d_info = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
            if d_info.returncode != 0:
                infra_failure = "Docker daemon is not running or reachable on this machine"
                print(f"[local_trial] {infra_failure}; open Docker Desktop and retry.", file=sys.stderr)
                log_build.write_text((d_info.stdout or "") + "\n" + (d_info.stderr or ""))
            else:
                img_tag = f"strhub-trial:{run_slug}"
                print(f"[local_trial] [1/3] Pre-flight ready (dataset={preflight.get('input_type')}, "
                      f"external_ready={preflight.get('external_ready')}, example_ready={preflight.get('example_ready')})",
                      file=sys.stderr)
                print(f"[local_trial] [2/3] Building image {img_tag}...", file=sys.stderr)
                try:
                    build_cmd = upstream_build_command(built["manifest"], proc, work_dir / "source", img_tag)
                except (ValueError, OSError, subprocess.CalledProcessError) as exc:
                    infra_failure = "upstream installation evidence could not be established at the pinned checkout"
                    b_res = subprocess.CompletedProcess([], 1, "", str(exc))
                    log_build.write_text(b_res.stderr)
                else:
                    b_res = subprocess.run(
                        ["bash", str(ROOT / "harness" / "record_terminal.sh"), str(log_build), *build_cmd],
                        cwd=str(ROOT), capture_output=True, text=True,
                    )
                if b_res.returncode == 0:
                    installs_flag = "pass"
                    hardening = [
                        "--network", "none",
                        "--memory", "6g", "--memory-swap", "6g",
                        "--cpus", "2", "--pids-limit", "512",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                    ]
                    timeout_min = str(preflight.get("timeout") or "20")
                    if preflight.get("external_ready") == "1":
                        actual_command = preflight["cmd"]
                        checked = subprocess.run([
                            sys.executable, str(ROOT / "harness" / "input_provenance.py"),
                            "--work", str(work_dir), "--manifest", preflight["manifest"],
                            f"--command={actual_command}",
                        ], cwd=str(ROOT), capture_output=True, text=True)
                        if checked.returncode:
                            infra_failure = checked.stderr.strip() or "the mounted dataset provenance check"
                        else:
                            print("[local_trial] [3/3] Running container (--network none) on STRhub reference dataset...",
                                  file=sys.stderr)
                            out_ext = work_dir / "out_external"
                            out_ext.mkdir(parents=True, exist_ok=True)
                            out_ext.chmod(0o777)
                            run_cmd = [
                                "bash", str(ROOT / "harness" / "run_container.sh"),
                                f"{run_slug}_ext", timeout_min, str(log_ext),
                                *hardening,
                                "-v", f"{work_dir / 'in_external'}:/data/in:ro",
                                "-v", f"{out_ext}:/data/out",
                                img_tag, actual_command,
                            ]
                            r_res = subprocess.run(run_cmd, cwd=str(ROOT), capture_output=True, text=True)
                            runs_flag = "pass" if r_res.returncode == 0 else "fail"
                            subprocess.run([
                                sys.executable, str(ROOT / "harness" / "check_io.py"),
                                str(manifest_path), str(out_ext), "--json", str(io_json),
                            ], cwd=str(ROOT), check=False, capture_output=True, text=True)
                            subprocess.run([
                                sys.executable, str(ROOT / "harness" / "check_content.py"),
                                str(manifest_path), str(out_ext), "--json", str(content_json),
                                "--panel", preflight.get("supported_loci", ""),
                            ], cwd=str(ROOT), check=False, capture_output=True, text=True)
                    if preflight.get("example_ready") == "1":
                        print("[local_trial] Running repository's own example (--network none)...", file=sys.stderr)
                        out_ex = work_dir / "out_example"
                        out_ex.mkdir(parents=True, exist_ok=True)
                        out_ex.chmod(0o777)
                        example_json = tmp_path / "example.json"
                        example_result = subprocess.run([
                            "bash", str(ROOT / "harness" / "run_container.sh"),
                            f"{run_slug}_ex", timeout_min, str(log_ex),
                            *hardening,
                            "-v", f"{out_ex}:/data/out",
                            img_tag, preflight.get("example_cmd", ""),
                        ], cwd=str(ROOT), check=False, capture_output=True, text=True)
                        example_flag = "success" if example_result.returncode == 0 else "failure"
                        subprocess.run([
                            sys.executable, str(ROOT / "harness" / "check_example.py"),
                            str(manifest_path), str(out_ex), "--json", str(example_json),
                        ], cwd=str(ROOT), check=False, capture_output=True, text=True)
        else:
            infra_failure = "local preview mode (no container was built or executed on this machine)"
            log_build.write_text(
                f"==== STRhub Verified recipe evaluation ({proc.get('install_method')}) ====\n"
                f"Repository: https://github.com/{slug} @ {ref}\n"
                f"Procedure classifier: ready (all 4 blocks of GUIA-PASO-1.md present).\n"
                f"Note: Docker container execution was not run in local preview mode.\n"
            )

        cat_slug = built["manifest"]["report"]["slug"]
        reports_dir = ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)

        cmd = [
            sys.executable, str(ROOT / "harness" / "report.py"),
            "--manifest", str(manifest_path),
            "--procedure-review", str(work_dir / "procedure_review.json"),
            "--mounted-inputs", str(work_dir / "mounted_inputs.json"),
            "--available", avail_flag,
            "--installs", installs_flag,
            "--runs", runs_flag,
            "--io", str(io_json),
            "--content", str(content_json),
            "--matrix", str(tmp_path / "no-matrix.json"),
            "--readme", str(tmp_path / "no-readme.json"),
            "--example", str(example_json),
            "--example-runs", example_flag,
            "--regions-validation", str(tmp_path / "no-regions.json"),
            "--log-build", str(log_build),
            "--log-external", str(log_ext),
            "--log-example", str(log_ex),
            "--ref", ref,
            "--mode", "trial",
            "--infra-failure", infra_failure,
            "--recipe-proposal", str(proposal_json),
        ]
        subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)

        subprocess.run([
            sys.executable, str(ROOT / "harness" / "attach_recipe.py"),
            cat_slug, "--dockerdir", str(prop_dir), "--proposal", str(proposal_json),
            "--procedure-review", str(work_dir / "procedure_review.json"),
            "--source-install-dockerfile", str(work_dir / "source-install.Dockerfile"),
        ], cwd=str(ROOT), check=True, capture_output=True, text=True)

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "preflight.json").write_text(json.dumps(preflight, indent=2))
        pdf_out = out_dir / "report.pdf"
        pdf_res = subprocess.run([
            sys.executable, str(ROOT / "harness" / "generate_pdf.py"),
            "--manifest", str(manifest_path),
            "--datasets", str(ROOT / "datasets" / "index.json"),
            "--publishable", "false",
            "--out", str(pdf_out),
        ], cwd=str(ROOT), check=False, capture_output=True, text=True)
        if pdf_res.returncode != 0 and run_docker:
            print(f"[local_trial] PDF warning: {pdf_res.stderr.strip().splitlines()[-1] if pdf_res.stderr else 'failed'}",
                  file=sys.stderr)

        shutil.copy2(reports_dir / f"{cat_slug}.json", out_dir / "report.json")
        shutil.copy2(reports_dir / f"{cat_slug}.recipe.json", out_dir / "recipe.json")
        shutil.copy2(reports_dir / f"{cat_slug}.summary.md", out_dir / "summary.md")
        shutil.copy2(reports_dir / f"{cat_slug}.html", out_dir / "report.html")
        for leg, log in (("build", log_build), ("external", log_ext), ("example", log_ex)):
            if log.is_file() and log.stat().st_size > 0:
                shutil.copy2(log, out_dir / f"log-{leg}.txt")
            transcript = log.with_suffix(log.suffix + ".terminal")
            if transcript.is_file() and transcript.stat().st_size > 0:
                shutil.copy2(transcript, out_dir / f"terminal-{leg}.txt")

        for p in reports_dir.glob(f"{cat_slug}.*"):
            p.unlink(missing_ok=True)

        return json.loads((out_dir / "report.json").read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="")
    ap.add_argument("--ref-label", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--prefer-offline", action="store_true")
    ap.add_argument("--docker", action="store_true",
                    help="build the Docker image and run the container with --network none")
    ap.add_argument("--resolve-only", action="store_true")
    args = ap.parse_args()
    slug = dr.repo_slug(args.repo)
    if args.resolve_only:
        sha, label, how = resolve_ref_git(slug, args.ref)
        print(json.dumps({"ok": True, "sha": sha, "label": label, "how": how}))
        return 0
    report = build_local_trial(args.repo, args.ref, args.ref_label, pathlib.Path(args.out_dir),
                               prefer_offline=args.prefer_offline, run_docker=args.docker)
    print(json.dumps({
        "ok": True,
        "slug": (report.get("report") or {}).get("slug") or report["tool"]["name"],
        "ref": (report.get("source") or {}).get("ref_resolved"),
        "step1": report.get("step1"),
        "verdict": (report.get("verdict") or {}).get("code"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
