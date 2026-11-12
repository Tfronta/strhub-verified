"""Stage and verify the only runner-supplied inputs allowed in an automatic run."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess

import _paths

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = "datasets/index.json"


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"cannot establish tracked dataset evidence ({args[0]})")
    return result.stdout.strip()


def _tracked(root, commit, relative):
    path = _paths.destination(root, relative)
    entry = _git(root, "ls-tree", commit, "--", relative).split()
    if (not path.is_file() or len(entry) < 4 or entry[:2] != ["100644", "blob"]
            or _git(root, "hash-object", "--no-filters", "--", str(path)) != entry[2]):
        raise ValueError(f"dataset file differs from the evaluator commit: {relative}")
    return path


def _sha256(path, unpack=False):
    opener = gzip.open if unpack else open
    with opener(path, "rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plan(root, input_type):
    commit = _git(root, "rev-parse", "HEAD")
    index = _tracked(root, commit, INDEX)
    dataset = json.loads(index.read_bytes())["datasets"].get(input_type)
    if not dataset:
        raise ValueError("the declared input type has no shared dataset")
    data = _tracked(root, commit, dataset["data"])
    canonical = dataset["canonical_input"]
    if len(_paths.relative(canonical).parts) != 1 or canonical != pathlib.PurePosixPath(canonical).name:
        raise ValueError("the shared dataset requires a single canonical filename")
    files = [(data, canonical, data.suffix == ".gz" and not canonical.endswith(".gz"))]
    if dataset["format"] == "bam":
        index_path = _tracked(root, commit, dataset["bam_index"])
        files.append((index_path, canonical + ".bai", False))
    return commit, dataset, files


def stage(root, work, input_type):
    """Copy the exact registered data into a new directory; never overlay it."""
    _, dataset, files = _plan(root, input_type)
    mount = _paths.destination(work, "in_external")
    mount.mkdir(parents=True, exist_ok=False)
    for source, name, unpack in files:
        opener = gzip.open if unpack else open
        with opener(source, "rb") as src, (mount / name).open("xb") as dest:
            shutil.copyfileobj(src, dest)
    return dataset


def verify(root, work, manifest, review, command):
    """Recompute provenance from Git and the files about to be mounted."""
    import authorization

    checked = authorization.validate(review, manifest)
    if not checked.valid or not checked.review["may_say_runs"] or command != manifest["run"]["cmd"]:
        raise ValueError("the launch command has no matching approved upstream procedure")
    input_type = manifest["inputs"]["type"]
    commit, dataset, files = _plan(root, input_type)
    mount = _paths.destination(work, "in_external")
    if {p.name for p in mount.iterdir()} != {name for _, name, _ in files}:
        raise ValueError("the input mount has missing or undeclared files")
    verified = []
    for source, name, unpack in files:
        path = _paths.destination(mount, name)
        expected = _sha256(source, unpack)
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"the mounted file differs from the shared dataset: {name}")
        verified.append({
            "mount_path": f"/data/in/{name}", "sha256": expected, "size_bytes": path.stat().st_size,
            "source_path": source.relative_to(root).as_posix(),
            "source_sha256": _sha256(source) if unpack else expected,
            "transformation": "gunzip" if unpack else "none",
        })
    return {"schema": "strhub-mounted-inputs/1", "leg": "external",
            "evaluator_commit": commit, "dataset_registry": INDEX, "input_type": input_type,
            "dataset": dataset["name"], "assembly": dataset.get("reference"), "source": dataset.get("source"),
            "procedure_evidence_sha256": review["evidence_sha256"], "files": verified}


def main():
    import _manifest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=pathlib.Path)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    output = _paths.destination(args.work, "mounted_inputs.json")
    output.unlink(missing_ok=True)
    try:
        review = json.loads((args.work / "procedure_review.json").read_bytes())
        result = verify(ROOT, args.work, _manifest.load(args.manifest), review, args.command)
        output.write_text(json.dumps(result, indent=2) + "\n")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Input provenance could not be established: {exc}\n")


if __name__ == "__main__":
    main()
