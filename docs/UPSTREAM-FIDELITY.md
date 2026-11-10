# Upstream procedure fidelity — profile 1

Policy: never repair a tool, its configuration, environment or documented
procedure to obtain a successful verification. An evaluator limitation is not
evidence that the upstream tool fails. A green gate cannot substitute for
procedure evidence.

The versioned profile is `strhub-upstream-procedure/1`. This is a conservative
admission profile, **not** a general shell-equivalence prover or a claim that
every documented installation can be executed by STRhub.

## Complete commands and closed substitutions

The proposal retains complete source documents, with their repository paths.
Each selected command must occur at the cited line of a full 40-character
upstream commit. Repository and commit must match the actual manifest. Wiki
pages, truncated quote snippets, `origin: proposed`, submitter identity and a
cached `may_say_runs: true` do not establish a procedure.

Only explicit shell line continuations are accepted when establishing the
citation. Separate flag lines are never joined to manufacture a command, and
a `Usage:` prefix is not removed to turn a synopsis into an executable line.

The closed table currently permits standalone read-file arguments after
`--in`, `--input`, `--bam`, `--bams`, `--reads`, `--fastq`, `-i` or `-b`, and
reference FASTA arguments after `--ref`, `--reference`, `--fasta` or `--genome`.
The file extension or explicit placeholder must establish the read-file kind;
BAM, CRAM and FASTQ are not interchanged to fit an available sample. Read or
reference compression is not changed. Explicit output-path placeholders may use the fixed
output name `sample`; existing output values are kept.

Each substitution records its source token, replacement, role and basis in the
declared dataset. A path in an unrelated argument is not proof that the command
reads the sample. Unknown arguments and missing inputs are not filled in.

After these substitutions, **the entire command text must match**, including
executable, option values, positional arguments, repeated flags, order, quoting,
whitespace, redirections and shell operators. Apparently harmless differences
are not inferred equivalent. The report retains cited and executed command
text, their SHA-256 digests, source document digests and the substitution table.

The evaluator capture wrapper must match exactly and use `.` so it does not
move the command out of the upstream image's working directory. The wrapper and
GitHub output transport preserve quoted whitespace. A modified capture prefix
or suffix cannot hide a different procedure.

No optional arguments are trimmed or added, shell variables/defaults invented,
input lists reduced, configuration selected by kit/name, executables relocated
to PATH, output directories created for the tool, or region files converted by
a tool-name lookup. Inferred prerequisites remain discovery findings and are
not automatically chained. Shell expansion, unresolved placeholders and other
unsupported constructs block execution instead of being repaired.

## Installation

Finding Makefile, CMake, conda, pip, Cargo or another packaging family is
discovery evidence. It does not prove every effective dependency, compiler
option, interpreter selection and environment adjustment that STRhub might add.
The generic Dockerfile generator has therefore been removed. This also removes
its generic packages, HTTPS protocol rewrites, symlinks, library-path changes,
tolerated submodule failures and generated fallback installations.

The original installation profile admits an **upstream Dockerfile**, unchanged, with a cited literal
`docker build` command using repository-root context. The supported build
arguments are an optional literal Dockerfile and image tag; other arguments,
contexts or submodule setups are evaluator limits. The evaluator's local image
tag is an output identifier, not a build-argument override. Duplicate or invalid
tag/file options are not silently fixed.

After checkout, before Docker, the source documents and Dockerfile are checked
against their recorded SHA-256 digests. A mismatch or read failure stops the
build as an evaluator evidence failure. No parent-context inference, recursive
submodule update, ignored checkout failure or build-argument override is used.
The selected build is attempted once, with its original failure preserved.

Execution additionally requires an upstream exec-form
`ENTRYPOINT ["/bin/bash", "-lc"]` compatible with this evaluator. Other entrypoints,
heredocs, alternate escaping and multiple build stages are not reinterpreted.
STRhub does not replace the image entrypoint. A documented image outside this
profile can have a valid installation procedure; the evaluator cannot certify
its execution through this profile.

The separately versioned [literal source-installation profile](SOURCE-INSTALLATION.md)
now supports one complete cited Ubuntu 22.04 APT + make transcript. It has no
tool-specific rules and does not relax this document's command policy. CI and
the local runner re-derive its container definition from checked source bytes;
no submitted descriptor or earlier successful experiment can authorize it.
Other source installations, release binaries and published packages/images
remain unsupported until a separate profile establishes every effective step.
An unsupported proposal contains a non-runnable descriptor, not installation
instructions to try. It cannot authorize a Docker build.

## Execution and reporting boundaries

`prepare.py` recomputes the review against the actual validated manifest and
writes `work/procedure_review.json`, bound to its manifest digest. It never
trusts a cached ready flag. Missing or malformed proposal evidence disables
installation and all execution legs. Unsupported examples cannot bypass this
control. No automatic `--help` invocation is proposed or executed.

CI requires `install_ready == 1`. The local runner uses the same preparation
and source checks; it builds the actual upstream checkout, never the proposed
descriptor. Both producers pass the recomputed review to the report. A missing,
rejected or mismatched review passed to reporting yields `undetermined`, even
if the supplied gates are green. Pre-build evidence failures are attributed to
the evaluator, not to the tool.

This closes the production execution paths' use of generated installations and
loose command comparison. **Step 5 remains**: unify durable evidence retrieval
for saved/submitted recipes and every reporting/publication entry point, remove
remaining origin/identity shortcuts and audit standalone legacy report calls.
Saved recipes currently lacking proof remain blocked; they are not silently
grandfathered. Existing published attestations are unchanged pending the planned
catalogue transition. This profile does not validate biological correctness,
all input compatibility, or the complete execution/evidence supply chain.

## Read-only review of the five current recipes

All five currently declare generated environments. They cannot be executed or
certified by profile 1 without a separately established installation profile.
Their source files, recipes, inputs and historical results were not patched.

| Recipe | Pinned upstream evidence | Observation |
| --- | --- | --- |
| ExpansionHunter | [installation](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/docs/02_Installation.md), [usage](https://github.com/Illumina/ExpansionHunter/blob/9f5db1d4ab72016b2d93330b9792842d71582622/docs/03_Usage.md) | Binary download is documented. That does not establish the complete generated runtime package bundle, links or catalog replacement. |
| mahi-mahi | [README](https://github.com/nanoporetech/mahi-mahi/blob/861ea09ab44e88424c45b04d8018f3948a8fefbb/README.md) | Repository pip installation and a concrete run example are documented. A supported Python range does not prove all the extra packages and protocol rewrites in the generated Dockerfile. Literal example values are not tuned after a failure. |
| STRaitRazor | [README](https://github.com/Ahhgust/STRaitRazor/blob/b618e9345ab40f348b504083ae8de2b39abb60fa/README.md) | The command contains config/input placeholders. Choosing a kit-matching file or the first config is not itself a cited binding. |
| STRspy | [README](https://github.com/unique379r/strspy/blob/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/README.md) | Setup/configuration includes script and config-generation steps. Substituting a micromamba environment file does not establish equivalence to that whole procedure; config files are not rewritten to make a staged BAM reachable. |
| TRGT | [README](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/README.md), [tutorial](https://github.com/PacificBiosciences/trgt/blob/b21c6217eeaef9a080205932fe29f730dc00e31f/docs/tutorial.md) | Binary download is documented. The tutorial invokes `./trgt`; changing that executable path, creating an output directory or replacing repeat definitions needs proof and is not done automatically. |

These are evidence gaps/profile limits, not new tool executions or findings that
the tools cannot run. A lower acceptance count is an intended consequence of
removing guesses, not a reason to repair the recipes.

## Regression checks

Tests retain the changed-threshold audit example and other adverse commands
unchanged. They cover executable/value/order/quoting/operator changes, forged
ready flags, missing/stale citations, input-kind swaps, entrypoint incompatibility
and source-byte changes. The real CI install shell is exercised with inert
Git/Docker replacements: an evidence mismatch makes zero Docker calls; an
authorized build failure makes one call and no retry. No STR tool is launched.

The pinned benchmark snapshots and expected upstream facts remain unchanged.
Discovery coverage floors remain. Old targets rewarding placeholder filling and
more supposedly runnable recipes no longer authorize execution; the benchmark
now exposes procedure review and attemptability separately. Development demo
scenarios lacking source evidence also remain blocked despite synthetic green
gates; proof was not invented to restore their former labels.
