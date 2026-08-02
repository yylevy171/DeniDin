"""
End-to-End Integration Test: Ledger Event Recognition (runtime_constitution.md) - text flow

Tests the real OpenAI function-calling mechanism end-to-end - NOT unit-testable, since
what's actually under test is whether the real model (a) classifies correctly (calls
`capture_ledger_event` only when the content genuinely warrants it) and (b) extracts
fields correctly.

Text-only counterpart to tests/expensive/test_ledger_event_capture_e2e.py (the image
flow, which stays `expensive` since it makes real vision calls). Split out per Feature
029 - these text-flow tests are billed (cheap, text-only), not expensive.

NO MOCKING - real OpenAI API calls, real session storage.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
class TestLedgerEventCaptureBilled:
    """
    Given/When/Then E2E coverage for Ledger Event Recognition's text flow:
    - Given a message that genuinely warrants capture, When processed, Then
      `capture_ledger_event` is called and the result lands in
      session.pending_ledger_events with plausible fields.
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
        return denidin.denidin_app

    @staticmethod
    def _fresh_chat_id(label: str) -> str:
        """A unique-per-run chat_id, so re-running a single test doesn't accumulate
        unbounded pending_ledger_events on a shared chat and confuse assertions."""
        return f"97250{uuid.uuid4().hex[:7]}_{label}@c.us"

    @staticmethod
    def _pending_events(denidin_app, chat_id):
        session = denidin_app.ai_handler.session_manager.get_session(chat_id)
        return session.pending_ledger_events

    @staticmethod
    def _read_persisted_session(denidin_app, chat_id):
        """Read session.json directly off disk - bypassing SessionManager.get_session
        entirely - so assertions prove the ledger event genuinely landed in the
        persisted file, not just in a process-local Session object that happens to
        agree with it. real persistence, not an in-memory proxy for it."""
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        session_file = session_manager.storage_dir / session_id / "session.json"
        with open(session_file, encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _assert_ledger_event_persisted(denidin_app, chat_id, expected_event_timestamp):
        """Cross-checks the in-memory Session (via get_session) against the raw
        session.json file on disk, and verifies the bookkeeping fields
        add_pending_ledger_event adds (message_timestamp, sender, captured_at) are
        present and correct - not just the model-extracted fields. Returns the
        last persisted event record for further field-specific assertions.

        expected_event_timestamp: the real Green API notification timestamp (unix
        epoch seconds) this event should be pointed at - the constitution's "hard
        pointer" requirement (never processing time, never a guess).
        """
        in_memory_events = TestLedgerEventCaptureBilled._pending_events(denidin_app, chat_id)
        assert len(in_memory_events) >= 1, "Expected capture_ledger_event to be called - none captured"

        persisted = TestLedgerEventCaptureBilled._read_persisted_session(denidin_app, chat_id)
        persisted_events = persisted["pending_ledger_events"]
        assert persisted_events == in_memory_events, (
            "In-memory Session.pending_ledger_events diverges from the real "
            "session.json file on disk - persistence did not actually happen "
            "as expected"
        )

        record = persisted_events[-1]
        expected_ts_iso = datetime.fromtimestamp(expected_event_timestamp, tz=timezone.utc).isoformat()
        assert record.get("message_timestamp") == expected_ts_iso, (
            f"message_timestamp={record.get('message_timestamp')!r} does not match the "
            f"real notification timestamp {expected_ts_iso!r} - the constitution's 'hard "
            f"pointer' requirement (never processing time, never a guess)"
        )
        assert record.get("sender"), "sender was not persisted"
        assert record.get("captured_at"), "captured_at was not persisted"
        return record

    def test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured(self, denidin_app):
        """Given a WhatsApp message stating a new fee agreement in the same shorthand
        style the real AHLedger source chat uses, When DeniDin processes it, Then
        capture_ledger_event is called with source_type=הסכם and the right client/amount."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("text_agreement")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000000,
            'idMessage': 'LEDGER_E2E_TEXT_AGREEMENT_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'רונית כהן - הצעת שכר טרחה לכתב הגנה: 9,000 ₪ כולל מעמ'
                }
            }
        })

        logger.info("GIVEN a clear fee-agreement text message")
        handle_text_message(notification)
        logger.info("WHEN DeniDin processes it")

        response = get_response(notification)
        assert_response_exists(response)

        # THEN: verify against the real persisted session.json on disk (not just the
        # in-memory Session object), including the bookkeeping fields
        # add_pending_ledger_event adds - message_timestamp must be the real
        # notification timestamp (1770000000), never processing time.
        captured = self._assert_ledger_event_persisted(denidin_app, chat_id, expected_event_timestamp=1770000000)
        logger.info(f"THEN captured event (persisted): {captured}")

        assert captured["source_type"] == "הסכם"
        assert captured["event_subtype"] == "יצירה"
        assert "רונית" in (captured.get("client_name") or "") or "כהן" in (captured.get("client_name") or "")
        assert "9" in (captured.get("amount") or "")
        assert captured.get("vat_status") == "כולל"
        assert captured.get("raw_message_excerpt")

    def test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured(self, denidin_app):
        """Given an ordinary conversational message with no money/engagement content,
        When processed, Then capture_ledger_event is NOT called - the false-positive
        guard matters as much as capturing real events does."""
        from denidin import handle_text_message

        chat_id = self._fresh_chat_id("text_chatter")
        before = len(self._pending_events(denidin_app, chat_id))

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

        after = len(self._pending_events(denidin_app, chat_id))
        logger.info(f"THEN pending_ledger_events count before={before}, after={after}")
        assert after == before, "capture_ledger_event should NOT have been called for ordinary chatter"
