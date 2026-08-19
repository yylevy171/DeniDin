"""
End-to-End Test: Ledger Event Recognition (runtime_constitution.md) - text flow

Split out of tests/expensive/test_ledger_event_capture_e2e.py (2026-08-03): that
file's whole class was marked `@pytest.mark.expensive`, but 9 of its 15 tests
send a plain `textMessage` webhook - no vision/image call involved at all, so
they were misclassified. Confirmed via source inspection (each test below builds
a `'typeMessage': 'textMessage'` notification, never `imageMessage`). Only the
image-flow tests (6 of the original 15) legitimately stay `expensive` - see that
file's own docstring.

Tests the real OpenAI function-calling mechanism end-to-end - NOT unit-testable,
since what's actually under test is whether the real model classifies correctly
(calls `capture_ledger_event` only when the content genuinely warrants it) and
extracts fields correctly, here via plain text (no vision pipeline).

Feature 033 (Ledger Event Persistence): events persist as their own files under
`{data_root}/events/{event_id}.json` via LedgerEventManager.

NO MOCKING - real OpenAI API calls, real session storage.

Run with: pytest tests/billed/test_ledger_event_capture_text_billed.py -m billed -v
"""

import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from src.utils.time_utils import local_from_timestamp
from tests.e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
    ClarificationAnswerBank,
    converse_until_ledger_events_captured,
    reserve_ledger_event_bucket_prefixes,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.billed
class TestLedgerEventCaptureTextBilled:
    """
    Given/When/Then E2E coverage for Ledger Event Recognition's text flow:
    - Given a text message that genuinely warrants capture, When processed, Then
      `capture_ledger_event` is called and the result lands in its own file under
      `data/events/`, correctly shaped per data-model.md.
    """

    @pytest.fixture
    def config(self):
        """Load test configuration (real credentials, isolated test_data/ root)."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        """Initialize the full denidin app - NO MOCKING."""
        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                'ai_vision_model': config.ai_vision_model,
                'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles,
                'mcp': config.mcp,
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)

        # Safety guard, every call (not just first-init): LedgerEventManager.storage_dir
        # MUST resolve under this test's isolated data_root (test_data/), never the real
        # production/dev data root - a wiring mistake here would write test noise into
        # the real financial ledger. Fails loud and immediately rather than silently
        # polluting data/events/ or dev_data/events/.
        actual_events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_events_dir.is_relative_to(expected_root), (
            f"LedgerEventManager.storage_dir={actual_events_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed, this "
            f"would write into production/dev ledger data"
        )
        return denidin.denidin_app

    # Fixed webhook 'timestamp' epochs used across this class's tests (mirrored
    # from each test's own notification literal below) - these are FIXED, not
    # "now", so every run maps to the exact same LedgerEventManager event_id
    # bucket (letter+ddmmyy+hhmm). REQ-ID-003 only allows 10 seq-digit files per
    # bucket; without cleanup, test_data/events/ accumulates one file per run
    # and permanently exhausts the bucket after ~10 runs - which is exactly what
    # happened 2026-08-10 (bugfix-028 billed run): two tests failed with "No free
    # seq digit" because their buckets already had all 10 slots filled from
    # earlier runs.
    _FIXED_MESSAGE_TIMESTAMPS = (
        1770000500, 1770000600, 1770001000, 1770002000, 1770002100, 1770002200,
        # 2026-08-18 player-review follow-up additions:
        1770000530,  # גיליאן דוידיאן follow-up answer (added to the existing test)
        1770003000,  # trigger_condition
        1770004000, 1770004100,  # reference_hint "addition" (two-message flow)
        1770005000,  # ask-instead-of-guess (hyphenated name)
        1770006000,  # hourly minimal-message regression
    )

    @classmethod
    def _event_id_bucket_prefixes(cls) -> set:
        """The event_id prefix (letter+ddmmyy+hhmm, sans seq digit) each fixed
        timestamp above maps to, computed the same way LedgerEventManager does
        (bugfix-037: via time_utils.local_from_timestamp) - so cleanup targets
        exactly the files these tests could have produced, nothing else in
        test_data/events/."""
        return {
            f"A{local_from_timestamp(ts).strftime('%d%m%y%H%M')}"
            for ts in cls._FIXED_MESSAGE_TIMESTAMPS
        }

    @pytest.fixture(autouse=True)
    def _clean_fixed_timestamp_events(self, config):
        """Before AND after every test in this class: remove any previously-
        persisted event file for this class's fixed-timestamp buckets, so
        REQ-ID-003's 10-seq-digit cap never silently exhausts across repeated
        runs again (see _FIXED_MESSAGE_TIMESTAMPS docstring above)."""
        def _clean():
            events_dir = Path(config.data_root) / "events"
            if not events_dir.exists():
                return
            prefixes = self._event_id_bucket_prefixes()
            for f in events_dir.glob("*.json"):
                if any(f.stem.startswith(p) for p in prefixes):
                    f.unlink()

        _clean()
        yield
        _clean()

    @staticmethod
    def _fresh_chat_id(label: str) -> str:
        """A unique-per-run chat_id, so re-running a single test doesn't accumulate
        unbounded ledger events for a shared chat and confuse assertions."""
        return f"97250{uuid.uuid4().hex[:7]}_{label}@c.us"

    @staticmethod
    def _israel_date_str(base_timestamp: int, days_ago: int = 0) -> str:
        """REQ-DATA-005: `DD/MM/YYYY`, `days_ago` days before the Israel-local date of
        `base_timestamp` - the model resolves 'אתמול'/'היום' against the MESSAGE'S
        OWN timestamp, not real wall-clock time (every real `AIHandler._build_instructions`
        call site passes `today_timestamp=request.timestamp`, confirmed 2026-08-18 -
        see `ai_handler.py:1216,1906,1981,2047`), so expected txn_date values must be
        computed from the same fixed message timestamp the test itself sends, never
        from whenever the test happens to actually run.

        Contrast with `captured_at`, which genuinely IS real wall-clock - it's
        persisted via `now_local()` at the moment `LedgerEventManager` writes the
        event to disk (`ledger_event_manager.py:297`), independent of the message's
        own timestamp. Don't generalize this fix to that field - only date fields
        the MODEL resolves from message text (txn_date, event_datetime) go through
        the message's own timestamp; `captured_at` is a write-time system stamp."""
        base_date = local_from_timestamp(base_timestamp)
        return (base_date - timedelta(days=days_ago)).strftime("%d/%m/%Y")

    @staticmethod
    def _events_for_chat(denidin_app, chat_id):
        """All persisted LedgerEvent files (data/events/*.json) for this chat_id,
        sorted by captured_at - reads the real files off disk, not an in-memory
        proxy, so assertions prove the event genuinely landed in permanent storage
        (Feature 033's whole point).

        2026-08-19: LedgerEvent no longer carries its own whatsapp_chat (removed -
        redundant with session_id, which already points at a session that carries
        its own whatsapp_chat) - filters by session_id instead, resolved via the
        real SessionManager for this chat_id."""
        session_id = denidin_app.ai_handler.session_manager.get_session(chat_id).session_id
        events_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
        results = []
        for f in events_dir.glob("*.json"):
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get("session_id") == session_id:
                results.append(data)
        results.sort(key=lambda d: d["captured_at"])
        return results

    @staticmethod
    def _assert_ledger_events_persisted(denidin_app, chat_id, expected_count, expected_event_timestamp):
        """Asserts events were persisted for this chat, each with the bookkeeping
        fields LedgerEventManager.add_ledger_event adds (event_datetime = the real
        hard pointer, captured_at, message_id) present and correct. Returns the
        events in capture order for further field-specific assertions.

        expected_count: exact count required, or None to only assert >=1.

        expected_event_timestamp: the real Green API notification timestamp (unix
        epoch seconds) these events should be pointed at - the constitution's "hard
        pointer" requirement (never processing time, never a guess).

        2026-08-18 (player-review follow-up audit): this helper was stale -
        `message_timestamp` and `sender` were both removed from the persisted
        record back in the original Phase 11 revision (2026-08-16; sender/
        message_timestamp fully covered by event_datetime, see data-model.md
        SS1b) but this helper still asserted on them, which would have failed
        the very next time this file actually ran. Fixed to check
        `event_datetime` (the field that actually replaced message_timestamp)
        and dropped the sender assertion entirely.
        """
        events = TestLedgerEventCaptureTextBilled._events_for_chat(denidin_app, chat_id)
        if expected_count is None:
            assert len(events) >= 1, f"Expected at least 1 persisted ledger event for {chat_id}, found 0"
        else:
            assert len(events) == expected_count, (
                f"Expected {expected_count} persisted ledger event(s) for {chat_id}, "
                f"found {len(events)}: {events}"
            )

        # bugfix-037/Phase 11: event_datetime is Israel local time, "DD/MM/YYYY HH:MM".
        expected_event_datetime = local_from_timestamp(expected_event_timestamp).strftime("%d/%m/%Y %H:%M")
        for record in events:
            assert record.get("event_datetime") == expected_event_datetime, (
                f"event_datetime={record.get('event_datetime')!r} does not match the "
                f"real notification timestamp {expected_event_datetime!r} - the constitution's "
                f"'hard pointer' requirement (never processing time, never a guess)"
            )
            assert record.get("captured_at"), "captured_at was not persisted"
            assert record.get("message_id"), (
                "message_id must be non-null for events captured after Feature 033 - "
                "closes the traceability gap that motivated this feature"
            )
            assert "raw_message_excerpt" not in record, (
                "raw_message_excerpt was removed from the persisted schema (2026-08-18) - "
                "the source content now lives on the message record itself "
                "(Message.content for text, Message.extracted_text for media)"
            )
        return events

    @staticmethod
    def _read_message(denidin_app, chat_id, message_id):
        """Reads the real persisted message record off disk (session_manager's
        actual storage), for field-level assertions beyond the ledger_event_ids
        cross-check below."""
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        message_file = session_manager.storage_dir / session_id / "messages" / f"{message_id}.json"
        with open(message_file, encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _assert_message_links_back_to_event(denidin_app, chat_id, event):
        """Cross-checks the reverse link: the source message's ledger_event_ids
        (Feature 033) must include this event's event_id."""
        message_data = TestLedgerEventCaptureTextBilled._read_message(denidin_app, chat_id, event["message_id"])
        assert event["event_id"] in message_data["ledger_event_ids"], (
            f"event {event['event_id']} not found in source message {event['message_id']}'s "
            f"ledger_event_ids={message_data.get('ledger_event_ids')!r}"
        )

    # ------------------------------------------------------------------
    # MULTI-COMPONENT SPLIT (Feature 033, US3) - the real message that motivated
    # this whole feature
    # ------------------------------------------------------------------

    def test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component(
        self, denidin_app
    ):
        """Given the EXACT, unmodified real message that originally produced ONE
        combined event with all 3 stages' amounts crammed into one `amount` field
        (the live-captured defect that motivated Feature 033 - verbatim source in
        specs/in-progress/033-ledger-event-persistence/data-model.md's migration
        appendix), When processed, Then the correct target behavior is 3 SEPARATE
        persisted events, one per conditional fee stage (T020a).

        This is a genuine test of real model behavior, not just this feature's
        persistence code. Per explicit instruction: write the strict correct
        assertion, don't pre-soften it - if the model still doesn't split it today,
        this test SHOULD fail, and that's real, separately-actionable information
        (reliably fixing the model's splitting behavior is deferred to the
        constitution/nuances follow-on feature per spec.md's "Deferred to a
        follow-on feature" - a failure here doesn't block this feature's other
        tests, all of which cover the persistence layer given whatever the model
        actually returns).

        2026-08-18 addition: real runs showed the model's turn-1 behavior for
        this message is genuinely non-deterministic - sometimes it captures
        directly, sometimes it asks a clarifying question about one or more
        specific fields first (real observed examples: whether משרד הרווחה is
        the payer or the related matter; whether "בית משפט השלום" is what's
        meant by the source text's "ימשפט שלום" typo) instead of calling the
        tool at all. Uses the generic converse_until_ledger_events_captured
        driver (tests/e2e_helpers.py) rather than ad-hoc per-test logic: it
        sends turns and checks for real persisted events after each one,
        stopping the moment capture happens (never sends a further turn once
        it has - an earlier version of this test that always sent one fixed
        follow-up unconditionally caused a genuine DOUBLE capture, 6 events
        instead of 3, when turn 1 had already captured on its own). If no
        capture happens, the model's own reply is matched against a
        deterministic keyword-based ClarificationAnswerBank (no AI, no NLP -
        this is a fixed, curated fixture message, so every field's
        ground-truth correct value is already known; "answering the question"
        is just "which known topic does its text touch") to compose the next
        turn - falling back to a generic "לא הבנתי, תעשה מה שאתה מבין" reply
        for a question that doesn't match any known topic, rather than
        guessing wrong or blocking."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("text_multi_stage")
        raw_text = (
            "גיליאן דוידיאן\n"
            "משרד הרווחה\n\n"
            "1. אם יהיה שימוע להשעיה - 8,000₪\n"
            "2. ⁠למידת תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע לסדר טיעון - 20,000₪\n"
            "3. ⁠אם המשא ימתן יכשל ונאלץ לנהל הוכחות ימשפט שלום - עוד 30,000₪"
        )
        answer_bank = ClarificationAnswerBank([
            {
                "topic": "payer_vs_matter",
                "keywords": ["משלם", "גורם המשלם", "מי משלם", "גוף המשלם"],
                "answer": "משרד הרווחה לא משלם, זה מקום העבודה/העניין של הלקוח - אין גורם משלם נפרד",
            },
            {
                "topic": "court_name_typo",
                "keywords": ["בית משפט", "בימ\"ש", "בית המשפט", "משפט שלום"],
                "answer": "הכוונה ל'בית משפט השלום', כן",
            },
            {
                "topic": "vat",
                "keywords": ["מע\"מ", "מעמ", "כולל מעמ"],
                "answer": "המע\"מ לא צוין באף אחד מהסכומים",
            },
            {
                "topic": "client_identity",
                "keywords": ["מי הלקוח", "שם הלקוח", "האם גיליאן"],
                "answer": "הלקוחה היא גיליאן דוידיאן",
            },
        ])

        MAX_TURNS = 4
        BASE_TIMESTAMP = 1770000500

        # This test's message_timestamps are fixed, not real wall-clock time -
        # so every possible turn always targets the exact same letter+DDMMYY+
        # HHMM event_id bucket(s) on every run. LedgerEventManager._next_seq
        # picks the next free seq digit by scanning REAL FILES already on disk
        # under storage_dir for that prefix (REQ-ID-002), which is never
        # cleaned between test runs - without cleanup here, a second run of
        # this exact test continues an earlier run's sequence instead of the
        # fresh one this test asserts (a real, order-independent failure,
        # 2026-08-03). Clean before AND after, across every bucket ANY of the
        # up-to-MAX_TURNS turns could have used - not just however many
        # actually ran this time.
        stale_prefixes = reserve_ledger_event_bucket_prefixes(BASE_TIMESTAMP, MAX_TURNS)

        def _clean_stale_events():
            for prefix in stale_prefixes:
                for stale_file in Path(denidin_app.ai_handler.ledger_event_manager.storage_dir).glob(f"{prefix}*.json"):
                    stale_file.unlink()

        _clean_stale_events()

        try:
            events, transcript = converse_until_ledger_events_captured(
                handle_text_message=handle_text_message,
                chat_id=chat_id,
                first_message_text=raw_text,
                answer_bank=answer_bank,
                events_for_chat=lambda cid: self._events_for_chat(denidin_app, cid),
                base_timestamp=BASE_TIMESTAMP,
                base_id_message="LEDGER_E2E_TEXT_MULTISTAGE",
                sender_data={'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
                max_turns=MAX_TURNS,
                test_logger=logger,
            )
            logger.info(f"THEN captured {len(events)} event(s) after {len(transcript)} turn(s): {events}")

            amounts = sorted(e.get("amount") for e in events)
            assert amounts == [8000, 20000, 30000], (
                f"Expected 3 separate components with amounts 8000/20000/30000, got "
                f"{amounts} (transcript: {transcript!r}) - if this fails, the model did "
                f"not split the message per component (see spec.md 'Deferred to a "
                f"follow-on feature')"
            )
            for e in events:
                assert e["source_type"] == "הסכם"
                assert e["client_name"] and "גיליאן" in e["client_name"]
                self._assert_message_links_back_to_event(denidin_app, chat_id, e)

            # each component's event_id must share the same letter+DDMMYY+HHMM prefix,
            # with sequential seq (0,1,2), never colliding - guaranteed by the driver
            # only ever asserting on one turn's worth of events (never a cross-turn mix).
            prefixes = {e["event_id"][:-1] for e in events}
            assert len(prefixes) == 1, f"expected all 3 to share one letter+minute prefix, got {prefixes}"
            seqs = sorted(int(e["event_id"][-1]) for e in events)
            assert seqs == [0, 1, 2]
        finally:
            _clean_stale_events()

    # ------------------------------------------------------------------
    # DATA-MODEL CORRECTNESS FOR AGREEMENTS (Feature 033) - one real message per
    # event_subtype/field-shape, verifying the full persisted record, not just
    # source_type/client_name/amount
    # ------------------------------------------------------------------

    def test_given_new_agreement_flat_fee_then_all_fields_correctly_persisted(self, denidin_app):
        """Given a plain new-agreement message with an explicit VAT-inclusive flat
        fee, When processed, Then every direct-mapped field is correct (T022a)."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("agreement_flat_fee")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000600,
            'idMessage': 'LEDGER_E2E_AGREEMENT_FLAT_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'עמוס כהן - ייצוג בהסכם שכירות, שכר טרחה 4,000 ₪ כולל מעמ'
                }
            }
        })

        logger.info("GIVEN a new-agreement message with a flat VAT-inclusive fee")
        handle_text_message(notification)
        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1, expected_event_timestamp=1770000600
        )
        captured = events[0]
        logger.info(f"THEN captured event: {captured}")

        assert captured["source_type"] == "הסכם"
        assert captured["event_subtype"] == "יצירה"
        assert "עמוס" in (captured.get("client_name") or "") or "כהן" in (captured.get("client_name") or "")
        assert captured["amount"] == 4000
        assert captured["vat_status"] == "כולל"
        assert captured["percent"] is None
        assert captured["hours"] is None

    def test_given_agreement_percent_based_fee_then_percent_fields_correct(self, denidin_app):
        """Given a percentage-of-outcome fee with no fixed amount (mirrors the real
        Events.csv "אתי אסולין" pattern found during this feature's research), When
        processed, Then percent/percent_base are populated and amount stays blank
        (T022e)."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("agreement_percent")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770001000,
            'idMessage': 'LEDGER_E2E_AGREEMENT_PERCENT_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'הסכם עם מירי שגיא: 20% מסכום הזכיה בתביעה, ללא סכום קבוע מראש'
                }
            }
        })

        logger.info("GIVEN a percentage-of-outcome fee agreement, no fixed amount")
        handle_text_message(notification)
        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1, expected_event_timestamp=1770001000
        )
        captured = events[0]
        logger.info(f"THEN captured event: {captured}")

        assert captured["source_type"] == "הסכם"
        assert captured["percent"] is not None and "20" in captured["percent"]
        assert captured["percent_base"], "expected percent_base to describe what the percent applies to"
        assert captured["amount"] is None, "no fixed amount was stated - amount should stay blank"

    # ------------------------------------------------------------------
    # HOURS FLOW (REQ-DATA-005, real work-log messages)
    # ------------------------------------------------------------------

    def test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted(
        self, denidin_app
    ):
        """Given the EXACT real single-day hourly work-log message "רן אורפני 4 שעות
        על היום", When processed, Then ONE event is captured with client_name, hours,
        and txn_date (REQ-DATA-005) all correctly populated - txn_date must equal the
        Israel-local date of the message's OWN timestamp (every real
        AIHandler._build_instructions call site passes today_timestamp=request.timestamp,
        confirmed 2026-08-18 - "today" is always resolved against the message's own
        timestamp, never real wall-clock time), not copied from event_date by
        coincidence."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("hours_single_day")
        raw_text = "רן אורפני 4 שעות על היום"
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770002000,
            'idMessage': 'LEDGER_E2E_HOURS_SINGLE_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': raw_text}
            }
        })

        logger.info("GIVEN the real single-day hours message רן אורפני 4 שעות על היום")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1, expected_event_timestamp=1770002000
        )
        captured = events[0]
        logger.info(f"THEN captured event: {captured}")

        assert "רן אורפני" in (captured.get("client_name") or "")
        assert captured.get("hours") == 4.0, f"expected hours=4.0 (REQ-DATA-009), got {captured.get('hours')!r}"
        expected_txn_date = self._israel_date_str(1770002000, 0)
        assert captured.get("txn_date") == expected_txn_date, (
            f"expected txn_date={expected_txn_date!r} (the Israel-local date of the "
            f"message's own timestamp - 'today' is resolved against request.timestamp, "
            f"not real wall-clock time), got {captured.get('txn_date')!r}"
        )
        assert captured["source_type"] == "הסכם"
        self._assert_message_links_back_to_event(denidin_app, chat_id, captured)

    def test_given_real_two_day_hours_message_then_split_per_day_with_correct_dates(
        self, denidin_app
    ):
        """Given the EXACT real message "ענבר בן סימון\\nתגובה לטיעון משלים\\nאתמול 4
        שעות\\nהיום 5 שעות" (two separate day-entries in one message - the constitution's
        existing "never aggregate" rule applies here exactly as it does to multi-stage
        fee agreements), When processed, Then TWO separate events are captured, one per
        day, each with its own correct hours + txn_date (REQ-DATA-005) - never both
        entries collapsed into one event, never both stamped with the same date."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("hours_two_day")
        raw_text = "ענבר בן סימון\nתגובה לטיעון משלים\nאתמול 4 שעות\nהיום 5 שעות"
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770002100,
            'idMessage': 'LEDGER_E2E_HOURS_TWODAY_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': raw_text}
            }
        })

        logger.info("GIVEN the real two-day hours message (ענבר בן סימון, אתמול 4 שעות / היום 5 שעות)")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=2, expected_event_timestamp=1770002100
        )
        logger.info(f"THEN captured {len(events)} events: {events}")

        for e in events:
            assert "ענבר בן סימון" in (e.get("client_name") or "")
            assert e["source_type"] == "הסכם"
            self._assert_message_links_back_to_event(denidin_app, chat_id, e)

        by_txn_date = {e.get("txn_date"): e for e in events}
        today_str = self._israel_date_str(1770002100, 0)
        yesterday_str = self._israel_date_str(1770002100, 1)
        assert set(by_txn_date.keys()) == {today_str, yesterday_str}, (
            f"expected txn_date values {{today={today_str!r}, yesterday={yesterday_str!r}}}, "
            f"got {set(by_txn_date.keys())!r}"
        )
        assert by_txn_date[yesterday_str].get("hours") == 4.0, (
            "the אתמול (yesterday) entry should carry 4 hours (REQ-DATA-009)"
        )
        assert by_txn_date[today_str].get("hours") == 5.0, (
            "the היום (today) entry should carry 5 hours (REQ-DATA-009)"
        )

    def test_given_real_hours_message_with_payer_reference_then_payer_name_captured(
        self, denidin_app
    ):
        """Given the EXACT real message "רן אורפני\\nדרך הראל\\nעל אתמול שעתיים\\nעל
        היום שעתיים" ("via הראל" - an insurer routing payment, distinct from the
        client), When processed, Then TWO events are captured (one per day, same
        never-aggregate rule as above), each with client_name=רן אורפני,
        payer_name referencing הראל, hours resolved from "שעתיים" (word-form "two
        hours") to a numeric 2, and the correct per-day txn_date (REQ-DATA-005)."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("hours_payer_ref")
        raw_text = "רן אורפני\nדרך הראל\nעל אתמול שעתיים\nעל היום שעתיים"
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770002200,
            'idMessage': 'LEDGER_E2E_HOURS_PAYER_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': raw_text}
            }
        })

        logger.info("GIVEN the real hours message with a payer reference (רן אורפני דרך הראל)")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=2, expected_event_timestamp=1770002200
        )
        logger.info(f"THEN captured {len(events)} events: {events}")

        for e in events:
            assert "רן אורפני" in (e.get("client_name") or "")
            assert "הראל" in (e.get("payer_name") or ""), (
                f"expected payer_name to reference הראל (the paying insurer), got "
                f"{e.get('payer_name')!r}"
            )
            assert e.get("hours") == 2.0, (
                f"expected 'שעתיים' resolved to 2.0 in hours (REQ-DATA-009), got {e.get('hours')!r}"
            )
            assert e["source_type"] == "הסכם"
            self._assert_message_links_back_to_event(denidin_app, chat_id, e)

        txn_dates = {e.get("txn_date") for e in events}
        today_str = self._israel_date_str(1770002200, 0)
        yesterday_str = self._israel_date_str(1770002200, 1)
        assert txn_dates == {today_str, yesterday_str}, (
            f"expected txn_date values {{today={today_str!r}, yesterday={yesterday_str!r}}}, "
            f"got {txn_dates!r}"
        )

    # ------------------------------------------------------------------
    # 2026-08-18 PLAYER-REVIEW FOLLOW-UP - real E2E coverage for the 10 findings
    # from a full interactive human review (approve/correct each real capture)
    # of a real historical export. Findings that need a real בנק image (checks,
    # payer_name/vat_status enforcement on בנק) are NOT coverable here - this
    # file is text-only by definition; those are covered instead by
    # tests/expensive/test_ledger_event_capture_e2e.py's image-flow tests.
    # ------------------------------------------------------------------

    def test_given_real_conditional_fee_text_then_trigger_condition_captured(self, denidin_app):
        """Finding #10: trigger_condition was previously hardcoded null with no
        schema property at all - LEDGER_EVENT_TOOL never exposed it, so a
        textbook conditional fee had nowhere to go. Given the real message that
        surfaced this (דוד אדלר, msg 18 of the גביה TEST export review - a base
        fee plus a second component conditional on the request being set for a
        hearing), When processed, Then at least one persisted component carries
        a non-null trigger_condition describing that condition."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("trigger_condition")
        raw_text = (
            "דוד אדלר\n"
            "חיפה\n"
            "שכר טירחה\n"
            "כתיבה והגשה של בקשת רשות ערעור, 10,000 שח\n"
            "אם הבקשה נקבעת לדיון עוד 5000₪"
        )
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770003000,
            'idMessage': 'LEDGER_E2E_TRIGGER_CONDITION_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': raw_text}
            }
        })

        logger.info("GIVEN the real דוד אדלר conditional-fee message (bקשה נקבעת לדיון)")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=None, expected_event_timestamp=1770003000
        )
        logger.info(f"THEN captured {len(events)} event(s): {events}")

        conditional = [e for e in events if e.get("trigger_condition")]
        assert conditional, (
            "expected at least one component to carry a non-null trigger_condition "
            f"for the 'אם הבקשה נקבעת לדיון' clause - got events={events!r}"
        )
        assert "דיון" in conditional[0]["trigger_condition"], (
            f"expected trigger_condition to reference the hearing condition, got "
            f"{conditional[0]['trigger_condition']!r}"
        )
        for e in events:
            assert e["source_type"] == "הסכם"
            assert "אדלר" in (e.get("client_name") or "")

    def test_given_real_addition_language_then_reference_hint_captured(self, denidin_app):
        """Finding #9: reference_hint was missed for an explicit 'addition' message
        ("תוספת על X ששולם") in the real review, despite it being exactly the kind
        of prior-relating language the field exists for. Given a first message
        establishing a paid fee, then a second message stating an addition to it
        in the SAME conversation, When processed, Then the second capture has
        reference_hint set (and reference resolves to the placeholder)."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("addition_reference")

        first = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770004000,
            'idMessage': 'LEDGER_E2E_ADDITION_BASE_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'ליאור טדלה\nשימוע 9,000₪'}
            }
        })
        logger.info("GIVEN a first message establishing a paid fee (ליאור טדלה, 9,000₪)")
        handle_text_message(first)
        assert_response_exists(get_response(first))

        second = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770004100,
            'idMessage': 'LEDGER_E2E_ADDITION_FOLLOWUP_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'ליאור טדלה\n6000₪ תוספת על 9000₪ ששולם'}
            }
        })
        logger.info("GIVEN a follow-up 'תוספת' (addition) message in the SAME conversation")
        handle_text_message(second)
        logger.info("WHEN DeniDin processes it")
        assert_response_exists(get_response(second))

        # NOTE: doesn't use _assert_ledger_events_persisted - that helper asserts
        # every returned event shares ONE expected_event_timestamp, but this test
        # spans two messages with two different timestamps (1770004000/…4100) by
        # design. Read events directly instead.
        events = self._events_for_chat(denidin_app, chat_id)
        assert events, f"expected at least one persisted event for {chat_id}, found none"
        addition_events = [e for e in events if e.get("amount") == 6000]
        assert addition_events, f"expected an event with amount=6000 (the addition), got {events!r}"

        addition = addition_events[0]
        assert addition.get("reference_hint"), (
            "expected reference_hint to be set for an explicit 'תוספת' addition "
            f"message, got {addition.get('reference_hint')!r}"
        )
        assert addition.get("reference") == "צריך למצוא", (
            f"expected reference to resolve to the placeholder given reference_hint "
            f"was set, got {addition.get('reference')!r}"
        )

    def test_given_ambiguous_hyphenated_name_then_model_asks_clarifying_question(self, denidin_app):
        """Finding #2: material name ambiguity (a hyphenated name that could be one
        full name or a client+matter/payer split) should prompt a clarifying
        question rather than a silent guess. This is a genuine test of real model
        judgment, not persistence code - per this file's existing precedent
        (test_given_real_gilyan_davidian...), write the strict correct assertion
        and accept it as real, separately-actionable signal if the model doesn't
        ask. Uses the exact real message from the player review that surfaced
        this finding."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("hyphenated_name_ask")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770005000,
            'idMessage': 'LEDGER_E2E_HYPHENATED_NAME_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'ליאור - שסטוביץ\nשימוע 9,000₪'}
            }
        })

        logger.info("GIVEN the real ambiguous hyphenated-name message (ליאור - שסטוביץ)")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        assert "?" in response, (
            "expected the model to ask a clarifying question about whether this is "
            "one person's full name or a client+matter/payer split - got reply: "
            f"{response!r}"
        )

    def test_given_real_minimal_hourly_message_then_captured_not_missed(self, denidin_app):
        """Finding #8 (real observed miss, 2026-08-17 player review): a
        structurally normal hourly work-log message with just client+matter+hours
        and nothing else produced ZERO ledger events in one real run. Given the
        real message that missed ("אורית בנימין מקורות שעתיים"), When processed,
        Then exactly one event IS captured with hours populated - locks in the
        strengthened 'no exceptions' constitution wording as real, checkable
        behavior, not just prompt text.

        2026-08-18: a single-shot version of this test (assert-on-turn-1-only)
        failed a real run - not because the event was missed (the original
        finding #8 bug this test guards against), but because the model asked
        a clarifying question first ("באיזה תאריך בוצעו שעתיים העבודה עבור אורית
        בנימין בנושא מקורות?" - the message gives no date at all, so the model
        reasonably wants one before capturing). That's legitimate real
        non-determinism, same category as the גיליאן דוידיאן test above - not
        a recurrence of finding #8 (which was a silent, unexplained skip with
        no question asked at all). Switched to the same
        converse_until_ledger_events_captured + ClarificationAnswerBank
        mechanism so the test tolerates either real behavior (direct capture,
        or ask-then-answer-then-capture) while still failing loudly if no
        event is ever captured within max_turns - which is the actual
        regression this test exists to catch."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("hourly_minimal_regression")
        raw_text = "אורית בנימין\nמקורות\nשעתיים"
        answer_bank = ClarificationAnswerBank([
            {
                "topic": "date",
                "keywords": ["תאריך", "מתי", "באיזה יום"],
                "answer": "היום",
            },
            {
                "topic": "rate",
                "keywords": ["תעריף", "מחיר לשעה", "שכר לשעה", "כמה לשעה"],
                "answer": "התעריף לא צוין, תשאיר את זה ריק",
            },
            {
                "topic": "matter_clarification",
                "keywords": ["מהו הנושא", "איזה עניין", "מה זה מקורות", "מה הכוונה במקורות"],
                "answer": "מקורות הוא שם התיק/העניין של הלקוחה אורית בנימין",
            },
        ])

        MAX_TURNS = 4
        BASE_TIMESTAMP = 1770006000

        # Same REQ-ID-002/003 bucket-collision concern as the גיליאן דוידיאן
        # test above - a multi-turn conversation can span more than one
        # letter+DDMMYY+HHMM bucket, which the class-level
        # _clean_fixed_timestamp_events fixture (single-timestamp only) does
        # not cover.
        stale_prefixes = reserve_ledger_event_bucket_prefixes(BASE_TIMESTAMP, MAX_TURNS)

        def _clean_stale_events():
            for prefix in stale_prefixes:
                for stale_file in Path(denidin_app.ai_handler.ledger_event_manager.storage_dir).glob(f"{prefix}*.json"):
                    stale_file.unlink()

        _clean_stale_events()

        try:
            logger.info("GIVEN the real minimal hourly message that missed in an earlier run (אורית בנימין מקורות שעתיים)")
            events, transcript = converse_until_ledger_events_captured(
                handle_text_message=handle_text_message,
                chat_id=chat_id,
                first_message_text=raw_text,
                answer_bank=answer_bank,
                events_for_chat=lambda cid: self._events_for_chat(denidin_app, cid),
                base_timestamp=BASE_TIMESTAMP,
                base_id_message="LEDGER_E2E_HOURLY_MINIMAL",
                sender_data={'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
                max_turns=MAX_TURNS,
                test_logger=logger,
            )
            logger.info(f"THEN captured {len(events)} event(s) after {len(transcript)} turn(s): {events}")

            assert len(events) == 1, (
                f"expected exactly 1 event (finding #8 regression - this message must "
                f"never be silently skipped), got {len(events)} (transcript: {transcript!r})"
            )
            captured = events[0]
            assert "אורית בנימין" in (captured.get("client_name") or "")
            assert captured.get("hours") == 2.0, f"expected 'שעתיים' resolved to 2.0, got {captured.get('hours')!r}"
            assert captured["source_type"] == "הסכם"
        finally:
            _clean_stale_events()
