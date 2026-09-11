"""
BDD Integration Test: editedMessage / deletedMessage webhook routing (Feature 076).

ENTRY POINT: a real Green API `incomingMessageReceived` webhook JSON.
FLOW: webhook dict -> real SDK Notification -> dispatch_notification -> handler.
VERIFICATION (user perspective):
  - editedMessage / deletedMessage: NO reply is sent, and a dated note lands in the
    chat's long-lived session.
  - audioMessage / poll / template / list: exactly one `סוג הודעה לא נתמך` reply.
  - reaction / sticker / location / brand-new type: NOTHING is sent.

NO MOCKING - real handler functions, real SessionManager, real SDK Notification.
Payload shapes are the official Green API docs shapes (see spec.md "Research").

See .github/CONSTITUTION.md §V for the integration-test definition.
"""

import time
from pathlib import Path

import pytest
from whatsapp_chatbot_python import Notification

from src.models.config import AppConfiguration
from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES


CHAT_ID = "972522968679@c.us"
SENDER = "972522968679@c.us"


@pytest.mark.integration
class TestEditedDeletedWebhookRouting:

    @pytest.fixture
    def denidin_app(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

        import denidin as denidin_module
        if denidin_module.denidin_app is None:
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
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)
        return denidin_module.denidin_app

    def _notification(self, event):
        n = Notification.__new__(Notification)
        n.event = event
        n._sent = []
        n.answer = lambda msg: n._sent.append(msg)
        return n

    def _dispatch(self, event):
        import denidin as denidin_module
        n = self._notification(event)
        denidin_module.dispatch_notification(event["messageData"]["typeMessage"], n)
        return n

    def _window_contents(self, denidin_app):
        return [
            m.get("content", "")
            for m in denidin_app.ai_handler.session_manager.get_rolling_window(CHAT_ID)
        ]

    # ---------- editedMessage ----------

    def test_edited_message_sends_no_reply_and_logs_a_dated_note(self, denidin_app):
        ts = int(time.time())
        idm = f"EDIT_{ts}"
        n = self._dispatch({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": ts,
            "idMessage": idm,
            "senderData": {"chatId": CHAT_ID, "sender": SENDER, "senderName": "Test User"},
            "messageData": {
                "typeMessage": "editedMessage",
                "editedMessageData": {
                    "textMessage": "עמיר כץ סמנכל ביטוח לאומי מכתב 3,000₪",
                    "stanzaId": "3A2F324F5A148E7F7D58",
                },
            },
        })

        assert n._sent == [], "editedMessage must not produce any WhatsApp reply"

        contents = self._window_contents(denidin_app)
        assert any(
            c == "[הודעה קודמת נערכה] עמיר כץ סמנכל ביטוח לאומי מכתב 3,000₪"
            for c in contents
        ), f"expected an edit note in the session window, got: {contents}"

    def test_edited_message_for_a_brand_new_chat_creates_the_session(self, denidin_app):
        fresh_chat = f"9725000{int(time.time()) % 1000000}@c.us"
        ts = int(time.time())
        import denidin as denidin_module
        n = self._notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": ts,
            "idMessage": f"EDIT_NEW_{ts}",
            "senderData": {"chatId": fresh_chat, "sender": fresh_chat, "senderName": "New User"},
            "messageData": {
                "typeMessage": "editedMessage",
                "editedMessageData": {"textMessage": "תיקון", "stanzaId": "ORIG1"},
            },
        })
        denidin_module.dispatch_notification("editedMessage", n)

        assert n._sent == []
        window = denidin_app.ai_handler.session_manager.get_rolling_window(fresh_chat)
        assert any(m.get("content") == "[הודעה קודמת נערכה] תיקון" for m in window)

    def test_redelivered_edited_message_is_logged_only_once(self, denidin_app):
        import denidin as denidin_module
        # fresh deduper so this test is independent of others in the run
        denidin_module._recent_notifications = denidin_module.RecentNotificationDeduper()
        ts = int(time.time())
        event = {
            "typeWebhook": "incomingMessageReceived",
            "timestamp": ts,
            "idMessage": f"EDIT_DUP_{ts}",
            "senderData": {"chatId": CHAT_ID, "sender": SENDER, "senderName": "Test User"},
            "messageData": {
                "typeMessage": "editedMessage",
                "editedMessageData": {"textMessage": "פעם אחת בלבד", "stanzaId": "ORIGDUP"},
            },
        }
        for _ in range(2):
            n = self._notification(event)
            denidin_module.dispatch_notification("editedMessage", n)

        contents = self._window_contents(denidin_app)
        assert contents.count("[הודעה קודמת נערכה] פעם אחת בלבד") == 1

    # ---------- deletedMessage ----------

    def test_deleted_message_sends_no_reply_and_logs_a_dated_note(self, denidin_app):
        ts = int(time.time())
        n = self._dispatch({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": ts,
            "idMessage": f"DEL_{ts}",
            "senderData": {"chatId": CHAT_ID, "sender": SENDER, "senderName": "Test User"},
            "messageData": {
                "typeMessage": "deletedMessage",
                "deletedMessageData": {"stanzaId": "84514217EF972039FC3F68A53C196306"},
            },
        })

        assert n._sent == [], "deletedMessage must not produce any WhatsApp reply"
        contents = self._window_contents(denidin_app)
        assert "[המשתמש מחק הודעה קודמת]" in contents, f"got: {contents}"

    # ---------- error-reply bucket ----------

    @pytest.mark.parametrize("type_message", [
        "audioMessage", "pollMessage", "templateMessage",
        "templateButtonsReplyMessage", "listMessage", "listResponseMessage",
    ])
    def test_error_reply_types_get_exactly_the_canned_reply(self, denidin_app, type_message):
        n = self._dispatch({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": int(time.time()),
            "idMessage": f"ERR_{type_message}_{int(time.time())}",
            "senderData": {"chatId": CHAT_ID, "sender": SENDER, "senderName": "Test User"},
            "messageData": {"typeMessage": type_message},
        })
        assert n._sent == [UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES]

    def test_canned_reply_constant_value_is_exactly_the_short_hebrew_string(self):
        assert UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES == "סוג הודעה לא נתמך"

    # ---------- silent bucket ----------

    @pytest.mark.parametrize("type_message", [
        "reactionMessage", "stickerMessage", "locationMessage",
        "pollUpdateMessage", "groupInviteMessage", "someBrandNewFutureType",
    ])
    def test_silent_types_send_nothing(self, denidin_app, type_message):
        n = self._dispatch({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": int(time.time()),
            "idMessage": f"SILENT_{type_message}_{int(time.time())}",
            "senderData": {"chatId": CHAT_ID, "sender": SENDER, "senderName": "Test User"},
            "messageData": {"typeMessage": type_message},
        })
        assert n._sent == [], f"{type_message} must produce no reply"
