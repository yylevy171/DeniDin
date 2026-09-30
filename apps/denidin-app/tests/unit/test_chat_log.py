"""
2026-09-30: every WhatsApp message is stored in the chat's session the moment it
crosses the boundary - received from the user -> stored on receipt; sent to the
user -> stored right after the send succeeds (never for a failed send). Replaces
bugfix-058's end-of-turn batch persistence (and its "interim message" tracking).

Real ChatLog + real SessionManager (tmp storage) + real WhatsAppHandler; only the
Green API notification object is a stand-in (external service, CONSTITUTION SS I).
"""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
from src.core.chat_log import ChatLog, REPLAY_REPLY_OFFSET_SECONDS
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.managers.session_manager import SessionManager
from src.models.message import AIResponse, WhatsAppMessage

CHAT_ID = "972500000000@c.us"


def _now():
    return int(time.time())


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


@pytest.fixture
def chat_log(session_manager):
    return ChatLog(session_manager, None, rbac_enabled=False, own_whatsapp_number="972559999999")


def _message(text="שלום", message_id="msg_1", whatsapp_id="WA1", **kwargs):
    fields = dict(
        message_id=message_id, chat_id=CHAT_ID, sender_id=CHAT_ID, sender_name="John",
        text_content=text, timestamp=_now(), message_type="textMessage",
        is_group=False, received_timestamp=datetime.now(timezone.utc),
        whatsapp_id_message=whatsapp_id,
    )
    fields.update(kwargs)
    return WhatsAppMessage(**fields)


def _stored(session_manager):
    session = session_manager.get_session(CHAT_ID)
    return [mdata for _mid, mdata in session_manager._iter_persisted_messages(session, live_only=True)]


def _notification(type_message="textMessage", **message_data):
    notification = MagicMock()
    notification.event = {
        "typeWebhook": "incomingMessageReceived", "timestamp": _now(), "idMessage": "WA-U1",
        "senderData": {"chatId": CHAT_ID, "sender": CHAT_ID, "senderName": "John"},
        "messageData": {"typeMessage": type_message, **message_data},
    }
    notification.answer.return_value = MagicMock(code=200, data={"idMessage": "WA-OUT"})
    return notification


class TestStoreInbound:
    def test_stored_under_the_messages_own_id(self, chat_log, session_manager):
        chat_log.store_inbound(_message("תפיק חשבונית", message_id="msg-42"))

        [stored] = _stored(session_manager)
        assert stored["message_id"] == "msg-42"
        assert stored["content"] == "תפיק חשבונית"
        assert stored["ai_required_role"] == "user"
        assert stored["whatsapp_id_message"] == "WA1"

    def test_a_redelivered_message_is_not_stored_twice(self, chat_log, session_manager):
        chat_log.store_inbound(_message(message_id="m1", whatsapp_id="WA-SAME"))
        chat_log.store_inbound(_message(message_id="m2", whatsapp_id="WA-SAME"))

        assert len(_stored(session_manager)) == 1

    def test_internal_content_is_stored_without_the_whatsapp_id(self, chat_log, session_manager):
        chat_log.store_inbound(_message("[ledger stash]"), internal=True)

        [stored] = _stored(session_manager)
        assert stored["whatsapp_id_message"] is None

    def test_never_raises_when_storage_fails(self):
        broken = MagicMock()
        broken.has_whatsapp_id_message.return_value = False
        broken.add_message_with_tokens.side_effect = OSError("disk full")

        assert ChatLog(broken, None, rbac_enabled=False).store_inbound(_message()) is None


class TestStoreOutbound:
    def test_stored_as_an_assistant_message_addressed_to_the_sender(self, chat_log, session_manager):
        chat_log.store_outbound(_message(), "החשבונית הופקה", mcp_calls=[{"name": "create_invoice"}])

        [stored] = _stored(session_manager)
        assert stored["ai_required_role"] == "assistant"
        assert stored["content"] == "החשבונית הופקה"
        assert stored["sender"] == "972559999999@c.us"
        assert stored["recipient"] == CHAT_ID
        assert stored["mcp_calls"] == [{"name": "create_invoice"}]

    def test_a_replayed_reply_sorts_just_after_the_message_it_answers(self, chat_log, session_manager):
        source = 1_780_000_000
        chat_log.store_outbound(_message(timestamp=source, is_replay=True), "תשובה")

        [stored] = _stored(session_manager)
        expected = datetime.fromtimestamp(source + REPLAY_REPLY_OFFSET_SECONDS, timezone.utc)
        assert datetime.fromisoformat(stored["timestamp"]) == expected


class TestUpdate:
    def test_fills_facts_into_the_stored_message(self, chat_log, session_manager):
        chat_log.store_inbound(_message("[a.jpg sent]", message_id="msg-img"))

        chat_log.update(CHAT_ID, "msg-img", image_path="media/DD-1.jpg", extracted_text="סכום 500",
                        ledger_event_ids=["A1"])

        [stored] = _stored(session_manager)
        assert (stored["image_path"], stored["extracted_text"], stored["ledger_event_ids"]) == (
            "media/DD-1.jpg", "סכום 500", ["A1"])

    def test_unknown_message_returns_false(self, chat_log):
        assert chat_log.update(CHAT_ID, "nope", extracted_text="x") is False


class TestRollingWindowExcludesTheCurrentMessage:
    def test_excluded_message_is_left_out(self, chat_log, session_manager):
        chat_log.store_inbound(_message("ישנה", message_id="old", whatsapp_id="WA-old"))
        chat_log.store_inbound(_message("נוכחית", message_id="current", whatsapp_id="WA-cur"))

        window = session_manager.get_rolling_window(CHAT_ID, exclude_message_ids=["current"])

        assert [m["content"] for m in window] == ["ישנה"]


class TestWhatsAppHandlerStoresAtTheBoundary:
    @pytest.fixture
    def handler(self, chat_log):
        handler = WhatsAppHandler()
        handler.chat_log = chat_log
        return handler

    def test_send_text_stores_the_sent_message(self, handler, session_manager):
        handler.send_text(_notification(), "הודעת שגיאה")

        [stored] = _stored(session_manager)
        assert stored["content"] == "הודעת שגיאה"
        assert stored["whatsapp_id_message"] == "WA-OUT"

    def test_a_failed_send_stores_nothing(self, handler, session_manager):
        notification = _notification()
        notification.answer.side_effect = ConnectionError("down")

        with pytest.raises(ConnectionError):
            handler.send_text(notification, "לא נשלח")

        assert _stored(session_manager) == []

    def test_unsupported_type_stores_the_received_message_then_the_reply(self, handler, session_manager):
        handler.handle_unsupported_message(_notification("stickerMessage"))

        assert [(m["ai_required_role"], m["content"]) for m in _stored(session_manager)] == [
            ("user", "[stickerMessage message]"),
            ("assistant", UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES),
        ]

    def test_send_response_stores_the_reply_with_its_mcp_calls(self, handler, session_manager):
        response = AIResponse(
            request_id="r1", response_text="בוצע", tokens_used=0, prompt_tokens=0,
            completion_tokens=0, model="m", finish_reason="stop", timestamp=_now(),
            mcp_calls=[{"name": "add_client"}],
        )
        handler.send_response(_notification(), response)

        [stored] = _stored(session_manager)
        assert stored["content"] == "בוצע"
        assert stored["mcp_calls"] == [{"name": "add_client"}]

    def test_a_no_reply_turn_stores_nothing(self, handler, session_manager):
        response = AIResponse(
            request_id="r1", response_text="[[NO_REPLY]]", tokens_used=0, prompt_tokens=0,
            completion_tokens=0, model="m", finish_reason="stop", timestamp=_now(),
            should_reply=False,
        )
        handler.send_response(_notification(), response)

        assert _stored(session_manager) == []

    def test_without_a_chat_log_sending_still_works(self):
        notification = _notification()
        WhatsAppHandler().send_text(notification, "שלום")
        notification.answer.assert_called_once_with("שלום")
