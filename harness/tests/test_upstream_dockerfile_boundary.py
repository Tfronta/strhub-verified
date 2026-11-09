"""Execute the real install-step shell with inert git/docker replacements."""
import os
import pathlib
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_checked_out_dockerfile_symlink_cannot_be_read_or_built(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/verify.yml").read_text())
    step = next(s for s in workflow["jobs"]["verify"]["steps"] if s.get("id") == "installs")
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
    sentinel = tmp_path / "private"
    sentinel.write_text("PRIVATE SENTINEL - MUST NOT APPEAR IN LOGS")
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path,
        env={**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
             "SENTINEL": str(sentinel), "TOOL_REPO": "https://github.com/example/tool",
             "TOOL_REF": "a" * 40, "DOCKER_DIR": "recipe", "DOCKER_FILE": "Dockerfile",
             "DOCKER_FROM_REPO": "Dockerfile", "GITHUB_OUTPUT": str(tmp_path / "outputs")},
        capture_output=True, text=True)
    assert result.returncode != 0
    assert "path escapes allowed root" in result.stderr
    assert "PRIVATE SENTINEL" not in result.stdout + result.stderr
    assert not (tmp_path / "builds.txt").exists()
