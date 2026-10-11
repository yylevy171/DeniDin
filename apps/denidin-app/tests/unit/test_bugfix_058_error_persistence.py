"""
bugfix-058: every message dispatched to the user - including error/fallback text - and the
user message it answers must be recorded in the chat's session.

2026-09-30: recording now happens at the WhatsApp boundary (DeniDin.store_inbound/store_outbound, denidin.py) - the
user's message the moment it's received, each reply right after it's sent - so these tests
drive the whole conversational pipeline (denidin._process_conversational_message) rather
than AIHandler alone.

Real AIHandler + real WhatsAppHandler + real DeniDin + real SessionManager (tmp storage);
only the OpenAI client and the Green API notification are stand-ins (external services,
CONSTITUTION SS I).
"""
import time
from unittest.mock import Mock, MagicMock

import pytest
from openai import APIError, APITimeoutError, RateLimitError

import denidin as denidin_module
from src.constants.error_messages import ERROR_PROCESSING_MESSAGE_TRY_AGAIN
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from tests.ai_handler_test_support import make_ai_handler

CHAT_ID = "972500000000@c.us"


@pytest.fixture
def ai_handler(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-4o-mini"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path)
    config.memory = {
        'session': {'storage_dir': str(tmp_path / 'sessions')},
        'longterm': {'enabled': False},
    }
    config.user_roles = {}
    config.godfather_phone = None
    config.feature_flags = {}
    return make_ai_handler(MagicMock(), config)


@pytest.fixture
def app(ai_handler, monkeypatch):
    app = ai_handler.denidin  # the real DeniDin the handler was built on
    app.ai_manager = ai_handler
    app.group_membership_resolver = None
    monkeypatch.setattr(denidin_module, "denidin_app", app)
    monkeypatch.setattr(denidin_module, "_run_post_turn_ledger_recognition", lambda **_kw: None)
    return app


def _notification(text="שלום, מה שלומך?"):
    notification = MagicMock()
    notification.event = {
        "typeWebhook": "incomingMessageReceived", "timestamp": int(time.time()), "idMessage": "WA-U1",
        "senderData": {"chatId": CHAT_ID, "sender": CHAT_ID, "senderName": "John"},
        "messageData": {"typeMessage": "textMessage", "textMessageData": {"textMessage": text}},
    }
    notification.answer.return_value = MagicMock(code=200, data={"idMessage": "WA-OUT"})
    return notification


def _stored(ai_handler):
    return [(m["role"], m["content"]) for m in ai_handler.session_manager.get_rolling_window(CHAT_ID)]


class TestOpenAIErrorRepliesAreStored:
    @pytest.mark.parametrize("error, expected_fragment", [
        (APITimeoutError(request=Mock()), "trouble connecting"),
        (RateLimitError("rate", response=Mock(), body={}), "at capacity"),
        (APIError("boom", request=Mock(), body={}), "error processing your request"),
        (ValueError("unexpected"), "unexpected error"),
    ])
    def test_user_message_and_the_error_reply_sent_are_stored(self, app, error, expected_fragment):
        app.ai_manager.client.responses.create.side_effect = error
        notification = _notification()

        denidin_module._process_conversational_message(notification)

        sent = notification.answer.call_args[0][0]
        assert expected_fragment in sent.lower()
        assert _stored(app.ai_manager) == [("user", "שלום, מה שלומך?"), ("assistant", sent)]


class TestTheUsersMessageIsStoredEvenWhenTheTurnCrashes:
    def test_crash_after_receipt_keeps_the_user_message_and_stores_the_error_sent(self, app, monkeypatch):
        def _crash(*_args, **_kwargs):
            raise RuntimeError("boom")
        monkeypatch.setattr(app.ai_manager, "single_turn", _crash)
        notification = _notification()

        denidin_module._process_conversational_message(notification)

        notification.answer.assert_called_once_with(ERROR_PROCESSING_MESSAGE_TRY_AGAIN)
        assert _stored(app.ai_manager) == [
            ("user", "שלום, מה שלומך?"), ("assistant", ERROR_PROCESSING_MESSAGE_TRY_AGAIN)]
