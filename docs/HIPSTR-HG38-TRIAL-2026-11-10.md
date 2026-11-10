# HipSTR hg38: manual trial evidence and web integration boundary

Both manual hg38 cases completed successfully on 2026-11-10. These are execution
smoke tests, not automated Verified runs, genotype accuracy benchmarks, or
authorization to publish an attestation.

| Case | Sample | Requested region rows | VCF records with GT | Omitted rows | Process exit |
| --- | --- | ---: | ---: | ---: | ---: |
| Autosomal | NA12878 | 24 | 22 | 2 | 0 |
| Y | HG002 | 17 | 11 | 6 | 0 |

Both outputs are VCF 4.1 and pass `strhub-vcf-structure/1`. All emitted rows
have nonmissing GT. Autosomal GTs have two allele slots; Y GTs have one. Sample
names and region identities match the fixed inputs. The 17 Y rows include
components of compound markers and are not 17 independent forensic markers.

The two autosomal omissions are SE33 and D21S11, which exceed HipSTR's unchanged
100 bp reference-length limit. Y-GATA-H4 and DYS385_2 exceed the same limit.
HipSTR aborted the remaining four Y loci (DYS19/DYS394, DYS389II.2, DYS448.1,
DYS448.2) because their flanking sequence is too repetitive. These outcomes
were retained; no filter was disabled and no omitted region was retried.

## Fixed source, inputs and environment

- Upstream: <https://github.com/tfwillems/HipSTR>, commit
  `b2033bfbb5cf55496b776463bdf2993fa763a4be`.
- Reused binary SHA256:
  `4bf7579512e67ed580b64ca99daa4fb527024fdf1e11b8e763419feaba5093ef`.
- Reused native Linux ARM64 image:
  `sha256:68e575be59f1778976ed9cf606e9667cbfba1c1fe3790bdd925beee77ef417de`.
- Input repository commit: `025ce998c4316afa15b7625a1671017c648d315b`.
- Existing autosomal and Y BAM/BAI pairs and their dataset-level HipSTR BEDs
  were copied byte-for-byte. No header, coordinate, region or alignment edits.
- Reference: the exact UCSC hg38 URL in both dataset manifests,
  <https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz>.
  Its published MD5 matched `1c9dcaddfa41027f17cd8f7a82c7293b`.
- Both commands used `--min-reads 15 --def-stutter-model`, selected before
  execution from the pinned README's recommendation for few samples. Y also
  used the documented `--haploid-chrs chrY`. All other filters stayed at
  their original defaults.
- Each case had one attempt, without runtime network, with read-only inputs
  and separate output directories. All 396 tracked upstream files, the binary,
  inputs and reference remained unchanged. Both containers exited normally
  without OOM.

This trial reused the image and binary built in the preceding tutorial
experiment. It did not test an automated clean-environment installation.
Used contig lengths and region bounds were checked. The BAM headers lack M5
for these contigs, so those checks do not prove base-by-base identity with the
aligner's original reference. No allele truth comparison was performed.

## Preserved evidence

[Complete evidence ZIP](evidence/hipstr-hg38-2026-11-10/evidence.zip)
contains the original VCFs and logs, the predeclared plan, exact argv receipts,
input/source hashes, before/after integrity checks, the structural validator,
per-region outcomes and recording scripts. Its `build-origin` directory holds
the preceding experiment's complete evidence solely to preserve the origin of
the reused executable and image; those hg19 results are not hg38 results.

ZIP SHA256: `30ee3b55ebd9a83ba33074e2c7be321dd6b03afda70da10bb43526cd52ca399d`.

[Structured results](evidence/hipstr-hg38-2026-11-10/results.json) and
[all 41 region outcomes](evidence/hipstr-hg38-2026-11-10/region-outcomes.tsv)
are also stored as text for review. The original report inside the ZIP retains
the local output paths recorded during the experiment; use these repository
links when reviewing on GitHub.

## What is still required before the web form can reproduce this

At the time of this check, engine PR #65 and web PR #73 are open drafts. They
are not merged into their default branches. The audited engine's
`strhub-upstream-procedure/1` currently admits an unchanged upstream Dockerfile
with a narrowly supported invocation; it does not admit this source build.

The web form sends a trial through `dispatchWorkflow`, which uses the
server-side `VERIFIED_ENGINE_BRANCH` setting, defaulting to `main`. The tool
commit entered in the form is separate from the engine branch. Pushing these
evidence files cannot connect the manual commands to that execution path.

The integration work must happen in this order:

1. Establish a separately versioned source-installation profile with pinned
   evidence for every effective dependency and build step. Cover the
   documented APT package command and `make`, without restoring generic
   dependencies or fallback builds. Keep the existing profile's rejections.
2. Establish native executable invocation and explicit dataset/reference/
   regions bindings. The manual commands combine a base invocation and
   separately documented options; their success does not itself satisfy the
   existing profile's literal-command evidence rule. Any supported expansion
   needs its own audited evidence rules, not an exception for HipSTR.
3. Bind the predeclared procedure to the effective manifest and recheck it
   before execution. Persist source, plan, command and input hashes; retain a
   failed attempt without repairs, parameter changes or alternate datasets.
4. Show process completion, structural validation, GT presence and omitted
   regions separately in the web report. A successful process must not be
   shown as complete coverage of the requested panel.
5. Test the form against an isolated preview using the audited engine branch
   and `publish=false`, then review the engine/web changes before deployment.
   A production form submission is not a substitute for that integration test.

No admission control was relaxed, automatic run dispatched, PR merged, badge
published or deployment changed by committing this evidence.
