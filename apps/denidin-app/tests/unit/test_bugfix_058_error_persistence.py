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
from src.constants import error_messages
from src.constants.error_messages import ERROR_PROCESSING_MESSAGE_TRY_AGAIN
from src.backbone.backbone import Backbone as AIHandler
from src.models.config import AppConfiguration
from tests.ai_handler_test_support import make_ai_handler
from tests.backbone_test_support import FakeBot

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
    config.allocation_threshold_nis = 5000
    return make_ai_handler(MagicMock(), config)


@pytest.fixture
def app(ai_handler, monkeypatch):
    app = ai_handler.denidin  # the real DeniDin the handler was built on
    app.ai_manager = ai_handler
    app.group_membership_resolver = None
    monkeypatch.setattr(denidin_module, "denidin_app", app)
    app.green_api_bot = FakeBot()
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
    @pytest.mark.parametrize("error, expected", [
        (APITimeoutError(request=Mock()), error_messages.BACKBONE_AI_TIMEOUT),
        (RateLimitError("rate", response=Mock(), body={}), error_messages.BACKBONE_AI_RATE_LIMITED),
        (APIError("boom", request=Mock(), body={}), error_messages.BACKBONE_AI_API_ERROR),
        (ValueError("unexpected"), error_messages.BACKBONE_UNEXPECTED_ERROR),
    ])
    def test_user_message_and_the_error_reply_sent_are_stored(self, app, error, expected):
        app.ai_manager.client.responses.create.side_effect = error

        denidin_module._process_conversational_message(_notification())

        assert app.green_api_bot.sent_texts == [expected]
        assert _stored(app.ai_manager) == [("user", "שלום, מה שלומך?"), ("assistant", expected)]


class TestTheUsersMessageIsStoredEvenWhenTheTurnCrashes:
    def test_crash_after_receipt_keeps_the_user_message_and_stores_the_error_sent(self, app, monkeypatch):
        def _crash(*_args, **_kwargs):
            raise RuntimeError("boom")
        monkeypatch.setattr(app.ai_manager, "handle_message", _crash)
        notification = _notification()

        denidin_module._process_conversational_message(notification)

        notification.answer.assert_called_once_with(ERROR_PROCESSING_MESSAGE_TRY_AGAIN)  # the app's own notice
        assert _stored(app.ai_manager) == [
            ("user", "שלום, מה שלומך?"), ("assistant", ERROR_PROCESSING_MESSAGE_TRY_AGAIN)]
