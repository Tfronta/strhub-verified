# Input boundary: validate before staging

The manifest is validated before any fixture is copied or downloaded, any
trial recipe is written or replaced, or any build is started. Validation
requires `jsonschema`; absence is an evaluator error and cannot silently
disable the contract. The existing workflow already installs that dependency.

## Allowed roots

- Committed local fixture and regions paths are relative to the engine checkout.
- `tools/<slug>/...` paths for the selected tool resolve against that recipe's
  directory, including a dispatched recipe under an external `--work` location.
  They are not translated into author-supplied absolute paths.
- Dockerfiles and assets are confined to the selected recipe directory. The
  actual upstream Dockerfile is checked again after checkout, before it is read
  or passed to Docker.
- Dataset files, indexes, library regions and supported-loci paths are confined
  to the engine checkout. Canonical input and reference-genome names must be
  filenames, not paths into another directory.
- Runner-owned staging locations cannot contain preexisting symlinks. Input
  symlinks are accepted only when their resolved targets remain within the
  appropriate root, outside `.git` metadata.

Paths reject absolute POSIX paths, home expansion, drive-prefixed paths,
backslashes, control characters, parent traversal and `.git` components. The
tool selector and report slug must be safe single directory/file names.
Directory fixtures are checked before copying any member, including BAM index
sidecars. All selected sources and existing staging destinations are checked
together before staging begins.

Remote pointers name a public GitHub repository root, a ref and a relative
file. URL components are quoted so a literal `?` or `#` in a filename cannot
change the request. The web validates these fields before its availability
request or dispatch; filesystem and symlink checks remain the engine's job.
The web and engine carry the same 21 path cases in their regression suites.

## What a refusal means

A schema or confinement error stops preparation. It does not repair the path,
modify the recipe or rerun the tool. Valid but unavailable fixtures/datasets
retain the existing unavailable/N/A behavior. A missing validator is a fault
of the evaluator, never evidence that an upstream tool failed to install.

This validates the files that the evaluator itself reads and copies. It is not
a sandbox for arbitrary shell commands or Dockerfile contents, and does not
prove recipe fidelity. Those controls remain separate. The validation assumes
that the workspace is not concurrently modified during staging.

## Validation

The tests use inert files and simulated executors. They cover invalid schema,
missing validator, traversal, external symlinks in fixtures/regions/assets/
Dockerfiles, BAM sidecars, stale staging links, unsafe tool/report names,
trial validation before replacing an existing recipe, and safe input copying.
The example checker also confines discovered files and the golden comparison
input, so an output symlink cannot make it read a runner file or count it as
output created by the program.
The install-shell test supplies fake git/docker executables and checks that
an external Dockerfile symlink never reaches the build command. It executes
no STR program and performs no network call.

Validation for this change: 353 engine tests, 623 web tests, TypeScript, 15 BED
cases and the picker self-test passed. The five current committed manifests
were validated without running their recipes.

```bash
python3 -m pytest harness/tests -q
python3 harness/test_validate_bed.py
python3 harness/pick_tools.py --selftest
```

VCF structural validation is step 3B and is not changed here. The missing
default CI canary remains the preexisting step 7 issue. No tool recipe,
upstream source, historical report or dataset is changed by this step.
