"""
Unit tests for LedgerEventManager (Feature 033: Ledger Event Persistence).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 2 (T002a-T006a): core file persistence, event_id generation
(local-time conversion, per-letter-per-minute seq collision handling), amount
normalization, reference placeholder logic, and reserved-null fields.

Phase 11 (043-production-data-setup-tooling, 2026-08-16): substantially revised
after a real-data-grounded audit against the actual historical Events.csv (1159
rows, real client PII - gitignored, not committed, not required to run this
suite; used only for that one-time interactive review) found several fields
that duplicated each other or diverged from real usage - see
specs/in-progress/043-production-data-setup-tooling/data-model.md §1b for the
full field-by-field writeup this file's shape now reflects: event_date/event_time
merged into event_datetime; notes removed (merged into description/
reference_hint); replaced_event_id/replaces_hint folded into reference/
reference_hint (found to be the same mechanism in the real ledger); sender/
message_timestamp removed (no reader, fully covered by event_datetime);
agreement_label no longer persisted (only used to build agreement_id).

See specs/in-progress/033-ledger-event-persistence/data-model.md for the
original field list and specs/in-progress/033-ledger-event-persistence/spec.md
for the Clarifications this behavior derives from.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.managers.ledger_event_manager import LedgerEventManager, is_incomplete_capture

# Raw arguments shape capture_ledger_event's LEDGER_EVENT_TOOL produces (Phase 11
# shape, 2026-08-16). Not every test needs every field non-null.
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
    "trigger_condition": None,
    "reference_hint": None,
    "agreement_label": "תיק בדיקה",
    "component_label": "בסיס",
}

CSV_MAPPED_FIELDS = {
    "event_id", "event_datetime", "source_type", "event_subtype",
    "client_name", "payer_name", "description", "amount",
    "reference", "agreement_id", "component_id", "component_label",
    "trigger_condition", "percent", "percent_base", "hours", "hourly_rate",
    "txn_date", "vat_status", "split_partner", "split_percent",
    "due_date", "invoice_status", "invoice_number", "invoice_type",
    "morning_document_id", "invoice_actual_creation_date",
}
# raw_message_excerpt removed (Feature 043, 2026-08-18): the ledger event's own
# message_id/session_id pointer is now sufficient - the source content lives on
# the Message record itself (content for text, + the new extracted_text field
# for media), never duplicated into the ledger event. See
# data-model.md §1b's follow-up entry for the full rationale.
INTERNAL_FIELDS = {
    "session_id", "whatsapp_chat", "message_id", "captured_at",
    "reference_hint", "schema_version",
    "bank_number", "bank_branch", "bank_account",
}
# trigger_condition removed (Feature 043, 2026-08-18, finding #10): now wired to
# the AI's own component-level input for הסכם (LEDGER_EVENT_TOOL exposes it) -
# still forced null for בנק, but no longer unconditionally reserved.
RESERVED_NULL_FIELDS = [
    "split_partner", "split_percent", "due_date",
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
            message_timestamp=FIXED_TS,
        )
        assert event_id is not None
        assert (temp_events_dir / f"{event_id}.json").exists()

    def test_written_file_has_exactly_the_27_csv_fields_plus_9_internal_fields(
        self, manager, temp_events_dir
    ):
        """Phase 11 (2026-08-16, human sign-off after a full field-by-field real-
        data-grounded review): was 30 CSV + 11 internal (schema v1), briefly 30 CSV
        + 16 internal (T027b's now-reverted payment_method/transaction_reference
        addition, schema v2), then 27 CSV + 10 internal (schema reset to v1) - see
        data-model.md §1b for the complete before/after field list. 2026-08-18
        (self-review follow-up): raw_message_excerpt removed from internal (now
        9) - the message pointer + Message.extracted_text replace it, see
        INTERNAL_FIELDS's own comment above."""
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert set(data.keys()) == CSV_MAPPED_FIELDS | INTERNAL_FIELDS

    def test_file_is_alphabetized_utf8_no_ascii_escaping(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
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
            message_timestamp=FIXED_TS,
        )
        assert event == original

    def test_direct_mapped_fields_populated_verbatim(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", whatsapp_chat="972500000000@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
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


class TestEventIdGeneration:
    """T003a: event_id format, local-time conversion, per-letter-per-minute seq."""

    def test_source_type_agreement_gets_A_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.startswith("A")

    def test_source_type_bank_gets_B_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.startswith("B")

    def test_date_time_converted_to_asia_jerusalem_local(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id == "A28072614060"

    def test_event_datetime_field_matches_local_conversion(self, manager, temp_events_dir):
        """Phase 11: event_date+event_time merged into one event_datetime field,
        format DD/MM/YYYY HH:MM (human decision, 2026-08-16)."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] == "28/07/2026 14:06"

    def test_first_event_for_new_minute_gets_seq_0(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.endswith("0")

    def test_second_event_same_minute_gets_seq_1(self, manager):
        first = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        second = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        assert first == "A28072614060"
        assert second == "A28072614061"

    def test_seq_scoped_per_letter_not_shared_across_letters(self, manager):
        agreement_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        bank_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m2", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert not any("Events.csv" in p for p in opened_paths)

    def test_eleventh_event_same_minute_returns_none_and_logs_error(self, manager, caplog):
        for i in range(10):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id=f"m{i}", message_timestamp=FIXED_TS,
            )
            assert event_id is not None

        with caplog.at_level(logging.ERROR):
            eleventh = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id="m10", message_timestamp=FIXED_TS,
            )

        assert eleventh is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_eleventh_event_does_not_overwrite_the_seq9_file(self, manager, temp_events_dir):
        for i in range(10):
            manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, client_name=f"client-{i}"),
                message_id=f"m{i}", message_timestamp=FIXED_TS,
            )
        seq9_file = temp_events_dir / "A28072614069.json"
        before = seq9_file.read_text(encoding="utf-8")

        manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, client_name="eleventh-client"),
            message_id="m10", message_timestamp=FIXED_TS,
        )

        assert seq9_file.read_text(encoding="utf-8") == before
        assert not (temp_events_dir / "A280726140610.json").exists()

    def test_none_message_timestamp_falls_back_and_logs_warning(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
                message_id="m", message_timestamp=None,
            )
        assert event_id is not None
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] is not None, "still derives from processing-time fallback"
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
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["amount"] == expected

    def test_unparseable_amount_left_blank_original_kept_in_description_and_warning_logged(
        self, manager, temp_events_dir, caplog
    ):
        """Phase 11: notes (CSV column) removed - this fallback text now appends
        to description instead (the component's own content, per data-model.md
        §1b's routing decision)."""
        raw = "8,000₪; 20,000₪; עוד 30,000₪"
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, amount=raw, description=None),
                message_id="m", message_timestamp=FIXED_TS,
            )
        data = _read(temp_events_dir, event_id)
        assert data["amount"] is None
        assert raw in (data["description"] or "")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unparseable_amount_appends_to_existing_description_not_overwrite(
        self, manager, temp_events_dir
    ):
        raw = "8,000₪; 20,000₪"
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, amount=raw, description="original description text"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert "original description text" in data["description"]
        assert raw in data["description"]


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
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == expected

    def test_unparseable_hours_left_blank_original_kept_in_description_and_warning_logged(
        self, manager, temp_events_dir, caplog
    ):
        raw = "כמה שעות שיידרשו"
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", description=None),
                message_id="m", message_timestamp=FIXED_TS,
            )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] is None
        assert raw in (data["description"] or "")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unparseable_hours_appends_to_existing_description_not_overwrite(
        self, manager, temp_events_dir
    ):
        raw = "כמה שעות שיידרשו"
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", description="original description text"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert "original description text" in data["description"]
        assert raw in data["description"]


class TestReferencePlaceholder:
    """T005a: REQ-DATA-002. Phase 11 (2026-08-16, human decision): unified
    reference mechanism - replaced_event_id/replaces_hint folded into
    reference/reference_hint. Real-data audit (against the actual 1159-row
    Events.csv) found both fields held real event_id(s) in practice, the only
    difference being direction (replaced_event_id one-directional; reference
    genuinely bidirectional in several real rows) - merged into one field/
    mechanism here, the direction/multi-ref question itself left open/deferred.
    See data-model.md §1b."""

    def test_reference_hint_present_sets_reference_placeholder(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="correction to prior arrangement"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] == "צריך למצוא"

    def test_reference_hint_absent_leaves_reference_blank(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint=None),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] is None

    def test_reference_hint_itself_still_preserved_as_internal_field(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="משרד הרווחה"),
            message_id="m", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in RESERVED_NULL_FIELDS:
            assert field in data, f"{field} must be present as a key, never omitted"
            assert data[field] is None, f"{field} must be null in this feature"


class TestAgreementAndComponentIds:
    """T006b (added 2026-07-30): REQ-DATA-004 — agreement_id/component_id
    generation, matching the real Events.csv convention, with the user's hard
    consistency requirement (byte-for-byte identical across a batch, guaranteed
    by construction, never by trusting repeated AI text).

    Phase 11 (2026-08-16): agreement_label itself confirmed no longer persisted
    as its own field (real-data audit found agreement_id already fully embeds
    the (slugified) label, and every component references the SAME agreement_id
    - never re-derived/reconstructed later, same discipline as a UUID - see
    data-model.md §1b)."""

    def test_agreement_event_gets_non_null_agreement_id_and_component_id(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is not None
        assert data["component_id"] is not None

    def test_bank_event_has_null_agreement_and_component_id(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is None
        assert data["component_id"] is None
        assert data["component_label"] is None

    def test_agreement_id_matches_real_csv_format(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, client_name="אתי אסולין", agreement_label="ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        # FIXED_TS -> 28/07/2026 local -> MMYY "0726"
        assert data["agreement_id"] == "0726-אתי_אסולין-ערעור_לארצי"

    def test_agreement_label_itself_not_persisted_as_its_own_field(
        self, manager, temp_events_dir
    ):
        """Phase 11 (2026-08-16, human requirement): "I never want to see the
        label in the data except embedded in the agreement id itself" - confirms
        agreement_label is a construction-only input, never a standalone output
        field."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, agreement_label="ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert "agreement_label" not in data
        assert "ערעור_לארצי" in data["agreement_id"]

    def test_component_id_is_agreement_id_plus_slugified_component_label(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, component_label="עדכון - ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["component_id"] == f"{data['agreement_id']}-עדכון_ערעור_לארצי"

    def test_standalone_call_without_explicit_agreement_id_derives_its_own(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
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
                message_id=f"m{i}", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["component_label"] == "שעות עבודה"


class TestTxnDate:
    """T006c/T006e (added 2026-07-30, unified same day - see spec.md Clarifications):
    REQ-DATA-005 - תאריך_ביצוע, code-normalized from the AI-resolved ISO-8601 txn_date.
    One field, two populating cases: (1) an hourly work-log component's worked-date
    (required whenever hours is set), (2) a בנק component's own stated transaction/
    value date (always optional). Both distinct from event_datetime (message-arrival
    instant)."""

    def test_txn_date_normalized_from_iso_to_ddmmyyyy(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-29"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "29/07/2026"

    def test_txn_date_null_when_hours_null(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours=None, txn_date=None),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] is None
        assert data["txn_date"] is None

    def test_txn_date_distinct_from_event_datetime_for_hours_case(self, manager, temp_events_dir):
        """The whole point of REQ-DATA-005: hours worked "אתמול" (yesterday) must be
        able to carry a DIFFERENT date than event_datetime (the message's own
        arrival instant, derived from FIXED_TS = 28/07/2026 local)."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-27"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] == "28/07/2026 14:06"
        assert data["txn_date"] == "27/07/2026"

    def test_hours_set_but_txn_date_missing_leaves_blank_and_logs_warning(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, hours="4", txn_date=None),
                message_id="m", message_timestamp=FIXED_TS,
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
                message_id="m", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == 2.0

    def test_txn_date_normalized_for_bank_transaction_date(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "26/07/2026"

    def test_txn_date_distinct_from_event_datetime_for_bank_case(self, manager, temp_events_dir):
        """A screenshot forwarded a day after the actual deposit must be able to carry
        a txn_date DIFFERENT from event_datetime (derived from FIXED_TS = 28/07/2026
        local, the message's own arrival time)."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] == "28/07/2026 14:06"
        assert data["txn_date"] == "26/07/2026"

    def test_txn_date_null_by_default_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק"),
            message_id="m", message_timestamp=FIXED_TS,
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
                message_id="m", message_timestamp=FIXED_TS,
            )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)


# A `capture_ledger_event` call's raw arguments (Phase 11 shape, 2026-08-16) -
# agreement-level fields top-level, per-component fields nested.
SAMPLE_CALL_ARGUMENTS = {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "ישראל ישראלי",
    "payer_name": None,
    "agreement_label": "תיק בדיקה",
    "reference_hint": None,
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
            "trigger_condition": None,
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
            message_id="m", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
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
            "agreement_label": None, "reference_hint": None,
            "component_count": 1,
            "components": [{
                "component_label": None, "description": "הפקדה", "amount": "9,440₪",
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None, "vat_status": "לא צוין",
                "trigger_condition": None,
            }],
        }

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS,
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
        exactly one flagged fallback record and log an ERROR. Phase 11: the
        explanatory text now lives in description (notes was removed)."""
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS, components=[])
        with caplog.at_level(logging.ERROR):
            event_ids = manager.add_ledger_events_from_call(
                session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
                message_id="m", message_timestamp=FIXED_TS,
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["client_name"] == "ישראל ישראלי"  # agreement-level fields still carried
        assert data["amount"] is None
        assert data["component_label"] is None
        assert "needs manual review" in (data["description"] or "")
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
                message_id="m", message_timestamp=FIXED_TS,
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["amount"] == 5000  # the real component is still persisted, not dropped
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_matching_component_count_logs_no_error(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.ERROR):
            manager.add_ledger_events_from_call(
                session_id="s", whatsapp_chat="w", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
                message_id="m", message_timestamp=FIXED_TS,
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
            message_id="m", message_timestamp=FIXED_TS,
        )

        for eid in event_ids:
            data = _read(temp_events_dir, eid)
            assert data["client_name"] == "ישראל ישראלי"

    def test_call_arguments_dict_not_mutated(self, manager):
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS)
        original = json.loads(json.dumps(call_arguments))  # deep copy for comparison
        manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert call_arguments == original


class TestSchemaVersion:
    """Feature 043, US5, T008a: every persisted record carries schema_version.
    Phase 11 (2026-08-16): reset to 1 as a new baseline generation after a
    substantial real-data-grounded revision - see data-model.md §1b and
    ledger_event_manager.py's own CURRENT_SCHEMA_VERSION comment for why
    resetting (rather than incrementing) is safe here (no real persisted file
    has ever carried a schema_version value at all)."""

    def test_persisted_record_has_current_schema_version(self, manager, temp_events_dir):
        from src.managers.ledger_event_manager import CURRENT_SCHEMA_VERSION

        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_current_schema_version_is_1(self):
        from src.managers.ledger_event_manager import CURRENT_SCHEMA_VERSION

        assert CURRENT_SCHEMA_VERSION == 1

    def test_add_ledger_events_from_call_also_stamps_schema_version(self, manager, temp_events_dir):
        from src.managers.ledger_event_manager import CURRENT_SCHEMA_VERSION

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", whatsapp_chat="w", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
            message_id="m", message_timestamp=FIXED_TS,
        )
        for eid in event_ids:
            assert _read(temp_events_dir, eid)["schema_version"] == CURRENT_SCHEMA_VERSION


class TestBankPaymentDetailFields:
    """Phase 11 (tasks.md, 043-production-data-setup-tooling), T027a/T027b.

    payment_method/transaction_reference (originally added in this same phase's
    first pass, T027b) were REMOVED in a same-day real-data-grounded follow-up
    review (2026-08-16, human decision): no payment-app support exists yet, and
    payment_method was redundant with bank_number/bank_branch/bank_account's own
    presence already implying a bank transfer. bank_number/bank_branch/
    bank_account themselves remain - closing the real gap this phase exists for
    (bugfix-028/038 added the equivalent fields to the Morning invoicing tools;
    the ledger's own capture never mirrored them). See data-model.md §1b.
    """

    NEW_FIELDS = {"bank_number", "bank_branch", "bank_account"}

    def test_bank_event_persists_all_three_fields_verbatim(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(
                SAMPLE_EVENT, source_type="בנק",
                bank_number="31", bank_branch="123", bank_account="456789",
            ),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["bank_number"] == "31"
        assert data["bank_branch"] == "123"
        assert data["bank_account"] == "456789"

    def test_bank_event_omitted_fields_default_to_null_not_a_keyerror(
        self, manager, temp_events_dir
    ):
        """The three fields must be accessed via .get(), same convention as every
        other optional field (payer_name, reference_hint, ...) - a caller that
        doesn't supply them (e.g. a genuinely unstated screenshot) must never
        crash."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in self.NEW_FIELDS:
            assert data[field] is None

    def test_agreement_event_forces_all_three_fields_null_even_if_present(
        self, manager, temp_events_dir
    ):
        """Defensive code-side nulling for source_type=הסכם, same discipline as
        component_label being forced null for בנק - never trust the caller/AI to
        have left an inapplicable field blank on its own."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(
                SAMPLE_EVENT, source_type="הסכם",
                bank_number="31", bank_branch="123", bank_account="456789",
            ),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in self.NEW_FIELDS:
            assert data[field] is None, f"{field} must be forced null for source_type=הסכם"


class TestPayerNameBankHandling:
    """Finding #4 (2026-08-18 player review, self-review of a full 33-message
    real run): payer_name has no meaning for a בנק event (no payer/client
    routing distinction applies to a bank deposit) - the model put the
    depositor/account-holder name here about half the time anyway despite the
    tool description already saying not to. Code-side enforcement closes the
    gap: forced null for בנק, and - since discarding a misplaced real name
    would be data loss for exactly the mistake this guards against - rescued
    into client_name when the model left that field empty."""

    def test_payer_name_forced_null_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", client_name="דני כהן", payer_name="דני כהן"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["payer_name"] is None

    def test_payer_name_rescued_into_client_name_when_client_name_empty(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", whatsapp_chat="w",
                event=dict(SAMPLE_EVENT, source_type="בנק", client_name=None, payer_name="דני כהן"),
                message_id="m", message_timestamp=FIXED_TS,
            )
        data = _read(temp_events_dir, event_id)
        assert data["client_name"] == "דני כהן", "misplaced name rescued, never silently dropped"
        assert data["payer_name"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_payer_name_not_rescued_when_client_name_already_set(self, manager, temp_events_dir):
        """Both given (a genuine same-name coincidence, or the model correctly set
        client_name and redundantly also set payer_name) - client_name wins as-is,
        never overwritten by the rescue path."""
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", client_name="שם נכון", payer_name="שם אחר"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["client_name"] == "שם נכון"
        assert data["payer_name"] is None

    def test_payer_name_untouched_for_agreement_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם", payer_name="הראל ביטוח"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["payer_name"] == "הראל ביטוח"


class TestVatStatusBankDefault:
    """Finding #6 (2026-08-18 player review): the model defaulted vat_status
    correctly for בנק events only 1 of 15 times in a real run, despite the
    underlying principle already existing elsewhere in the constitution for
    Morning payment-reference documents ("money already deposited necessarily
    contains the VAT element already"). Code-side enforcement: unconditionally
    כולל for every בנק event, regardless of what the AI passed."""

    @pytest.mark.parametrize("given", ["לא צוין", "לא כולל", "כולל", None])
    def test_vat_status_always_kolel_for_bank_event(self, manager, temp_events_dir, given):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", vat_status=given),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["vat_status"] == "כולל"

    def test_vat_status_untouched_for_agreement_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם", vat_status="לא כולל"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["vat_status"] == "לא כולל"


class TestTriggerConditionField:
    """Finding #10 (2026-08-18 player review): trigger_condition was previously
    hardcoded None regardless of input - LEDGER_EVENT_TOOL never even exposed
    it as a component property, so a textbook conditional fee (msg 18: "אם
    הבקשה נקבעת לדיון") had nowhere to go and got folded into description
    instead. Now wired to the AI's own component-level input for הסכם, forced
    null for בנק (no conditional-fee concept applies to a bank deposit)."""

    def test_trigger_condition_persisted_for_agreement_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם", trigger_condition="אם הבקשה נקבעת לדיון"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["trigger_condition"] == "אם הבקשה נקבעת לדיון"

    def test_trigger_condition_null_when_not_given(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["trigger_condition"] is None

    def test_trigger_condition_forced_null_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, source_type="בנק", trigger_condition="אם משהו"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["trigger_condition"] is None


class TestResolveReference:
    """Feature 043, US2, T008a: LedgerEventManager.resolve_reference. Renamed from
    resolve_replaced_event_id (Phase 11, 2026-08-16) - operates on the unified
    reference field now, see TestReferencePlaceholder above and data-model.md
    §1b for why replaced_event_id/reference were folded together."""

    def test_resolves_placeholder_with_resolved_id_when_currently_placeholder(
        self, manager, temp_events_dir
    ):
        prior_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        correction_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="the original agreement"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        assert _read(temp_events_dir, correction_id)["reference"] == "צריך למצוא"

        result = manager.resolve_reference(correction_id, prior_id)

        assert result is True
        assert _read(temp_events_dir, correction_id)["reference"] == prior_id

    def test_returns_false_and_does_not_overwrite_when_not_currently_placeholder(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),  # reference_hint=None
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert _read(temp_events_dir, event_id)["reference"] is None

        result = manager.resolve_reference(event_id, "SOME_OTHER_ID")

        assert result is False
        assert _read(temp_events_dir, event_id)["reference"] is None

    def test_returns_false_for_nonexistent_event_id(self, manager, caplog):
        with caplog.at_level(logging.ERROR):
            result = manager.resolve_reference("DOES_NOT_EXIST", "TARGET")
        assert result is False
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_only_targeted_event_file_is_modified(self, manager, temp_events_dir):
        prior_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        untouched_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="something else entirely"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        correction_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w",
            event=dict(SAMPLE_EVENT, reference_hint="the original agreement"),
            message_id="m3", message_timestamp=FIXED_TS,
        )
        before_untouched = _read(temp_events_dir, untouched_id)

        manager.resolve_reference(correction_id, prior_id)

        assert _read(temp_events_dir, untouched_id) == before_untouched


class TestApplyReviewAnswer:
    """Feature 043, US3, T008a: LedgerEventManager.apply_review_answer (second-pass)."""

    def test_patches_specified_fields(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )

        result = manager.apply_review_answer(
            event_id, {"payer_name": "דני כהן", "description": "resolved via review queue"}
        )

        assert result is True
        data = _read(temp_events_dir, event_id)
        assert data["payer_name"] == "דני כהן"
        assert data["description"] == "resolved via review queue"

    def test_unspecified_fields_unchanged(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        before = _read(temp_events_dir, event_id)

        manager.apply_review_answer(event_id, {"payer_name": "דני כהן"})

        after = _read(temp_events_dir, event_id)
        for key in before:
            if key != "payer_name":
                assert after[key] == before[key]

    def test_returns_false_for_nonexistent_event_id(self, manager, caplog):
        with caplog.at_level(logging.ERROR):
            result = manager.apply_review_answer("DOES_NOT_EXIST", {"payer_name": "x"})
        assert result is False
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_only_targeted_event_file_is_modified(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        other_id = manager.add_ledger_event(
            session_id="s", whatsapp_chat="w", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        before_other = _read(temp_events_dir, other_id)

        manager.apply_review_answer(event_id, {"payer_name": "דני כהן"})

        assert _read(temp_events_dir, other_id) == before_other
