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
agreement_label was, at that point, still a construction-only tool input used
to build agreement_id and never persisted on its own (bugfix-agreement-label,
2026-08-24: agreement_label is now gone entirely - the AI builds agreement_id
itself, fully-formed, in the documented '{MMYY}-{client_slug}-{label_slug}'
format, and it's the only thing ever supplied/persisted; code no longer
computes or slugifies any part of it).

See specs/in-progress/033-ledger-event-persistence/data-model.md for the
original field list and specs/in-progress/033-ledger-event-persistence/spec.md
for the Clarifications this behavior derives from.
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.managers.ledger_event_manager import LedgerEventManager, is_incomplete_capture, _parse_iso_local

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
    "agreement_id": "0726-ישראל_ישראלי-תיק_בדיקה",
    "component_label": "בסיס",
}

CSV_MAPPED_FIELDS = {
    "event_id", "event_datetime", "source_type", "event_subtype",
    "client_name", "payer_name", "description", "amount",
    "reference", "agreement_id", "component_id", "component_label",
    "trigger_condition", "percent", "percent_base", "hours", "hourly_rate",
    "txn_date", "vat_status", "split_partner", "split_percent",
    "accounting_document_display_number",
    "accounting_document_status",
    # Feature 025 Phase 9 (2026-08-23)
    "accounting_document_status_code", "accounting_document_status_label",
    "accounting_document_payment_method",
    # due_date removed 2026-08-25 (user directive): dead, always-null reserved
    # field with no populating code path - dropped from the schema entirely.
    # accounting_document_creation_date removed 2026-08-25 (user directive): was
    # a byte-for-byte duplicate of event_datetime for every חשבונית record -
    # event_datetime is now the only creation-date field, for every source_type.
}
# raw_message_excerpt removed (Feature 043, 2026-08-18): the ledger event's own
# message_id/session_id pointer is now sufficient - the source content lives on
# the Message record itself (content for text, + the new extracted_text field
# for media), never duplicated into the ledger event. See
# data-model.md §1b's follow-up entry for the full rationale.
# whatsapp_chat removed (2026-08-19): redundant with session_id - the session
# it points at already carries its own whatsapp_chat, and message_id+session_id
# together are already sufficient traceability.
INTERNAL_FIELDS = {
    "session_id", "message_id", "captured_at",
    "reference_hint", "schema_version",
    "bank_number", "bank_branch", "bank_account",
}
# trigger_condition removed (Feature 043, 2026-08-18, finding #10): now wired to
# the AI's own component-level input for הסכם (LEDGER_EVENT_TOOL exposes it) -
# still forced null for בנק, but no longer unconditionally reserved.
# accounting_document_display_number/_type/_status/_creation_date (renamed/
# merged from invoice_*/morning_document_id, Feature 025 - round 3,
# 2026-08-21, merged the originally-planned separate _id/_number fields into
# one _display_number field) moved OUT of this always-null list (2026-08-20)
# - they're now populated for source_type="חשבונית" and only forced null
# for הסכם/בנק. See
# TestAccountingDocumentFields below for their new conditional-null coverage.
RESERVED_NULL_FIELDS = [
    "split_partner", "split_percent",
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
            session_id="sess-1", event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
        )
        assert event_id is not None
        assert (temp_events_dir / f"{event_id}.json").exists()

    def test_written_file_has_exactly_the_26_csv_fields_plus_8_internal_fields(
        self, manager, temp_events_dir
    ):
        """Phase 11 (2026-08-16, human sign-off after a full field-by-field real-
        data-grounded review): was 30 CSV + 11 internal (schema v1), briefly 30 CSV
        + 16 internal (T027b's now-reverted payment_method/transaction_reference
        addition, schema v2), then 27 CSV + 10 internal (schema reset to v1) - see
        data-model.md §1b for the complete before/after field list. 2026-08-18
        (self-review follow-up): raw_message_excerpt removed from internal (then
        9) - the message pointer + Message.extracted_text replace it. 2026-08-19:
        whatsapp_chat also removed (now 8) - redundant with session_id, see
        INTERNAL_FIELDS's own comment above. 2026-08-25: due_date and
        accounting_document_creation_date removed from CSV_MAPPED_FIELDS (now 26)
        - see that constant's own comment."""
        event_id = manager.add_ledger_event(
            session_id="sess-1", event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert set(data.keys()) == CSV_MAPPED_FIELDS | INTERNAL_FIELDS

    def test_file_is_alphabetized_utf8_no_ascii_escaping(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", event=dict(SAMPLE_EVENT), message_id="msg-1",
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
            session_id="sess-1", event=event, message_id="msg-1",
            message_timestamp=FIXED_TS,
        )
        assert event == original

    def test_direct_mapped_fields_populated_verbatim(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="sess-1", event=dict(SAMPLE_EVENT), message_id="msg-1",
            message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["source_type"] == "הסכם"
        assert data["event_subtype"] == "יצירה"
        assert data["client_name"] == "ישראל ישראלי"
        assert data["description"] == "כתב הגנה"
        assert data["vat_status"] == "לא צוין"
        assert data["session_id"] == "sess-1"
        assert data["message_id"] == "msg-1"


class TestEventIdGeneration:
    """T003a: event_id format, local-time conversion, per-letter-per-minute seq."""

    def test_source_type_agreement_gets_A_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.startswith("A")

    def test_source_type_bank_gets_B_prefix(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.startswith("B")

    def test_date_time_converted_to_asia_jerusalem_local(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id == "A28072614060"

    def test_event_datetime_field_matches_local_conversion(self, manager, temp_events_dir):
        """Phase 11: event_date+event_time merged into one event_datetime field,
        format DD/MM/YYYY HH:MM (human decision, 2026-08-16)."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] == "28/07/2026 14:06"

    def test_first_event_for_new_minute_gets_seq_0(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert event_id.endswith("0")

    def test_second_event_same_minute_gets_seq_1(self, manager):
        first = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        second = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        assert first == "A28072614060"
        assert second == "A28072614061"

    def test_seq_scoped_per_letter_not_shared_across_letters(self, manager):
        agreement_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        bank_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
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
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert not any("Events.csv" in p for p in opened_paths)

    def test_eleventh_event_same_minute_returns_none_and_logs_error(self, manager, caplog):
        for i in range(10):
            event_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT),
                message_id=f"m{i}", message_timestamp=FIXED_TS,
            )
            assert event_id is not None

        with caplog.at_level(logging.ERROR):
            eleventh = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT),
                message_id="m10", message_timestamp=FIXED_TS,
            )

        assert eleventh is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_eleventh_event_does_not_overwrite_the_seq9_file(self, manager, temp_events_dir):
        for i in range(10):
            manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT, client_name=f"client-{i}"),
                message_id=f"m{i}", message_timestamp=FIXED_TS,
            )
        seq9_file = temp_events_dir / "A28072614069.json"
        before = seq9_file.read_text(encoding="utf-8")

        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="eleventh-client"),
            message_id="m10", message_timestamp=FIXED_TS,
        )

        assert seq9_file.read_text(encoding="utf-8") == before
        assert not (temp_events_dir / "A280726140610.json").exists()

    def test_none_message_timestamp_falls_back_and_logs_warning(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT),
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
            session_id="s", event=dict(SAMPLE_EVENT, amount=raw),
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
                session_id="s", event=dict(SAMPLE_EVENT, amount=raw, description=None),
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
            session_id="s", event=dict(SAMPLE_EVENT, amount=raw, description="original description text"),
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
            session_id="s", event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28" if raw else None),
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
                session_id="s", event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", description=None),
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
            session_id="s", event=dict(SAMPLE_EVENT, hours=raw, txn_date="2026-07-28", description="original description text"),
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
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint="correction to prior arrangement"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] == "צריך למצוא"

    def test_reference_hint_absent_leaves_reference_blank(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint=None),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] is None

    def test_reference_hint_itself_still_preserved_as_internal_field(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint="משרד הרווחה"),
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
            session_id="s", event=dict(SAMPLE_EVENT),
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
    the (slugified) label - see data-model.md §1b).

    bugfix-agreement-label (2026-08-24): agreement_label removed entirely, even
    as a construction-only tool input - the AI now builds agreement_id itself,
    fully-formed, and every component references the SAME agreement_id, never
    re-derived/reconstructed later, same discipline as a UUID."""

    def test_agreement_event_gets_non_null_agreement_id_and_component_id(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is not None
        assert data["component_id"] is not None

    def test_bank_event_has_null_agreement_and_component_id(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] is None
        assert data["component_id"] is None
        assert data["component_label"] is None

    def test_agreement_id_is_persisted_verbatim_as_supplied(self, manager, temp_events_dir):
        """bugfix-agreement-label (2026-08-24): agreement_id is fully AI-authored,
        already in the documented '{MMYY}-{client_slug}-{label_slug}' format -
        code no longer computes or slugifies any part of it, only persists
        exactly what was given."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(
                SAMPLE_EVENT, client_name="אתי אסולין",
                agreement_id="0726-אתי_אסולין-ערעור_לארצי",
            ),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] == "0726-אתי_אסולין-ערעור_לארצי"

    def test_agreement_label_is_not_a_field_anywhere(
        self, manager, temp_events_dir
    ):
        """bugfix-agreement-label (2026-08-24, human requirement): "GET RID OF
        AGREEMENT LABEL AS A FIELD" - agreement_label no longer exists as a tool
        input, a SAMPLE_EVENT key, or a persisted field. The label lives ONLY as
        a substring inside agreement_id, which the AI builds itself."""
        assert "agreement_label" not in SAMPLE_EVENT
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert "agreement_label" not in data

    def test_component_id_is_agreement_id_plus_slugified_component_label(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, component_label="עדכון - ערעור לארצי"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["component_id"] == f"{data['agreement_id']}-עדכון_ערעור_לארצי"

    def test_standalone_call_without_caller_supplied_agreement_id_uses_events_own(
        self, manager, temp_events_dir
    ):
        """When add_ledger_event's own `agreement_id` kwarg is not given (a
        standalone, non-batched capture), the persisted agreement_id comes
        straight from the event's own AI-authored agreement_id field - never
        derived or recomputed by code."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] == SAMPLE_EVENT["agreement_id"]

    def test_caller_supplied_agreement_id_used_as_is_for_batch_consistency(
        self, manager, temp_events_dir
    ):
        """The user's hard requirement: when a caller (AIHandler batching multiple
        components of one agreement) supplies the agreement_id kwarg explicitly,
        it MUST be used verbatim - even if this component's own event["agreement_id"]
        differs slightly. Consistency is structural, never dependent on the AI
        repeating identical text across separate tool-call components."""
        explicit_id = "0726-custom-batch-id"
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, agreement_id="0726-a-slightly-different-id"),
            message_id="m", message_timestamp=FIXED_TS,
            agreement_id=explicit_id,
        )
        data = _read(temp_events_dir, event_id)
        assert data["agreement_id"] == explicit_id

    def test_multiple_components_sharing_caller_supplied_agreement_id_are_identical(
        self, manager, temp_events_dir
    ):
        shared_id = "0726-גיליאן_דוידיאן-משרד_הרווחה"
        ids = []
        for i in range(3):
            event_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT, client_name="גיליאן דוידיאן", component_label=f"רכיב {i}"),
                message_id=f"m{i}", message_timestamp=FIXED_TS,
                agreement_id=shared_id,
            )
            ids.append(_read(temp_events_dir, event_id)["agreement_id"])
        assert len(set(ids)) == 1, "every component of the same batch must share one identical agreement_id"
        assert ids[0] == shared_id

    def test_component_label_populated_verbatim_for_agreement_events(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, component_label="שעות עבודה"),
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
            session_id="s", event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-29"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "29/07/2026"

    def test_txn_date_null_when_hours_null(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, hours=None, txn_date=None),
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
            session_id="s", event=dict(SAMPLE_EVENT, hours="4", txn_date="2026-07-27"),
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
                session_id="s", event=dict(SAMPLE_EVENT, hours="4", txn_date=None),
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
                session_id="s", event=dict(SAMPLE_EVENT, hours="4", txn_date="אתמול"),
                message_id="m", message_timestamp=FIXED_TS,
            )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_hours_word_form_normalized_to_number(self, manager, temp_events_dir):
        """REQ-DATA-009 (added 2026-08-02): hours must always be numerical when
        populated - a Hebrew word form like 'שעתיים' is not persisted verbatim."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, hours="שעתיים", txn_date="2026-07-28"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["hours"] == 2.0

    def test_txn_date_normalized_for_bank_transaction_date(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] == "26/07/2026"

    def test_txn_date_distinct_from_event_datetime_for_bank_case(self, manager, temp_events_dir):
        """A screenshot forwarded a day after the actual deposit must be able to carry
        a txn_date DIFFERENT from event_datetime (derived from FIXED_TS = 28/07/2026
        local, the message's own arrival time)."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="2026-07-26"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["event_datetime"] == "28/07/2026 14:06"
        assert data["txn_date"] == "26/07/2026"

    def test_txn_date_null_by_default_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["txn_date"] is None

    def test_txn_date_unparseable_for_bank_event_leaves_blank_and_logs_warning(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", txn_date="אתמול"),
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
    "agreement_id": "0726-ישראל_ישראלי-תיק_בדיקה",
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
            session_id="s", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
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
            session_id="s", call_arguments=call_arguments,
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
            "agreement_id": None, "reference_hint": None,
            "component_count": 1,
            "components": [{
                "component_label": None, "description": "הפקדה", "amount": "9,440₪",
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None, "vat_status": "לא צוין",
                "trigger_condition": None,
            }],
        }

        event_ids = manager.add_ledger_events_from_call(
            session_id="s", call_arguments=call_arguments,
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
                session_id="s", call_arguments=call_arguments,
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
                session_id="s", call_arguments=call_arguments,
                message_id="m", message_timestamp=FIXED_TS,
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["amount"] == 5000  # the real component is still persisted, not dropped
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_matching_component_count_logs_no_error(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.ERROR):
            manager.add_ledger_events_from_call(
                session_id="s", call_arguments=dict(SAMPLE_CALL_ARGUMENTS),
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
            session_id="s", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS,
        )

        for eid in event_ids:
            data = _read(temp_events_dir, eid)
            assert data["client_name"] == "ישראל ישראלי"

    def test_call_arguments_dict_not_mutated(self, manager):
        call_arguments = dict(SAMPLE_CALL_ARGUMENTS)
        original = json.loads(json.dumps(call_arguments))  # deep copy for comparison
        manager.add_ledger_events_from_call(
            session_id="s", call_arguments=call_arguments,
            message_id="m", message_timestamp=FIXED_TS,
        )
        assert call_arguments == original


# TestSchemaVersion class removed entirely (2026-08-26, human decision, post-incident - see
# ledger_event_manager.py's CURRENT_SCHEMA_VERSION/SCHEMA_VERSION_HISTORY comments): every test
# it held existed solely to assert an exact schema_version value (either hardcoded ==3, or
# ==CURRENT_SCHEMA_VERSION), and nothing meaningful remained once that assertion was removed.
# Policy going forward: no test anywhere may assert on schema_version's value, ever - the
# constant itself is a human-approved governance decision (see CLAUDE.md's "LEDGER SCHEMA
# VERSION BUMPS ARE HUMAN-ONLY" rule), not a piece of application behavior a test should pin.
# Coverage this removed (documented here rather than silently lost):
# - every persisted record carries a schema_version key at all
# - a plain הסכם/בנק capture gets the same global schema_version an accounting capture does
#   (i.e. the field is stamped globally, not per-source_type)
# - add_ledger_events_from_call stamps schema_version on every event in a multi-component batch
# If this coverage needs restoring, do it via a value-agnostic check (e.g. comparing two
# freshly-persisted events' schema_version fields to each other, never to a literal number or to
# CURRENT_SCHEMA_VERSION), decided fresh with the human next time this area is touched.
#
# Master's Feature 044 independently reached the same "never assert on schema_version" endpoint
# for the CURRENT_SCHEMA_VERSION constant itself (both branches reverted 3->2 - see
# ledger_event_manager.py's SCHEMA_VERSION_HISTORY), but had kept a TestSchemaVersion class
# comparing against the imported constant rather than a literal - removed here on merge per this
# session's stricter, already-decided policy (no comparison against CURRENT_SCHEMA_VERSION
# either, not just no hardcoded literal).


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
            session_id="s", event=dict(
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
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק"),
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
            session_id="s", event=dict(
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
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", client_name="דני כהן", payer_name="דני כהן"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["payer_name"] is None

    def test_payer_name_rescued_into_client_name_when_client_name_empty(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", client_name=None, payer_name="דני כהן"),
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
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", client_name="שם נכון", payer_name="שם אחר"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["client_name"] == "שם נכון"
        assert data["payer_name"] is None

    def test_payer_name_untouched_for_agreement_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם", payer_name="הראל ביטוח"),
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
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", vat_status=given),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["vat_status"] == "כולל"

    def test_vat_status_untouched_for_agreement_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם", vat_status="לא כולל"),
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
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם", trigger_condition="אם הבקשה נקבעת לדיון"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["trigger_condition"] == "אם הבקשה נקבעת לדיון"

    def test_trigger_condition_null_when_not_given(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["trigger_condition"] is None

    def test_trigger_condition_forced_null_for_bank_event(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", trigger_condition="אם משהו"),
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
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        correction_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint="the original agreement"),
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
            session_id="s", event=dict(SAMPLE_EVENT),  # reference_hint=None
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
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        untouched_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint="something else entirely"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        correction_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, reference_hint="the original agreement"),
            message_id="m3", message_timestamp=FIXED_TS,
        )
        before_untouched = _read(temp_events_dir, untouched_id)

        manager.resolve_reference(correction_id, prior_id)

        assert _read(temp_events_dir, untouched_id) == before_untouched


class TestApplyReviewAnswer:
    """Feature 043, US3, T008a: LedgerEventManager.apply_review_answer (second-pass)."""

    def test_patches_specified_fields(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
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
            session_id="s", event=dict(SAMPLE_EVENT),
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
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        other_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        before_other = _read(temp_events_dir, other_id)

        manager.apply_review_answer(event_id, {"payer_name": "דני כהן"})

        assert _read(temp_events_dir, other_id) == before_other


def _write_raw_event_file(events_dir, event_id, content):
    """T001a helper: write a raw event JSON file directly to events_dir BEFORE a
    LedgerEventManager exists over it, so construction-time index loading has
    something real to find. `content` may be a dict (written as JSON) or a raw
    str (written verbatim, for the deliberately-malformed-JSON case)."""
    events_dir.mkdir(parents=True, exist_ok=True)
    path = events_dir / f"{event_id}.json"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False)


class TestInMemoryIndex:
    """Feature 044, T001a: the in-memory ledger-event index - populated at
    construction from {storage_dir}/*.json, kept current on writes.

    NOTE: these tests inspect `manager._index` directly rather than going
    through a public query method - Feature 044's actual query surface
    (`query_events`, T002a onward) doesn't exist yet at this point in the
    phase, and the index itself (this task's own scope) needs to be provable
    on its own before anything is built on top of it. `_index` is this
    class's own persisted-in-memory state, not an unrelated internal - a
    white-box check of it here is the honest, minimal-dependency way to test
    T001b's actual scope in isolation.
    """

    def test_construction_loads_all_existing_valid_files_into_index(
        self, temp_events_dir
    ):
        _write_raw_event_file(temp_events_dir, "A2807261406", dict(SAMPLE_EVENT, event_id="A2807261406"))
        _write_raw_event_file(temp_events_dir, "A2807261407", dict(SAMPLE_EVENT, event_id="A2807261407"))
        _write_raw_event_file(temp_events_dir, "B2807261408", dict(SAMPLE_EVENT, event_id="B2807261408"))

        manager = LedgerEventManager(storage_dir=str(temp_events_dir))

        assert len(manager._index) == 3
        assert {e["event_id"] for e in manager._index} == {
            "A2807261406", "A2807261407", "B2807261408",
        }

    def test_construction_with_no_existing_files_yields_empty_index(self, temp_events_dir):
        manager = LedgerEventManager(storage_dir=str(temp_events_dir))
        assert manager._index == []

    def test_corrupt_file_skipped_not_raised_others_still_load(self, temp_events_dir, caplog):
        _write_raw_event_file(temp_events_dir, "A2807261406", dict(SAMPLE_EVENT, event_id="A2807261406"))
        _write_raw_event_file(temp_events_dir, "A2807261407", "{not valid json at all")
        _write_raw_event_file(temp_events_dir, "B2807261408", dict(SAMPLE_EVENT, event_id="B2807261408"))

        with caplog.at_level(logging.ERROR):
            manager = LedgerEventManager(storage_dir=str(temp_events_dir))

        # FR-007: the corrupt file never prevents the others from loading, and
        # never crashes construction (no exception raised above).
        assert {e["event_id"] for e in manager._index} == {"A2807261406", "B2807261408"}
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_add_ledger_event_appends_to_index_immediately(self, manager, temp_events_dir):
        assert manager._index == []

        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT), message_id="m",
            message_timestamp=FIXED_TS,
        )

        assert len(manager._index) == 1
        assert manager._index[0]["event_id"] == event_id
        # The indexed record matches exactly what was persisted to disk (FR-003 -
        # same write, not a second, possibly-divergent copy).
        assert manager._index[0] == _read(temp_events_dir, event_id)

    def test_add_ledger_event_after_construction_from_existing_files_grows_index(
        self, temp_events_dir
    ):
        _write_raw_event_file(temp_events_dir, "A2807261406", dict(SAMPLE_EVENT, event_id="A2807261406"))
        manager = LedgerEventManager(storage_dir=str(temp_events_dir))
        assert len(manager._index) == 1

        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT), message_id="m",
            message_timestamp=FIXED_TS,
        )

        assert len(manager._index) == 2


# Feature 044: the old FIXED_TS_AUG5/AUG20 date-range test fixtures are gone -
# the 2026-08-24 redesign dropped range filtering from query_events entirely
# (see the module-level _HINT_GROUPS comment); every test below reuses the
# shared FIXED_TS from the top of this file.


class TestQueryEventsCriteriaMatching:
    """Feature 044, redesigned 2026-08-24 (see the module-level _HINT_GROUPS
    comment for why the old separate client_name/date_from/date_to/amount_min/
    amount_max/source_type/event_subtype/free_text parameters were replaced).
    `criteria` is a list of {"text": str, "hint": Optional[str]} pairs; every
    criterion is searched against EVERY searchable field on EVERY event -
    never restricted to one field, hint or no hint. A number is compared
    numerically against numeric fields only; anything else is fuzzy/typo-
    tolerant text matching against every field."""

    def test_text_criterion_matches_client_name_with_typo(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "דויד כהן", "hint": "identity"}])
        assert result["count"] == 1

    def test_text_criterion_matches_payer_name_even_with_identity_hint(self, manager):
        manager.add_ledger_event(
            session_id="s",
            event=dict(SAMPLE_EVENT, client_name="לקוח מקורי", payer_name="חברת הביטוח"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "חברת הביטוח", "hint": "identity"}])
        assert result["count"] == 1

    def test_text_criterion_searches_every_field_not_just_description(self, manager):
        """The core behavior change this redesign exists for: a text criterion
        is compared against EVERY searchable field (here, trigger_condition),
        never just description/free-text fields - the user's explicit
        correction ("EVERY text search searches ALL text fields")."""
        manager.add_ledger_event(
            session_id="s",
            event=dict(SAMPLE_EVENT, description="דבר אחר לגמרי",
                       trigger_condition="בכפוף לתשלום מקדמה"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "בכפוף לתשלום מקדמה", "hint": None}])
        assert result["count"] == 1

    def test_text_criterion_matches_accounting_document_display_number(self, manager):
        manager._index.append(dict(
            SAMPLE_EVENT, event_id="H_TEST_3", source_type="חשבונית",
            accounting_document_display_number="40406",
        ))
        result = manager.query_events(criteria=[{"text": "40406", "hint": "document"}])
        assert result["count"] == 1

    def test_text_criterion_matches_accounting_document_status_label(self, manager):
        manager._index.append(dict(
            SAMPLE_EVENT, event_id="H_TEST_4", source_type="חשבונית",
            accounting_document_status_label="מסמך סגור",
        ))
        result = manager.query_events(criteria=[{"text": "מסמך סגור", "hint": "document"}])
        assert result["count"] == 1

    def test_text_criterion_matches_accounting_document_payment_method(self, manager):
        manager._index.append(dict(
            SAMPLE_EVENT, event_id="H_TEST_5", source_type="חשבונית",
            accounting_document_payment_method="העברה בנקאית",
        ))
        result = manager.query_events(criteria=[{"text": "העברה בנקאית", "hint": "document"}])
        assert result["count"] == 1

    def test_text_criterion_never_raises_on_a_raw_int_status_code_field(self, manager):
        """accounting_document_status_code (a raw int, deliberately excluded
        from _SEARCHABLE_FIELDS - accounting_document_status_label is the
        searchable text form) must never crash _score_criterion even though
        other events on the same index carry stray non-string field values."""
        manager._index.append(dict(
            SAMPLE_EVENT, event_id="H_TEST_6", source_type="חשבונית",
            accounting_document_status_code=2,
        ))
        result = manager.query_events(criteria=[{"text": "2", "hint": None}])
        assert result["count"] == 0  # status_code itself isn't a searched field

    def test_numeric_criterion_matches_amount_exactly(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, amount="5,000₪"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "5000", "hint": "amount"}])
        assert result["count"] == 1

    def test_numeric_criterion_does_not_match_a_different_amount(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, amount="5,000₪"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "38", "hint": "amount"}])
        assert result["count"] == 0

    def test_numeric_criterion_never_fuzzy_matches_an_unrelated_digit_heavy_text_field(self, manager):
        """Empirically-found bug (2026-08-24): fuzzy STRING matching between a
        numeric query and a digit-heavy non-numeric field (e.g. a date string)
        spuriously scores high via raw character overlap. A number criterion
        must ONLY ever be compared against genuinely numeric fields."""
        manager.add_ledger_event(
            session_id="s",
            event=dict(SAMPLE_EVENT, amount="0", txn_date="2026-08-24", hours="2"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "100", "hint": None}])
        assert result["count"] == 0

    def test_multiple_criteria_all_must_individually_match(self, manager):
        """Two events share the same amount but only one shares the identity -
        every criterion must clear the match floor INDIVIDUALLY, not just on
        average (2026-08-24 regression, found via a real OR-query test: a
        perfect amount match was "carrying" an irrelevant identity score past
        a mean-of-scores gate)."""
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה",
                                        client_name="אלי אבירם", amount="100"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה",
                                        client_name="דוד כרמון", amount="100"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[
            {"text": "אלי אבירם", "hint": "identity"},
            {"text": "100", "hint": "amount"},
        ])
        assert result["count"] == 1
        assert result["matches"][0]["client_name"] == "אלי אבירם"

    def test_hint_is_a_soft_bonus_not_a_hard_filter(self, manager):
        """A wrong/mismatched hint must never exclude an otherwise-real match -
        it only ever adds (or withholds) a scoring bonus."""
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "דוד כהן", "hint": "amount"}])
        assert result["count"] == 1

    def test_no_plausible_match_returns_empty_not_ambiguous(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(
            criteria=[{"text": "ישות שלא קיימת לגמרי", "hint": "identity"}]
        )
        assert "matches" in result
        assert result["count"] == 0

    def test_differently_worded_paraphrase_does_not_match(self, manager):
        """research.md's accepted limitation still holds after the redesign:
        keyword/typo-tolerant matching, NOT meaning-based - a completely
        different wording of the same legal matter is NOT expected to match."""
        manager.add_ledger_event(
            session_id="s",
            event=dict(SAMPLE_EVENT, description="אי הפרעה בשימוש במקרקעין"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "צו מניעה", "hint": "free_text"}])
        assert result["count"] == 0

    def test_matches_carry_a_confidence_score_at_or_above_the_floor(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "דוד כהן", "hint": "identity"}])
        assert result["matches"][0]["confidence"] >= 55


class TestQueryEventsIdentityAmbiguity:
    """Feature 044. 2026-08-26 (explicit user directive): the tool used to
    intercept an `identity`-hinted criterion matching 2+ distinct stored
    client_name/payer_name values and return a candidates shape INSTEAD of
    real events, forcing a clarifying question with no way to ever proceed
    past it (confirmed live: T028's billed test kept hitting the identical
    block even after the user had already resolved the ambiguity in
    conversation). Removed entirely - the tool always returns real matched
    events for every distinct name that clears the floor, and reasoning
    about whether more than one distinct name showing up is worth asking
    the user about is the model's own job now, not this tool's."""

    def test_exactly_one_distinct_candidate_returns_matches(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "דוד כהן", "hint": "identity"}])
        assert "matches" in result
        assert result["count"] == 1

    def test_two_distinct_names_both_returned_as_real_matches(self, manager):
        """A fuzzy multi-name match no longer blocks - both distinct
        client_names come back as ordinary, separately-scored matches."""
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד כהן"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, client_name="דוד לוי"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "דוד", "hint": "identity"}])
        assert "matches" in result
        assert "ambiguous_field" not in result
        client_names = {m["client_name"] for m in result["matches"]}
        assert client_names == {"דוד כהן", "דוד לוי"}


class TestQueryEventsVagueQueryGuard:
    """Feature 044: query_events refuses to scan the whole ledger when no
    criteria were given at all."""

    def test_empty_criteria_returns_no_search_criteria_error(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT), message_id="m1",
            message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[])
        assert result == {
            "error": "no_search_criteria",
            "message": result.get("message"),
        }
        assert "matches" not in result

    def test_none_criteria_returns_no_search_criteria_error(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT), message_id="m1",
            message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=None)
        assert result["error"] == "no_search_criteria"

    def test_single_criterion_proceeds_normally(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="הסכם"),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        result = manager.query_events(criteria=[{"text": "הסכם", "hint": "event_type"}])
        assert "matches" in result
        assert result["count"] == 1


# Feature 025 (Morning-Sourced Ledger Events), round 3 (2026-08-21) - raw
# arguments shape a reconciliation-sweep-driven capture_ledger_event call
# carries. Unlike SAMPLE_EVENT/SAMPLE_CALL_ARGUMENTS above (recognized from
# free-text/image signal), every accounting_document_* value here is
# transcribed directly from a real Morning Invoice record's own structured
# fields - never inferred - per data-model.md's LEDGER_EVENT_TOOL
# schema-change notes. The document's own creation_date carries full HH:MM
# precision (round 3 finding: Morning's real creationDate field is a genuine
# epoch timestamp, not date-only) and message_timestamp below is the epoch
# this same instant maps to, matching contracts/ledger-event-manager-
# extension.md's "message_timestamp for a חשבונית capture" note.
ACCOUNTING_DOC_TS = int(datetime(2026, 7, 28, 15, 6, 0, tzinfo=timezone.utc).timestamp())
# 2026-07-28T15:06:00 UTC -> Asia/Jerusalem local (UTC+3) -> 2026-07-28 18:06 local

# Phase 9 (2026-08-23): a חשבונית capture now arrives as ONE verbatim-copied
# JSON blob from morning-mcp-app, not as flat AI-transcribed fields. These
# helpers keep every pre-Phase-9 test below exercising the SAME behaviour
# (forced-null rules, dedup, cache, pruning) through the new input shape.
_SAMPLE_DOC = {
    "display_number": "40406",
    "internal_morning_id": "056ee93c-77ab-4d87-a170-d357988e876c",
    "type": 305, "type_name": "חשבונית מס",
    "status": "paid", "status_code": 1, "status_label": "מסמך סגור",
    "client_name": "לקוח בדיקה", "description": "חשבונית מס 100",
    "amount": 1000, "amount_excl_vat": 1000, "vat_amount": 180, "vat_rate": 0.18,
    "currency": "ILS", "document_date": "2026-07-28", "due_date": None,
    "creation_date": "2026-07-28T18:06:00+03:00",
    "payment": None, "linked_document": None,
}


def _accounting_event(**doc_overrides):
    """A חשבונית capture in its Phase 9 shape. Overrides apply to the DOCUMENT
    JSON (e.g. display_number=..., creation_date=...), not to flat event keys."""
    doc = dict(_SAMPLE_DOC, **doc_overrides)
    return {
        "source_type": "חשבונית",
        "event_subtype": "הפקה",
        "accounting_document_json": json.dumps(doc, ensure_ascii=False),
    }


SAMPLE_ACCOUNTING_EVENT = _accounting_event()

ACCOUNTING_DOCUMENT_FIELDS = [
    "accounting_document_display_number", "accounting_document_status",
]
# accounting_document_creation_date removed 2026-08-25 (user directive): was a
# byte-for-byte duplicate of event_datetime for every חשבונית record - dropped
# from the persisted schema; event_datetime itself is covered separately below
# (test_accounting_document_event_persists_its_fields), since it's populated
# for every source_type, not conditionally forced-null like the fields above.

# Every field that has no meaning for a source_type="חשבונית" capture (no
# agreement/component/conditional-fee/bank concept applies to a Morning
# document) - mirrors the existing per-source_type forced-null lists above
# (bank_number/etc for הסכם, agreement_id/etc for בנק).
NON_APPLICABLE_FIELDS_FOR_ACCOUNTING_DOCUMENT = [
    "agreement_id", "component_id", "component_label", "trigger_condition",
    "percent", "percent_base", "hours", "hourly_rate",
    "bank_number", "bank_branch", "bank_account", "payer_name",
]





class TestParseIsoLocalRobustness:
    """Feature 025, regression guard originally added after a real live-dev
    incident (2026-08-21): a first real 8-document sweep had EVERY event fall
    back to processing time instead of the document's own real creation time -
    the exact model output format was never logged at the time this happened,
    so the fix (below) covers the known-strict gaps in Python 3.9's
    datetime.fromisoformat rather than a single confirmed root cause, plus
    adds the diagnostic logging this incident was missing.

    Moved here 2026-08-25 from test_ai_handler_ledger_events.py's
    TestAccountingDocumentMessageTimestamp: that class exercised
    AIHandler._accounting_document_message_timestamp, which read the raw,
    un-expanded capture_ledger_event call arguments - a field that never
    actually appeared there in real traffic, making that method dead code
    (now removed). The real, working parsing lives here, in
    LedgerEventManager._parse_iso_local, reached via
    _expand_accounting_document_json's `creation_date` -> add_ledger_event's
    `accounting_created_dt` derivation - so the robustness coverage moves with
    it, exercising the function that actually runs in production."""

    def test_plain_iso_no_timezone_parses(self):
        assert _parse_iso_local("2026-08-20T18:52:00") is not None

    def test_trailing_z_suffix_parses(self):
        """Python 3.9's fromisoformat does NOT accept a trailing Z (only
        added in 3.11) - a real, known gap against what Morning's own
        creationDate field might plausibly carry."""
        assert _parse_iso_local("2026-08-20T18:52:00Z") is not None

    def test_space_separated_variant_parses(self):
        assert _parse_iso_local("2026-08-20 18:52:00") is not None

    def test_missing_value_returns_none_silently(self):
        assert _parse_iso_local(None) is None
        assert _parse_iso_local("") is None

    def test_genuinely_unparseable_value_returns_none_and_logs_the_raw_value(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = _parse_iso_local("not a date at all")
        assert result is None
        assert any("not a date at all" in r.message for r in caplog.records)


class TestAccountingDocumentFields:
    """Feature 025, T005a: the extended record shape for source_type="חשבונית"
    (data-model.md's field-rename table, round 3 - **4 fields, not 5**):
    accounting_document_display_number/_type/_status/_creation_date
    populated only for חשבונית, forced null for הסכם/בנק regardless of what's
    passed; event_subtype="הפקה" accepted; schema_version=2 globally (see
    TestSchemaVersion above); the old reserved field names never appear in a
    persisted record; there is no separate accounting_document_id field."""

    def test_accounting_document_event_persists_its_fields(
        self, manager, temp_events_dir
    ):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        data = _read(temp_events_dir, event_id)
        assert data["accounting_document_display_number"] == "40406"
        assert data["accounting_document_status"] == "שולם"
        # event_datetime is the sole creation-date field (2026-08-25) - derived
        # from the document's own real creation_date, not the capture instant.
        assert data["event_datetime"] == "28/07/2026 18:06"

    def test_event_subtype_carries_the_morning_doc_type(self, manager, temp_events_dir):
        """Superseded "הפקה" (2026-08-23) - see
        TestAccountingDocumentSubtypeIsTheMorningDocType."""
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        assert _read(temp_events_dir, event_id)["event_subtype"] == "חשבונית מס"

    def test_event_id_uses_letter_h_for_accounting_document(self, manager):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        assert event_id.startswith("H")

    def test_accounting_document_fields_forced_null_for_agreement_source_type(
        self, manager, temp_events_dir
    ):
        """Even if a caller mistakenly passes accounting_document_* values
        alongside source_type="הסכם", they're forced null - same defensive
        discipline as bank_number/payer_name/etc elsewhere in this file."""
        event = dict(SAMPLE_EVENT, **{f: "should be dropped" for f in ACCOUNTING_DOCUMENT_FIELDS})
        event_id = manager.add_ledger_event(
            session_id="s", event=event, message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in ACCOUNTING_DOCUMENT_FIELDS:
            assert data[field] is None, f"{field} must be null for source_type='הסכם'"

    def test_accounting_document_fields_forced_null_for_bank_source_type(
        self, manager, temp_events_dir
    ):
        event = dict(
            SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה",
            **{f: "should be dropped" for f in ACCOUNTING_DOCUMENT_FIELDS},
        )
        event_id = manager.add_ledger_event(
            session_id="s", event=event, message_id="m", message_timestamp=FIXED_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in ACCOUNTING_DOCUMENT_FIELDS:
            assert data[field] is None, f"{field} must be null for source_type='בנק'"

    def test_non_applicable_fields_forced_null_for_accounting_document(
        self, manager, temp_events_dir
    ):
        """The reverse direction: agreement/component/bank/payer concepts
        don't apply to a חשבונית capture - forced null regardless of what a
        caller passes."""
        event = dict(
            SAMPLE_ACCOUNTING_EVENT,
            agreement_id="should not matter", component_label="should be dropped",
            trigger_condition="should be dropped", percent="50", percent_base="1000",
            hours="3", hourly_rate="500", payer_name="should be dropped",
        )
        event_id = manager.add_ledger_event(
            session_id="s", event=event, message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        data = _read(temp_events_dir, event_id)
        for field in NON_APPLICABLE_FIELDS_FOR_ACCOUNTING_DOCUMENT:
            assert data[field] is None, f"{field} must be null for source_type='חשבונית'"

    def test_old_reserved_field_names_no_longer_present(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        data = _read(temp_events_dir, event_id)
        for old_name in (
            "morning_document_id", "invoice_number", "invoice_type",
            "invoice_status", "invoice_actual_creation_date",
            "accounting_document_id",  # round 3: never existed as its own field
        ):
            assert old_name not in data


class TestScanAccountingDocuments:
    """Feature 025, T006a: scan_accounting_documents - the one-time (per
    process) disk-scan bootstrap for LedgerEventManager's in-memory
    accounting-document cache, per data-model.md's round-3
    "AccountingDocumentReconciliationState" section. Returns
    Dict[display_number, List[AccountingDocumentCacheEntry]] (each entry a
    (timestamp, event_id) pair - added during implementation so an anomaly's
    pending_review.json entry can name the real prior event_id, not just its
    timestamp), NOT the old Tuple[Set[str],
    Optional[date]] shape."""

    def test_empty_storage_dir_returns_empty_dict(self, manager):
        assert manager.scan_accounting_documents() == {}

    def test_one_accounting_document_event_returns_its_number_and_timestamp(
        self, manager
    ):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        result = manager.scan_accounting_documents()
        assert list(result.keys()) == ["40406"]
        assert len(result["40406"]) == 1
        assert result["40406"][0].timestamp.strftime("%d/%m/%Y %H:%M") == "28/07/2026 18:06"

    def test_two_events_sharing_a_display_number_both_timestamps_present(
        self, manager
    ):
        """Simulates the anomaly case having already happened once - both of
        a display_number's distinct timestamps must be visible to a fresh
        scan, not just the latest."""
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m1", message_timestamp=ACCOUNTING_DOC_TS,
        )
        manager.add_ledger_event(
            session_id="s",
            event=_accounting_event(creation_date="2026-07-29T09:00:00+03:00"),
            message_id="m2", message_timestamp=None,
        )
        result = manager.scan_accounting_documents()
        assert len(result["40406"]) == 2

    def test_non_accounting_events_ignored_entirely(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m", message_timestamp=FIXED_TS,
        )
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        assert manager.scan_accounting_documents() == {}

    def test_malformed_json_file_skipped_with_warning(
        self, manager, temp_events_dir, caplog
    ):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        bad_file = temp_events_dir / "H999999999.json"
        bad_file.write_text("{not valid json", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = manager.scan_accounting_documents()

        assert list(result.keys()) == ["40406"]
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestAccountingDocumentCacheLazyInit:
    """Feature 025, T006a (second half): _ensure_accounting_document_cache
    must scan the disk AT MOST ONCE per manager instance, regardless of how
    many add_ledger_event calls happen afterward - the "no reading and
    parsing of the ledger events... per tick" guarantee (spec.md
    Clarifications, round 3)."""

    def test_scan_accounting_documents_called_at_most_once_across_multiple_captures(
        self, manager, monkeypatch
    ):
        call_count = {"n": 0}
        original = manager.scan_accounting_documents

        def _counting_scan():
            call_count["n"] += 1
            return original()

        monkeypatch.setattr(manager, "scan_accounting_documents", _counting_scan)

        manager.add_ledger_event(
            session_id="s", event=_accounting_event(accounting_document_display_number="1"),
            message_id="m1", message_timestamp=ACCOUNTING_DOC_TS,
        )
        manager.add_ledger_event(
            session_id="s", event=_accounting_event(accounting_document_display_number="2"),
            message_id="m2", message_timestamp=ACCOUNTING_DOC_TS,
        )
        manager.add_ledger_event(
            session_id="s", event=_accounting_event(accounting_document_display_number="3"),
            message_id="m3", message_timestamp=ACCOUNTING_DOC_TS,
        )

        assert call_count["n"] == 1


class TestAccountingDocumentTriState:
    """Feature 025, T007a: the tri-state new/duplicate/anomaly logic that
    REPLACES the old hard-refusal design (round 3, user directive: "I don't
    like the hard refusal... The 'since when' mechanism SHOULD NOT RELY ON A
    REFUSAL MECHANISM"). Lives entirely inside add_ledger_event/
    LedgerEventManager - a ledger concern, not an ai_handler.py one."""

    def test_new_display_number_persists_normally(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        assert event_id is not None
        assert len(list(temp_events_dir.glob("*.json"))) == 1

    def test_same_display_number_same_timestamp_is_true_duplicate_discarded(
        self, manager, temp_events_dir, caplog
    ):
        first_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m1", message_timestamp=ACCOUNTING_DOC_TS,
        )
        assert first_id is not None

        with caplog.at_level(logging.INFO):
            second_id = manager.add_ledger_event(
                session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
                message_id="m2", message_timestamp=ACCOUNTING_DOC_TS,
            )

        assert second_id is None
        assert len(list(temp_events_dir.glob("*.json"))) == 1
        assert not any(r.levelno >= logging.WARNING for r in caplog.records), (
            "a true duplicate is a normal re-poll, not a warning-worthy event"
        )

    def test_same_display_number_different_timestamp_is_anomaly_persisted_and_flagged(
        self, manager, temp_events_dir, caplog
    ):
        first_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m1", message_timestamp=ACCOUNTING_DOC_TS,
        )
        with caplog.at_level(logging.WARNING):
            second_id = manager.add_ledger_event(
                session_id="s",
                event=_accounting_event(creation_date="2026-07-29T09:00:00+03:00"),
                message_id="m2", message_timestamp=None,
            )

        assert second_id is not None
        assert second_id != first_id
        assert len(list(temp_events_dir.glob("*.json"))) == 2, (
            "an anomaly persists a NEW event, never overwrites/drops"
        )
        assert any(r.levelno == logging.WARNING for r in caplog.records)

        review_file = temp_events_dir.parent / "accounting_reconciliation" / "pending_review.json"
        assert review_file.exists()
        entries = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(entries) == 1
        assert entries[0]["accounting_document_display_number"] == "40406"
        assert entries[0]["prior_event_id"] == first_id
        assert entries[0]["new_event_id"] == second_id

    def test_guard_never_fires_for_non_accounting_source_types(self, manager, temp_events_dir):
        """הסכם/בנק events always have accounting_document_display_number=None
        - the guard must never treat two Nones as a collision with each
        other."""
        first_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m1", message_timestamp=FIXED_TS,
        )
        second_id = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT),
            message_id="m2", message_timestamp=FIXED_TS,
        )
        assert first_id is not None
        assert second_id is not None
        assert len(list(temp_events_dir.glob("*.json"))) == 2


class TestPruneAccountingDocumentCache:
    """Feature 025, T008a: prune_accounting_document_cache - drops cache
    entries older than the 5-day safety-cap boundary plus a 2-day margin (7
    days total) before `now`, per data-model.md's "Pruning" note."""

    def test_entry_older_than_boundary_is_dropped(self, manager):
        manager.add_ledger_event(
            session_id="s",
            event=_accounting_event(creation_date="2026-07-01T15:00:00+03:00"),
            message_id="m", message_timestamp=None,
        )
        now = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)  # 31 days later

        manager.prune_accounting_document_cache(now=now)

        assert manager._accounting_document_cache == {}

    def test_entry_within_boundary_is_kept(self, manager):
        manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_ACCOUNTING_EVENT),
            message_id="m", message_timestamp=ACCOUNTING_DOC_TS,
        )
        now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)  # 1 day later

        manager.prune_accounting_document_cache(now=now)

        assert "40406" in manager._accounting_document_cache

    def test_empty_cache_is_a_no_op(self, manager):
        manager.prune_accounting_document_cache()  # must not raise


# ============================================================================
# Feature 025 Phase 9: capture driven by morning-mcp-app's machine-readable
# JSON instead of AI-transcribed prose fields.
#
# The model copies one JSON blob verbatim; ALL mapping and derivation happens
# here in code. Payload shape below is real - captured from the dev sandbox
# 2026-08-23 (see specs/.../artifacts/v0/morning_raw_all18.json).
# ============================================================================

ACCOUNTING_DOC_JSON = {
    "display_number": "40406",
    "internal_morning_id": "056ee93c-77ab-4d87-a170-d357988e876c",
    "type": 300,
    "type_name": "חשבון עסקה",
    "status": "paid",
    "status_code": 2,
    "status_label": "מסמך סומן ידנית כסגור",
    "client_name": "נאדר קרא",
    "description": "תחזוקה",
    "amount": 51.92,
    "amount_excl_vat": 44,
    "vat_amount": 7.92,
    "vat_rate": 0.18,
    "currency": "ILS",
    "document_date": "2026-08-20",
    "due_date": None,
    "creation_date": "2026-08-20T18:52:48+03:00",
    "payment": None,
    "linked_document": None,
}

BANK_PAYMENT_JSON = {
    "method": "העברה בנקאית", "type": 4, "date": "2026-07-12", "amount": 1500,
    "bank_number": "31", "bank_branch": "109", "bank_account": "105542585",
}


def _json_event(**doc_overrides):
    """A capture_ledger_event call as the sweep now makes it: the model sets
    source_type/event_subtype and pastes the document JSON verbatim."""
    doc = dict(ACCOUNTING_DOC_JSON, **doc_overrides)
    return {
        "source_type": "חשבונית",
        "event_subtype": "הפקה",
        "accounting_document_json": json.dumps(doc, ensure_ascii=False),
    }


class TestAccountingDocumentJsonCapture:
    """Phase 9: every persisted value is derived in code from the JSON."""

    def test_core_fields_derived_from_json_not_from_ai_fields(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["accounting_document_display_number"] == "40406"
        assert data["client_name"] == "נאדר קרא"
        assert data["description"] == "תחזוקה"
        assert data["amount"] == 52  # normalized to int NIS by existing code

    def test_creation_timestamp_comes_from_json_with_real_time(self, manager, temp_events_dir):
        """The whole point of Phase 9's predecessor: never a fabricated 00:00."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        # accounting_document_creation_date removed 2026-08-25 - event_datetime
        # (derived from the same real JSON creation_date) is the sole assertion now.
        assert data["event_datetime"] == "20/08/2026 18:52"
        assert event_id.startswith("H2008261852")

    def test_status_keeps_canonical_hebrew_plus_morning_raw_code_and_label(
        self, manager, temp_events_dir
    ):
        """Morning's axis is open/closed, not paid/unpaid - keep its literal
        words alongside our interpretation so the real value is never lost."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["accounting_document_status"] == "שולם"
        assert data["accounting_document_status_code"] == 2
        assert data["accounting_document_status_label"] == "מסמך סומן ידנית כסגור"

    def test_payment_method_and_bank_details_captured(self, manager, temp_events_dir):
        """Bank fields were force-nulled for anything but source_type=בנק until
        Phase 9 lifted that (user decision, 2026-08-23)."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(payment=BANK_PAYMENT_JSON),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["accounting_document_payment_method"] == "העברה בנקאית"
        assert data["bank_number"] == "31"
        assert data["bank_branch"] == "109"
        assert data["bank_account"] == "105542585"

    def test_payment_date_maps_onto_the_existing_txn_date_field(self, manager, temp_events_dir):
        """User's catch: this is txn_date - "the transaction/value date" - not a
        new field. Real case: payment dated 12/07 on a document created 20/08."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(payment=BANK_PAYMENT_JSON),
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, event_id)["txn_date"] == "12/07/2026"

    def test_bank_fields_stay_null_when_payment_is_cash(self, manager, temp_events_dir):
        cash = {"method": "מזומן", "type": 1, "date": "2026-08-20", "amount": 500,
                "bank_number": None, "bank_branch": None, "bank_account": None}
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(payment=cash),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["accounting_document_payment_method"] == "מזומן"
        assert data["bank_number"] is None

    def test_vat_status_derived_in_code_not_asked_of_the_model(self, manager, temp_events_dir):
        with_vat = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(),
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, with_vat)["vat_status"] == "כולל"

    def test_vat_status_is_not_asserted_when_document_has_no_vat(self, manager, temp_events_dir):
        """A VAT-exempt document is neither inclusive nor exclusive - saying
        either would assert something false."""
        exempt = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(display_number="52204", vat_amount=0, amount_excl_vat=62, amount=62),
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, exempt)["vat_status"] == "לא צוין"

    # test_schema_version_is_3 / test_schema_version_is_current removed (2026-08-26, human
    # decision, post-incident) - see TestSchemaVersion's removal comment above for the full
    # policy rationale: no test may assert on schema_version's value, ever, not even against
    # the imported CURRENT_SCHEMA_VERSION constant.

    def test_malformed_json_is_rejected_and_logged_never_half_persisted(self, manager, caplog):
        event = {"source_type": "חשבונית", "event_subtype": "הפקה",
                 "accounting_document_json": "{not valid json"}
        with caplog.at_level(logging.ERROR):
            result = manager.add_ledger_event(
                session_id="accounting-reconciliation", event=event,
                message_id=None, message_timestamp=None,
            )
        assert result is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestAccountingDocumentLinkage:
    """Phase 9: linked documents map onto the EXISTING reference/reference_hint
    mechanism (user correction) - no linked_number/linked_type fields."""

    LINKED = {"number": "52203", "type": 305, "type_name": "חשבונית מס"}

    def test_reference_hint_always_written_with_number_and_hebrew_type(
        self, manager, temp_events_dir
    ):
        """Must carry everything known, with the type in Hebrew - never the
        raw 305 (user decision)."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(display_number="70284", linked_document=self.LINKED),
            message_id=None, message_timestamp=None,
        )
        hint = _read(temp_events_dir, event_id)["reference_hint"]
        assert "52203" in hint
        assert "חשבונית מס" in hint
        assert "305" not in hint

    def test_reference_resolves_to_the_real_event_id_when_target_already_captured(
        self, manager, temp_events_dir
    ):
        target_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(display_number="52203"),
            message_id=None, message_timestamp=None,
        )
        credit_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(display_number="70284", linked_document=self.LINKED,
                              creation_date="2026-08-20T01:57:00+03:00"),
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, credit_id)["reference"] == target_id

    def test_unresolved_link_keeps_placeholder_and_notes_the_failure_in_the_hint(
        self, manager, temp_events_dir
    ):
        """Expected to be common: the list is newest-first, so a credit note is
        often captured before the document it cancels."""
        from src.managers.ledger_event_manager import REFERENCE_PLACEHOLDER

        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_json_event(display_number="70284", linked_document=self.LINKED),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] == REFERENCE_PLACEHOLDER
        assert "52203" in data["reference_hint"]
        assert "לא אותר" in data["reference_hint"]   # failure noted, per user

    def test_no_linked_document_leaves_reference_fields_null(self, manager, temp_events_dir):
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_json_event(),
            message_id=None, message_timestamp=None,
        )
        data = _read(temp_events_dir, event_id)
        assert data["reference"] is None
        assert data["reference_hint"] is None


class TestAccountingDocumentLineItems:
    """Phase 9 (user decision, 2026-08-23): "use only the 1st. log and warn if
    the array has more elements" - a multi-line document must never be
    silently half-captured."""

    def test_single_line_item_used_without_warning(self, manager, temp_events_dir, caplog):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="accounting-reconciliation",
                event=_accounting_event(line_items=[
                    {"description": "ייעוץ", "quantity": 1, "price": 1000, "amount": 1000},
                ]),
                message_id=None, message_timestamp=None,
            )
        assert _read(temp_events_dir, event_id)["description"] == "ייעוץ"
        assert not any("line item" in r.message.lower() for r in caplog.records)

    def test_multiple_line_items_uses_the_first_and_warns(
        self, manager, temp_events_dir, caplog
    ):
        with caplog.at_level(logging.WARNING):
            event_id = manager.add_ledger_event(
                session_id="accounting-reconciliation",
                event=_accounting_event(line_items=[
                    {"description": "ייעוץ", "quantity": 1, "price": 1000, "amount": 1000},
                    {"description": "נסיעות", "quantity": 1, "price": 250, "amount": 250},
                    {"description": "צילומים", "quantity": 1, "price": 50, "amount": 50},
                ]),
                message_id=None, message_timestamp=None,
            )
        data = _read(temp_events_dir, event_id)
        assert data["description"] == "ייעוץ"          # first only
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("3" in m and "40406" in m for m in warnings), (
            "the warning must name how many line items were dropped, and for which document"
        )

    def test_no_line_items_falls_back_to_document_level_description(
        self, manager, temp_events_dir
    ):
        """A 400/קבלה genuinely has no income[] at all."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event=_accounting_event(line_items=[], description="שרותי גרירה"),
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, event_id)["description"] == "שרותי גרירה"


class TestAccountingDocumentEmptyComponents:
    """Phase 9: the sweep sends component_count=0/components=[] because the JSON
    payload carries everything - that must NOT trigger REQ-DATA-008's
    "AI capture returned zero components" fallback record, which is meant for a
    genuinely failed conversational capture."""

    def test_empty_components_is_normal_for_an_accounting_document(
        self, manager, temp_events_dir, caplog
    ):
        call_args = dict(_accounting_event(), component_count=0, components=[])
        with caplog.at_level(logging.ERROR):
            event_ids = manager.add_ledger_events_from_call(
                session_id="accounting-reconciliation", call_arguments=call_args,
                message_id=None, message_timestamp=None,
            )
        assert len(event_ids) == 1
        data = _read(temp_events_dir, event_ids[0])
        assert data["accounting_document_display_number"] == "40406"
        assert "needs manual review" not in (data["description"] or "")
        assert not any(r.levelno == logging.ERROR for r in caplog.records)


class TestAccountingDocumentJsonRobustness:
    """Real live finding (2026-08-23): 3 of 18 documents were silently lost
    because the MODEL introduced literal control characters (newlines) while
    copying the JSON - the source payload from morning-mcp-app is always valid,
    json.dumps escapes newlines as \\n, but the copy came back with real ones.
    Tolerating that is correct: the content is intact, only the whitespace
    escaping was mangled in transit."""

    def test_literal_newlines_inside_the_copied_json_are_tolerated(
        self, manager, temp_events_dir
    ):
        doc = dict(_SAMPLE_DOC, description="ייעוץ\nמשפטי")
        mangled = json.dumps(doc, ensure_ascii=False).replace("\\n", "\n")  # model's mistake
        event = {"source_type": "חשבונית", "event_subtype": "הפקה",
                 "accounting_document_json": mangled}

        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=event,
            message_id=None, message_timestamp=None,
        )

        assert event_id is not None, "a mangled-whitespace copy must not lose the document"
        assert _read(temp_events_dir, event_id)["accounting_document_display_number"] == "40406"

    def test_genuinely_broken_json_is_still_rejected(self, manager, caplog):
        """Tolerance is limited to whitespace escaping - real corruption must
        still fail loudly rather than persist a half-read document."""
        event = {"source_type": "חשבונית", "event_subtype": "הפקה",
                 "accounting_document_json": '{"display_number": "40406", "type"'}
        with caplog.at_level(logging.ERROR):
            result = manager.add_ledger_event(
                session_id="accounting-reconciliation", event=event,
                message_id=None, message_timestamp=None,
            )
        assert result is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestAccountingDocumentSubtypeIsTheMorningDocType:
    """User decision (2026-08-23): the Morning document type is persisted in
    `event_subtype`, using Morning's OWN label retrieved from its API - never a
    hand-written string. That makes the separate accounting_document_type field
    redundant, so it is removed.

    Replaces the previous flat mapping, where all five document types collapsed
    to event_subtype="הפקה" and the real type survived only in a descriptive
    field."""

    MORNING_TYPES = {
        300: "חשבון עסקה",
        305: "חשבונית מס",
        320: "חשבונית מס / קבלה",
        330: "חשבונית זיכוי",
        400: "קבלה",
    }

    def test_event_subtype_is_the_morning_document_type_label(
        self, manager, temp_events_dir
    ):
        for code, label in self.MORNING_TYPES.items():
            event_id = manager.add_ledger_event(
                session_id="accounting-reconciliation",
                event=_accounting_event(display_number=f"doc-{code}", type=code, type_name=label),
                message_id=None, message_timestamp=None,
            )
            assert _read(temp_events_dir, event_id)["event_subtype"] == label, f"type {code}"

    def test_the_model_supplied_subtype_is_ignored_for_an_accounting_document(
        self, manager, temp_events_dir
    ):
        """Code derives it from the payload - whatever the model passed is not
        trusted, same discipline as every other Phase 9 value."""
        event = dict(_accounting_event(type=330, type_name="חשבונית זיכוי"),
                     event_subtype="הפקה")
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=event,
            message_id=None, message_timestamp=None,
        )
        assert _read(temp_events_dir, event_id)["event_subtype"] == "חשבונית זיכוי"

    def test_accounting_document_type_field_is_gone(self, manager, temp_events_dir):
        """Redundant now that the type lives in event_subtype."""
        event_id = manager.add_ledger_event(
            session_id="accounting-reconciliation", event=_accounting_event(),
            message_id=None, message_timestamp=None,
        )
        assert "accounting_document_type" not in _read(temp_events_dir, event_id)

    def test_agreement_and_bank_subtypes_are_untouched(self, manager, temp_events_dir):
        """Only the חשבונית path changes - הסכם/בנק keep their own vocabulary."""
        a = manager.add_ledger_event(session_id="s", event=dict(SAMPLE_EVENT),
                                     message_id="m", message_timestamp=FIXED_TS)
        b = manager.add_ledger_event(
            session_id="s", event=dict(SAMPLE_EVENT, source_type="בנק", event_subtype="הפקדה"),
            message_id="m2", message_timestamp=FIXED_TS)
        assert _read(temp_events_dir, a)["event_subtype"] == "יצירה"
        assert _read(temp_events_dir, b)["event_subtype"] == "הפקדה"
