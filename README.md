# STRhub Verified

Independent, automated, reproducible-execution attestation for forensic STR
software. It answers the one question a reviewer most needs and can least
afford to check by hand: **does this tool actually install and run end-to-end,
producing output in the documented format, in a stated environment?**

It is **not** a concordance/accuracy benchmark, **not** a casework validation,
and **not** a ranking. Every attestation carries this scope statement:

> Executed end-to-end in the stated environment with output in the expected
> format. Concerns reproducible execution only; no claim of accuracy, casework
> fitness, or regulatory validation.

## Why this needs almost no infrastructure
The "server" is **GitHub Actions**. Standard runners are free and unlimited on
public repositories, so each verification is an ephemeral container job at ~zero
cost. There is no always-on server and no database — the git repo is the
registry, the CI log is the evidence, and `reports/*.json` + badges are static.
The only escalation is a tool that needs a GPU to run, which would use a
self-hosted runner (e.g. Jairu, or a small cloud GPU instance).

## The gates
| Gate | Question | Where it runs |
|------|----------|---------------|
| Available | Is the source public at a pinned ref? | `git ls-remote` |
| Installs | Does the declared environment build? | `docker build` |
| Runs | Does it execute to completion (exit 0)? | `docker run` on the fixture |
| Expected IO | Are the outputs present, non-empty, and valid format? | `harness/check_io.py` |
| *Reproduces own example* (optional) | Does it match the tool's OWN published example output? | golden-file compare |

The badge reflects the furthest contiguous gate cleared, and is honest about
partial results (a tool can be "Installs" but fail "Runs").

## Layout
```
.github/workflows/verify.yml   the engine (build -> run -> check -> report)
schema/manifest.schema.json    the manifest contract
harness/                       check_io.py, report.py, _manifest.py  (stdlib + pyyaml)
tools/<tool>/manifest.yml      author-declared: repo, ref, run cmd, expected outputs
tools/<tool>/Dockerfile        the pinned environment
fixtures/                      tiny consent-clean test inputs
reports/                       generated attestations + shields.io badges
```

## Add a tool (self-service)
1. Create `tools/<your-tool>/` with a `manifest.yml` (see `schema/` and the
   STRait Razor example) and a `Dockerfile`.
2. Pin `source.ref` to an immutable commit.
3. Open a PR. CI runs the gates and posts the attestation as an artifact.
4. STRhub independently re-runs the same harness to attest — you never hand
   over anything beyond your public repo at the pinned ref.

## Run locally
```bash
docker build --build-arg STRAITRAZOR_REF=<sha> -f tools/strait-razor/Dockerfile -t toolimg tools/strait-razor
mkdir -p work/out
docker run --rm -v "$PWD/fixtures/example:/data/in:ro" -v "$PWD/work/out:/data/out" toolimg \
  "str8rzr -c /opt/strait-razor/PowerSeqv2.31.config /data/in/sample.fastq > /data/out/sample.allsequences.txt"
python harness/check_io.py tools/strait-razor/manifest.yml work/out
python harness/report.py --manifest tools/strait-razor/manifest.yml --installs pass --runs pass
```

## Status
v0 scaffold. STRait Razor is the worked example; lines marked `# VERIFY` must be
confirmed against the tool's manual before the first real attestation.
License: AGPL-3.0 (to match STRhub).
