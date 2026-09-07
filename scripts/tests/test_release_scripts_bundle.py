"""Tests for the shared host-side ops-scripts bundling feature (bugfix-043).

Covers the 4-layer testing plan agreed for this feature (2026-09-06): cutting a release also
produces a verified scripts bundle tarball (scripts/cut_release.sh + scripts/lib/
release_scripts_manifest.sh); scripts/lib/unpack_scripts_bundle.sh - the exact same helper
deploy_release.sh ships to prod and runs there over SSH - can be exercised directly, with no SSH
and no real infrastructure, against a scratch target directory; a local/dev deploy never unpacks
the bundle onto this checkout's own tracked scripts; and deploying a version cut before this
feature existed (no bundle file at all) still succeeds, just skipping the unpack, for backward
compatibility. The actual remote/SSH shipping+unpacking steps in deploy_release.sh's prod path
have no automated coverage here for the same reason the rest of that path doesn't (see
test_deploy_release.py's own module docstring) - relies on a manual gate against real
infrastructure instead.
"""
import json
import subprocess
import tarfile

from conftest import (
    BUNDLE_STUB_FILES,
    UNPACK_SCRIPTS_BUNDLE_SCRIPT,
    git_log,
    run_script,
)


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


def test_cut_release_produces_verified_scripts_bundle(scratch_repo):
    """cut_release.sh must produce a *-scripts.tar.gz containing every file in the manifest, and
    record it in the JSON manifest under "scripts_bundle"."""
    result = _cut(scratch_repo, version="1.0.0")
    assert result.returncode == 0, result.stderr

    bundle_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0-scripts.tar.gz"
    assert bundle_path.exists(), f"expected scripts bundle at {bundle_path}"

    with tarfile.open(bundle_path, "r:gz") as tf:
        names = set(tf.getnames())
    for expected in BUNDLE_STUB_FILES:
        assert expected in names, f"{expected} missing from scripts bundle: {sorted(names)}"

    manifest_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["scripts_bundle"] == "denidin-app-v1.0.0-scripts.tar.gz"


def test_cut_release_refuses_when_bundle_file_missing_from_checkout(scratch_repo):
    """A checkout missing one of the manifest's own files must fail loudly, before any side
    effect - not silently ship a partial bundle."""
    missing_file = scratch_repo["repo"] / "scripts" / "env_lock.sh"
    missing_file.unlink()

    before_log = git_log(scratch_repo["repo"])
    result = _cut(scratch_repo, version="1.0.0")

    assert result.returncode != 0
    assert "env_lock.sh" in result.stderr
    assert git_log(scratch_repo["repo"]) == before_log, "must not commit anything on this failure"

    bundle_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0-scripts.tar.gz"
    assert not bundle_path.exists()


def test_unpack_scripts_bundle_succeeds_against_scratch_target(scratch_repo, tmp_path):
    """The exact helper deploy_release.sh ships to prod over SSH, run directly with no SSH and no
    real infrastructure - proves the extraction+verification mechanism itself works."""
    cut = _cut(scratch_repo, version="1.0.0")
    assert cut.returncode == 0, cut.stderr
    bundle_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0-scripts.tar.gz"

    target_dir = tmp_path / "scratch_prod_deploy_dir"
    result = subprocess.run(
        ["bash", str(UNPACK_SCRIPTS_BUNDLE_SCRIPT), str(bundle_path), str(target_dir)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("OK:")
    for expected in BUNDLE_STUB_FILES:
        assert (target_dir / expected).is_file(), f"{expected} missing after unpack"


def test_unpack_scripts_bundle_fails_loudly_on_incomplete_bundle(tmp_path):
    """A corrupt/incomplete bundle (missing a manifest file) must fail loudly and name exactly
    what's missing - never a silent partial success."""
    incomplete_bundle = tmp_path / "incomplete-scripts.tar.gz"
    with tarfile.open(incomplete_bundle, "w:gz") as tf:
        only_file = tmp_path / "run_all.sh"
        only_file.write_text("#!/bin/bash\necho stub\n")
        tf.add(only_file, arcname="scripts/run_all.sh")

    target_dir = tmp_path / "scratch_target"
    result = subprocess.run(
        ["bash", str(UNPACK_SCRIPTS_BUNDLE_SCRIPT), str(incomplete_bundle), str(target_dir)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode != 0
    assert "missing" in result.stderr.lower()
    assert "scripts/stop_all.sh" in result.stderr


def test_unpack_scripts_bundle_fails_loudly_on_missing_bundle_file(tmp_path):
    result = subprocess.run(
        ["bash", str(UNPACK_SCRIPTS_BUNDLE_SCRIPT), str(tmp_path / "does-not-exist.tar.gz"),
         str(tmp_path / "target")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


def test_local_deploy_does_not_unpack_bundle_onto_checkout(scratch_deploy_repo):
    """A local/dev deploy must never touch this checkout's own tracked scripts files - the bundle
    is present in the artifact but deliberately left unapplied (see deploy_release.sh's local
    path comment)."""
    cut = _cut(scratch_deploy_repo, version="1.0.0")
    assert cut.returncode == 0, cut.stderr

    before_log = git_log(scratch_deploy_repo["repo"])
    status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=scratch_deploy_repo["repo"],
        capture_output=True, text=True, check=True,
    ).stdout

    result = _deploy(scratch_deploy_repo, env="dev", version="1.0.0")
    assert result.returncode == 0, result.stderr
    assert "not applied" in result.stdout.lower() or "not applied" in result.stderr.lower()

    status_after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=scratch_deploy_repo["repo"],
        capture_output=True, text=True, check=True,
    ).stdout
    # A real deploy now genuinely runs stop_env.sh/run_env.sh (2026-09-06 revision), which write
    # real runtime log/state files under logs/health_monitoring/ - a legitimate new untracked
    # directory, not the bundle being unpacked onto tracked files. Only tracked-file changes (any
    # porcelain line NOT starting with "??") are what this test actually cares about.
    tracked_changes_before = [line for line in status_before.splitlines() if not line.startswith("??")]
    tracked_changes_after = [line for line in status_after.splitlines() if not line.startswith("??")]
    assert tracked_changes_after == tracked_changes_before, \
        "local deploy must not modify any TRACKED working-tree file"
    assert git_log(scratch_deploy_repo["repo"]) == before_log


def test_deploy_of_pre_bundle_version_skips_unpack_without_failing(scratch_deploy_repo):
    """Backward compatibility: a version cut before bugfix-043 existed has no scripts bundle file
    at all - deploying it must still succeed, just logging a note and skipping the unpack."""
    cut = _cut(scratch_deploy_repo, version="1.0.0")
    assert cut.returncode == 0, cut.stderr

    bundle_path = (
        scratch_deploy_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.0.0-scripts.tar.gz"
    )
    assert bundle_path.exists()
    bundle_path.unlink()  # simulate a pre-bugfix-043 cut, which never produced this file

    result = _deploy(scratch_deploy_repo, env="dev", version="1.0.0")
    assert result.returncode == 0, result.stderr
    assert "predates bugfix-043" in result.stdout or "predates bugfix-043" in result.stderr
