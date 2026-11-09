# Publication evidence review: GangSTR and STRsearch

This is an editorial review of publications at gh-pages commit
`b2815e3ac0eb3bf0da3a5a47304f1a155d2c7a94`, not a new verification run.
The review plan and exact original report digests are in
[`evidence-reviews/2026-11-09.json`](evidence-reviews/2026-11-09.json).

## Findings

| Publication | Cited CI | Finding |
| --- | --- | --- |
| GangSTR at `6ea9b2b8daca51dcab1f0e46210622b94b52ff17` | [42253585030](https://github.com/Tfronta/strhub-verified/actions/runs/42253585030) | The linked run tested a curated recipe, while the publication describes a documented build failure. |
| STRsearch at `c70179b3b175adc82a7314409af06900b3861d61` | [42254219171](https://github.com/Tfronta/strhub-verified/actions/runs/42254219171) | The linked curated run installed and ran, while the publication describes a usearch download failure. |

Seven original artifact sets were recovered through `gh run download`, without
dispatching a workflow or executing a recipe:

| Tool | Run | What the original artifact records |
| --- | --- | --- |
| GangSTR | [41308001752](https://github.com/Tfronta/strhub-verified/actions/runs/41308001752) | Earlier successful run at `6ea9b2b`; preserved as historical evidence, not re-certified. |
| GangSTR | [42066986140](https://github.com/Tfronta/strhub-verified/actions/runs/42066986140) | Build failure at the same `6ea9b2b` commit; the command and full log differ from the publication. This is real failure evidence, but cannot silently become its originating artifact. |
| GangSTR | [42216592702](https://github.com/Tfronta/strhub-verified/actions/runs/42216592702), [42488855247](https://github.com/Tfronta/strhub-verified/actions/runs/42488855247) | Build failures at the different commit `e368b9f4dbf7ab7585036a5ff2e68480d0623c80`. |
| STRsearch | [41308009228](https://github.com/Tfronta/strhub-verified/actions/runs/41308009228) | Earlier successful run at `c70179b`; not the claimed download failure. |
| STRsearch | [42067018462](https://github.com/Tfronta/strhub-verified/actions/runs/42067018462), [42483706971](https://github.com/Tfronta/strhub-verified/actions/runs/42483706971) | Successful installation using `anjing123/strsearch:latest`; source-commit execution classified as undetermined. |

The historical recipes include evaluator-generated decisions that require the
later fidelity audit. Recovery of an artifact does not certify its procedure
under the strict policy. No exact originating artifact for either published
report and its extract was established in the reviewed evidence. This does not
establish that the reported build errors were fabricated.

## Editorial correction

`harness/publication_review.py` checks the inspected report's SHA-256 before any
write. It archives the original root and historical files, records file hashes,
adds a retirement notice beside the historical result, and creates a separate
root record marked `record_type: editorial_review`. That record says **Evidence
insufficient** and contains no execution gates, command, environment or CI run.
The old report JSON, commands and logs are not edited. The old catalogue is also
preserved. Recovered artifact sets remain separate, identified by their real
run IDs, tool commits and file hashes.

The prepared publication contains 43 archived original files, seven recovered
artifact sets, two editorial HTML/Markdown/JSON notices and two one-page PDF
notices. All archived original files were compared byte-for-byte to their Git
blobs at the publication commit. Recovered files were checked against the local
downloads' SHA-256 values. These hashes are not cryptographic signatures or a
claim that the original CI recipe was faithful.

The companion `strhub-web` change renders these records separately, without
execution gates, a verification date, a certificate claim or repair suggestions.
Deploy that reader support **before** merging the gh-pages correction. Older
readers assume every record is an execution report and cannot safely render a
notice without execution fields.

## Future reports

Reports now preserve `run.effective_cmd` and `run.step_outcome`. HTML, Markdown,
PDF and the web say **Planned command** when execution is not established, and
**Command submitted to runner** for success/failure step outcomes. A failed step
alone does not prove that the program started. Legacy reports without an outcome
are treated as unconfirmed. PDF generation prefers the recorded command over a
later-edited manifest.

## Review and integration

1. Review/integrate step 1, then the engine changes in this branch.
2. Review/deploy the companion web change.
3. Review/integrate the gh-pages editorial correction. This is a publication
   correction, not a new execution. The public site remains unchanged until then.

The default CI canary remains the preexisting missing
`tools/strait-razor-powerseq/manifest.yml`; it belongs to step 7. No STR execution
or retry was used to resolve it. Strict recipe fidelity, mandatory evidence in
every execution path, and global immutable publication remain later steps.
