# No adaptive retries

Verified must record what happens to the procedure selected before execution.
A failure is evidence to preserve, not a request to make the tool succeed.

## Runtime policy

- Installation builds the selected primary environment once. A failure never
  triggers a second Dockerfile, image or package installation route.
- Each declared data leg runs once with its selected input. A nonzero exit,
  timeout, memory limit or missing/invalid output never selects another dataset.
- The original command, manifest, output, log and exit status remain the
  evidence for that attempt. A later successful attempt cannot replace them.
- Medical datasets remain selectable before execution. This policy removes
  the forensic-to-medical retry after observing a result; it does not remove
  medical datasets or the selection of compatible inputs before execution.
- Diagnostics can explain the failure and suggest what the author should
  document. They cannot apply changes or dispatch modified recipes.

## Retired repair agent

`.github/workflows/assist.yml` is removed. `harness/assist.py` is a compatibility
entry point that exits 2 with an explanation, regardless of legacy arguments
or available credentials. It contains no model client, repair loop, trial
dispatcher or PR writer. Its former implementation remains in Git history.
Historical revisions are for inspection, not for launching repairs.

`harness/assist_report.py` remains a read-only renderer for existing historical
reports and labels them as such. Existing reports, fixtures and upstream source
code are not modified. `environment.fallback` (a second Dockerfile older recipes
declared) is no longer part of the manifest schema: nothing reads it, nothing
builds it, and a manifest that declares it fails validation.

## Regression checks

The normal harness suite covers the retired CLI, direct invocation, historical
report rendering, selected-dataset staging and refusal of the old
`--promote-medical` mutation command. It also executes the actual workflow shell
with fake runners to check that install failure, run failure, timeout, memory
failure and exit-zero with invalid output do not trigger a second attempt or
replace evidence. These tests execute no STR software and require no Docker,
model credentials or network.

Run the repository's existing checks:

```bash
python -m pytest harness/tests -q
python harness/test_validate_bed.py
python3 harness/pick_tools.py --selftest
```

This change retires adaptive execution. The separate audit work on procedure
fidelity, provenance requirements, format validation, immutable publications
and the default CI canary is not completed by this policy change.
