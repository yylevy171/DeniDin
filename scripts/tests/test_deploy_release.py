"""Script-level tests for scripts/deploy_release.sh (Feature 034, T012a).

One script for three shapes - initial deploy, promotion, rollback - all the same mechanism
(research.md Decision 9). Exercises the REAL script via subprocess against a scratch git repo, a
genuinely long-running container (loops printing its own version - not `FROM scratch`, which has
no running process to verify against), and a scratch docker-compose file with a project name
deliberately distinct from the real repo's "denidin-dev"/"denidin-prod" (see conftest.py's
scratch_deploy_repo docstring for why this matters - never change it to match the real name).

See specs/in-progress/034-versioning-release-mgmt/contracts/deploy_release_cli.md for the full
contract. Covers denidin-app's docker-logs-based verification path thoroughly; morning-mcp-app's
/health-poll path is structurally parallel but not covered by an automated scratch test here -
relies on T013's manual gate against real infrastructure instead.
"""
import subprocess
import time

from conftest import git_log, run_script


def _cut(scratch, app="denidin-app", version="1.0.0", summary="Test release"):
    return run_script(
        scratch["cut_script"],
        [app, version, "--artifacts-root", str(scratch["artifacts_root"]),
         "--summary", summary],
        cwd=scratch["repo"],
        stdin="y\n",
    )


def _deploy(scratch, app="denidin-app", env="dev", version="1.0.0"):
    return run_script(
        scratch["deploy_script"],
        [app, env, version, "--artifacts-root", str(scratch["artifacts_root"])],
        cwd=scratch["repo"],
        stdin="",
        timeout=90,
    )


def _container_logs(scratch):
    container = f"{scratch['project_name']}-denidin-app-dev-1"
    result = subprocess.run(
        ["docker", "logs", container, "--tail", "20"],
        capture_output=True, text=True,
    )
    return result.stdout + result.stderr


def test_missing_args_exits_2(scratch_deploy_repo):
    result = run_script(scratch_deploy_repo["deploy_script"], ["denidin-app", "dev"],
                         cwd=scratch_deploy_repo["repo"], stdin="")
    assert result.returncode == 2


def test_bad_env_exits_2(scratch_deploy_repo):
    result = _deploy(scratch_deploy_repo, env="staging")
    assert result.returncode == 2


def test_missing_artifact_exits_1_no_docker_build(scratch_deploy_repo):
    result = _deploy(scratch_deploy_repo, version="9.9.9")

    assert result.returncode == 1
    assert "9.9.9" in result.stderr or "9.9.9" in result.stdout
    # No build step should ever be invoked by deploy_release.sh, for any of the 3 shapes.
    assert "Building" not in result.stdout
    assert "Successfully built" not in result.stdout


def test_manifest_mismatch_refuses(scratch_deploy_repo):
    cut = _cut(scratch_deploy_repo, version="1.0.0")
    assert cut.returncode == 0, cut.stderr

    # Corrupt the manifest so it claims a different version than the filename implies.
    manifest_path = scratch_deploy_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0.json"
    import json
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = "2.5.0"
    manifest_path.write_text(json.dumps(manifest))

    result = _deploy(scratch_deploy_repo, version="1.0.0")
    assert result.returncode == 1


def test_initial_deploy_loads_no_rebuild_and_verifies(scratch_deploy_repo):
    cut = _cut(scratch_deploy_repo, version="1.0.0")
    assert cut.returncode == 0, cut.stderr

    before_log = git_log(scratch_deploy_repo["repo"])

    result = _deploy(scratch_deploy_repo, env="dev", version="1.0.0")

    assert result.returncode == 0, result.stderr
    assert "Building" not in result.stdout
    assert "Successfully built" not in result.stdout

    logs = _container_logs(scratch_deploy_repo)
    assert "[v1.0.0]" in logs

    # [post-/speckit.analyze finding H1] no git history change from a deploy, ever.
    assert git_log(scratch_deploy_repo["repo"]) == before_log


def test_promotion_shape_deploys_newer_version(scratch_deploy_repo):
    """A "promotion" (or plain forward deploy of a newer version) is the exact same call shape
    as the initial deploy - just a version that happens to be newer than what's running."""
    _cut(scratch_deploy_repo, version="1.0.0")
    _deploy(scratch_deploy_repo, env="dev", version="1.0.0")

    cut2 = _cut(scratch_deploy_repo, version="1.1.0", summary="Second release")
    assert cut2.returncode == 0, cut2.stderr

    result = _deploy(scratch_deploy_repo, env="dev", version="1.1.0")

    assert result.returncode == 0, result.stderr
    logs = _container_logs(scratch_deploy_repo)
    assert "[v1.1.0]" in logs


def test_rollback_shape_deploys_older_version(scratch_deploy_repo):
    """Rollback is the exact same call shape too - just a version older than what's running."""
    _cut(scratch_deploy_repo, version="1.0.0")
    _cut(scratch_deploy_repo, version="1.1.0", summary="Second release")
    _deploy(scratch_deploy_repo, env="dev", version="1.1.0")
    assert "[v1.1.0]" in _container_logs(scratch_deploy_repo)

    before_log = git_log(scratch_deploy_repo["repo"])

    result = _deploy(scratch_deploy_repo, env="dev", version="1.0.0")

    assert result.returncode == 0, result.stderr
    assert "Building" not in result.stdout
    logs = _container_logs(scratch_deploy_repo)
    assert "[v1.0.0]" in logs
    assert git_log(scratch_deploy_repo["repo"]) == before_log


def test_verification_timeout_reports_failure(scratch_deploy_repo):
    """A genuine verification-timeout scenario: the artifact/manifest for "1.0.0" pass every
    precondition, but the tarball's actual image content is swapped for a *different* cut
    version's image after the fact - so the container that actually starts never logs
    "[v1.0.0]". Verification must time out and report FAILURE (exit 1), never a false success,
    even though the container did technically start. Uses --verify-timeout to keep this fast
    (a few seconds) rather than waiting out the real default window."""
    cut_a = _cut(scratch_deploy_repo, version="1.0.0")
    assert cut_a.returncode == 0, cut_a.stderr
    cut_b = _cut(scratch_deploy_repo, version="2.0.0", summary="Different content")
    assert cut_b.returncode == 0, cut_b.stderr

    artifacts_dir = scratch_deploy_repo["artifacts_root"] / "denidin-app"
    # Swap "1.0.0"'s tarball for "2.0.0"'s image content, while its manifest still (truthfully,
    # per its own app/version fields) claims "1.0.0" - so precondition checks pass, but the
    # container that actually comes up will log "[v2.0.0]", never "[v1.0.0]".
    (artifacts_dir / "denidin-app-v1.0.0.tar").write_bytes(
        (artifacts_dir / "denidin-app-v2.0.0.tar").read_bytes()
    )

    result = run_script(
        scratch_deploy_repo["deploy_script"],
        ["denidin-app", "dev", "1.0.0", "--artifacts-root", str(artifacts_dir.parent),
         "--verify-timeout", "6"],
        cwd=scratch_deploy_repo["repo"],
        stdin="",
        timeout=60,
    )

    assert result.returncode == 1
    assert "FAILED" in result.stderr or "failed" in result.stderr.lower()
