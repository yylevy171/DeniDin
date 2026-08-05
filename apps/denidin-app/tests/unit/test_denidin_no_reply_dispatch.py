"""
Unit tests for the no-reply dispatch check in denidin.py (Feature 039, US4a).

Mocks AIHandler/WhatsAppHandler on denidin_app to isolate _process_conversational_message's
own logic (the new `if not ai_response.should_reply: return` branch) from a real OpenAI call -
that real-model behavior is covered by tests/billed/test_group_etiquette_billed.py instead.
"""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from whatsapp_chatbot_python import Notification

import denidin as denidin_module
from src.models.message import AIResponse, WhatsAppMessage


def _make_notification():
    notification = Notification.__new__(Notification)
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'senderData': {
            'chatId': '972501234567@c.us',
            'sender': '972501234567@c.us',
            'senderName': 'Test User'
        },
        'messageData': {
            'typeMessage': 'textMessage',
            'textMessageData': {'textMessage': 'Hi'}
        }
    }
    return notification


def _make_ai_response(should_reply, text="response text"):
    return AIResponse(
        request_id="req_1",
        response_text=text,
        tokens_used=10,
        prompt_tokens=5,
        completion_tokens=5,
        model="gpt-4o-mini",
        finish_reason="stop",
        timestamp=1234567890,
        should_reply=should_reply
    )


@pytest.fixture
def mocked_denidin_app(monkeypatch):
    mock_whatsapp_handler = Mock()
    mock_whatsapp_handler.validate_message_type.return_value = True
    mock_whatsapp_handler.process_notification.return_value = WhatsAppMessage(
        message_id="msg_1",
        chat_id="972501234567@c.us",
        sender_id="972501234567@c.us",
        sender_name="Test User",
        text_content="Hi",
        timestamp=1234567890,
        message_type="textMessage",
        is_group=False,
        received_timestamp=datetime.now(timezone.utc),
        sender_display_name="Test User"
    )

    mock_ai_handler = Mock()
    mock_ai_handler.create_request.return_value = Mock(request_id="req_1")

    mock_app = Mock()
    mock_app.whatsapp_handler = mock_whatsapp_handler
    mock_app.ai_handler = mock_ai_handler
    mock_app.group_membership_resolver = None

    monkeypatch.setattr(denidin_module, 'denidin_app', mock_app)
    return mock_app


class TestNoReplyDispatchSkipsSend:
    def test_should_reply_false_skips_send_response(self, mocked_denidin_app):
        mocked_denidin_app.ai_handler.get_response.return_value = _make_ai_response(should_reply=False)

        denidin_module._process_conversational_message(_make_notification())

        mocked_denidin_app.whatsapp_handler.send_response.assert_not_called()

    def test_should_reply_true_sends_response(self, mocked_denidin_app):
        mocked_denidin_app.ai_handler.get_response.return_value = _make_ai_response(should_reply=True)

        denidin_module._process_conversational_message(_make_notification())

        mocked_denidin_app.whatsapp_handler.send_response.assert_called_once()

    def test_should_reply_false_does_not_raise_or_send_fallback(self, mocked_denidin_app):
        """no-reply is a first-class successful outcome, not an error path - no
        fallback error message should be sent either."""
        mocked_denidin_app.ai_handler.get_response.return_value = _make_ai_response(should_reply=False)

        # Should not raise
        denidin_module._process_conversational_message(_make_notification())

        mocked_denidin_app.whatsapp_handler.send_response.assert_not_called()
