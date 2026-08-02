"""Shared fixtures for scripts/*.sh tests (Feature 034).

Every test here runs the REAL script against a scratch git repo + a trivial `FROM scratch`
Dockerfile (instant build, no network pull) - no mocking of git/docker subprocess calls
(CONSTITUTION SS I/V: mock only third-party network services, not local tools).

scripts/cut_release.sh and scripts/deploy_release.sh resolve their own REPO_ROOT from their own
on-disk location ($BASH_SOURCE), same pattern every other script in this repo uses (see
scripts/killall_containers.sh) - so copying the script into a scratch repo tree naturally scopes
all of its git/file operations to that scratch tree without needing any env-var override.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CUT_RELEASE_SCRIPT = REPO_ROOT / "scripts" / "cut_release.sh"
DEPLOY_RELEASE_SCRIPT = REPO_ROOT / "scripts" / "deploy_release.sh"

TRIVIAL_DOCKERFILE = "FROM scratch\nCOPY . /\n"


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def scratch_repo(tmp_path):
    """A scratch git repo mimicking this repo's layout for one app (denidin-app), with both
    release scripts copied in so their own $SCRIPT_DIR/REPO_ROOT resolution scopes to this
    scratch tree instead of the real repo."""
    repo = tmp_path / "scratch_repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)

    app_dir = repo / "apps" / "denidin-app"
    app_dir.mkdir(parents=True)
    (app_dir / "Dockerfile").write_text(TRIVIAL_DOCKERFILE)
    (app_dir / "VERSION").write_text("1.0.0\n")
    (app_dir / "CHANGELOG.md").write_text("# Changelog\n")
    (app_dir / "RELEASES.md").write_text("# Releases\n")

    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    for src in (CUT_RELEASE_SCRIPT, DEPLOY_RELEASE_SCRIPT):
        if src.exists():
            dest = scripts_dir / src.name
            shutil.copy(src, dest)
            os.chmod(dest, 0o755)

    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "initial"], repo)

    artifacts_root = tmp_path / "artifacts"
    (artifacts_root / "denidin-app").mkdir(parents=True)

    return {
        "repo": repo,
        "app_dir": app_dir,
        "artifacts_root": artifacts_root,
        "cut_script": scripts_dir / "cut_release.sh",
        "deploy_script": scripts_dir / "deploy_release.sh",
    }


def git_log(repo):
    result = subprocess.run(
        ["git", "log", "--format=%H"], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout


def run_script(script, args, cwd, stdin="y\n", env_overrides=None, timeout=60):
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(script)] + args,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
