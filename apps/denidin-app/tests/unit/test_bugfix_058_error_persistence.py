"""
bugfix-058: every message dispatched to the user - including error/fallback text - and the
user message it answers must be recorded in the chat's session.

Real AIHandler + real SessionManager (tmp storage); only the OpenAI client is a stand-in
(external service, CONSTITUTION SS I).
"""
import time
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

import pytest
from openai import APIError, APITimeoutError, RateLimitError

from src.constants.error_messages import APPROVAL_FAILED_TRY_AGAIN
from src.handlers.ai_handler import AIHandler, _active_interim_messages
from src.managers.pending_approval_manager import PendingApproval
from src.models.config import AppConfiguration
from src.models.message import AIRequest, WhatsAppMessage

CHAT_ID = "972500000000@c.us"


def _now():
    """A current epoch - the rolling window only returns the last 14 days."""
    return int(time.time())


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
    return AIHandler(MagicMock(), config)


def _window(handler):
    return handler.session_manager.get_rolling_window(CHAT_ID)


def _contents(handler, role):
    return [m["content"] for m in _window(handler) if m["role"] == role]


def _message(text="שלום, מה שלומך?"):
    return WhatsAppMessage(
        message_id="msg_1", chat_id=CHAT_ID, sender_id=CHAT_ID, sender_name="John",
        text_content=text, timestamp=_now(), message_type="textMessage",
        is_group=False, received_timestamp=datetime.now(timezone.utc),
    )


class TestOpenAIErrorBranchesArePersisted:
    @pytest.mark.parametrize("error, expected_fragment", [
        (APITimeoutError(request=Mock()), "trouble connecting"),
        (RateLimitError("rate", response=Mock(), body={}), "at capacity"),
        (APIError("boom", request=Mock(), body={}), "error processing your request"),
        (ValueError("unexpected"), "unexpected error"),
    ])
    def test_user_message_and_fallback_reply_are_stored(self, ai_handler, error, expected_fragment):
        ai_handler.client.responses.create.side_effect = error
        request = ai_handler.create_request(_message())

        response = ai_handler.get_response(request)

        assert expected_fragment in response.response_text.lower()
        assert _contents(ai_handler, "user") == ["שלום, מה שלומך?"]
        assert _contents(ai_handler, "assistant") == [response.response_text]


class TestApprovalPathErrorsArePersisted:
    def test_the_users_yes_and_the_failure_reply_are_stored(self, ai_handler):
        """The user's "כן" is an ordinary message; when resolving the approval then fails, the
        error they are told about is stored right after it."""
        pending = PendingApproval(
            response_id="resp_1", approval_request_id="req_1", tool_name="create_invoice",
            arguments='{"client_name": "דנה כהן", "amount": 500}', server_label="morning",
            created_at="2026-08-04T00:00:00+00:00",
        )
        request = AIRequest(
            user_prompt="כן", constitution="", max_tokens=500, model="gpt-4o-mini",
            chat_id=CHAT_ID, message_id="msg-yes", timestamp=_now(),
        )
        ai_handler.client.with_options.return_value.responses.create.side_effect = RateLimitError(
            "rate", response=Mock(), body={}
        )

        result = ai_handler._resolve_pending_approval(
            pending, request, effective_chat_id=CHAT_ID, user_obj=None, user_role="godfather",
            sender=CHAT_ID, recipient=None,
        )

        assert result.response_text == APPROVAL_FAILED_TRY_AGAIN
        assert _contents(ai_handler, "user") == ["כן"]
        assert _contents(ai_handler, "assistant") == [APPROVAL_FAILED_TRY_AGAIN]


class TestInterimMessagesArePersisted:
    def test_interim_messages_sit_between_the_user_message_and_the_final_reply(self, ai_handler):
        request = ai_handler.create_request(_message("תפיק לי חשבונית"))
        token = _active_interim_messages.set(["רגע, בודק את הלקוח…", "עוד רגע…"])
        try:
            ai_handler._persist_turn(request, "החשבונית הופקה", True, CHAT_ID, None, "client", "John")
        finally:
            _active_interim_messages.reset(token)

        assert [(m["role"], m["content"]) for m in _window(ai_handler)] == [
            ("user", "תפיק לי חשבונית"),
            ("assistant", "רגע, בודק את הלקוח…"),
            ("assistant", "עוד רגע…"),
            ("assistant", "החשבונית הופקה"),
        ]

    def test_interim_messages_are_stored_only_once(self, ai_handler):
        request = ai_handler.create_request(_message())
        token = _active_interim_messages.set(["רגע…"])
        try:
            ai_handler._persist_turn(request, "תשובה", True, CHAT_ID, None, "client", "John")
            ai_handler._persist_turn(request, "תשובה", True, CHAT_ID, None, "client", "John")
        finally:
            _active_interim_messages.reset(token)

        assert _contents(ai_handler, "assistant").count("רגע…") == 1


class TestRecordExchange:
    def test_records_user_text_and_assistant_text(self, ai_handler):
        ai_handler.record_exchange(
            CHAT_ID, user_text="[stickerMessage message]", assistant_text="לא נתמך",
            sender_phone=CHAT_ID, sender_display="John", whatsapp_id_message="WA1",
            source_timestamp=_now(),
        )

        assert _contents(ai_handler, "user") == ["[stickerMessage message]"]
        assert _contents(ai_handler, "assistant") == ["לא נתמך"]

    def test_assistant_only_when_no_user_text(self, ai_handler):
        ai_handler.record_exchange(
            CHAT_ID, user_text=None, assistant_text="הודעת שגיאה", sender_phone=CHAT_ID,
            sender_display="John",
        )

        assert _contents(ai_handler, "user") == []
        assert _contents(ai_handler, "assistant") == ["הודעת שגיאה"]

    def test_does_not_store_the_user_message_twice_for_the_same_whatsapp_id(self, ai_handler):
        for _ in range(2):
            ai_handler.record_exchange(
                CHAT_ID, user_text="שלום", assistant_text="שגיאה", sender_phone=CHAT_ID,
                sender_display="John", whatsapp_id_message="WA-SAME", source_timestamp=_now(),
            )

        assert _contents(ai_handler, "user") == ["שלום"]
        assert _contents(ai_handler, "assistant") == ["שגיאה", "שגיאה"]

    def test_never_raises_when_storage_fails(self, ai_handler):
        ai_handler.session_manager = Mock()
        ai_handler.session_manager.add_message.side_effect = OSError("disk full")

        ai_handler.record_exchange(
            CHAT_ID, user_text="שלום", assistant_text="שגיאה", sender_phone=CHAT_ID,
            sender_display="John",
        )


class TestWhatsAppHandlerRecordsErrorExchanges:
    """bugfix-058: exchanges that never reach AIHandler.get_response (unsupported type, ...)
    are handed to the injected recorder with the user's text and the reply that was sent."""

    @pytest.fixture
    def recorded(self):
        return []

    @pytest.fixture
    def handler(self, recorded):
        from src.handlers.whatsapp_handler import WhatsAppHandler
        handler = WhatsAppHandler()
        handler.record_exchange = lambda chat_id, **kwargs: recorded.append((chat_id, kwargs))
        return handler

    @pytest.fixture
    def notification(self):
        notification = MagicMock()
        notification.event = {
            "typeWebhook": "incomingMessageReceived", "timestamp": _now(), "idMessage": "WA-U1",
            "senderData": {"chatId": CHAT_ID, "sender": CHAT_ID, "senderName": "John"},
            "messageData": {"typeMessage": "stickerMessage"},
        }
        return notification

    def test_unsupported_type_reply_is_recorded_with_the_users_message(self, handler, notification, recorded):
        from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES

        handler.handle_unsupported_message(notification)

        assert len(recorded) == 1
        chat_id, kwargs = recorded[0]
        assert chat_id == CHAT_ID
        assert kwargs["user_text"] == "[stickerMessage message]"
        assert kwargs["assistant_text"] == UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
        assert kwargs["whatsapp_id_message"] == "WA-U1"

    def test_nothing_is_recorded_when_no_recorder_is_injected(self, notification):
        from src.handlers.whatsapp_handler import WhatsAppHandler

        WhatsAppHandler().handle_unsupported_message(notification)  # must simply not raise

    def test_a_failing_recorder_never_breaks_the_reply(self, handler, notification):
        def _boom(*_args, **_kwargs):
            raise OSError("disk full")
        handler.record_exchange = _boom

        handler.handle_unsupported_message(notification)

        notification.answer.assert_called_once()
