# Literal source installation — profile 1

`strhub-source-install/1` is a generic, closed installation profile. It does
not have a repository registry, tool-name rules, per-tool package lists,
previous-success lookups, or manual-trial exceptions. A source build being
possible is not evidence that this evaluator can automate it faithfully.

The existing `strhub-upstream-procedure/1` command policy remains unchanged.
Installation eligibility and execution eligibility are separate decisions.
An admitted installation cannot authorize a changed command or a run on a
different input kind, list cardinality, configuration or region layout.

## Supported transcript

The first source profile deliberately supports one narrow structure:

- A full immutable source commit and the same repository/commit in the manifest.
- One root `Makefile` or `makefile`, with its complete source bytes available.
- One complete installation section in a repository document. Its heading
  explicitly names Ubuntu 22.04 and installation/build/compilation. Supported
  headings include `Installation (Ubuntu 22.04)`, `Install on Ubuntu 22.04`
  and `Build for Ubuntu 22.04` at Markdown heading levels 1 through 6.
- That section contains only one `sh`, `bash` or `shell` fenced block, with
  three complete commands in this order: `apt`/`apt-get update`,
  `apt`/`apt-get install` with an already documented `-y` or `--yes`, and `make`.
- The package list is literal and includes make. Package versions, architecture
  qualifiers and an explicitly written `--no-install-recommends` are retained.

This describes the parser's present limits. **It is not a request to edit an
upstream README or script to make a tool eligible.** Other layouts remain
evaluator limitations until a separate generic rule is established and tested.

The evaluator never adds `apt update`, `-y`, packages, compiler flags, a shell
pipeline, `sudo`, `PATH`, library paths or a second build attempt. Interactive
APT instructions are unsupported by this noninteractive profile; they are
not classified as broken instructions. Force, unauthenticated and repair
options are rejected. Dependencies selected transitively by APT are normal
resolver behavior, not extra packages chosen by STRhub.

Split blocks, prose assembly, version ranges, alternate operating systems,
multiple candidate sections, shell operators/expansions, subdirectory builds,
submodules, `.dockerignore`, `GNUmakefile`, missing file contents and ambiguous
Makefile names remain unsupported. No later outcome changes that decision.

## Fixed evaluator container

For an admitted transcript, the same envelope is used for every repository:

1. Select the Ubuntu 22.04 operating-system condition explicitly named by the
   cited section, represented by `ubuntu:22.04`.
2. Copy the pinned checkout to `/opt/tool` and use that directory.
3. Run exactly the three cited argv arrays in their documented order.
4. Provide the evaluator's shell transport for the independently reviewed
   command and the existing output-capture wrapper.

The Dockerfile is supplied by the evaluator and is labelled `documented` in
the manifest, not `repository`. It is a fixed execution envelope around an
upstream transcript, not a Dockerfile supplied by the tool's author. There is
no upstream image entrypoint to replace. No executable is moved or added to
PATH. The source program is still invoked by the command whose full citation
and substitutions were independently checked.

The source-profile record includes the complete commands, argv arrays, line
numbers, source commit, document digest, Makefile digest, base condition and
container-definition digest. The base image tag and APT resolver are not
frozen dependencies: this profile establishes procedure fidelity, not
bit-for-bit reproducibility or the complete supply chain.

## Before Docker

Preparation recomputes the installation and command reviews against the actual
manifest. `source: documented`, a cached ready flag or an earlier successful
trial cannot authorize anything by themselves. Historical `generated` recipes
are not automatically admitted.

CI and the local runner obtain the pinned source once, verify its identity,
check document and Makefile bytes, and re-derive the entire source plan from
the checked-out material. Any changed package, command, carrier or source
evidence stops before Docker. The carrier is materialised exclusively and
cannot overwrite an earlier file. Both paths use this same implementation.

The selected build is invoked once. Failure is retained with no fallback
Dockerfile, package additions, flags, environment changes or retry. Runtime
legs remain gated by the separate complete-command review. No extra help or
version command is inferred.

## Evidence export

The report identifies the evaluator-supplied container. Trial artifacts retain
the original submitted descriptor separately and identify only the verified
carrier selected for the source build. A submitted Dockerfile is not used to
build this profile. Missing or mismatched installation evidence prevents
attaching a claimed source-installation recipe. An unbuilt carrier is not
exported as though it had been selected for a build.

This does not finish the separate audit of all historical saved-recipe and
publication entry points. Existing unsupported recipes remain blocked and no
old attestation is upgraded by this change.

## HipSTR remains an evaluator limitation

The manual hg38 experiment is preserved separately. It is not an eligibility
record. A read-only detection/classification of the same pinned HipSTR clone
after this change still yields `install_ready: false`, `may_say_runs: false`
and `install_profile_unsupported`; no install or STR command was launched.

Its README contains an Ubuntu version range and separates prerequisites from
the build instructions. Its APT command does not include the noninteractive
option or index-update command required by the current transcript profile.
These are evaluator limits, not instructions for changing the README.

The manual genotyping commands also combined the invocation with separately
documented options. The existing automatic complete-command, input-list and
substitution rules are not relaxed to reproduce those manual results.
Therefore this change does **not** make the successful manual HipSTR trial
automatically reproducible through the web form. That remains a separate
evidence/design problem, not a reason for a HipSTR-specific recipe.

## Validation

The harness suite has 570 passing tests after this change, plus all 15 shared
BED cases and the tool-picker self-test. New tests cover repository/tool-name
independence, exact transcripts, missing steps, added repair/force options,
source and carrier tampering, retained command-value checks, stale/manual
success claims, descriptor/export mismatches and both installation producers.
The actual CI shell is exercised with inert Git/Docker replacements: evidence
mismatch makes zero build calls; a selected failed build makes one, with no
retry. No STR software is run by these tests.
