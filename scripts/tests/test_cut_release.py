"""Script-level tests for scripts/cut_release.sh (Feature 034, T010a).

Exercises the REAL script via subprocess against a scratch git repo + throwaway `FROM scratch`
Dockerfile - never touches this repo's real tags/VERSION/artifacts folder. See
specs/in-progress/034-versioning-release-mgmt/contracts/cut_release_cli.md for the full contract.
"""
import json
import re
import subprocess

from conftest import git_log, run_script


def _cut(scratch, app="denidin-app", version="1.1.0", summary="Test release summary",
          stdin="y\n", env_overrides=None):
    return run_script(
        scratch["cut_script"],
        [app, version, "--artifacts-root", str(scratch["artifacts_root"]),
         "--summary", summary],
        cwd=scratch["repo"],
        stdin=stdin,
        env_overrides=env_overrides,
    )


def test_missing_args_exits_2_with_no_side_effects(scratch_repo):
    before_log = git_log(scratch_repo["repo"])

    result = run_script(scratch_repo["cut_script"], ["denidin-app"], cwd=scratch_repo["repo"])

    assert result.returncode == 2
    assert git_log(scratch_repo["repo"]) == before_log
    assert not list(scratch_repo["artifacts_root"].glob("**/*.tar"))


def test_malformed_version_exits_2_with_no_side_effects(scratch_repo):
    before_log = git_log(scratch_repo["repo"])

    result = _cut(scratch_repo, version="not-a-version")

    assert result.returncode == 2
    assert git_log(scratch_repo["repo"]) == before_log


def test_unknown_app_exits_2(scratch_repo):
    result = _cut(scratch_repo, app="some-other-app")
    assert result.returncode == 2


def test_happy_path_updates_version_changelog_releases_tag_and_artifact(scratch_repo):
    result = _cut(scratch_repo, version="1.1.0", summary="Adds versioning support")

    assert result.returncode == 0, result.stderr

    app_dir = scratch_repo["app_dir"]
    assert app_dir.joinpath("VERSION").read_text().strip() == "1.1.0"

    changelog = app_dir.joinpath("CHANGELOG.md").read_text()
    assert "1.1.0" in changelog
    assert "Adds versioning support" in changelog

    releases = app_dir.joinpath("RELEASES.md").read_text()
    assert "1.1.0" in releases
    assert "Adds versioning support" in releases

    tag_result = subprocess.run(
        ["git", "tag", "-l", "denidin-app-v1.1.0"],
        cwd=scratch_repo["repo"], capture_output=True, text=True, check=True,
    )
    assert tag_result.stdout.strip() == "denidin-app-v1.1.0"

    tar_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.1.0.tar"
    manifest_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.1.0.json"
    assert tar_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["app"] == "denidin-app"
    assert manifest["version"] == "1.1.0"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", manifest["date"])
    assert re.match(r"^[0-9a-f]{40}$", manifest["git_commit"])
    assert manifest["image_id"].startswith("sha256:")


def test_declining_confirmation_exits_0_with_no_side_effects(scratch_repo):
    before_log = git_log(scratch_repo["repo"])
    before_version = scratch_repo["app_dir"].joinpath("VERSION").read_text()

    result = _cut(scratch_repo, version="1.1.0", stdin="n\n")

    assert result.returncode == 0
    assert git_log(scratch_repo["repo"]) == before_log
    assert scratch_repo["app_dir"].joinpath("VERSION").read_text() == before_version
    assert not list(scratch_repo["artifacts_root"].glob("**/*.tar"))


def test_recutting_same_version_refuses_without_overwriting(scratch_repo):
    first = _cut(scratch_repo, version="1.1.0", summary="First cut")
    assert first.returncode == 0, first.stderr

    tar_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.1.0.tar"
    manifest_before = tar_path.with_suffix(".json").read_text()

    second = _cut(scratch_repo, version="1.1.0", summary="Attempted second cut")

    assert second.returncode == 1
    assert tar_path.with_suffix(".json").read_text() == manifest_before


def test_dates_are_utc_not_local_timezone(scratch_repo):
    """[post-/speckit.analyze finding C1] CONSTITUTION SS II: UTC everywhere, always."""
    import datetime
    utc_today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    result = _cut(
        scratch_repo, version="1.1.0", summary="TZ test",
        env_overrides={"TZ": "Pacific/Kiritimati"},  # UTC+14, always a different date than UTC
    )

    assert result.returncode == 0, result.stderr
    manifest_path = scratch_repo["artifacts_root"] / "denidin-app" / "denidin-app-v1.1.0.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["date"] == utc_today

    changelog = scratch_repo["app_dir"].joinpath("CHANGELOG.md").read_text()
    assert utc_today in changelog


def test_build_failure_leaves_zero_trace_no_partial_commit(scratch_repo):
    """Regression test for a real bug found cutting the actual first release (2026-08-02): a
    Docker build failure used to happen AFTER the VERSION/CHANGELOG/RELEASES commit, so a failed
    build left a dangling "release:" commit with no matching tag/artifact - and a naive re-run
    then appended a SECOND duplicate changelog/releases entry on top of it. The build (and save)
    must now happen BEFORE any commit, so a failure here leaves the working tree and git history
    completely untouched."""
    before_log = git_log(scratch_repo["repo"])
    before_version = scratch_repo["app_dir"].joinpath("VERSION").read_text()
    before_changelog = scratch_repo["app_dir"].joinpath("CHANGELOG.md").read_text()

    # Sabotage the build so it deterministically fails.
    dockerfile = scratch_repo["app_dir"] / "Dockerfile"
    dockerfile.write_text("FROM this-image-does-not-exist-anywhere:latest\n")

    result = _cut(scratch_repo, version="1.1.0", summary="Should never land")

    assert result.returncode == 1
    assert git_log(scratch_repo["repo"]) == before_log
    assert scratch_repo["app_dir"].joinpath("VERSION").read_text() == before_version
    assert scratch_repo["app_dir"].joinpath("CHANGELOG.md").read_text() == before_changelog
    assert not list(scratch_repo["artifacts_root"].glob("**/*.tar"))

    # A retry after fixing the Dockerfile must produce exactly ONE clean commit/entry, not two.
    dockerfile.write_text("FROM scratch\nCOPY . /\n")
    retry = _cut(scratch_repo, version="1.1.0", summary="Real release this time")
    assert retry.returncode == 0, retry.stderr
    changelog_after = scratch_repo["app_dir"].joinpath("CHANGELOG.md").read_text()
    assert changelog_after.count("## [1.1.0]") == 1
