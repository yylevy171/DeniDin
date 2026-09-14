"""Real (non-mocked) tests for lib/sqlite_backup.sh (Feature 078).

Exercises the actual claim from research.md R2: `.backup` is safe against a
concurrently writing process. A real background thread hammers inserts into
a real SQLite DB while the real sqlite3 CLI backs it up - no mocking.
"""
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SQLITE_BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "lib" / "sqlite_backup.sh"


def _run_backup(src, dest):
    script = f"""
set -e
source "{SQLITE_BACKUP_SCRIPT}"
backup_sqlite_db "{src}" "{dest}"
"""
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)


def _make_db(path: Path, rows: int = 100):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    con.executemany("INSERT INTO t (val) VALUES (?)", [(f"row{i}",) for i in range(rows)])
    con.commit()
    con.close()


def _integrity_ok(path: Path) -> bool:
    con = sqlite3.connect(str(path))
    result = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
    return result == "ok"


def test_backup_simple_db(tmp_path):
    src = tmp_path / "src.db"
    dest = tmp_path / "dest.db"
    _make_db(src, rows=50)

    result = _run_backup(src, dest)

    assert result.returncode == 0, result.stderr
    assert dest.exists()
    assert _integrity_ok(dest)
    con = sqlite3.connect(str(dest))
    count = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    con.close()
    assert count == 50


def test_backup_missing_source(tmp_path):
    src = tmp_path / "does_not_exist.db"
    dest = tmp_path / "dest.db"

    result = _run_backup(src, dest)

    assert result.returncode != 0
    assert not dest.exists()


def test_backup_creates_dest_parent_dir(tmp_path):
    src = tmp_path / "src.db"
    dest = tmp_path / "nested" / "sub" / "dest.db"
    _make_db(src, rows=5)

    result = _run_backup(src, dest)

    assert result.returncode == 0, result.stderr
    assert dest.exists()


def test_backup_safe_under_concurrent_writes(tmp_path):
    """The claim research.md R2 relies on: .backup produces a consistent
    snapshot even while another process is actively writing."""
    src = tmp_path / "src.db"
    dest = tmp_path / "dest.db"
    _make_db(src, rows=10)

    stop_flag = threading.Event()
    errors = []

    def writer():
        try:
            con = sqlite3.connect(str(src), timeout=5)
            i = 0
            while not stop_flag.is_set():
                con.execute("INSERT INTO t (val) VALUES (?)", (f"concurrent{i}",))
                con.commit()
                i += 1
                time.sleep(0.005)
            con.close()
        except Exception as e:  # pragma: no cover - surfaced via errors list
            errors.append(e)

    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    time.sleep(0.05)  # let the writer get going first

    result = _run_backup(src, dest)

    stop_flag.set()
    writer_thread.join(timeout=5)

    assert not errors, f"writer thread errored: {errors}"
    assert result.returncode == 0, result.stderr
    assert dest.exists()
    assert _integrity_ok(dest), "backup taken during concurrent writes must still be consistent"
