# Mandatory procedure evidence

No result, origin label, submitter identity or saved success authorizes a
procedure. Installation and execution decisions must be recomputed against
the effective manifest and preserved source evidence. A missing or invalid
review is an evaluator limitation, never a success or a failure of the tool.

This change closes permissive verdict/report/publication entry points. It
does not extend the supported installation or command profiles, create a
tool-specific recipe, or make the manual HipSTR experiment automatically
eligible.

## Evidence capsule

`strhub-procedure-evidence/1` preserves:

- The complete effective manifest, including source identity, environment,
  command, output declarations and declared input contract.
- The source proposal, including complete documents and installation-file
  contents used by the existing fidelity reviewers.
- The pre-execution limitations and caveats passed to the reviewer.
- Digests of the manifest and evidence, and the complete derived review.

The proposal's cached `procedure` field is excluded. Preparation and proposal
generation use the same `authorization.prepare_review` function. The evidence
is copied so later mutation of a proposal cannot alter an existing capsule.

`authorization.validate` requires the actual effective manifest, validates its
schema and paths, compares it with the preserved contract, checks the digests,
and recomputes the entire procedure classification. The complete saved review
must match that recomputation. Updating a digest or a ready flag cannot
authorize a package, command or input change that the source evidence does
not establish.

An internally consistent **rejected** review remains useful evidence. Valid
evidence does not mean execution is eligible: the existing installation and
complete-command profiles still make that decision. Historical unbound
reviews are not automatically upgraded.

## Build producers

The CI installation step supplies the actual manifest to the fidelity CLI.
The local installer rejects an invalid review before Git or Docker. Both
continue to verify the real pinned checkout and its cited source bytes before
building. The source carrier is still independently re-derived from those
checked bytes. No fallback or retry is added.

Runtime legs remain gated by the preparation outputs derived from the same
effective manifest. This change does not alter their command, sample selection,
filters, source code or attempt count.

## Verdict and report

Both the public verdict function and its internal decision function reject a
missing, malformed, legacy, mismatched or modified review. They require the
effective manifest; a complete-looking saved review by itself is insufficient.
Green observations cannot override that rejection. Nor can red observations
turn missing evidence into a finding that the tool fails.

The verdict uses the preserved proposal/limitations and actual manifest's
compatibility declarations after validation. Optional legacy arguments cannot
replace those facts. Contradictory or malformed execution-gate observations
are attributed to the evaluator. A fallback flag does not establish what
happened to the original procedure.

`report.py` always requires its dedicated pre-execution review input for a
documented execution finding. It no longer falls back to `proposal.procedure`,
including when that cached decision says it is ready. Invalid supplied
reviews are retained separately for inspection; the active review is a
rejection. The report includes `procedure_validation` and `input_contract`.

The report's effective source ref, tool, instrument, environment, command,
working directory and input contract must match its manifest. A different
`--ref` cannot be reported as though the old review covered it. The original
observations and mismatched supplied values are retained; they are not changed
to obtain a valid result.

For newly generated reports whose procedure finding is not established, the
certificate/PDF closing statements are neutral. Green observations cannot
become claims of end-to-end execution or reproducibility, and red observations
cannot become a claim that the tool fails. Stored historical certificate
blocks retain their original wording.

## Publication and aliases

Publication checks the evidence again, binds the report fields to its
preserved manifest, and recomputes the verdict from its observations. A final
`runs` label is not permission to publish. The private-trial setting remains
effective even when a report is valid.

The direct layout writer and alias selector use the same validated-finding
gate. Missing proof, evaluator-attributed limitations and altered reports are
rejected before a new run's files are copied. A historical file's presence,
its date or its proposed/maintainer label cannot grant it a new authoritative
alias. Pinned historical files remain readable and are not rewritten with
invented proof.

No deployment, migration, withdrawal or catalogue rewrite was performed by
this code change. When these writers are explicitly run later, old records
without proof will not be eligible for fresh promotion. Catalogue transition
must be reviewed as a separate external-state operation.

## Boundaries and remaining work

This capsule is a consistency mechanism, **not a cryptographic execution
signature**. Authenticity still depends on the trusted engine/workflow and
its source-check-before-build boundary. An actor with arbitrary write access
to that trusted environment is outside this mechanism's protection.

`input_contract` binds declared dataset/configuration selections; this change
does not add byte-level receipts for staged BAMs or downloaded FASTA files.
It does not finish the full execution/evidence supply chain. Saved recipes
without retrievable source proof remain blocked rather than being grandfathered.

The advanced web autoconfiguration still needs its separate removal of
rewrite/generation behavior. The general documentation reader remains narrow;
unsupported instructions stay blocked. No upstream README or tool script
should be edited to satisfy its current grammar. Web previews and production
rollout remain subsequent work.

## Validation

The complete harness suite passes 626 tests, plus all 15 shared BED cases and
the picker self-test. The new adverse cases cover missing/legacy reviews,
saved booleans, rehashed but changed evidence, effective-manifest changes,
submitter labels, source/carrier checks, standalone report invocation,
publication through direct writers, inconsistent labels and historical alias
promotion. Positive cases retain legitimate report/publication behavior and
private trials stay private.

Tests use explicitly synthetic cited contracts and inert build substitutes.
They do not add evidence to pinned upstream fixtures or change their outputs.
No STR program is launched. Generated report tests write only to temporary
directories; no synthetic certificate is left in the repository report area.
