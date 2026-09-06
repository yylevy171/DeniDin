"""
End-to-End Integration Test: Ledger Event Recognition (runtime_constitution.md) - text flow

Tests the real OpenAI function-calling mechanism end-to-end - NOT unit-testable, since
what's actually under test is whether the real model (a) classifies correctly (calls
`capture_ledger_event` only when the content genuinely warrants it) and (b) extracts
fields correctly.

Text-only counterpart to tests/expensive/test_ledger_event_capture_e2e.py (the image
flow, which stays `expensive` since it makes real vision calls). Split out per Feature
029 - these text-flow tests are billed (cheap, text-only), not expensive.

Feature 033 (Ledger Event Persistence): events persist as their own files under
`{data_root}/events/{event_id}.json` via LedgerEventManager, not in session.json's
(long since removed) `pending_ledger_events` - this file was rewritten 2026-08-02
after a merge from master revealed it still referenced that removed mechanism (it was
split off from test_ledger_event_capture_e2e.py, per Feature 029, on a master line of
history that predated Feature 033's redesign there). See
specs/in-progress/033-ledger-event-persistence/ for the full design.

NO MOCKING - real OpenAI API calls, real session storage.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import (
    sanity_worker_data_root,
    create_real_notification,
    event_datetime_for_message_ts,
    get_response,
    assert_response_exists,
    ClarificationAnswerBank,
    converse_until_ledger_events_captured,
)
from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID, _seed_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.billed
class TestLedgerEventCaptureBilled:
    """
    Given/When/Then E2E coverage for Ledger Event Recognition's text flow:
    - Given a message that genuinely warrants capture, When processed, Then
      `capture_ledger_event` is called and the result lands in its own file under
      `data/events/`, correctly shaped per data-model.md.
    - Given a message that doesn't, When processed, Then it is NOT called - the
      false-positive guard matters as much as the capture itself.
    """

    @pytest.fixture
    def config(self):
        """Load test configuration (real credentials, isolated test_data/ root)."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = sanity_worker_data_root()  # per-xdist-worker under -n (Feature 075)
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        # Feature 069: ledger capture is now a post-turn recognition call that needs
        # the Morning tools attached (client must resolve in Morning first), so the
        # capture test runs as GODFATHER_CHAT_ID rather than a roleless _fresh_chat_id.
        config.godfather_phone = GODFATHER_CHAT_ID
        return config

    @pytest.fixture
    def denidin_app(self, config, live_morning_tunnel):
        """Initialize the full denidin app - NO MOCKING - against the live Morning
        tunnel (Feature 069 post-turn recognition resolves the client in Morning)."""
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
    def _assert_ledger_events_persisted(denidin_app, chat_id, expected_count):
        """Asserts events were persisted for this chat, each with the bookkeeping
        fields LedgerEventManager.add_ledger_event adds (event_datetime,
        captured_at, message_id) present and correct. Returns the events in
        capture order for further field-specific assertions.

        Feature 069 decision #10: capture is a post-turn recognition step dated
        from the COMPLETING message (`record["message_id"]`, the reply this
        round). event_datetime is asserted to equal that message's OWN persisted
        timestamp, formatted the way `_message_epoch` does - clock-free, so it
        holds for live and WhatsApp-export player replay alike.
        """
        events = TestLedgerEventCaptureBilled._events_for_chat(denidin_app, chat_id)
        assert len(events) == expected_count, (
            f"Expected {expected_count} persisted ledger event(s) for {chat_id}, "
            f"found {len(events)}: {events}"
        )

        for record in events:
            raw = record.get("event_datetime")
            try:
                datetime.strptime(raw, "%d/%m/%Y %H:%M")
            except (TypeError, ValueError):
                raise AssertionError(
                    f"event_datetime={raw!r} is not a well-formed 'DD/MM/YYYY HH:MM' value"
                ) from None
            completing = TestLedgerEventCaptureBilled._read_message(
                denidin_app, chat_id, record["message_id"]
            )
            expected_dt = event_datetime_for_message_ts(completing["timestamp"])
            assert raw == expected_dt, (
                f"event_datetime={raw!r} does not match the completing message's own "
                f"persisted timestamp {completing['timestamp']!r} (-> {expected_dt!r}). "
                f"069 dates the event from that message."
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
        message_data = TestLedgerEventCaptureBilled._read_message(denidin_app, chat_id, event["message_id"])
        assert event["event_id"] in message_data["ledger_event_ids"], (
            f"event {event['event_id']} not found in source message {event['message_id']}'s "
            f"ledger_event_ids={message_data.get('ledger_event_ids')!r}"
        )

    @pytest.mark.sanity
    def test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured(self, denidin_app):
        """Given a WhatsApp message stating a new fee agreement in the same shorthand
        style the real AHLedger source chat uses, When DeniDin processes it, Then
        capture_ledger_event is called with source_type=הסכם and the right client/amount,
        persisted under data/events/.

        Feature 069 (2026-09-04): capture moved to a post-turn recognition call that
        requires the client to already resolve in Morning. The test seeds an
        EXACT-match client first, then drives the agreement turn through
        converse_until_ledger_events_captured. The inbound message timestamp no
        longer drives event_datetime (the ledgerer dates the event from the
        completing message = the actual capture time), so no synthetic timestamp
        is pinned. Runs as GODFATHER_CHAT_ID; tests/billed/conftest.py wipes all
        persisted ledger events before AND after every test, so the shared chat
        starts from zero."""
        from denidin import handle_text_message

        chat_id = GODFATHER_CHAT_ID
        # Fixed reused name -> ensure_exists=True is idempotent (probe, create only
        # if missing). The agreement text names this exact client so the post-turn
        # recognition resolves it as an EXACT Morning match and captures on turn 1.
        _seed_client(chat_id, "LEDGER_AGREEMENT", name="רונית כהן", ensure_exists=True)

        logger.info("GIVEN a clear fee-agreement text message")
        events, transcript = converse_until_ledger_events_captured(
            handle_text_message=handle_text_message,
            chat_id=chat_id,
            first_message_text='רונית כהן - הצעת שכר טרחה לכתב הגנה: 9,000 ₪ כולל מעמ',
            answer_bank=ClarificationAnswerBank([], fallback="כן, זה נכון, תרשום"),
            events_for_chat=lambda cid: self._events_for_chat(denidin_app, cid),
            base_timestamp=int(time.time()),
            base_id_message='LEDGER_E2E_TEXT_AGREEMENT_001',
            sender_data={'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            max_turns=3,
            test_logger=logger,
        )
        logger.info(f"WHEN DeniDin processes it (captured after {len(transcript)} turn(s))")

        # THEN: verify against the real persisted data/events/{event_id}.json file
        # (Feature 033 - not session.json anymore), including the bookkeeping fields
        # LedgerEventManager.add_ledger_event adds.
        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1
        )
        captured = events[0]
        logger.info(f"THEN captured event (persisted): {captured}")

        assert captured["source_type"] == "הסכם"
        assert captured["event_subtype"] == "יצירה"
        assert "רונית" in (captured.get("client_name") or "") or "כהן" in (captured.get("client_name") or "")
        assert captured.get("amount") == 9000, (
            f"expected amount normalized to int 9000, got {captured.get('amount')!r}"
        )
        assert captured.get("vat_status") == "כולל"
        assert captured["event_id"].startswith("A")
        self._assert_message_links_back_to_event(denidin_app, chat_id, captured)

        # Finding #1 (2026-08-18 player review): a plain new agreement mention -
        # no correction/addition/cancellation language at all - must NOT set
        # reference/reference_hint, even though this is the very first message in
        # a fresh chat (nothing to reference by construction, but this locks in
        # the general rule with a real model response).
        assert captured.get("reference") is None, (
            f"a brand-new agreement mention should not set reference, got {captured.get('reference')!r}"
        )
        assert captured.get("reference_hint") is None

        # Feature 043 (2026-08-18): raw_message_excerpt's replacement - a text
        # message's own content already IS the verbatim source (Message.content),
        # so extracted_text (media-only) must stay None here.
        message_data = self._read_message(denidin_app, chat_id, captured["message_id"])
        assert message_data.get("extracted_text") is None, (
            "extracted_text is media-only - a text message must never populate it"
        )
        assert "רונית" in message_data["content"] or "כהן" in message_data["content"], (
            "the message's own content must carry the real verbatim text - this IS "
            "the hard-pointer content now that raw_message_excerpt is gone"
        )

    @pytest.mark.sanity
    def test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured(self, denidin_app):
        """Given an ordinary conversational message with no money/engagement content,
        When processed, Then capture_ledger_event is NOT called - no file created
        under data/events/."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("text_chatter")
        before = len(self._events_for_chat(denidin_app, chat_id))

        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000100,
            'idMessage': 'LEDGER_E2E_TEXT_CHATTER_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'מה קורה? מוכנה לפגישה של מחר?'}
            }
        })

        logger.info("GIVEN ordinary chatter with no engagement/money content")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        after = len(self._events_for_chat(denidin_app, chat_id))
        logger.info(f"THEN persisted-event count before={before}, after={after}")
        assert after == before, "capture_ledger_event should NOT have been called for ordinary chatter"
