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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
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

    @staticmethod
    def _fresh_chat_id(label: str) -> str:
        """A unique-per-run chat_id, so re-running a single test doesn't accumulate
        unbounded ledger events for a shared chat and confuse assertions."""
        return f"97250{uuid.uuid4().hex[:7]}_{label}@c.us"

    @staticmethod
    def _israel_date_str(days_ago: int = 0) -> str:
        """REQ-DATA-005: the real local Asia/Jerusalem calendar date, `DD/MM/YYYY`,
        `days_ago` days before whenever this test actually runs - the model resolves
        'אתמול'/'היום' against the REAL current date injected into its instructions
        (`AIHandler._build_instructions`), not against any synthetic notification
        timestamp this test supplies, so expected txn_date values must be computed
        the same way, at run time, not hardcoded."""
        israel_now = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Jerusalem"))
        return (israel_now - timedelta(days=days_ago)).strftime("%d/%m/%Y")

    @staticmethod
    def _events_for_chat(denidin_app, chat_id):
        """All persisted LedgerEvent files (data/events/*.json) for this chat_id,
        sorted by captured_at - reads the real files off disk, not an in-memory
        proxy, so assertions prove the event genuinely landed in permanent storage
        (Feature 033's whole point)."""
        events_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
        results = []
        for f in events_dir.glob("*.json"):
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get("whatsapp_chat") == chat_id:
                results.append(data)
        results.sort(key=lambda d: d["captured_at"])
        return results

    @staticmethod
    def _assert_ledger_events_persisted(denidin_app, chat_id, expected_count, expected_event_timestamp):
        """Asserts events were persisted for this chat, each with the bookkeeping
        fields LedgerEventManager.add_ledger_event adds (message_timestamp = the
        real hard pointer, sender, captured_at, message_id) present and correct.
        Returns the events in capture order for further field-specific assertions.

        expected_count: exact count required, or None to only assert >=1.

        expected_event_timestamp: the real Green API notification timestamp (unix
        epoch seconds) these events should be pointed at - the constitution's "hard
        pointer" requirement (never processing time, never a guess).
        """
        events = TestLedgerEventCaptureTextBilled._events_for_chat(denidin_app, chat_id)
        if expected_count is None:
            assert len(events) >= 1, f"Expected at least 1 persisted ledger event for {chat_id}, found 0"
        else:
            assert len(events) == expected_count, (
                f"Expected {expected_count} persisted ledger event(s) for {chat_id}, "
                f"found {len(events)}: {events}"
            )

        expected_ts_iso = datetime.fromtimestamp(expected_event_timestamp, tz=timezone.utc).isoformat()
        for record in events:
            assert record.get("message_timestamp") == expected_ts_iso, (
                f"message_timestamp={record.get('message_timestamp')!r} does not match the "
                f"real notification timestamp {expected_ts_iso!r} - the constitution's 'hard "
                f"pointer' requirement (never processing time, never a guess)"
            )
            assert record.get("sender"), "sender was not persisted"
            assert record.get("captured_at"), "captured_at was not persisted"
            assert record.get("message_id"), (
                "message_id must be non-null for events captured after Feature 033 - "
                "closes the traceability gap that motivated this feature"
            )
        return events

    @staticmethod
    def _assert_message_links_back_to_event(denidin_app, chat_id, event):
        """Cross-checks the reverse link: the source message's ledger_event_ids
        (Feature 033) must include this event's event_id."""
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        message_id = event["message_id"]
        message_file = session_manager.storage_dir / session_id / "messages" / f"{message_id}.json"
        with open(message_file, encoding='utf-8') as f:
            message_data = json.load(f)
        assert event["event_id"] in message_data["ledger_event_ids"], (
            f"event {event['event_id']} not found in source message {message_id}'s "
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
        actually returns)."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("text_multi_stage")
        raw_text = (
            "גיליאן דוידיאן\n"
            "משרד הרווחה\n\n"
            "1. אם יהיה שימוע להשעיה - 8,000₪\n"
            "2. ⁠למידת תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע לסדר טיעון - 20,000₪\n"
            "3. ⁠אם המשא ימתן יכשל ונאלץ לנהל הוכחות ימשפט שלום - עוד 30,000₪"
        )
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000500,
            'idMessage': 'LEDGER_E2E_TEXT_MULTISTAGE_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': raw_text}
            }
        })

        # This test's message_timestamp is fixed (1770000500), not real
        # wall-clock time - so it always targets the exact same
        # letter+DDMMYY+HHMM event_id prefix on every run.
        # LedgerEventManager._next_seq picks the next free seq digit by
        # scanning REAL FILES already on disk under storage_dir for that
        # prefix (REQ-ID-002), which is never cleaned between test runs -
        # without cleanup here, a second run of this exact test continues an
        # earlier run's sequence (e.g. [3,4,5]) instead of the fresh [0,1,2]
        # this test asserts (a real, order-independent failure, 2026-08-03 -
        # surfaced simply by running the billed suite more than once against
        # the same test_data/, no test reordering needed to trigger it).
        # Clean before AND after: before, so a leftover run doesn't shift our
        # own sequence; after, so this test never leaves stale state for its
        # own next run either.
        fixed_local_dt = datetime.fromtimestamp(1770000500, tz=timezone.utc).astimezone(ZoneInfo("Asia/Jerusalem"))
        stale_prefix = f"A{fixed_local_dt.strftime('%d%m%y')}{fixed_local_dt.strftime('%H%M')}"

        def _clean_stale_events():
            for stale_file in Path(denidin_app.ai_handler.ledger_event_manager.storage_dir).glob(f"{stale_prefix}*.json"):
                stale_file.unlink()

        _clean_stale_events()

        try:
            logger.info("GIVEN the real, unmodified גיליאן דוידיאן 3-stage message")
            handle_text_message(notification)
            logger.info("WHEN DeniDin processes it")

            response = get_response(notification)
            assert_response_exists(response)

            events = self._assert_ledger_events_persisted(
                denidin_app, chat_id, expected_count=3, expected_event_timestamp=1770000500
            )
            logger.info(f"THEN captured {len(events)} events (persisted): {events}")

            amounts = sorted(e.get("amount") for e in events)
            assert amounts == [8000, 20000, 30000], (
                f"Expected 3 separate components with amounts 8000/20000/30000, got "
                f"{amounts} - if this fails, the model did not split the message per "
                f"component (see spec.md 'Deferred to a follow-on feature')"
            )
            for e in events:
                assert e["source_type"] == "הסכם"
                assert e["client_name"] and "גיליאן" in e["client_name"]
                self._assert_message_links_back_to_event(denidin_app, chat_id, e)

            # each component's event_id must share the same letter+DDMMYY+HHMM prefix,
            # with sequential seq (0,1,2), never colliding
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
        and txn_date (REQ-DATA-005) all correctly populated - txn_date must equal
        TODAY's real local date, resolved by the model itself from its injected
        current-date context, not copied from event_date by coincidence."""
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
        assert captured.get("txn_date") == self._israel_date_str(0), (
            f"expected txn_date={self._israel_date_str(0)!r} (today), got "
            f"{captured.get('txn_date')!r}"
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
        today_str = self._israel_date_str(0)
        yesterday_str = self._israel_date_str(1)
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
        today_str = self._israel_date_str(0)
        yesterday_str = self._israel_date_str(1)
        assert txn_dates == {today_str, yesterday_str}, (
            f"expected txn_date values {{today={today_str!r}, yesterday={yesterday_str!r}}}, "
            f"got {txn_dates!r}"
        )
