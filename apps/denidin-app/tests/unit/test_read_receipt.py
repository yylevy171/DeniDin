"""
Unit tests for Feature 045's read-receipt decision logic: extracting a (chatId,
idMessage) target from a raw Green API notification body, and the orchestrating
`mark_message_read` callback that decides whether/how to call
`bot.api.marking.readChat`.

`readChat` (a real Green API call) is mocked here - permitted for external
services in tests/unit/ per CONSTITUTION.md SS V; real, unmocked confirmation
lives in tests/billed/test_real_api_connectivity.py.
"""
from unittest.mock import MagicMock

import pytest

from src.utils.green_api_bot import _extract_read_receipt_target, mark_message_read


class TestExtractReadReceiptTarget:
    def test_extracts_chat_id_and_id_message(self):
        body = {
            "idMessage": "ABC123",
            "senderData": {"chatId": "972500000000@c.us"},
        }
        assert _extract_read_receipt_target(body) == ("972500000000@c.us", "ABC123")

    def test_missing_id_message_returns_none(self):
        body = {"senderData": {"chatId": "972500000000@c.us"}}
        assert _extract_read_receipt_target(body) is None

    def test_missing_sender_data_returns_none(self):
        body = {"idMessage": "ABC123"}
        assert _extract_read_receipt_target(body) is None

    def test_missing_chat_id_returns_none(self):
        body = {"idMessage": "ABC123", "senderData": {}}
        assert _extract_read_receipt_target(body) is None

    def test_empty_body_returns_none(self):
        assert _extract_read_receipt_target({}) is None


class TestMarkMessageRead:
    def _body(self):
        return {
            "idMessage": "ABC123",
            "senderData": {"chatId": "972500000000@c.us"},
        }

    def test_calls_read_chat_when_not_blocked(self):
        bot = MagicMock()
        mark_message_read(bot, self._body(), is_blocked=False)
        bot.api.marking.readChat.assert_called_once_with(
            "972500000000@c.us", idMessage="ABC123"
        )

    def test_does_not_call_when_blocked(self):
        bot = MagicMock()
        mark_message_read(bot, self._body(), is_blocked=True)
        bot.api.marking.readChat.assert_not_called()

    def test_does_not_call_when_target_unextractable(self):
        bot = MagicMock()
        mark_message_read(bot, {}, is_blocked=False)
        bot.api.marking.readChat.assert_not_called()

    def test_swallows_read_chat_exception(self):
        bot = MagicMock()
        bot.api.marking.readChat.side_effect = RuntimeError("boom")
        # Must not raise - best-effort, log-only per plan.md.
        mark_message_read(bot, self._body(), is_blocked=False)
        bot.api.marking.readChat.assert_called_once()
