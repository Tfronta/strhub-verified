"""Prepare a verify run: read the manifest, resolve the external dataset, and
stage only the shared dataset admitted by the upstream procedure review.

Centralising this in Python (vs bash in the workflow) keeps it testable and
keeps the YAML small. It emits GitHub-Actions `key=value` step outputs and
stages files under <work>/in_own and <work>/in_external.

Usage:
  python harness/prepare.py <tool> --work work [--trial --proposal <evidence.json>]

A URL trial reads the evaluator's descriptor from <work>/proposal. Its manifest
is checked against pinned upstream evidence before any Docker step.
"""
from __future__ import annotations
import argparse
import gzip
import json
import pathlib
import re
import shutil
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import datasets as datasets_lib  # noqa: E402
import regions_library  # noqa: E402
import _manifest  # noqa: E402
import _paths  # noqa: E402
import input_provenance  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Coordinate-based tools read /data/in/regions.bed; the author's BED (whatever its
# original name) is staged under this canonical name so one run cmd fits both legs.
REGIONS_CANONICAL = "regions.bed"
#: A catalog in JSON (ExpansionHunter's) is staged under its own extension.
REGIONS_JSON = "regions.json"


def _local_input(value: str, tool_dir=None, tool=None) -> pathlib.Path:
    rel = _paths.relative(value)
    # A dispatched upload has a virtual tools/<slug>/ path. Resolve it against
    # the explicit recipe root, never by accepting an absolute manifest path.
    if tool_dir is not None and tool is not None:
        prefix = pathlib.PurePosixPath("tools") / tool
        if rel.is_relative_to(prefix):
            return _paths.confined(tool_dir, str(rel.relative_to(prefix)))
    return _paths.confined(ROOT, value)


def _check_source(path: pathlib.Path, root: pathlib.Path) -> None:
    _paths.confined(root, str(path.relative_to(root)))
    if path.is_dir():
        for child in path.iterdir():
            _paths.confined(root, str(child.relative_to(root)))
    elif path.name.endswith(".bam"):
        _paths.confined(root, str(_bam_sidecar(path).relative_to(root)))


def _check_fixture(fixture, tool_dir=None, tool=None) -> None:
    if isinstance(fixture, dict):
        _paths.raw_url(fixture)
    elif fixture is not None:
        src = _local_input(fixture, tool_dir, tool)
        root = tool_dir if tool_dir is not None and src.is_relative_to(tool_dir) else ROOT
        _check_source(src, root)


def _check_regions(regions, input_type=None, tool_dir=None, tool=None) -> None:
    if isinstance(regions, dict) and "repo" in regions:
        _paths.raw_url(regions)
    elif isinstance(regions, dict) and "library" in regions:
        src = regions_library.library_path(input_type or "", regions["library"])
        if src is not None:
            _check_source(src, ROOT)
    elif regions is not None:
        value = regions["path"] if isinstance(regions, dict) else regions
        _local_input(value, tool_dir, tool)


def _check_dataset(input_type) -> None:
    rec = datasets_lib.load_index().get("datasets", {}).get(input_type)
    if not rec:
        return
    for key in ("data", "bam_index", "supported_loci"):
        if rec.get(key):
            src = _paths.confined(ROOT, rec[key])
            _check_source(src, ROOT)
    if rec.get("canonical_input"):
        # A canonical name is a filename, never a destination directory.
        if len(_paths.relative(rec["canonical_input"]).parts) != 1:
            raise ValueError("canonical_input must be a filename")
    rg = rec.get("reference_genome") or {}
    if rg.get("filename") and len(_paths.relative(rg["filename"]).parts) != 1:
        raise ValueError("reference genome filename must be a filename")


def preflight(m: dict, tool_dir: pathlib.Path, tool: str, work: pathlib.Path) -> None:
    """All runner-side paths are checked before the first staging effect."""
    for name in ("proposal", "in_own", "in_external", "out_external", "out_example", "ctx"):
        dest = _paths.destination(work, name)
        if dest.is_dir():
            # Includes stale files: urlretrieve/copy2 must not follow a symlink
            # that a previous attempt left at a canonical destination filename.
            for child in dest.rglob("*"):
                _paths.destination(work, str(child.relative_to(work)))
    _paths.confined(tool_dir, m["environment"]["dockerfile"])
    assets = _paths.confined(tool_dir, "assets")
    if assets.is_dir():
        _check_source(assets, tool_dir)
    inputs = m.get("inputs") or {}
    _check_fixture(inputs.get("fixture"), tool_dir, tool)
    _check_regions(inputs.get("regions"), inputs.get("type"), tool_dir, tool)
    _check_dataset(inputs.get("type"))


def _bam_sidecar(bam: pathlib.Path) -> pathlib.Path:
    """Return the .bai path for a BAM (handles *.codis.bam → *.codis.bam.bai)."""
    return bam.parent / f"{bam.name}.bai"


def _copy_bam_pair(
    src_bam: pathlib.Path,
    dest_dir: pathlib.Path,
    canonical: str | None = None,
) -> bool:
    """Copy a BAM and its .bai sidecar into dest_dir, optionally renaming to
    a canonical filename so that the same run command works for both legs."""
    if not src_bam.is_file():
        return False
    dest_name = canonical or src_bam.name
    dest = _paths.destination(dest_dir, dest_name)
    bai_dest = _paths.destination(dest_dir, f"{dest_name}.bai")
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_bam, dest)
    bai = _bam_sidecar(src_bam)
    if bai.is_file():
        shutil.copy2(bai, bai_dest)
    return True


def stage_own(
    fixture,
    work_in: pathlib.Path,
    canonical: str | None = None,
    *, tool_dir=None, tool=None,
) -> bool:
    """Stage the author's own fixture. Returns True if staged.

    When *canonical* is set (e.g. ``"input.bam"``), the primary data file is
    renamed so that the same run command works identically for the own and
    external legs.
    """
    _check_fixture(fixture, tool_dir, tool)
    if isinstance(fixture, dict):
        # Remote BYOR: fetch the single file from the author's PUBLIC repo.
        path = fixture["path"]
        url = _paths.raw_url(fixture)
        raw_name = pathlib.Path(path).name
        dest_name = canonical or raw_name
        dest = _paths.destination(work_in, dest_name)
        _paths.destination(work_in, f"{dest_name}.bai")
        work_in.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 (public raw URL)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::could not fetch BYOR fixture {url}: {exc}",
                  file=sys.stderr)
            return False
        if dest.stat().st_size > 0:
            # For BAM files fetched remotely, also try to fetch the .bai sidecar.
            if dest_name.endswith(".bam"):
                for bai_suffix in [".bai", ".bam.bai"]:
                    bai_url = url + bai_suffix
                    bai_dest = work_in / f"{dest_name}.bai"
                    try:
                        urllib.request.urlretrieve(bai_url, bai_dest)  # noqa: S310
                        if bai_dest.stat().st_size > 0:
                            break
                        bai_dest.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        bai_dest.unlink(missing_ok=True)
            return True
        return False
    # Local path in this repo: copy the directory contents.
    src = _local_input(fixture, tool_dir, tool)
    if not src.exists():
        print(f"::warning::own fixture path not found: {src}", file=sys.stderr)
        return False
    if src.is_dir():
        destinations = [(f, _paths.destination(work_in, f.name)) for f in src.iterdir() if f.is_file()]
        work_in.mkdir(parents=True, exist_ok=True)
        for f, dest in destinations:
            shutil.copy2(f, dest)
    elif src.suffix == ".bam" or src.name.endswith(".bam"):
        if not _copy_bam_pair(src, work_in, canonical):
            return False
    else:
        dest_name = canonical or src.name
        dest = _paths.destination(work_in, dest_name)
        work_in.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return any(work_in.iterdir())


def stage_regions(regions, legs: list[pathlib.Path], input_type: str | None = None,
                  *, tool_dir=None, tool=None) -> str:
    """Stage the regions BED into every leg as canonical ``regions.bed``.

    An explicit ``inputs.regions`` takes precedence over any per-tool asset
    regions.bed already staged (which is why this runs after asset staging).

    Returns the provenance, used by the workflow to decide whether to validate and
    by the report to say who chose the regions:
      "tool"   — the author chose them: uploaded through the form (stored under the
                 tool's assets/), or a remote pointer. VALIDATED against the panel.
      "strhub" — a path committed by us, or a legacy per-tool asset. Trusted.
      "none"   — no regions BED anywhere.
    """
    _check_regions(regions, input_type, tool_dir, tool)
    for leg in legs:
        _paths.destination(leg, REGIONS_JSON)
        _paths.destination(leg, REGIONS_CANONICAL)

    def _fan_out(src: pathlib.Path) -> bool:
        name = REGIONS_JSON if src.suffix.lower() == ".json" else REGIONS_CANONICAL
        for leg in legs:
            leg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, leg / name)
        return True

    if isinstance(regions, dict) and "path" in regions and "repo" not in regions:
        # Author uploaded it; we store it. The file is ours to read, but the CHOICE
        # of loci was theirs — provenance must survive that, or the report would
        # credit STRhub for the author's panel.
        src = _local_input(regions["path"], tool_dir, tool)
        if not src.is_file():
            print(f"::error::uploaded regions BED not found: {src}", file=sys.stderr)
            return "none"
        _fan_out(src)
        return "tool" if regions.get("provided_by") == "author" else "strhub"

    if isinstance(regions, dict) and "library" in regions:
        # A ready-made file from the dataset's regions library, chosen by
        # format. STRhub's provenance: the loci are the panel's, the layout is
        # the tool's, and nobody had to write it.
        src = regions_library.library_path(input_type or "", regions["library"])
        if src is None:
            print(f"::error::no '{regions['library']}' regions file in the library for {input_type!r}",
                  file=sys.stderr)
            return "none"
        _fan_out(src)
        return "strhub"

    if isinstance(regions, dict):
        # Remote pointer (deprecated; hand-written manifests only). Fetch once from
        # the author's PUBLIC repo, then fan out.
        url = _paths.raw_url(regions)
        first = legs[0] / REGIONS_CANONICAL
        legs[0].mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, first)  # noqa: S310 (public raw URL)
        except Exception as exc:  # noqa: BLE001
            print(f"::error::could not fetch regions BED {url}: {exc}", file=sys.stderr)
            return "none"
        if first.stat().st_size == 0:
            print(f"::error::regions BED is empty: {url}", file=sys.stderr)
            return "none"
        for leg in legs[1:]:
            leg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(first, leg / REGIONS_CANONICAL)
        return "tool"

    if isinstance(regions, str):
        src = _local_input(regions, tool_dir, tool)
        if not src.is_file():
            print(f"::warning::regions path not found: {src}", file=sys.stderr)
            return "none"
        _fan_out(src)
        return "strhub"

    # No explicit regions — a legacy per-tool asset may already have staged one.
    if any((leg / REGIONS_CANONICAL).is_file() for leg in legs):
        return "strhub"
    return "none"


def stage_external(input_type, work_in: pathlib.Path) -> tuple[bool, str]:
    """Stage the typed external dataset. Returns (staged, dataset_name).

    Files are renamed to their ``canonical_input`` name (if configured) so the
    same run command works identically for both the own and external legs.
    """
    _check_dataset(input_type)
    rec = datasets_lib.resolve(input_type)
    if not rec:
        return False, ""
    data = ROOT / rec["data"]
    if not data.exists():
        return False, ""
    canonical = rec.get("canonical_input")
    _paths.destination(work_in, canonical or data.name)
    _paths.destination(work_in, f"{canonical or data.name}.bai")
    work_in.mkdir(parents=True, exist_ok=True)
    if rec.get("format") == "bam" or str(data).endswith(".bam"):
        if not _copy_bam_pair(data, work_in, canonical):
            return False, ""
        # Verify the index was staged too.
        expected_bai = f"{canonical}.bai" if canonical else None
        bam_index = rec.get("bam_index")
        if bam_index:
            idx_src = ROOT / bam_index
            if idx_src.is_file() and expected_bai:
                idx_dest = work_in / expected_bai
                if not idx_dest.exists():
                    shutil.copy2(idx_src, idx_dest)
    elif data.suffix == ".gz" and canonical and not canonical.endswith(".gz"):
        # Committed compressed, handed over uncompressed: every FASTQ reader
        # takes plain text, not every one takes gzip.
        with gzip.open(data, "rb") as src, open(work_in / canonical, "wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        dest_name = canonical or data.name
        shutil.copy2(data, work_in / dest_name)
    return True, rec.get("name", input_type or "")


def example_wrapper(cmd: str, cwd: str) -> str:
    """The README command, wrapped so that whatever it creates ends up under
    /data/out, whatever it was called and wherever it was written.

    A README example writes where it likes (`results/`, the cwd, a path in the
    command); the IO check reads /data/out. Instead of asking the author to
    rewrite their documented command to STRhub's mount, the wrapper marks the
    time, runs the command exactly as documented, and copies every regular file
    created or modified afterwards. The command's own exit status is preserved.
    """
    cmd = cmd.strip()
    return (
        f"cd {cwd!r} && touch /tmp/.strhub_mark && ( {cmd} ); rc=$?; "
        # -xdev: stay on the image's own filesystem. From a WORKDIR of `/`,
        # /proc and /sys are "newer" than the mark by construction, and copying
        # them passed a command that did not even exist; /data/out is a mount
        # too, so the copy never feeds on itself.
        "find . -xdev -type f -newer /tmp/.strhub_mark -size +0 ! -path './.git/*' "
        "! -path './proc/*' ! -path './sys/*' ! -path './dev/*' ! -path './data/*' "
        "! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' "
        "2>/dev/null | head -500 | "
        "while IFS= read -r f; do mkdir -p \"/data/out/$(dirname \"$f\")\" && cp \"$f\" \"/data/out/$f\"; done; "
        "exit $rc"
    )


_WRAPPED = re.compile(r"^cd (?P<cwd>'[^']*'|\S+) && touch /tmp/\.strhub_mark && \( (?P<cmd>.+?) \); rc=\$\?; ", re.S)


def unwrap_example(cmd: str) -> tuple[str, str | None]:
    """The tool's own command back out of `example_wrapper`, with the directory
    it ran from; an unwrapped command comes back as it is, with no directory.

    The report names what the gates ran. The wrapper is STRhub's plumbing
    around that — marking the time, copying files — and a reader shown the
    whole line cannot tell which part is the tool's."""
    m = _WRAPPED.match(cmd)
    if not m:
        return cmd, None
    return m.group("cmd"), m.group("cwd").strip("'")


#: What may run the program without being it: an interpreter and its script.
_RUNNERS = {"python", "python3", "python2", "bash", "sh", "perl", "Rscript", "julia", "java"}
_NOT_THE_TOOL = {"mkdir", "cd", "export", "true", "echo", "touch", "cp", "mv", "rm", "ln", "gunzip", "zcat"}


def is_placeholder_command(run_cmd: str) -> bool:
    """The run command a proposal writes when the README documents none."""
    cmd, _ = unwrap_example(run_cmd)
    return re.sub(r"(?:^|\s)#.*$", "", cmd).strip() in ("", "true")


def starts_command(run_cmd: str, cwd: str | None = None) -> str:
    """`<program> --help`, from the run command: the first segment of a chain
    that is not STRhub's plumbing (mkdir, cd), and the interpreter with its
    script when there is one (`python straglr.py`, `bash ./run.sh`). Empty
    when there is no program to ask (`true  # no command found`)."""
    cmd, wcwd = unwrap_example(run_cmd)
    cwd = cwd or wcwd or ""
    # A comment is not a command, whatever punctuation it holds.
    cmd = re.sub(r"(?:^|\s)#.*$", "", cmd)
    for seg in re.split(r"\s*(?:&&|;|\|\|)\s*", cmd):
        if seg.split()[:1] == ["true"]:
            return ""
        toks = seg.split()
        while toks and re.match(r"^\w+=", toks[0]):
            toks.pop(0)
        if not toks or toks[0].split("/")[-1] in _NOT_THE_TOOL:
            continue
        prog = toks[:1]
        if toks[0].split("/")[-1] in _RUNNERS:
            if toks[0].split("/")[-1] == "java" and len(toks) > 2 and toks[1] == "-jar":
                prog = toks[:3]
            elif len(toks) > 1:
                prog = toks[:2]
        head = " ".join(prog).split("|")[0].strip()
        if not head or head.startswith(("-", "<", ">")):
            return ""
        return (f"cd {cwd!r} && " if cwd else "") + f"{head} --help"
    return ""


def _output_value(value) -> str:
    """One $GITHUB_OUTPUT value. Newlines are the delimiter of that file, so a
    manifest value carrying one could inject further keys (own_ready=1, ...)."""
    return str(value if value is not None else "").replace("\r", " ").replace("\n", " ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tool")
    ap.add_argument("--work", default="work")
    ap.add_argument("--trial", action="store_true", help="read the descriptor generated in <work>/proposal")
    ap.add_argument("--proposal", default="",
                    help="path to recipe_proposal.json when the recipe was proposed in this run")
    ap.add_argument("--plan-out", default="",
                    help="also write the step outputs as JSON: the plan harness/engine runs")
    args = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.tool):
        raise ValueError("tool must be a single safe directory name")
    work = pathlib.Path(args.work)
    if args.trial:
        tool_dir = _paths.destination(work, "proposal")
        mode = "trial"
    else:
        tool_dir = _paths.confined(ROOT, f"tools/{args.tool}")
        mode = "publish"
    mf = _paths.confined(tool_dir, "manifest.yml")
    m = _manifest.load(str(mf))
    preflight(m, tool_dir, args.tool, work)
    inputs = m.get("inputs", {})
    input_type = inputs.get("type")

    # Recompute the review against the actual manifest. Cached may_say_runs
    # or an origin label is not authorization to build or run a procedure.
    import authorization
    proposal_data = {}
    prop_path = pathlib.Path(args.proposal) if args.proposal else None
    if prop_path and prop_path.is_file():
        try:
            proposal_data = json.loads(prop_path.read_text())
            if not isinstance(proposal_data, dict):
                proposal_data = {}
        except (ValueError, OSError):
            proposal_data = {}
    review = authorization.prepare_review(proposal_data, m, proposal_data.get("limitations") or [],
                                    (m.get("caveats") or {}).get("items") or [])
    procedure_ready = review["may_say_runs"]
    install_ready = review["install_ready"]
    import fidelity
    work.mkdir(parents=True, exist_ok=True)
    review_path = _paths.destination(work, "procedure_review.json")
    review_path.write_text(json.dumps(review, indent=2) + "\n")

    # Only a shared, registered dataset can enter the runtime mount. The
    # repository's own example reads its files at the original paths in the image.
    external_ready = False
    dataset_name = supported_loci = input_failure = ""
    if procedure_ready and input_type:
        try:
            ds = input_provenance.stage(ROOT, work, input_type)
            external_ready = True
            dataset_name = ds["name"]
            supported_loci = ds.get("supported_loci", "")
        except (ValueError, OSError, KeyError) as exc:
            input_failure = f"shared dataset staging could not be verified: {exc}"
            print(f"::error::{input_failure}", file=sys.stderr)
            install_ready = procedure_ready = False

    example_ready = install_ready and procedure_ready and bool(fidelity.example_citation(proposal_data, m))
    example = m.get("example") or {}

    values = {
        "ref": m["source"]["ref"],
        "procedure_ready": "1" if procedure_ready else "0",
        "install_ready": "1" if install_ready else "0",
        "installation_profile": (review.get("installation") or {}).get("profile", ""),
        # Whether the installed program starts at all: its --help, in the
        # built image, before anything is asked of it (the Starts check).
        # No inferred --help invocation: it is a command too. A future explicit
        # starts profile must establish it from upstream before executing it.
        "starts_cmd": "",
        "example_ready": "1" if example_ready else "0",
        "example_cmd": example_wrapper(example["cmd"], example["cwd"]) if example_ready else "",
        "cmd": m["run"]["cmd"],
        "dockerdir": tool_dir.relative_to(ROOT) if tool_dir.is_relative_to(ROOT) else tool_dir,
        "dockerfile": m["environment"]["dockerfile"],
        # Set when the repository ships its own Dockerfile: the Installs step then
        # clones the repository and builds that file with the clone as context,
        # and the run legs use the image's own entrypoint.
        "dockerfile_from_repo": (m["environment"].get("from_repo") or "") if m["environment"].get("source") == "repository" else "",
        "timeout": min(int(m["run"].get("timeout_minutes", 30)), 120),
        # The step's own ceiling, a little above the run's: harness/run_container.sh
        # enforces `timeout` and writes why into the log; this is only a backstop.
        "step_timeout": min(int(m["run"].get("timeout_minutes", 30)), 120) + 3,
        "manifest": mf,
        "repo": m["source"]["repo"],
        "mode": mode,
        "input_type": input_type or "",
        "own_ready": "0",
        "external_ready": "1" if external_ready else "0",
        "dataset_name": dataset_name,
        "input_failure": input_failure,
        "supported_loci": supported_loci,
    }
    # Every value is flattened to one line: this goes to $GITHUB_OUTPUT, where a
    # newline starts a new key. Only `cmd` used to be flattened.
    print("\n".join(f"{k}={_output_value(v)}" for k, v in values.items()))
    if args.plan_out:
        # The same values, the same flattening, as one document: what the
        # engine (harness/engine) runs instead of reading them back off
        # $GITHUB_OUTPUT one `steps.m.outputs.*` at a time.
        plan = {"tool": args.tool, **{k: _output_value(v) for k, v in values.items()}}
        out = pathlib.Path(args.plan_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
