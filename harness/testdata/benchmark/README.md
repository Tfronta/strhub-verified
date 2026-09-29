# Recipe benchmark: 23 STR tools, pinned

What `detect_recipe.py` + `propose_manifest.py` make of repositories they were
NOT tuned on. The five catalogue tools taught the engine everything it knows;
on 24 September 2026 it produced a viable run command for none of eighteen
others (docs/INFORME-AUDITORIA-2026-09-24.md, section 3). This directory is
the fixed yardstick every change to recipe detection is measured against.

`repos.tsv` names each tool, its repository, the release tag when there is one,
and the commit it is pinned to. `set` is `new` (never seen by the engine when
it was written) or `catalogue` (the five it was tuned on).

Each `<name>/` holds:

| file | what | written by |
|---|---|---|
| `tree.json` | the file tree at the pinned commit (`repo`, `ref`, `tag`, `readme_name`, `tree`) | `harness/snapshot_repo.py` |
| `README.md` | the README at the pinned commit, whatever its real name | `snapshot_repo.py` |
| `docs/`, `wiki/` | in-repository documents and wiki pages the README links to | `snapshot_repo.py` |
| `files/` | build and packaging files (Makefile, CMakeLists.txt, setup.py, pyproject.toml, environment files, Cargo.toml, DESCRIPTION, ...) | `snapshot_repo.py` |
| `published.json` | what exists outside the repository: Bioconda versions of the package, the release's assets | `snapshot_repo.py` |
| `expected.json` | **the ground truth**, read by a person from the documentation | by hand |

A snapshot is what `detect_recipe` reads online, frozen: `detect_recipe.py
--offline harness/testdata/benchmark/<name>` gives the same proposal a trial
of that commit would, without the network.

## expected.json

Every value carries `where`: the file and line at the pinned commit it was read
from, or the URL for documentation outside the repository. Nothing in it is
what STRhub does today; it is what the documentation says a user should do.

```json
{
  "_about": "Hand-checked against <repo> at <sha> on <date>, from <which documents>.",
  "program": {"value": "LongTR", "subcommand": null, "where": "README.md:35"},
  "command": {"value": "<the documented genotyping invocation, verbatim>",
              "source": "readme | repo_docs | wiki | external_docs | none",
              "where": "README.md:34-40"},
  "install": {"documented": "<what the docs tell a user to do, in a few words>",
              "acceptable_methods": ["make"],
              "where": "README.md:23-30"},
  "published": {"bioconda_documented": null,
                "bioconda_available": {"package": "longtr", "version_at_ref": "1.2"},
                "image_documented": null,
                "release_binary_documented": false,
                "where": "..."},
  "input": {"kinds": ["bam"], "platforms": ["pacbio", "ont"],
            "strhub_type": "ont-bam-hg38", "where": "README.md:1,35-45"},
  "extra_inputs": [{"what": "TR regions BED: chrom, start, end, motif[, name]", "required": true,
                    "strhub_has": true, "where": "README.md:143-155"}],
  "runnable_on_strhub_data": {"value": true, "why": "..."},
  "notes": "..."
}
```

- `program.value`: the executable a user types, as its basename (`ExpansionHunter`,
  `trgt`, `straglr.py`); `subcommand` when the tool has them (`genotype`, `call`).
  For a pipeline of several commands, the one that genotypes.
- `install.acceptable_methods`: the `detect_recipe` build methods that are a
  faithful reading of the documented install: `dockerfile`, `docker_image`,
  `bioconda`, `conda`, `pip`, `cmake`, `make`, `autotools`, `cargo`, `go`,
  `release_binary`, `r`, `nim`, `script`.
- `published.bioconda_documented`: only when the README or the docs tell users
  to install from Bioconda (a command, a badge, a link). `bioconda_available`
  is what api.anaconda.org holds, documented or not.
- `input.strhub_type`: the STRhub dataset a faithful run would use, or `null`
  when none fits: `illumina-str-fastq` (NIST ForenSeq amplicon FASTQ),
  `illumina-bam-hg38` (NA12878, hg38, 24 forensic loci), `illumina-bam-hg38-y`
  (HG002, Y-STRs), `ont-bam-hg38` (1000 Genomes ONT R10, CODIS loci ±10 kb).
- `runnable_on_strhub_data`: whether a faithful recipe could run at all on that
  dataset with what STRhub supplies (hg38 FASTA, a regions BED in HipSTR,
  GangSTR, STRsearch, plain BED4 or chrom/start/end/motif layout). False with the reason when the tool
  needs something STRhub does not hold.

`harness/benchmark_recipes.py` scores the current engine against these files;
`harness/tests/test_benchmark.py` holds it to the recorded floor.
