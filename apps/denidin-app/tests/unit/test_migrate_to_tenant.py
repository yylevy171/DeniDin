"""
Unit tests for scripts/migrate_to_tenant.py (Feature 055: Multi-Tenancy, REQ-MIGRATE-001).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 3, T013a: migrates the existing single-tenant deployment's
sessions/memory/events directories into `{data_root}/{tenant_id}/...` (data-model.md's
tenant-scoped data-root layout) — copy-only (never destructive), idempotent, with a
dry-run mode. Location precedent confirmed at `speckit.analyze` (finding A1):
`apps/denidin-app/scripts/` already holds `migrate_stray_ledger_events.py`, a
comparable one-off data-migration script.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.migrate_to_tenant import migrate_tenant_data


def _write_file(path: Path, content: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


TENANT_ID = "b6f1c2a4-0000-0000-0000-000000000001"


class TestMigrateTenantData:
    """Test the core copy-only migration logic."""

    def test_migrates_sessions_memory_and_events(self, tmp_path):
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")
        _write_file(tmp_path / "memory" / "chroma.sqlite3", "memory-data")
        _write_file(tmp_path / "events" / "A010101010001.json", "event-data")

        migrate_tenant_data(tmp_path, TENANT_ID)

        assert (tmp_path / TENANT_ID / "sessions" / "abc" / "session.json").read_text() == (
            "session-data"
        )
        assert (tmp_path / TENANT_ID / "memory" / "chroma.sqlite3").read_text() == "memory-data"
        assert (tmp_path / TENANT_ID / "events" / "A010101010001.json").read_text() == (
            "event-data"
        )

    def test_original_source_directories_are_untouched(self, tmp_path):
        """Copy-only, never destructive — the migration script must never delete or
        move the original data."""
        source_file = tmp_path / "sessions" / "abc" / "session.json"
        _write_file(source_file, "session-data")

        migrate_tenant_data(tmp_path, TENANT_ID)

        assert source_file.exists()
        assert source_file.read_text() == "session-data"

    def test_missing_source_subdirectory_is_skipped_without_error(self, tmp_path):
        """A fresh install might not have an events/ dir yet — that's fine, not an
        error; the other subdirs still migrate."""
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")
        # No memory/ or events/ dirs at all.

        actions = migrate_tenant_data(tmp_path, TENANT_ID)

        assert (tmp_path / TENANT_ID / "sessions" / "abc" / "session.json").exists()
        assert not (tmp_path / TENANT_ID / "memory").exists()
        assert not (tmp_path / TENANT_ID / "events").exists()
        assert any("sessions" in a for a in actions)

    def test_idempotent_second_run_does_not_raise_or_duplicate(self, tmp_path):
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")

        migrate_tenant_data(tmp_path, TENANT_ID)
        # Second run must not raise (e.g. shutil.copytree's "dest exists" error) and
        # must not corrupt/duplicate what's already there.
        migrate_tenant_data(tmp_path, TENANT_ID)

        assert (tmp_path / TENANT_ID / "sessions" / "abc" / "session.json").read_text() == (
            "session-data"
        )

    def test_second_run_reports_already_migrated_not_a_fresh_copy(self, tmp_path):
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")

        migrate_tenant_data(tmp_path, TENANT_ID)
        actions = migrate_tenant_data(tmp_path, TENANT_ID)

        assert any("already migrated" in a.lower() for a in actions)


class TestMigrateTenantDataDryRun:
    """Test dry-run mode: reports the plan, touches nothing."""

    def test_dry_run_does_not_create_target_directory(self, tmp_path):
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")

        migrate_tenant_data(tmp_path, TENANT_ID, dry_run=True)

        assert not (tmp_path / TENANT_ID).exists()

    def test_dry_run_reports_the_planned_actions(self, tmp_path):
        _write_file(tmp_path / "sessions" / "abc" / "session.json", "session-data")
        _write_file(tmp_path / "memory" / "chroma.sqlite3", "memory-data")

        actions = migrate_tenant_data(tmp_path, TENANT_ID, dry_run=True)

        assert any("sessions" in a for a in actions)
        assert any("memory" in a for a in actions)

    def test_dry_run_does_not_touch_source(self, tmp_path):
        source_file = tmp_path / "sessions" / "abc" / "session.json"
        _write_file(source_file, "session-data")

        migrate_tenant_data(tmp_path, TENANT_ID, dry_run=True)

        assert source_file.read_text() == "session-data"
