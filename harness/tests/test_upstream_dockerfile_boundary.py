"""Execute the engine's Installs gate with inert git/docker replacements."""
import os
import pathlib

from engine import stages
from engine.executor import Executor
from engine.record import StageResult

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_checked_out_dockerfile_symlink_cannot_be_read_or_built(tmp_path, monkeypatch, capsys):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = clone ]; then\n'
        '  mkdir -p "$5"\n'
        '  ln -s "$SENTINEL" "$5/Dockerfile"\n'
        'elif [ "$3" = rev-parse ]; then echo "$TOOL_REF"; fi\n'
    )
    git.chmod(0o755)
    docker = bindir / "docker"
    docker.write_text('#!/bin/sh\necho unexpected-build >> builds.txt\nexit 0\n')
    docker.chmod(0o755)
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness/_paths.py").write_bytes((ROOT / "harness/_paths.py").read_bytes())
    (tmp_path / "harness/record_terminal.sh").write_bytes((ROOT / "harness/record_terminal.sh").read_bytes())
    sentinel = tmp_path / "private"
    sentinel.write_text("PRIVATE SENTINEL - MUST NOT APPEAR IN LOGS")
    (tmp_path / "work").mkdir()
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SENTINEL", str(sentinel))
    monkeypatch.setenv("TOOL_REF", "a" * 40)
    ctx = stages.Ctx(plan={"repo": "https://github.com/example/tool", "ref": "a" * 40, "install_ready": "1",
                           "dockerdir": "recipe", "dockerfile": "Dockerfile", "dockerfile_from_repo": "Dockerfile",
                           "installation_profile": "", "manifest": str(tmp_path / "manifest.yml")},
                     work=pathlib.Path("work"), root=tmp_path, exe=Executor())
    result = stages.installs(ctx, StageResult(stage="available", status="passed", exit_code=0))
    out = capsys.readouterr()
    assert result.status == "failed" and result.outputs["failed_check"] == "_paths.py"
    assert "path escapes allowed root" in (tmp_path / "work/log_build.txt").read_text()
    assert "PRIVATE SENTINEL" not in out.out + out.err + (tmp_path / "work/log_build.txt").read_text()
    assert not (tmp_path / "builds.txt").exists()
