"""Real (non-mocked) tests for verify_restore.sh (Feature 078, US3).

Real un-tar + real sqlite3 PRAGMA integrity_check against real fixture
archives - no unittest.mock. The boot-check smoke test (docker compose
against an ephemeral override) is intentionally NOT covered here - see
verify_restore.sh's own header comment for why (a documented, accepted
manual-only gap, same as this repo's other real-environment-dependent
scripts).
"""
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFY_RESTORE_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "verify_restore.sh"


def _make_db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    con.execute("INSERT INTO t (val) VALUES ('hello')")
    con.commit()
    con.close()


def _make_archive(tmp_path, name, build_fn):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    build_fn(src_dir)
    archive = tmp_path / name
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src_dir, arcname=".")
    return archive


def _run(archive):
    return subprocess.run(
        ["bash", str(VERIFY_RESTORE_SCRIPT), str(archive)],
        capture_output=True, text=True, timeout=30,
    )


def test_healthy_archive_passes(tmp_path):
    def build(src_dir):
        _make_db(src_dir / "data" / "sessions" / "chat_index.db")
        _make_db(src_dir / "data" / "reminders" / "reminders.db")

    archive = _make_archive(tmp_path, "good.tgz", build)

    result = _run(archive)

    assert result.returncode == 0, result.stderr
    assert "PASS: data/sessions/chat_index.db" in result.stdout
    assert "PASS: data/reminders/reminders.db" in result.stdout
    assert "All SQLite stores passed" in result.stdout


def test_corrupted_db_fails_and_names_the_store(tmp_path):
    def build(src_dir):
        _make_db(src_dir / "data" / "sessions" / "chat_index.db")
        corrupt = src_dir / "data" / "reminders" / "reminders.db"
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_bytes(b"this is not a valid sqlite database file at all")

    archive = _make_archive(tmp_path, "bad.tgz", build)

    result = _run(archive)

    assert result.returncode != 0
    assert "PASS: data/sessions/chat_index.db" in result.stdout
    assert "FAIL: data/reminders/reminders.db" in result.stdout


def test_missing_archive_exits_nonzero(tmp_path):
    result = _run(tmp_path / "does_not_exist.tgz")

    assert result.returncode != 0


def test_archive_with_no_db_files_warns_but_does_not_fail(tmp_path):
    def build(src_dir):
        (src_dir / "config").mkdir()
        (src_dir / "config" / "runtime_constitution.md").write_text("# constitution")

    archive = _make_archive(tmp_path, "no_dbs.tgz", build)

    result = _run(archive)

    assert result.returncode == 0, result.stderr
    assert "WARNING: no .db/.sqlite3 files found" in result.stdout
