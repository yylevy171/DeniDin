"""
Unit tests for scripts/migrate_stray_ledger_events.py (Feature 033, US4/REQ-MIGRATE-001).

Tests the migration script's pure splitting/mapping logic and its
write-then-clear behavior, using a FIXTURE session.json (not the real
dev_data file) - per contracts/ledger-event-manager.md's migration-script
contract: build_components() is hardcoded (independent of the session file's
own content), the session file is only read/written for the final
pending_ledger_events clear step.

Revised 2026-07-30 (REQ-DATA-004 + REQ-MIGRATE-001 amendment): real
message_id per component (no longer null), agreement_id/component_id now
populated for the 5 הסכם components, source message files get
ledger_event_ids patched, and notes must never contain migration/process
commentary.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.migrate_stray_ledger_events import (  # noqa: E402
    GILYAN_MESSAGE_ID, MALKA_MESSAGE_ID, SARIT_MESSAGE_ID,
    build_components, run_migration,
)


@pytest.fixture
def fixture_session_file(tmp_path):
    """Mirrors the real stray session's shape (not its exact content - that's
    irrelevant here, see module docstring) - just needs a pending_ledger_events
    key to be clearable."""
    session_file = tmp_path / "session.json"
    session_file.write_text(
        json.dumps({
            "session_id": "4454746c-350a-4fa7-a5ef-fda2c685b0d5",
            "whatsapp_chat": "972522968679@c.us",
            "message_ids": ["some-message-id"],
            "message_counter": 30,
            "created_at": "2026-07-28T10:55:12.317139+00:00",
            "last_active": "2026-07-29T08:21:47.809055+00:00",
            "total_tokens": 1299,
            "transferred_to_longterm": False,
            "storage_path": None,
            "pending_ledger_events": [{"placeholder": "old-shape record"}],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return session_file


@pytest.fixture
def fixture_messages_dir(tmp_path):
    """The 3 real source message files the migration must patch with
    ledger_event_ids - shape mirrors real Message records closely enough for
    the patch (read, add key, write) to exercise real behavior."""
    messages_dir = tmp_path / "messages"
    messages_dir.mkdir()
    for message_id in (GILYAN_MESSAGE_ID, SARIT_MESSAGE_ID, MALKA_MESSAGE_ID):
        (messages_dir / f"{message_id}.json").write_text(
            json.dumps({
                "message_id": message_id,
                "role": "user",
                "content": "placeholder",
                "timestamp": "2026-07-28T11:07:08.265929+00:00",
                "ledger_event_ids": [],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return messages_dir


class TestBuildComponents:
    """T014a: the component-split mapping itself."""

    def test_returns_six_components(self):
        assert len(build_components()) == 6

    def test_gilyan_splits_into_exactly_three_components(self):
        components = build_components()
        gilyan = [c for c in components if c["event"]["client_name"] == "גיליאן דוידיאן"]
        assert len(gilyan) == 3

    def test_gilyan_components_have_correct_amounts(self):
        components = build_components()
        gilyan = [c for c in components if c["event"]["client_name"] == "גיליאן דוידיאן"]
        amounts = sorted(c["event"]["amount"] for c in gilyan)
        assert amounts == ["20,000₪", "30,000₪", "8,000₪"]

    def test_gilyan_components_share_message_id_and_agreement_label(self):
        components = build_components()
        gilyan = [c for c in components if c["event"]["client_name"] == "גיליאן דוידיאן"]
        assert all(c["message_id"] == GILYAN_MESSAGE_ID for c in gilyan)
        assert all(c["event"]["agreement_label"] == "משרד הרווחה" for c in gilyan)

    def test_gilyan_components_have_distinct_component_labels(self):
        components = build_components()
        gilyan = [c for c in components if c["event"]["client_name"] == "גיליאן דוידיאן"]
        labels = {c["event"]["component_label"] for c in gilyan}
        assert len(labels) == 3, "each component must have its own distinct label"

    def test_sarit_splits_into_exactly_two_components(self):
        components = build_components()
        sarit = [
            c for c in components
            if c["event"]["client_name"] == "עו\"ד שרית יוגב ועו\"ד מרדכי רצבגר"
        ]
        assert len(sarit) == 2

    def test_sarit_components_have_correct_amounts(self):
        components = build_components()
        sarit = [
            c for c in components
            if c["event"]["client_name"] == "עו\"ד שרית יוגב ועו\"ד מרדכי רצבגר"
        ]
        amounts = sorted(c["event"]["amount"] for c in sarit)
        assert amounts == ["1,500 ש\"ח כולל מע\"מ", "10,000 ש\"ח כולל מע\"מ"]

    def test_sarit_components_share_message_id_and_agreement_label(self):
        components = build_components()
        sarit = [
            c for c in components
            if c["event"]["client_name"] == "עו\"ד שרית יוגב ועו\"ד מרדכי רצבגר"
        ]
        assert all(c["message_id"] == SARIT_MESSAGE_ID for c in sarit)
        assert all(c["event"]["agreement_label"] == "שירות המילואים" for c in sarit)

    def test_malka_stays_a_single_bank_component(self):
        components = build_components()
        malka = [
            c for c in components
            if c["event"]["client_name"] == "מלכה בן סעדון לירון עו\"ד"
        ]
        assert len(malka) == 1
        assert malka[0]["event"]["source_type"] == "בנק"
        assert malka[0]["event"]["event_subtype"] == "הפקדה"
        assert malka[0]["event"]["amount"] == "₪12,500.00"
        assert malka[0]["message_id"] == MALKA_MESSAGE_ID

    def test_malka_has_no_agreement_or_component_label(self):
        components = build_components()
        malka = [
            c for c in components
            if c["event"]["client_name"] == "מלכה בן סעדון לירון עו\"ד"
        ][0]
        assert malka["event"]["agreement_label"] is None
        assert malka["event"]["component_label"] is None

    def test_all_components_share_the_real_session_and_chat(self):
        components = build_components()
        for c in components:
            assert c["session_id"] == "4454746c-350a-4fa7-a5ef-fda2c685b0d5"
            assert c["whatsapp_chat"] == "972522968679@c.us"
            assert c["sender"] == "972522968679@c.us"

    def test_no_component_has_replaces_hint(self):
        """None of the 3 original records had replaces_hint - so no split
        component should end up with replaced_event_id='צריך למצוא'."""
        components = build_components()
        assert all(c["event"]["replaces_hint"] is None for c in components)

    def test_no_component_notes_contain_migration_process_commentary(self):
        """notes is real business content a human reviewer reads - it must
        never carry engineering/migration metadata about Feature 033 itself."""
        components = build_components()
        for c in components:
            notes = c["event"]["notes"] or ""
            assert "033" not in notes
            assert "Feature" not in notes
            assert "פוצל" not in notes, "no 'was split' migration commentary"


class TestRunMigration:
    """T014a: write-then-clear behavior, via the same LedgerEventManager code
    path live captures use (never a direct file write)."""

    def test_dry_run_writes_nothing_and_does_not_clear_session_file(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        exit_code = run_migration(
            fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=True
        )

        assert exit_code == 0
        assert not events_dir.exists()
        with fixture_session_file.open(encoding="utf-8") as f:
            data = json.load(f)
        assert "pending_ledger_events" in data

    def test_real_run_writes_six_files_via_ledger_event_manager(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        exit_code = run_migration(
            fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False
        )

        assert exit_code == 0
        files = list(events_dir.glob("*.json"))
        assert len(files) == 6

    def test_real_run_all_events_have_real_message_id(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        expected_ids = {GILYAN_MESSAGE_ID, SARIT_MESSAGE_ID, MALKA_MESSAGE_ID}
        for f in events_dir.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["message_id"] in expected_ids

    def test_real_run_gilyan_components_share_one_agreement_id(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        gilyan_agreement_ids = set()
        for f in events_dir.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if data["client_name"] == "גיליאן דוידיאן":
                gilyan_agreement_ids.add(data["agreement_id"])
        assert len(gilyan_agreement_ids) == 1
        assert None not in gilyan_agreement_ids

    def test_real_run_sarit_components_share_one_agreement_id_distinct_from_gilyan(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        by_client = {}
        for f in events_dir.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            by_client.setdefault(data["client_name"], set()).add(data["agreement_id"])

        sarit_ids = by_client["עו\"ד שרית יוגב ועו\"ד מרדכי רצבגר"]
        gilyan_ids = by_client["גיליאן דוידיאן"]
        assert len(sarit_ids) == 1
        assert sarit_ids != gilyan_ids

    def test_real_run_malka_has_no_agreement_or_component_id(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        for f in events_dir.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if data["client_name"] == "מלכה בן סעדון לירון עו\"ד":
                assert data["agreement_id"] is None
                assert data["component_id"] is None

    def test_real_run_component_ids_are_distinct_within_shared_agreement(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        gilyan_component_ids = set()
        for f in events_dir.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if data["client_name"] == "גיליאן דוידיאן":
                gilyan_component_ids.add(data["component_id"])
        assert len(gilyan_component_ids) == 3

    def test_real_run_patches_source_message_files_with_ledger_event_ids(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        gilyan_message = json.loads(
            (fixture_messages_dir / f"{GILYAN_MESSAGE_ID}.json").read_text(encoding="utf-8")
        )
        assert len(gilyan_message["ledger_event_ids"]) == 3

        sarit_message = json.loads(
            (fixture_messages_dir / f"{SARIT_MESSAGE_ID}.json").read_text(encoding="utf-8")
        )
        assert len(sarit_message["ledger_event_ids"]) == 2

        malka_message = json.loads(
            (fixture_messages_dir / f"{MALKA_MESSAGE_ID}.json").read_text(encoding="utf-8")
        )
        assert len(malka_message["ledger_event_ids"]) == 1

    def test_real_run_clears_pending_ledger_events_from_session_file(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        with fixture_session_file.open(encoding="utf-8") as f:
            data = json.load(f)
        assert "pending_ledger_events" not in data
        # everything else in the session file must be untouched
        assert data["session_id"] == "4454746c-350a-4fa7-a5ef-fda2c685b0d5"
        assert data["message_counter"] == 30

    def test_event_ids_follow_the_real_letter_and_local_time_scheme(
        self, fixture_session_file, fixture_messages_dir, tmp_path
    ):
        events_dir = tmp_path / "events"
        run_migration(fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False)

        event_ids = {f.stem for f in events_dir.glob("*.json")}
        # 5 הסכם components -> A prefix, 1 בנק component -> B prefix
        assert sum(1 for e in event_ids if e.startswith("A")) == 5
        assert sum(1 for e in event_ids if e.startswith("B")) == 1

    def test_failed_component_aborts_and_does_not_clear_session_file(
        self, fixture_session_file, fixture_messages_dir, tmp_path, monkeypatch
    ):
        """If any component fails to persist (REQ-ID-003's rare exhaustion case),
        the script MUST NOT clear pending_ledger_events - never leave the source
        data half-migrated-and-deleted."""
        from src.managers import ledger_event_manager as lem_module

        original = lem_module.LedgerEventManager.add_ledger_event
        call_count = {"n": 0}

        def flaky_add_ledger_event(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                return None
            return original(self, *args, **kwargs)

        monkeypatch.setattr(
            lem_module.LedgerEventManager, "add_ledger_event", flaky_add_ledger_event
        )

        events_dir = tmp_path / "events"
        exit_code = run_migration(
            fixture_session_file, str(events_dir), fixture_messages_dir, dry_run=False
        )

        assert exit_code == 1
        with fixture_session_file.open(encoding="utf-8") as f:
            data = json.load(f)
        assert "pending_ledger_events" in data, "must not clear on partial failure"
