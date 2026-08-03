"""
Unit tests for LedgerEventManager (Feature 033: Ledger Event Persistence).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 2 (T002a-T006a): core file persistence, event_id generation
(local-time conversion, per-letter-per-minute seq collision handling), amount
normalization, replaced/reference placeholder logic, and reserved-null fields.

See specs/in-progress/033-ledger-event-persistence/data-model.md for the full
field list and specs/in-progress/033-ledger-event-persistence/spec.md for the
Clarifications this behavior derives from.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.managers.ledger_event_manager import LedgerEventManager, is_incomplete_capture

# Raw arguments shape capture_ledger_event's LEDGER_EVENT_TOOL always produces
# (19 keys as of 2026-07-30, ai_handler.py - added agreement_label/component_label
# [REQ-DATA-004], txn_date [REQ-DATA-005, unified from hours_date/transaction_date
# same day]). Not every test needs every field non-null.
SAMPLE_EVENT = {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "ישראל ישראלי",
    "payer_name": None,
    "description": "כתב הגנה",
    "amount": "5,000₪",
    "percent": None,
    "percent_base": None,
    "hours": None,
    "hourly_rate": None,
    "txn_date": None,
    "vat_status": "לא צוין",
    "replaces_hint": None,
    "reference_hint": None,
    "notes": None,
    "raw_message_excerpt": "ישראל ישראלי 5,000₪ כתב הגנה",
    "agreement_label": "תיק בדיקה",
    "component_label": "בסיס",
}

CSV_MAPPED_FIELDS = {
    "event_id", "event_date", "event_time", "source_type", "event_subtype",
    "client_name", "payer_name", "description", "amount", "replaced_event_id",
    "reference", "notes", "agreement_id", "component_id", "component_label",
    "trigger_condition", "percent", "percent_base", "hours", "hourly_rate",
    "txn_date", "vat_status", "split_partner", "split_percent",
    "due_date", "invoice_status", "invoice_number", "invoice_type",
    "morning_document_id", "invoice_actual_creation_date",
}
INTERNAL_FIELDS = {
    "session_id", "whatsapp_chat", "message_id", "message_timestamp",
    "sender", "captured_at", "raw_message_excerpt", "replaces_hint",
    "reference_hint", "agreement_label",
}
RESERVED_NULL_FIELDS = [
    "trigger_condition", "split_partner", "split_percent", "due_date",
    "invoice_status", "invoice_number", "invoice_type",
    "morning_document_id", "invoice_actual_creation_date",
]

# 2026-07-28T11:06:58+00:00 UTC -> Asia/Jerusalem local (UTC+3, Israel DST in July)
# -> 2026-07-28 14:06:58 local -> event_id date/time portion "280726"+"1406"
FIXED_TS = int(datetime(2026, 7, 28, 11, 6, 58, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def temp_events_dir(tmp_path):
    return tmp_path / "events"


@pytest.fixture
def manager(temp_events_dir):
    return LedgerEventManager(storage_dir=str(temp_events_dir))


def _read(temp_events_dir, event_id):
    with (temp_events_dir / f"{event_id}.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestLedgerEventManagerCore:
    """T002a: storage dir creation, basic file-write behavior."""

    def test_storage_dir_created_on_init(self, temp_events_dir):
        assert not temp_events_dir.exists()
        LedgerEventManager(storage_dir=str(temp_events_dir))
        assert temp_events_dir.exists()

    def test_add_ledger_event_writes_file_named_by_event_id(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS, sender="972500000000@c.us",
        )
        assert event_id is not None
        assert (temp_events_dir / f"{event_id}.json").exists()

    def test_written_file_has_exactly_the_30_csv_fields_plus_10_internal_fields(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS, sender="972500000000@c.us",
        )
        data = _read(temp_events_dir, event_id)
        assert set(data.keys()) == CSV_MAPPED_FIELDS | INTERNAL_FIELDS

    def test_file_is_alphabetized_utf8_no_ascii_escaping(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS, sender="972500000000@c.us",
        )
        raw = (temp_events_dir / f"{event_id}.json").read_text(encoding="utf-8")
        assert "ישראל ישראלי" in raw, "Hebrew must not be \\u-escaped (ensure_ascii=False)"
        data = json.loads(raw)
        assert list(data.keys()) == sorted(data.keys())

    def test_input_event_dict_not_mutated(self, manager):
        event = dict(SAMPLE_EVENT)
        original = dict(event)
        manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=event, message_id="msg-1",
            message_timestamp=FIXED_TS, sender="972500000000@c.us",
        )
        assert event == original

    def test_direct_mapped_fields_populated_verbatim(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS, sender="972500000000@c.us",
        )
        data = _read(temp_events_dir, event_id)
        assert data["source_type"] == "הסכם"
        assert data["event_subtype"] == "יצירה"
        assert data["client_name"] == "ישראל ישראלי"
        assert data["description"] == "כתב הגנה"
        assert data["vat_status"] == "לא צוין"
        assert data["session_id"] == "sess-1"
        assert data["whatsapp_chat"] == "972500000000@c.us"
        assert data["message_id"] == "msg-1"
        assert data["sender"] == "972500000000@c.us"
        assert data["raw_message_excerpt"] == SAMPLE_EVENT["raw_message_excerpt"]


class TestEventIdGeneration:
    """T003a: event_id format, local-time conversion, per-letter-per-minute seq."""

    def test_source_type_agreement_gets_A_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert event_id.startswith("A")

    def test_source_type_bank_gets_B_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert event_id.startswith("B")

    def test_date_time_converted_to_asia_jerusalem_local(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert event_id == "A28072614060"

    def test_event_date_and_event_time_fields_match_local_conversion(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_date"] == "28/07/2026"
        assert data["event_time"] == "14:06"

    def test_first_event_for_new_minute_gets_seq_0(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert event_id.endswith("0")

    def test_second_event_same_minute_gets_seq_1(self, manager):
        first = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS, sender="w",
        )
        second = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS, sender="w",
        )
        assert first == "A28072614060"
        assert second == "A28072614061"

    def test_seq_scoped_per_letter_not_shared_across_letters(self, manager):
        agreement_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m1", message_timestamp=FIXED_TS, sender="w",
        )
        bank_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m2", message_timestamp=FIXED_TS, sender="w",
        )
        assert agreement_id == "A28072614060"
        assert bank_id == "B28072614060", "different letter must not share the other's seq counter"

    def test_collision_check_never_reads_events_csv(self, manager, monkeypatch):
        original_open = Path.open
        opened_paths = []

        def spy_open(self, *args, **kwargs):
            opened_paths.append(str(self))
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", spy_open)
        manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert not any("Events.csv" in p for p in opened_paths)

    def test_eleventh_event_same_minute_returns_none_and_logs_error(self, manager, caplog):
        for i in range(10):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id=f"m{i}", message_timestamp=FIXED_TS, sender="w",
            )
            assert event_id is not None

        with caplog.at_level(logging.ERROR):
            eleventh = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id="m10", message_timestamp=FIXED_TS, sender="w",
            )

        assert eleventh is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_eleventh_event_does_not_overwrite_the_seq9_file(self, manager, temp_events_dir):
        for i in range(10):
            manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, client_name=f"client-{i}"),
                message_id=f"m{i}", message_timestamp=FIXED_TS, sender="w",
            )
        seq9_file = temp_events_dir / "A28072614069.json"
        before = seq9_file.read_text(encoding="utf-8")

        manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, client_name="eleventh-client"),
            message_id="m10", message_timestamp=FIXED_TS, sender="w",
        )

        assert seq9_file.read_text(encoding="utf-8") == before
        assert not (temp_events_dir / "A280726140610.json").exists()

    def test_none_message_timestamp_falls_back_and_logs_warning(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id="m", message_timestamp=None, sender="w",
            )
        assert event_id is not None
        data = _read(temp_events_dir, event_id)
        assert data["message_timestamp"] is None, "the hard pointer is genuinely unknown, must stay None"
        assert data["event_date"] is not None
        assert data["event_time"] is not None
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestAmountNormalization:
    """T004a: code-side amount parsing (never AI math)."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("8,000₪", 8000),
            ("-7,000", -7000),
            ("₪12,500.00", 12500),
            ('1,500 ש"ח', 1500),
            (None, None),
        ],
    )
    def test_amount_normalized(self, manager, temp_events_dir, raw, expected):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT, amount=raw),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["amount"] == expected

    def test_unparseable_amount_left_blank_original_kept_in_notes_and_warning_logged(
        self, manager, temp_events_dir, caplog
    ):
        raw = "8,000₪; 20,000₪; עוד 30,000₪"
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, amount=raw, notes=None),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        data = _read(temp_events_dir, event_id)
        assert data["amount"] is None
        assert raw in (data["notes"] or "")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unparseable_amount_appends_to_existing_notes_not_overwrite(self, manager, temp_events_dir):
        raw = "8,000₪; 20,000₪"
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, amount=raw, notes="original note text"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert "original note text" in data["notes"]
        assert raw in data["notes"]


class TestHoursNormalization:
    """REQ-DATA-009 (added 2026-08-02, user directive: "hours should always be
    numerical") - code-side hours parsing (never AI math/word-form verbatim),
    same discipline as TestAmountNormalization above."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("4", 4.0),
            ("2.5", 2.5),
            ("3 שעות", 3.0),
            ("שעה", 1.0),
            ("שעתיים", 2.0),
            ("שלוש שעות", 3.0),
            ("עשר שעות", 10.0),
            ("חצי שעה", 0.5),
            ("רבע שעה", 0.25),
            ("שעה וחצי", 1.5),
            ("שלוש שעות וחצי", 3.5),
            (None, None),
        ],
    )
    def test_hours_normalized(self, manager, temp_events_dir, raw, expected):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28" if raw else None),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == expected

    def test_unparseable_hours_left_blank_original_kept_in_notes_and_warning_logged(
        self, manager, temp_events_dir, caplog
    ):
        raw = "כמה שעות שיידרשו"
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", notes=None),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] is None
        assert raw in (data["notes"] or "")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unparseable_hours_appends_to_existing_notes_not_overwrite(self, manager, temp_events_dir):
        raw = "כמה שעות שיידרשו"
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", notes="original note text"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert "original note text" in data["notes"]
        assert raw in data["notes"]


class TestReplacedEventAndReferencePlaceholders:
    """T005a: REQ-DATA-002."""

    def test_replaces_hint_present_sets_replaced_event_id_placeholder(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, replaces_hint="correction to prior arrangement"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["replaced_event_id"] == "צריך למצוא"

    def test_replaces_hint_absent_leaves_replaced_event_id_blank(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, replaces_hint=None),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["replaced_event_id"] is None

    def test_reference_always_blank_regardless_of_reference_hint(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="משרד הרווחה"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] is None

    def test_reference_hint_itself_still_preserved_as_internal_field(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="משרד הרווחה"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference_hint"] == "משרד הרווחה"


class TestReservedNullFields:
    """T006a: REQ-DATA-003 — nuances-feature and invoice-linkage fields, always null,
    always present as keys. (Revised 2026-07-30: agreement_id/component_id/
    component_label moved OUT of this list to TestAgreementAndComponentIds below,
    per REQ-DATA-004.)"""

    def test_all_reserved_fields_always_null(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        for field in RESERVED_NULL_FIELDS:
            assert field in data, f"{field} must be present as a key, never omitted"
            assert data[field] is None, f"{field} must be null in this feature"


class TestAgreementAndComponentIds:
    """T006b (added 2026-07-30): REQ-DATA-004 — agreement_id/component_id
    generation, matching the real Events.csv convention, with the user's hard
    consistency requirement (byte-for-byte identical across a batch, guaranteed
    by construction, never by trusting repeated AI text)."""

    def test_agreement_event_gets_non_null_agreement_id_and_component_id(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is not None
        assert data["component_id"] is not None

    def test_bank_event_has_null_agreement_component_id_and_labels(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is None
        assert data["component_id"] is None
        assert data["component_label"] is None
        assert data["agreement_label"] is None

    def test_agreement_id_matches_real_csv_format(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, client_name="אתי אסולין", agreement_label="ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        # FIXED_TS -> 28/07/2026 local -> MMYY "0726"
        assert data["agreement_id"] == "0726-אתי_אסולין-ערעור_לארצי"

    def test_component_id_is_agreement_id_plus_slugified_component_label(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, component_label="עדכון - ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["component_id"] == f"{data['agreement_id']}-עדכון_ערעור_לארצי"

    def test_standalone_call_without_explicit_agreement_id_derives_its_own(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        expected = manager.build_agreement_id("ישראל ישראלי", "תיק בדיקה", FIXED_TS)
        assert data["agreement_id"] == expected

    def test_caller_supplied_agreement_id_used_as_is_for_batch_consistency(
        self, manager, temp_events_dir
    ):
        """The user's hard requirement: when a caller (AIHandler batching multiple
        components of one agreement) supplies agreement_id explicitly, it MUST be
        used verbatim - even if this component's own agreement_label differs
        slightly from what would've been derived standalone. Consistency is
        structural, never dependent on the AI repeating identical text."""
        explicit_id = "0726-custom-batch-id"
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, agreement_label="a slightly different label"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
            agreement_id=explicit_id,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] == explicit_id

    def test_multiple_components_sharing_caller_supplied_agreement_id_are_identical(
        self, manager, temp_events_dir
    ):
        shared_id = manager.build_agreement_id("גיליאן דוידיאן", "משרד הרווחה", FIXED_TS)
        ids = []
        for i in range(3):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, client_name="גיליאן דוידיאן", component_label=f"רכיב {i}"),
                message_id=f"m{i}", message_timestamp=FIXED_TS, sender="w",
                agreement_id=shared_id,
            )
            ids.append(_read(temp_events_dir, event_id)["agreement_id"])
        assert len(set(ids)) == 1, "every component of the same batch must share one identical agreement_id"
        assert ids[0] == shared_id

    def test_build_agreement_id_is_pure_and_deterministic(self, manager):
        first = manager.build_agreement_id("ישראל ישראלי", "תיק בדיקה", FIXED_TS)
        second = manager.build_agreement_id("ישראל ישראלי", "תיק בדיקה", FIXED_TS)
        assert first == second

    def test_component_label_populated_verbatim_for_agreement_events(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, component_label="שעות עבודה"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["component_label"] == "שעות עבודה"


class TestTxnDate:
    """T006c/T006e (added 2026-07-30, unified same day - see spec.md Clarifications):
    REQ-DATA-005 - תאריך_ביצוע, code-normalized from the AI-resolved ISO-8601 txn_date.
    One field, two populating cases: (1) an hourly work-log component's worked-date
    (required whenever hours is set), (2) a בנק component's own stated transaction/
    value date (always optional). Both distinct from event_date (message-arrival date)."""

    def test_txn_date_normalized_from_iso_to_ddmmyyyy(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-29"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "29/07/2026"

    def test_txn_date_null_when_hours_null(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours=None, txn_date=None),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] is None
        assert data["txn_date"] is None

    def test_txn_date_distinct_from_event_date_for_hours_case(self, manager, temp_events_dir):
        """The whole point of REQ-DATA-005: hours worked "אתמול" (yesterday) must be
        able to carry a DIFFERENT date than event_date (the message's own arrival
        date, derived from FIXED_TS = 28/07/2026 local)."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-27"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_date"] == "28/07/2026"
        assert data["txn_date"] == "27/07/2026"
        assert data["txn_date"] != data["event_date"]

    def test_hours_set_but_txn_date_missing_leaves_blank_and_logs_warning(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, hours="4", txn_date=None),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == 4.0
        assert data["txn_date"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_hours_set_but_txn_date_unparseable_leaves_blank_and_logs_warning(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, hours="4", txn_date="אתמול"),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_hours_word_form_normalized_to_number(self, manager, temp_events_dir):
        """REQ-DATA-009 (added 2026-08-02): hours must always be numerical when
        populated - a Hebrew word form like 'שעתיים' is not persisted verbatim."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours="שעתיים", txn_date="2026-07-28"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == 2.0

    def test_txn_date_normalized_for_bank_transaction_date(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "26/07/2026"

    def test_txn_date_distinct_from_event_date_for_bank_case(self, manager, temp_events_dir):
        """A screenshot forwarded a day after the actual deposit must be able to carry
        a txn_date DIFFERENT from event_date (derived from FIXED_TS = 28/07/2026
        local, the message's own arrival time)."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_date"] == "28/07/2026"
        assert data["txn_date"] == "26/07/2026"
        assert data["txn_date"] != data["event_date"]

    def test_txn_date_null_by_default_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק"),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None

    def test_txn_date_unparseable_for_bank_event_leaves_blank_and_logs_warning(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="אתמול"),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)


# A `capture_ledger_event` call's raw arguments (2026-07-30 components-array
# redesign) - agreement-level fields top-level, per-component fields nested.
SAMPLE_CALL_ARGUMENTS = {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "ישראל ישראלי",
    "payer_name": None,
    "agreement_label": "תיק בדיקה",
    "replaces_hint": None,
    "reference_hint": None,
    "raw_message_excerpt": "ישראל ישראלי - הצעת שכר טרחה",
    "component_count": 1,
    "components": [
        {
            "component_label": "בסיס",
            "description": "כתב הגנה",
            "amount": "5,000₪",
            "percent": None,
            "percent_base": None,
            "hours": None,
            "hourly_rate": None,
            "txn_date": None,
            "vat_status": "לא צוין",
            "notes": None,
        },
    ],
}


class TestIsIncompleteCapture:
    """REQ-DATA-008 (added 2026-08-02): the shared empty-components/count-mismatch
    detector used both by AIHandler.capture_ledger_events_from_text (retry trigger)
    and LedgerEventManager.add_ledger_events_from_call (fallback trigger)."""

    def test_empty_components_is_incomplete(self):
        assert is_incomplete_capture({"components": [], "component_count": 0}) is True

    def test_missing_components_key_is_incomplete(self):
        assert is_incomplete_capture({"component_count": 1}) is True

    def test_matching_count_is_not_incomplete(self):
        assert is_incomplete_capture(
            {"components": [{"a": 1}, {"a": 2}], "component_count": 2}
        ) is False

    def test_mismatched_count_is_incomplete(self):
        assert is_incomplete_capture(
            {"components": [{"a": 1}], "component_count": 3}
        ) is True

    def test_missing_component_count_with_nonempty_components_is_not_incomplete(self):
        """No component_count to compare against - can't detect a mismatch, but a
        non-empty components list is still a valid-looking capture on its own."""
        assert is_incomplete_capture({"components": [{"a": 1}]}) is False


class TestAddLedgerEventsFromCall:
    """T006d (added 2026-07-30): LedgerEventManager.add_ledger_events_from_call -
    REQ-DATA-004's components-array redesign. Replaces relying on the model
    choosing to invoke capture_ledger_event N times (proven unreliable even with a
    materially stronger model - see spec.md's Clarifications) with one call whose
    `components` array carries all of one agreement's components."""

    def test_single_component_persists_one_event(self, manager, temp_events_dir):
        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["client_name"] == "ישראל ישראלי"
        assert data["description"] == "כתב הגנה"
        assert data["amount"] == 5000
        assert data["component_label"] == "בסיס"

    def test_multiple_components_all_persisted_sharing_one_agreement_id(
        self, manager, temp_events_dir
    ):
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS, component_count=3)
        call_arguments["components"] = [
            dict(SAMPLE_CALL_ARGUMENTS["components"][0]),
            dict(SAMPLE_CALL_ARGUMENTS["components"][0], component_label="שלב שני", amount="2,000₪"),
            dict(SAMPLE_CALL_ARGUMENTS["components"][0], component_label="שלב שלישי", amount="8,000₪"),
        ]

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )

        assert len(event_ids) == 3
        records = [_read(temp_events_dir, eid) for eid in event_ids]
        agreement_ids = {r["agreement_id"] for r in records}
        component_ids = {r["component_id"] for r in records}
        assert None not in agreement_ids
        assert len(agreement_ids) == 1, "all components of one call must share one agreement_id"
        assert len(component_ids) == 3, "component_id must differ per component"
        amounts = sorted(r["amount"] for r in records)
        assert amounts == [2000, 5000, 8000]

    def test_bank_event_component_has_null_agreement_and_component_id(
        self, manager, temp_events_dir
    ):
        call_arguments = {
            "source_type": "בנק", "event_subtype": "הפקדה",
            "client_name": None, "payer_name": None,
            "agreement_label": None, "replaces_hint": None, "reference_hint": None,
            "raw_message_excerpt": "הפקדה בסך 9,440 ₪",
            "component_count": 1,
            "components": [{
                "component_label": None, "description": "הפקדה", "amount": "9,440₪",
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None, "vat_status": "לא צוין",
                "notes": None,
            }],
        }

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )

        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["source_type"] == "בנק"
        assert data["agreement_id"] is None
        assert data["component_id"] is None
        assert data["amount"] == 9440

    def test_empty_components_list_persists_one_flagged_fallback_event(
        self, manager, temp_events_dir, caplog
    ):
        """REQ-DATA-008 (added 2026-08-02, real billed incident 2026-07-31): an empty
        components array must never silently persist nothing - that's exactly the
        Mor ben-Shaya failure (1 call, 0 persisted, 0 errors logged). Must persist
        exactly one flagged fallback record and log an ERROR."""
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS, components=[])
        with caplog.at_level(logging.ERROR):
            event_ids = manager.add_ledger_events_from_call(
                session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["client_name"] == "ישראל ישראלי"  # agreement-level fields still carried
        assert data["amount"] is None
        assert data["description"] is None
        assert data["component_label"] is None
        assert "needs manual review" in (data["notes"] or "")
        assert data["agreement_id"] is not None, "still traceable/groupable, even though empty"
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_component_count_mismatch_persists_given_components_and_logs_error(
        self, manager, temp_events_dir, caplog
    ):
        """REQ-DATA-008: a non-empty but component_count-mismatched components list
        must never drop real data - persist what was given, just log an ERROR so a
        human can review for possibly-missing components."""
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS, component_count=3)  # only 1 given
        with caplog.at_level(logging.ERROR):
            event_ids = manager.add_ledger_events_from_call(
                session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["amount"] == 5000  # the real component is still persisted, not dropped
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_matching_component_count_logs_no_error(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.ERROR):
            manager.add_ledger_events_from_call(
                session_id="s", whatsapp_chat="w", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
                message_id="m", message_timestamp=FIXED_TS, sender="w",
            )
        assert not any(r.levelno == logging.ERROR for r in caplog.records)

    def test_shared_fields_applied_to_every_component(self, manager, temp_events_dir):
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS, component_count=2)
        call_arguments["components"] = [
            dict(SAMPLE_CALL_ARGUMENTS["components"][0]),
            dict(SAMPLE_CALL_ARGUMENTS["components"][0], component_label="שלב שני"),
        ]

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )

        for eid in event_ids:
            data = _read(temp_events_dir, eid)
            assert data["client_name"] == "ישראל ישראלי"
            assert data["agreement_label"] == "תיק בדיקה"
            assert data["raw_message_excerpt"] == "ישראל ישראלי - הצעת שכר טרחה"

    def test_call_arguments_dict_not_mutated(self, manager):
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS)
        original = json.loads(json.dumps(call_arguments))  # deep copy for comparison
        manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS, sender="w",
        )
        assert call_arguments == original
