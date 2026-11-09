# STRhub Verified

Independent, automated attestations of documented execution for Short Tandem Repeat (STR) software (forensic and medical/genomics).

We verify whether an STR tool installs and runs end-to-end strictly following the instructions in its public repository, in a clean and reproducible environment. Our purpose is to help authors and users identify documentation or environment friction to collaborate on fixes. It does not evaluate genotype concordance (not a biological benchmark) nor constitute evidence for forensic casework fitness.

Every attestation carries this scope statement:

> Executed end-to-end in the stated environment with output in the expected format. Concerns reproducible execution only; no claim of accuracy, casework fitness, or regulatory validation.

Each result is a fixed, dated attestation verified on the tool's public repository at an immutable commit. It does not constitute continuous monitoring nor a guarantee for subsequent versions or modified environments. STRhub stores no tool source code.

## Verification Gates

The evaluation is conducted in an isolated container without network access and with strict resource ceilings:

| Gate | Question | Verification method |
|------|----------|---------------------|
| Available | Is the source public at a pinned ref? | `git ls-remote` / commit check |
| Installs | Does the environment build from declared instructions? | `docker build` from declared procedure or repo Dockerfile |
| Starts | Does the installed binary start and respond to `--help`? | Execution in clean container |
| Runs | Does it execute end-to-end without crashing (exit code 0)? | `docker run` on reference or test dataset |
| Expected IO | Does it produce non-empty files in declared formats? | Format validation (`harness/check_io.py`) |
| Plausible Output | Does output contain structured, genotype-bearing records? | Plausibility checks (`harness/check_content.py`) |

The resulting badge reflects the furthest contiguous gate cleared, providing honest and constructive transparency into where execution stopped.

## Execution Modes

### No adaptive retries

Each run leg uses the procedure, environment and dataset selected before it
starts. A failed install or run is recorded with its original exit status,
outputs and logs. It never triggers recipe repair, a fallback environment or
a retry on another dataset. Medical datasets can still be selected before
execution when appropriate to the documented procedure.

The recipe-repair agent is retired: its workflow has been removed and
`harness/assist.py` refuses legacy invocations. Historical curated reports
remain available as historical evidence, not as a reason to rerun repairs.
Diagnostics may recommend an upstream documentation change; they do not apply
or execute it. See [the policy and regression checks](docs/NO-ADAPTIVE-RETRIES.md).

### Verification entry points

Manifest validation is mandatory before input staging. Local paths and symlink
targets must stay in their declared roots; unsafe paths stop preparation.
See [Input boundary](docs/INPUT-BOUNDARY.md) for the policy and regression checks.

VCF outputs must pass the [versioned structural checks](docs/VCF-STRUCTURE.md).
Format validity, data-row counts and genotype-call presence are recorded
separately. These checks do not establish biological correctness or full VCF
conformance, and never repair a tool's output.

1. **1-Click URL Trial**: Evaluates a tool directly from its public repository URL. The harness inspects the README, repository tree, and dependency files to propose an install procedure and command, evaluating it immediately in CI.
2. **Curated Catalogue Verification**: Evaluates curated configurations under `tools/<slug>/` against open reference datasets (Illumina STR FASTQ, ONT BAM, PacBio HiFi BAM).

## Repository Layout

```
.github/workflows/verify.yml   The verification engine workflow
schema/manifest.schema.json    Manifest specification contract
datasets/                      Open reference datasets and panel BED definitions
harness/                       Recipe detection, execution runners, and report generators
tools/<tool>/                  Curated tool recipes (manifest.yml, Dockerfile, assets)
```

## Reproducible Execution Architecture

- **Engine**: GitHub Actions with standard ephemeral Ubuntu runners.
- **Container Hardening**: Evaluated inside Docker with `--network none`, `--cap-drop ALL`, `--security-opt no-new-privileges`, and strict CPU, process, and memory caps.
- **Artifacts**: Every verification generates an immutable attestation package comprising a signed JSON report, an HTML report, and a formal PDF certificate with cryptographic digests.

## License

AGPL-3.0 (matching STRhub).
