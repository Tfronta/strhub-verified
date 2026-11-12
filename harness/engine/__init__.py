"""The gate runner: one implementation of the ladder for CI and local trials.

What used to be bash in `.github/workflows/verify.yml` — Available, Installs,
Starts, the three run legs and their checks, the matrix — is one Python
package. Each gate is a function that returns a StageResult; the runner walks
them in order and writes a RunRecord, the one document report.py reads.

The runner records; it does not rescue. No gate retries, no gate edits the
recipe or the clone, and a gate that cannot run says why (`not_run` with a
reason) instead of being skipped in silence. When the loci a tool genotypes
are unknown, the forensic and medical slices are two legs planned up front,
both run and both reported; the record states which one the badge rests on.
"""
