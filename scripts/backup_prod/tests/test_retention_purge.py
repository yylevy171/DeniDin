"""Real (non-mocked) tests for lib/retention_purge.sh (Feature 078).

Real files on a real scratch directory, real `bash`/`date` subprocess calls -
no unittest.mock, per CONSTITUTION SS I/V.
"""
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RETENTION_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "lib" / "retention_purge.sh"


def _run_purge(directory, amount, unit):
    script = f"""
set -e
source "{RETENTION_SCRIPT}"
purge_older_than "{directory}" "{amount}" "{unit}"
"""
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)


def _touch(directory: Path, name: str):
    (directory / name).write_text("fake archive contents")


def _date_str(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_purge_daily_keeps_recent_deletes_old(tmp_path):
    d = tmp_path / "daily"
    d.mkdir()
    recent = f"denidin-prod-backup-{_date_str(5)}.tgz"
    old = f"denidin-prod-backup-{_date_str(45)}.tgz"
    _touch(d, recent)
    _touch(d, old)

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr
    assert (d / recent).exists()
    assert not (d / old).exists()


def test_purge_boundary_exactly_30_days_is_kept(tmp_path):
    d = tmp_path / "daily"
    d.mkdir()
    boundary = f"denidin-prod-backup-{_date_str(30)}.tgz"
    _touch(d, boundary)

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr
    assert (d / boundary).exists(), "exactly 30 days old should be kept, not 'older than 30'"


def test_purge_just_over_30_days_is_deleted(tmp_path):
    d = tmp_path / "daily"
    d.mkdir()
    just_over = f"denidin-prod-backup-{_date_str(31)}.tgz"
    _touch(d, just_over)

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr
    assert not (d / just_over).exists()


def test_purge_ignores_non_matching_filenames(tmp_path):
    d = tmp_path / "daily"
    d.mkdir()
    weird = "not-a-backup.tgz"
    _touch(d, weird)

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr
    assert (d / weird).exists(), "non-matching filenames must never be deleted"


def test_purge_empty_directory_is_noop(tmp_path):
    d = tmp_path / "daily"
    d.mkdir()

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr


def test_purge_missing_directory_is_noop(tmp_path):
    d = tmp_path / "does_not_exist"

    result = _run_purge(d, 30, "days")

    assert result.returncode == 0, result.stderr


def test_purge_monthly_keeps_recent_deletes_old(tmp_path):
    d = tmp_path / "monthly"
    d.mkdir()
    recent = f"denidin-prod-backup-{_date_str(30)}.tgz"  # 1 month ago
    old = f"denidin-prod-backup-{_date_str(37 * 30)}.tgz"  # ~37 months ago
    _touch(d, recent)
    _touch(d, old)

    result = _run_purge(d, 36, "months")

    assert result.returncode == 0, result.stderr
    assert (d / recent).exists()
    assert not (d / old).exists()
