"""
2026-09-30: every WhatsApp message is stored in the chat's session the moment it
crosses the boundary - received from the user -> stored on receipt; sent to the
user -> stored right after the send succeeds (never for a failed send). Replaces
bugfix-058's end-of-turn batch persistence (and its "interim message" tracking).

REQ-063-08: DeniDin stores them - WhatsAppHandler only parses and sends, the
SessionManager only stores the values it's given, and neither knows the other.

Real DeniDin + real SessionManager (tmp storage) + real WhatsAppHandler; only the
Green API notification object is a stand-in (external service, CONSTITUTION SS I).
"""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import denidin as denidin_module
from denidin import REPLAY_REPLY_OFFSET_SECONDS
from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.models.message import AIResponse, WhatsAppMessage
from tests.denidin_test_support import make_denidin, make_session_manager

CHAT_ID = "972500000000@c.us"


def _now():
    return int(time.time())


@pytest.fixture
def session_manager(tmp_path):
    return make_session_manager(storage_dir=str(tmp_path / "sessions"))


@pytest.fixture
def app(session_manager):
    """A DeniDin with sessions and its WhatsApp side (own number 972559999999)."""
    app = make_denidin(session_manager=session_manager)
    app.whatsapp_handler = WhatsAppHandler(app)
    app.whatsapp_handler.own_whatsapp_number = "972559999999"
    return app


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
    def test_stored_under_the_messages_own_id(self, app, session_manager):
        app.store_inbound(_message("תפיק חשבונית", message_id="msg-42"))

        [stored] = _stored(session_manager)
        assert stored["message_id"] == "msg-42"
        assert stored["content"] == "תפיק חשבונית"
        assert stored["ai_required_role"] == "user"
        assert stored["whatsapp_id_message"] == "WA1"

    def test_a_redelivered_message_is_not_stored_twice(self, app, session_manager):
        app.store_inbound(_message(message_id="m1", whatsapp_id="WA-SAME"))
        app.store_inbound(_message(message_id="m2", whatsapp_id="WA-SAME"))

        assert len(_stored(session_manager)) == 1

    def test_internal_content_is_stored_without_the_whatsapp_id(self, app, session_manager):
        app.store_inbound(_message("[ledger stash]"), internal=True)

        [stored] = _stored(session_manager)
        assert stored["whatsapp_id_message"] is None

    def test_never_raises_when_storage_fails(self):
        broken = MagicMock()
        broken.has_whatsapp_id_message.return_value = False
        broken.add_message_with_tokens.side_effect = OSError("disk full")

        assert make_denidin(session_manager=broken).store_inbound(_message()) is None


class TestStoreOutbound:
    def test_stored_as_an_assistant_message_addressed_to_the_sender(self, app, session_manager):
        app.store_outbound(_message(), "החשבונית הופקה", mcp_calls=[{"name": "create_invoice"}])

        [stored] = _stored(session_manager)
        assert stored["ai_required_role"] == "assistant"
        assert stored["content"] == "החשבונית הופקה"
        assert stored["sender"] == "972559999999@c.us"
        assert stored["recipient"] == CHAT_ID
        assert stored["mcp_calls"] == [{"name": "create_invoice"}]

    def test_a_replayed_reply_sorts_just_after_the_message_it_answers(self, app, session_manager):
        source = 1_780_000_000
        app.store_outbound(_message(timestamp=source, is_replay=True), "תשובה")

        [stored] = _stored(session_manager)
        expected = datetime.fromtimestamp(source + REPLAY_REPLY_OFFSET_SECONDS, timezone.utc)
        assert datetime.fromisoformat(stored["timestamp"]) == expected


class TestUpdate:
    def test_fills_facts_into_the_stored_message(self, app, session_manager):
        app.store_inbound(_message("[a.jpg sent]", message_id="msg-img"))

        app.update_message(CHAT_ID, "msg-img", image_path="media/DD-1.jpg", extracted_text="סכום 500",
                        ledger_event_ids=["A1"])

        [stored] = _stored(session_manager)
        assert (stored["image_path"], stored["extracted_text"], stored["ledger_event_ids"]) == (
            "media/DD-1.jpg", "סכום 500", ["A1"])

    def test_unknown_message_returns_false(self, app):
        assert app.update_message(CHAT_ID, "nope", extracted_text="x") is False


class TestRollingWindowExcludesTheCurrentMessage:
    def test_excluded_message_is_left_out(self, app, session_manager):
        app.store_inbound(_message("ישנה", message_id="old", whatsapp_id="WA-old"))
        app.store_inbound(_message("נוכחית", message_id="current", whatsapp_id="WA-cur"))

        window = session_manager.get_rolling_window(CHAT_ID, exclude_message_ids=["current"])

        assert [m["content"] for m in window] == ["ישנה"]


class TestDeniDinStoresAtTheBoundary:
    def test_send_text_stores_the_sent_message(self, app, session_manager):
        app.send_text(_notification(), "הודעת שגיאה")

        [stored] = _stored(session_manager)
        assert stored["content"] == "הודעת שגיאה"
        assert stored["whatsapp_id_message"] == "WA-OUT"

    def test_a_failed_send_stores_nothing(self, app, session_manager):
        notification = _notification()
        notification.answer.side_effect = ConnectionError("down")

        with pytest.raises(ConnectionError):
            app.send_text(notification, "לא נשלח")

        assert _stored(session_manager) == []

    def test_unsupported_type_stores_the_received_message_then_the_reply(self, app, session_manager,
                                                                         monkeypatch):
        monkeypatch.setattr(denidin_module, "denidin_app", app)
        denidin_module._reply_unsupported(_notification("stickerMessage"))

        assert [(m["ai_required_role"], m["content"]) for m in _stored(session_manager)] == [
            ("user", "[stickerMessage message]"),
            ("assistant", UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES),
        ]

    def test_send_response_stores_the_reply_with_its_mcp_calls(self, app, session_manager):
        response = AIResponse(
            request_id="r1", response_text="בוצע", tokens_used=0, prompt_tokens=0,
            completion_tokens=0, model="m", finish_reason="stop", timestamp=_now(),
            mcp_calls=[{"name": "add_client"}],
        )
        app.send_response(_notification(), response)

        [stored] = _stored(session_manager)
        assert stored["content"] == "בוצע"
        assert stored["mcp_calls"] == [{"name": "add_client"}]

    def test_a_no_reply_turn_stores_nothing(self, app, session_manager):
        response = AIResponse(
            request_id="r1", response_text="[[NO_REPLY]]", tokens_used=0, prompt_tokens=0,
            completion_tokens=0, model="m", finish_reason="stop", timestamp=_now(),
            should_reply=False,
        )
        app.send_response(_notification(), response)

        assert _stored(session_manager) == []

    def test_the_whatsapp_handler_itself_stores_nothing(self, app, session_manager):
        notification = _notification()
        sent = app.whatsapp_handler.send_text(notification, "שלום")
        notification.answer.assert_called_once_with("שלום")
        assert (sent.text, sent.whatsapp_id_message) == ("שלום", "WA-OUT")
        assert _stored(session_manager) == []

    def test_a_progress_update_is_sent_in_the_turn_in_progress_and_stored(self, app, session_manager):
        notification = _notification()
        app.begin_turn(notification, _message(), is_blocked=False)

        assert app.send_progress_update(CHAT_ID, "רגע, בודק") is True
        notification.answer.assert_called_once_with("רגע, בודק")
        [stored] = _stored(session_manager)
        assert (stored["content"], stored["whatsapp_id_message"]) == ("רגע, בודק", "WA-OUT")

    def test_no_progress_update_outside_a_turn(self, app, session_manager):
        app.begin_turn(_notification(), _message(), is_blocked=False)
        app.end_turn(CHAT_ID)

        assert app.send_progress_update(CHAT_ID, "רגע") is False
        assert _stored(session_manager) == []
