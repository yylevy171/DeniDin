"""Real (non-mocked) tests for run_daily_backup.sh (Feature 078, US1).

Runs the real script against a real scratch fixture tree (fake data/,
config/, logs/prod/ with real tiny SQLite DBs), asserts on the real .tgz it
produces. No unittest.mock, per CONSTITUTION SS I/V.
"""
import json
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_DAILY_BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "run_daily_backup.sh"


def _make_db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    con.execute("INSERT INTO t (val) VALUES ('hello')")
    con.commit()
    con.close()


def _build_fixture_tree(root: Path):
    data = root / "data"
    config = root / "config"
    logs_prod = root / "logs_prod"
    daily = root / "daily_backups"
    monthly = root / "monthly_backups"
    for d in (data, config, logs_prod, daily, monthly):
        d.mkdir(parents=True, exist_ok=True)

    _make_db(data / "sessions" / "chat_index.db")
    _make_db(data / "reminders" / "reminders.db")
    _make_db(data / "memory_rolls" / "roll_markers.db")
    _make_db(data / "memory" / "chroma.sqlite3")
    (data / "events").mkdir(parents=True, exist_ok=True)
    (data / "events" / "A0101250101.json").write_text('{"event": "ordinary file"}')
    (config / "runtime_constitution.md").write_text("# constitution")
    (logs_prod / "denidin.log").write_text("some log line\n")

    config_json = root / "backup_config.json"
    config_json.write_text(json.dumps({
        "data_dir": str(data),
        "config_dir": str(config),
        "logs_prod_dir": str(logs_prod),
        "daily_backup_dir": str(daily),
        "monthly_backup_dir": str(monthly),
    }))
    return {
        "data": data, "config": config, "logs_prod": logs_prod,
        "daily": daily, "monthly": monthly, "config_json": config_json,
    }


def _run(fixture, today, log_dir=None, extra_args=None):
    args = [
        "bash", str(RUN_DAILY_BACKUP_SCRIPT),
        "--config", str(fixture["config_json"]),
        "--today", today,
    ]
    if log_dir:
        args += ["--log-dir", str(log_dir)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def test_produces_correctly_named_archive(tmp_path):
    fixture = _build_fixture_tree(tmp_path)

    result = _run(fixture, "2026-03-15", log_dir=tmp_path / "logs")

    assert result.returncode == 0, result.stderr
    expected = fixture["daily"] / "denidin-prod-backup-2026-03-15.tgz"
    assert expected.exists()


def test_no_partial_file_left_on_success(tmp_path):
    fixture = _build_fixture_tree(tmp_path)

    result = _run(fixture, "2026-03-15", log_dir=tmp_path / "logs")

    assert result.returncode == 0, result.stderr
    partials = list(fixture["daily"].glob("*.partial"))
    assert partials == []


def test_archive_reproduces_ordinary_files_and_db_integrity(tmp_path):
    fixture = _build_fixture_tree(tmp_path)

    result = _run(fixture, "2026-03-15", log_dir=tmp_path / "logs")
    assert result.returncode == 0, result.stderr

    archive = fixture["daily"] / "denidin-prod-backup-2026-03-15.tgz"
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()
    with tarfile.open(archive) as tf:
        tf.extractall(extract_dir)

    # ordinary files reproduced byte-for-byte
    assert (extract_dir / "config" / "runtime_constitution.md").read_text() == "# constitution"
    assert (extract_dir / "data" / "events" / "A0101250101.json").read_text() == '{"event": "ordinary file"}'

    # every .db/.sqlite3 passes integrity_check
    for db_path in extract_dir.rglob("*"):
        if db_path.suffix in (".db",) or db_path.name.endswith(".sqlite3"):
            con = sqlite3.connect(str(db_path))
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            con.close()


def test_missing_config_exits_nonzero(tmp_path):
    result = subprocess.run(
        ["bash", str(RUN_DAILY_BACKUP_SCRIPT), "--config", str(tmp_path / "nope.json"), "--today", "2026-03-15"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0


def test_no_docker_invocation_in_source():
    """research.md R6 / task T008a: static guard that the script never
    INVOKES docker/docker compose as a command - zero-downtime by
    construction, not by luck. Comment/docstring mentions of the word
    'docker' (explaining *why* it's avoided) are fine; only real command
    lines are checked."""
    code_lines = []
    for line in RUN_DAILY_BACKUP_SCRIPT.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        code_lines.append(stripped)
    code_only = "\n".join(code_lines)
    assert "docker compose" not in code_only
    assert "docker " not in code_only
    assert not code_only.rstrip().endswith("docker")


def test_daily_purge_runs_after_successful_backup(tmp_path):
    fixture = _build_fixture_tree(tmp_path)
    old_archive = fixture["daily"] / "denidin-prod-backup-2026-01-01.tgz"
    old_archive.write_text("stale old archive")

    result = _run(fixture, "2026-03-15", log_dir=tmp_path / "logs")

    assert result.returncode == 0, result.stderr
    assert not old_archive.exists(), "backups older than 30 days must be purged after a successful run"


def test_monthly_promotion_on_first_of_month(tmp_path):
    fixture = _build_fixture_tree(tmp_path)

    result = _run(fixture, "2026-04-01", log_dir=tmp_path / "logs")

    assert result.returncode == 0, result.stderr
    assert (fixture["monthly"] / "denidin-prod-backup-2026-04-01.tgz").exists()


def test_no_monthly_promotion_on_non_first_of_month(tmp_path):
    fixture = _build_fixture_tree(tmp_path)

    result = _run(fixture, "2026-04-15", log_dir=tmp_path / "logs")

    assert result.returncode == 0, result.stderr
    assert list(fixture["monthly"].glob("*.tgz")) == []


def test_roll_marker_warning_when_no_committed_marker(tmp_path):
    fixture = _build_fixture_tree(tmp_path)
    # roll_markers.db exists (created by _build_fixture_tree) but has no
    # roll_markers table/rows at all -> should warn, not fail.
    log_dir = tmp_path / "logs"

    result = _run(fixture, "2026-03-15", log_dir=log_dir)

    assert result.returncode == 0, result.stderr
    log_file = log_dir / "run_daily_backup_2026-03-15.log"
    assert "WARNING" in log_file.read_text()


def test_roll_marker_no_warning_when_committed(tmp_path):
    fixture = _build_fixture_tree(tmp_path)
    roll_db = fixture["data"] / "memory_rolls" / "roll_markers.db"
    con = sqlite3.connect(str(roll_db))
    con.execute("CREATE TABLE roll_markers (chat TEXT, date TEXT, status TEXT)")
    con.execute("INSERT INTO roll_markers VALUES ('chat1', '2026-03-14', 'committed')")
    con.commit()
    con.close()
    log_dir = tmp_path / "logs"

    result = _run(fixture, "2026-03-15", log_dir=log_dir)

    assert result.returncode == 0, result.stderr
    log_file = log_dir / "run_daily_backup_2026-03-15.log"
    assert "WARNING" not in log_file.read_text()
