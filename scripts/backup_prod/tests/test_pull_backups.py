"""Real (non-mocked) tests for pull_backups.sh (Feature 078, US2/US5).

Real rsync subprocess calls throughout. The real SSH branch has no
automated coverage here (documented gap, same as register_prober_schedule.sh's
schtasks.exe branch) - these tests use ssh_host_alias="LOCAL_TEST", which
makes pull_backups.sh treat the "remote" side as a plain local path so the
real rsync/purge logic still gets real, non-mocked coverage without needing
passwordless SSH to an arbitrary host inside a sandboxed test runner. The
one true-unreachable-host case below uses a real (non-existent) hostname -
still no mocking, just a real DNS/connect failure.
"""
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PULL_BACKUPS_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "pull_backups.sh"


def _build_fixture(tmp_path, ssh_host_alias="LOCAL_TEST"):
    win_daily = tmp_path / "win_daily"
    win_monthly = tmp_path / "win_monthly"
    mac_daily = tmp_path / "mac_daily"
    mac_monthly = tmp_path / "mac_monthly"
    win_daily.mkdir()
    win_monthly.mkdir()

    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "daily_backup_dir": str(win_daily),
        "monthly_backup_dir": str(win_monthly),
        "mac_daily_backup_dir": str(mac_daily),
        "mac_monthly_backup_dir": str(mac_monthly),
        "ssh_host_alias": ssh_host_alias,
    }))
    return {
        "win_daily": win_daily, "win_monthly": win_monthly,
        "mac_daily": mac_daily, "mac_monthly": mac_monthly, "config": config,
    }


def _run(fixture, today="2026-03-15"):
    return subprocess.run(
        ["bash", str(PULL_BACKUPS_SCRIPT), "--config", str(fixture["config"]), "--today", today],
        capture_output=True, text=True, timeout=30,
    )


def _date_str(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_pulls_several_new_archives_at_once(tmp_path):
    """Simulates a Mac that was asleep for days - several archives pile up
    on the Windows side and all get pulled in one run."""
    fixture = _build_fixture(tmp_path)
    names = [f"denidin-prod-backup-{_date_str(d)}.tgz" for d in (3, 2, 1, 0)]
    for name in names:
        (fixture["win_daily"] / name).write_text("archive contents")

    result = _run(fixture, today=_date_str(0))

    assert result.returncode == 0, result.stderr
    for name in names:
        assert (fixture["mac_daily"] / name).exists()


def test_zero_new_files_is_noop(tmp_path):
    fixture = _build_fixture(tmp_path)

    result = _run(fixture, today="2026-03-15")

    assert result.returncode == 0, result.stderr
    assert list(fixture["mac_daily"].glob("*.tgz")) == []


def test_partial_file_never_pulled(tmp_path):
    fixture = _build_fixture(tmp_path)
    (fixture["win_daily"] / "denidin-prod-backup-2026-03-15.tgz.partial").write_text("mid-write")

    result = _run(fixture, today="2026-03-15")

    assert result.returncode == 0, result.stderr
    assert list(fixture["mac_daily"].glob("*")) == [], "a .tgz.partial file must never be pulled"


def test_unreachable_host_fails_and_leaves_dest_untouched(tmp_path):
    fixture = _build_fixture(tmp_path, ssh_host_alias="this-host-definitely-does-not-exist-078.invalid")
    (fixture["win_daily"] / "denidin-prod-backup-2026-03-15.tgz").write_text("archive contents")

    result = _run(fixture, today="2026-03-15")

    assert result.returncode != 0
    assert not (fixture["mac_daily"] / "denidin-prod-backup-2026-03-15.tgz").exists()


def test_local_retention_purge_after_pull(tmp_path):
    fixture = _build_fixture(tmp_path)
    old_name = f"denidin-prod-backup-{_date_str(45)}.tgz"
    (fixture["win_daily"] / old_name).write_text("stale archive")

    result = _run(fixture, today=_date_str(0))

    assert result.returncode == 0, result.stderr
    assert not (fixture["mac_daily"] / old_name).exists(), "pulled-then-stale archives must be purged locally too"


def test_monthly_tier_pulled_too(tmp_path):
    fixture = _build_fixture(tmp_path)
    name = "denidin-prod-backup-2026-04-01.tgz"
    (fixture["win_monthly"] / name).write_text("monthly archive")

    result = _run(fixture, today="2026-04-15")

    assert result.returncode == 0, result.stderr
    assert (fixture["mac_monthly"] / name).exists()
