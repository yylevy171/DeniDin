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


@pytest.fixture
def scratch_webapp_repo(tmp_path):
    """Like scratch_repo, but laid out for `webapp` - a TWO-image app: apps/webapp/VERSION +
    CHANGELOG/RELEASES, plus apps/webapp/backend/Dockerfile and apps/webapp/frontend/Dockerfile
    both built from repo-root context (mirrors the real Dockerfiles). cut_release.sh should
    build both, bundle them into ONE artifact tar, and write one manifest + one tag."""
    repo = tmp_path / "scratch_webapp_repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)

    webapp = repo / "apps" / "webapp"
    (webapp / "backend").mkdir(parents=True)
    (webapp / "frontend").mkdir(parents=True)
    (webapp / "VERSION").write_text("0.5.4\n")
    (webapp / "CHANGELOG.md").write_text("# Changelog\n")
    (webapp / "RELEASES.md").write_text("# Releases\n")
    # Repo-root build context (context "." in cut_release.sh's BUILD_SPECS for webapp).
    (webapp / "backend" / "Dockerfile").write_text(TRIVIAL_DOCKERFILE)
    (webapp / "frontend" / "Dockerfile").write_text(TRIVIAL_DOCKERFILE)

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
    (artifacts_root / "webapp").mkdir(parents=True)

    return {
        "repo": repo,
        "webapp_dir": webapp,
        "artifacts_root": artifacts_root,
        "cut_script": scripts_dir / "cut_release.sh",
        "deploy_script": scripts_dir / "deploy_release.sh",
    }


RUNNING_DOCKERFILE = (
    'FROM python:3.11-slim\n'
    'COPY VERSION /VERSION\n'
    'CMD ["sh", "-c", "while true; do echo \\"[v$(cat /VERSION)] alive\\"; sleep 1; done"]\n'
)


@pytest.fixture
def scratch_deploy_repo(tmp_path):
    """Like scratch_repo, but with a genuinely long-running container (loops printing its own
    version to stderr/stdout) and a scratch docker-compose file, so deploy_release.sh's real
    retag + `docker compose up -d --no-build` + automatic verification mechanism can be
    exercised end-to-end - not just its argument validation.

    SAFETY: the compose project name below ("scratch-034-deploy-test") is deliberately distinct
    from the real repo's "denidin-dev"/"denidin-prod" - deploy_release.sh derives the project
    name from the compose file's own `name:` field rather than hardcoding it (research.md
    Decision 5's safety-critical detail), specifically so this can never collide with a real
    running dev/prod environment on the same machine. Do not "simplify" this to match the real
    project name.
    """
    repo = tmp_path / "scratch_deploy_repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)

    app_dir = repo / "apps" / "denidin-app"
    app_dir.mkdir(parents=True)
    (app_dir / "Dockerfile").write_text(RUNNING_DOCKERFILE)
    (app_dir / "VERSION").write_text("1.0.0\n")
    (app_dir / "CHANGELOG.md").write_text("# Changelog\n")
    (app_dir / "RELEASES.md").write_text("# Releases\n")

    docker_dir = repo / "docker"
    docker_dir.mkdir()
    (docker_dir / "docker-compose.dev.yml").write_text(
        "name: scratch-034-deploy-test\n"
        "services:\n"
        "  denidin-app-dev:\n"
        "    build:\n"
        "      context: ./apps/denidin-app\n"
        '    restart: "no"\n'
    )

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

    yield {
        "repo": repo,
        "app_dir": app_dir,
        "artifacts_root": artifacts_root,
        "cut_script": scripts_dir / "cut_release.sh",
        "deploy_script": scripts_dir / "deploy_release.sh",
        "compose_file": docker_dir / "docker-compose.dev.yml",
        "project_name": "scratch-034-deploy-test",
    }

    # Teardown: tear down the scratch compose project so containers/networks don't leak between
    # test runs (images are left for docker's own cache - harmless, distinct tags per test).
    subprocess.run(
        ["docker", "compose", "-f", str(docker_dir / "docker-compose.dev.yml"),
         "--project-directory", str(repo), "down", "--remove-orphans"],
        cwd=repo, capture_output=True, text=True, timeout=60,
    )


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
