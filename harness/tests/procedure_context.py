"""Synthetic cited source for tests of decisions after a valid procedure review.

Not an upstream fixture, an execution receipt or a shortcut in production.
Tests use the real reviewer and validator; no STR program is launched.
"""
import copy

import authorization
import fidelity
import prepare

COMMAND = 'tool --reads sample.bam --output result.vcf'
DOCKERFILE = 'FROM scratch\nENTRYPOINT ["/bin/bash", "-lc"]\n'


def context(proposal_fields=None, manifest_fields=None):
    source = {"repo": "https://github.com/example/tool", "ref": "a" * 40}
    document = '# Tool\n```sh\ndocker build -t upstream .\n' + COMMAND + '\n```\n'
    p = {**source, "build": {"method": "dockerfile", "file": "Dockerfile"},
         "commands": [{"cmd": COMMAND, "file": "README.md", "line": 4, "origin": "readme"}],
         "source_documents": [{"file": "README.md", "origin": "readme", "text": document}],
         "upstream_files": {"Dockerfile": DOCKERFILE}, "tree_paths": ["Dockerfile", "README.md"]}
    p.update(copy.deepcopy(proposal_fields or {}))
    m = {"tool": {"name": "Example", "version": "test"}, "source": source,
         "environment": {"source": "repository", "from_repo": "Dockerfile", "dockerfile": "Dockerfile"},
         "inputs": {"type": "illumina-bam-hg38"},
         "run": {"cmd": prepare.example_wrapper(fidelity.rewrite(COMMAND, "illumina-bam-hg38")["command"], ".")},
         "outputs": [{"path": "result.vcf", "format": "vcf", "min_records": 1}]}
    m.update(copy.deepcopy(manifest_fields or {}))
    r = authorization.prepare_review(p, m, p.get("limitations", []), [])
    return p, m, r


def decide(gates, diagnostics=None, **kwargs):
    import verdict
    proposal = kwargs.pop("recipe_proposal", None)
    compatibility = kwargs.pop("declared_compatibility", None)
    p, m, reviewed = context(proposal, {"compatibility": compatibility} if compatibility else None)
    return verdict.decide(gates, diagnostics, recipe_proposal=p, manifest=m, procedure=reviewed, **kwargs)


def report(code="runs", repo="https://github.com/example/tool", ref="a" * 40, instrument="documented"):
    """A freshly synthesized bound report for publication-policy tests."""
    import certificate_text
    import verdict
    origin = {"documented": "proposed", "maintainer": "maintainer", "curated": "curated"}[instrument]
    source = {"repo": repo, "ref": ref}
    p, m, reviewed = context({**source}, {"source": source, "recipe": {"origin": origin}})
    gates = {"available": True, "installs": True, "runs": code == "runs", "io": code == "runs", "content": code == "runs"}
    inner, cwd = prepare.unwrap_example(m["run"]["cmd"])
    return {"schema": "strhub-verified/1", "tool": m["tool"], "source": {**source, "ref_resolved": ref},
            "environment": m["environment"], "input_contract": m["inputs"], "gates": gates,
            "instrument": certificate_text.instrument_of(m), "recipe": m["recipe"],
            "procedure_review": reviewed,
            "run": {"cmd": inner, "effective_cmd": m["run"]["cmd"], "cwd": cwd,
                    "step_outcome": "success" if gates["runs"] else "failure"},
            "verdict": verdict.decide(gates, procedure=reviewed, manifest=m)}
