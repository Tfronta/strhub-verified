"""STRhub's recipe agent, driven by a scripted model and scripted trials: no
network, no API key. What is tested is the harness around the model: the
rules it enforces, what reaches a trial, and what comes out."""
import contextlib
import types

import assist

SHA = "2be6cf5ec0b108601719c16171a3f0099d1cb88d"
SRC = {
    "tree_resp": {"tree": [{"path": p, "type": "blob", "size": 10} for p in
                           ("README.md", "Makefile", "src/main.cpp", "config/tool.conf", "docs/usage.md")],
                  "truncated": False},
    "readme": "# Tool\n\nDocs at https://tool.readthedocs.io/en/latest/.\n\n```\n./tool --bams x.bam\n```\n",
    "readme_name": "README.md",
    "files": {"Makefile": "all:\n\tg++ -o tool src/main.cpp\n"},
    "docs": [{"path": "docs/usage.md", "origin": "repo", "text": "Run ./tool --bams in.bam --out calls.vcf"}],
    "published": {"bioconda": {}, "release": None},
    "tag": "v1.2",
}
GOOD_DOCKERFILE = (f"FROM ubuntu:22.04\nRUN apt-get update && apt-get install -y git build-essential\n"
                   f"ARG TOOL_REF={SHA}\nRUN git clone https://github.com/o/tool.git /opt/tool && cd /opt/tool "
                   "&& git checkout \"${TOOL_REF}\" && make\nENTRYPOINT [\"/bin/bash\", \"-lc\"]\n")
GOOD_MANIFEST = """\
tool: {name: Tool}
environment: {dockerfile: Dockerfile, os: [ubuntu-22.04]}
run: {cmd: "cd /data/out && /opt/tool/tool --bams /data/in/input.bam --out calls.vcf", timeout_minutes: 20}
inputs: {type: ont-bam-hg38}
outputs: [{path: "*.vcf", format: vcf, min_records: 1}]
"""


def repo(**kw):
    return assist.Repo("o/tool", SHA, SRC, fetch=lambda p: f"contents of {p}",
                       fetch_url=kw.get("fetch_url", lambda u: f"page {u}"))


def block(kind, **kw):
    return types.SimpleNamespace(type=kind, **kw)


def msg(*blocks, stop="tool_use"):
    return types.SimpleNamespace(content=list(blocks), stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=10, output_tokens=5,
                                                             cache_read_input_tokens=0,
                                                             cache_creation_input_tokens=0))


class FakeClient:
    """client.beta.messages.stream(...) as a context manager whose
    get_final_message() replays a script. Records every request."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(stream=self._stream))

    @contextlib.contextmanager
    def _stream(self, **kw):
        # The messages as they were when sent: the agent keeps extending the list.
        self.requests.append({**kw, "messages": list(kw["messages"])})
        m = self.script.pop(0)
        yield types.SimpleNamespace(get_final_message=lambda: m)


class FakeTrials:
    def __init__(self, verdicts):
        self.verdicts, self.recipes = list(verdicts), []

    def run(self, recipe, tool, attempt):
        self.recipes.append(recipe)
        return {"run": f"https://example/run/{attempt}", "verdict": self.verdicts.pop(0), "gates": {}}


def agent(client, trials, **kw):
    documented = {"recipe": {"manifest_yml": "tool: {name: Tool}\n", "dockerfile": "FROM ubuntu\n"},
                  "result": {"verdict": "fails", "reason": "build failed"}}
    return assist.Agent(client, trials, repo(), {}, documented, "tool-ont", tag="v1.2", log=lambda *_: None, **kw)


def submit(i, manifest=GOOD_MANIFEST, dockerfile=GOOD_DOCKERFILE, workarounds=None):
    return block("tool_use", id=f"s{i}", name="submit_recipe", input={
        "manifest_yml": manifest, "dockerfile": dockerfile, "reasoning": "try",
        "workarounds": workarounds if workarounds is not None else
        [{"what": "Builds with make in the clone", "instead_of": "not documented", "why": "no install steps"}]})


def finish(outcome="runs"):
    return block("tool_use", id="f", name="finish",
                 input={"outcome": outcome, "summary": "done", "recommendations": ["Document the build."]})


def test_a_failed_trial_goes_back_to_the_model_and_the_recipe_that_ran_comes_out():
    client = FakeClient([
        msg(block("tool_use", id="r1", name="read_file", input={"path": "Makefile"})),
        msg(submit(1)),
        msg(submit(2)),
        msg(finish()),
    ])
    trials = FakeTrials(["fails", "runs"])
    out = agent(client, trials).run()
    assert out["success"] and out["stop"] == "finished" and len(out["attempts"]) == 2
    # The harness writes its own fields: the pinned source, the curated origin
    # with the workarounds, the catalogue slug; never the model.
    m = out["recipe"]["manifest_yml"]
    assert f"ref: {SHA}" in m and "origin: curated" in m and "slug: tool-ont" in m and "Builds with make" in m
    # What went back to the model after the first trial says it failed and how many are left.
    second = client.requests[2]["messages"][-1]["content"][0]["content"]
    assert "did not run to the end" in second and "3 submission(s) left" in second


def test_the_history_is_only_appended_to():
    client = FakeClient([msg(submit(1)), msg(finish())])
    agent(client, FakeTrials(["runs"])).run()
    first, second = client.requests[0]["messages"], client.requests[1]["messages"]
    assert second[: len(first)] == first


def test_a_recipe_that_changes_the_tool_s_code_never_reaches_a_trial():
    patched = GOOD_DOCKERFILE.replace("&& make", "&& sed -i 's/abort()/return 0/' src/main.cpp && make")
    client = FakeClient([msg(submit(1, dockerfile=patched)), msg(finish("gave_up"))])
    trials = FakeTrials([])
    out = agent(client, trials).run()
    assert trials.recipes == [] and out["attempts"] == []
    answer = client.requests[1]["messages"][-1]["content"][0]
    assert answer["is_error"] and "Rule 1" in answer["content"]


def test_editing_a_configuration_file_the_docs_mention_is_allowed():
    configured = GOOD_DOCKERFILE.replace("&& make", "&& sed -i 's#YOUR PATH#/usr/bin#' conf.py && make")
    recipe, why = assist.validate(GOOD_MANIFEST, configured, repo(), "tool-ont", [], "v1.2")
    assert recipe is not None, why


def test_the_pinned_commit_and_the_entrypoint_are_required():
    unpinned = GOOD_DOCKERFILE.replace(f"ARG TOOL_REF={SHA}\n", "").replace('git checkout "${TOOL_REF}" && ', "")
    assert "Rule 2" in assist.validate(GOOD_MANIFEST, unpinned, repo(), "s", [], "")[1]
    no_entry = GOOD_DOCKERFILE.replace('ENTRYPOINT ["/bin/bash", "-lc"]', 'CMD ["tool"]')
    assert "Rule 3" in assist.validate(GOOD_MANIFEST, no_entry, repo(), "s", [], "")[1]


def test_a_manifest_the_schema_rejects_is_answered_before_a_trial():
    bad = GOOD_MANIFEST.replace("timeout_minutes: 20", "timeout_minutes: 100000")
    recipe, why = assist.validate(bad, GOOD_DOCKERFILE, repo(), "s", [], "")
    assert recipe is None and "schema" in why


def test_documentation_is_fetched_only_from_sites_the_repository_links():
    r = repo()
    assert r.fetch("https://tool.readthedocs.io/en/latest/usage.html").startswith("page ")
    for url in ("https://evil.example.com/x", "http://tool.readthedocs.io/x"):
        try:
            r.fetch(url)
            raise AssertionError(url)
        except ValueError:
            pass


def test_files_are_read_only_from_the_tree():
    r = repo()
    assert r.read("Makefile").startswith("all:")          # from the snapshot
    assert r.read("config/tool.conf") == "contents of config/tool.conf"
    try:
        r.read("../../etc/passwd")
        raise AssertionError
    except ValueError as e:
        assert "not in the tree" in str(e)


def test_the_number_of_trials_is_capped():
    client = FakeClient([msg(submit(1)), msg(submit(2)), msg(finish("gave_up"))])
    trials = FakeTrials(["fails"])
    out = agent(client, trials, max_attempts=1).run()
    assert len(trials.recipes) == 1 and not out["success"]
    answer = client.requests[2]["messages"][-1]["content"][0]
    assert answer["is_error"] and "No submissions left" in answer["content"]


def test_a_refusal_stops_the_session_without_running_anything():
    client = FakeClient([msg(submit(1), stop="refusal")])
    trials = FakeTrials([])
    out = agent(client, trials).run()
    assert out["stop"] == "refusal" and trials.recipes == []


def test_a_truncated_turn_is_not_executed():
    client = FakeClient([msg(submit(1), stop="max_tokens"), msg(finish("gave_up"))])
    trials = FakeTrials([])
    agent(client, trials).run()
    assert trials.recipes == []
    answer = client.requests[1]["messages"][-1]["content"][0]
    assert answer["is_error"] and "cut off" in answer["content"]


def test_the_request_caches_the_stable_prefix_and_asks_for_fallbacks():
    client = FakeClient([msg(finish("gave_up"))])
    agent(client, FakeTrials([])).run()
    req = client.requests[0]
    assert req["model"] == assist.MODEL and req["output_config"] == {"effort": assist.EFFORT}
    assert req["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert req["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert req["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in req["betas"]
    assert all(t["strict"] for t in req["tools"])


def test_the_report_lists_the_attempts_the_workarounds_and_the_cost():
    import assist_report
    client = FakeClient([msg(submit(1)), msg(submit(2)), msg(finish())])
    out = agent(client, FakeTrials(["fails", "runs"])).run()
    out["documented"] = {"result": {"verdict": "fails", "reason": "build failed", "run": "https://example/run/0"}}
    text = assist_report.render(out, pr=True)
    assert "| 1 | fails |" in text and "| 2 | runs |" in text
    assert "Builds with make in the clone" in text and "Document the build." in text
    assert "curated" in text and "about $" in text
