# The contract between strhub-verified and strhub-web

This file is the whole of what the web (`Tfronta/strhub-web`) depends on from
this engine. Nothing else the engine writes is read by the web, and nothing
the web reads is outside this file. **A change to any item below changes
this file in the same commit**, and lands on the web in the same step: a
fresh real artifact goes to `lib/verified/__fixtures__/` there, and its
test (`lib/verified/trial-artifact.test.ts`) says what the web stopped
reading. Fields the engine stops writing are removed from the web's
`types/verified.ts` in that same change, so nothing dead stays readable
by mistake.

What the feature is, in the owner's words: an external auditor. It reads
the public repository, checks whether it holds everything needed to install
and run the tool exactly as the author documents, tries to run it that way,
and if anything is missing or fails it does not force it: "could not run"
is a result. The report shows the terminal with the exact error. "Could
not run" may mean "badly documented"; then the author is asked, through a
GitHub issue draft, to document better and try again.

## 1. Dispatch (web → engine)

One `workflow_dispatch` of `.github/workflows/verify.yml` on `main`
(`VERIFIED_ENGINE_BRANCH` on the web, default `main`), sent by the web's
GitHub App installation (`lib/verified/github.ts::dispatchTrial`). Inputs:

| input | value |
|---|---|
| `tool` | the run's own name, e.g. `trial-hipstr-v0.7`; also the artifact's suffix |
| `repo` | the public repository URL the user typed |
| `ref` | the commit, tag or branch to pin; empty means the default branch |
| `ref_label` | optional, the ref as the user typed it, for the page |
| `dispatch_id` | `tr_<…>`, the web's correlation id |
| `mode` | `trial` (the web never dispatches a publication) |
| `publish` | `false` |

The run is named `Trial <tool> [<dispatch_id>]` (`run-name` in the
workflow). GitHub returns no run id for a dispatch, so the web finds the
run by that name (`findRunByDispatchId`). Do not change the shape of the
run name.

## 2. The trial artifact (engine → web)

Uploaded by the workflow's `Upload attestation` step, named
`trial-<tool>`, kept 30 days. Its layout since c485b42:

```
reports/<slug>.json            the report (§3)
reports/<slug>.recipe.json     the manifest and Dockerfile the run used
reports/<slug>.summary.md      the report in prose
reports/<slug>.badge.json      shields.io badge (not read by the web)
reports/<slug>.html            static page of the report
reports/<slug>.pdf             certificate
reports/<slug>.log-<leg>.txt       output of a leg that ran (build, starts, example, own, external)
reports/<slug>.terminal-<leg>.txt  the same with the exact argv, as record_terminal.sh wrote it
run_record.json                every stage's command, exit status and log path (not read by the web yet)
```

`<slug>` is the report's slug (`report.slug` in the manifest, e.g.
`hipstr`), which is not the run's `tool` name. The web finds the report
first (`reports/<slug>.json`, else `<slug>.json`, else any JSON that is not
`.recipe.json`, `.badge.json` or `run_record.json`) and keys every other
file off the stem it was found under. Before c485b42 the same files sat at
the artifact's root; the web still reads that layout for artifacts within
their 30 days.

A leg that did not run has no log and no terminal. When the review refuses
to run (no proven install procedure, a command that cannot be established
at the pinned commit), the only text is `verdict.reason`.

## 3. The report, `schema: strhub-verified/1`

Written by `harness/report.py`. The web's type is
`types/verified.ts::VerifiedReport`. Fields the web reads, by what they
are for:

**Identity and source**
- `schema`, `generated`, `ci_run`, `mode` (`trial` | `publish`)
- `tool`: `{ name, version?, contact? }`
- `source`: `{ repo, ref, ref_resolved?, committed? }`
- `submission`: `{ by }`
- `instrument`: `documented` | `curated` (a curated run never carries the badge)
- `record_type`: `editorial_review` marks a hand-written review, not a run

**What happened**
- `gates`: `{ available, installs, runs, io, content }`, booleans
- `level`: the furthest gate passed (`none` … `content`)
- `verdict`: `{ code, title, reason, basis?, readme_gaps?, blockers? }`;
  `code` ∈ `runs` | `fails` | `undetermined` | `out_of_scope`;
  `blockers[]` = `{ code, what, ask_owner: { title, body } }` — the issue
  the web drafts for the author. **Never again:** `self_fix`,
  `self_fix_text` (removed in ca612d9).
- `step1`: the documented run as the headline: `{ code, headline, body, missing, missing_text, guide }`
- `environment`: `{ dockerfile?, os?, source? }`. **Never again:**
  `environment.fallback`, `fallback_used` (removed in df57a78).
- `install_detail`: `{ passed?, diagnostics?, faults? }` — why the build failed
- `io_detail`, `content_detail`, `datasets`, `run`: what the run read and wrote
- `diagnostics`: per leg, the errors the tool's own log reported
- `logs`, `terminals`: `{ <leg>: <file name> }`, the files of §2 / §4
- `evidence[]`: `{ claim, kind, path, line?, text?, url }` — where each
  claim was read in the repository, openable at the pinned ref. `claim`
  includes `fallback_environment` (the published image the README names;
  evidence, not a plan B).
- `upstream`, `procedure_review`, `procedure_validation`, `readme_check`,
  `author_known_issues`, `needed_beyond_repo`, `repo_test_data`,
  `caveats`, `scope`, `recipe`, `certificate`, `manual_verification`

## 4. Publication (engine → gh-pages → web)

`harness/publish_layout.py` lands a published run at
`<slug>/<sha>/<slug>.{json,html,pdf,badge.json,log-*.txt,terminal-*.txt}`
on `gh-pages`, with the root `<slug>.*` set an alias of the newest commit.
`index.json` at the root (`harness/build_index.py`) is what the web's
catalogue reads (`lib/verified.ts`, raw.githubusercontent on `gh-pages`):
one entry per slug with `slug, name, level, label, verdict, generated,
sha, version, variant, committed, versions[], report, page, …` and per
version `{ sha, instrument, version, variant, committed, generated, level,
label, verdict, errors_reported, ci_run, report, page, pdf?, retired? }`.
**Never again:** `fallback_used` on entries or versions.

## 5. How to change any of this

1. Change the engine and this file in one commit.
2. Run one trial from the web form; download its artifact
   (`gh run download <run> -n trial-<tool>` or the API zip) into
   strhub-web `lib/verified/__fixtures__/` and point the test at it.
3. Change the web's reader and types in the same pull request as the
   fixture, and remove every field the engine no longer writes.
4. Merge the engine first, then the web (the web deploys to production
   from `main`).
