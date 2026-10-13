"""
Component-Integration Test: group media (Feature 039 Phase 11/US6, updated for the no-turn
redesign - Feature 067).

A media message in a group goes through `handle_image_message` -> `_process_media_message`,
which hands the downloaded file RAW to the AI implementation: the model alone decides what
to say (or to stay silent) - there is no etiquette/no-reply machinery of the app's own in
between. Uses the real bot.router-registered handler, WhatsAppHandler, SessionManager and
Backbone; only the genuine external boundaries are stood in for: the Green API file download,
the OpenAI client (scripted) and the Green API bot (records what it was told to send).
"""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone
from tests.backbone_test_support import FakeBot

ADMIN_SENDER_ID = "972509999999@c.us"
GROUP_CHAT_ID = "120363999999999999@g.us"


def _send(text, rid="r1"):
    item = SimpleNamespace(type="function_call", name="send_to_user", arguments=json.dumps({"text": text}),
                           call_id="c1")
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None)


def _end(rid="r2"):
    return SimpleNamespace(output=[], output_text="", id=rid, usage=None)


@pytest.mark.integration
class TestGroupMedia:
    """Media in groups reaches the model with the file attached and the sender's resolved
    display name; what the model sends is delivered to the group and stored."""

    @pytest.fixture
    def denidin_app(self, tmp_path, monkeypatch):
        import denidin as denidin_module
        from src.models.config import AppConfiguration
        from tests.denidin_test_support import make_session_manager
        config_path = __import__("pathlib").Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config_dict = {
            'green_api_instance_id': config.green_api_instance_id, 'green_api_token': config.green_api_token,
            'ai_api_key': config.ai_api_key, 'ai_model': config.ai_model,
            'ai_vision_model': config.ai_vision_model, 'ai_embedding_model': config.ai_embedding_model,
            'ai_reply_max_tokens': config.ai_reply_max_tokens, 'log_level': config.log_level,
            'data_root': str(tmp_path / "data"), 'godfather_phone': config.godfather_phone,
            'memory': {**config.memory, 'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
                       'longterm': {'storage_dir': str(tmp_path / "data" / "memory"), 'enabled': False}},
            'backbone_config': config.backbone_config, 'user_roles': config.user_roles,
            'mcp': config.mcp,
        }
        app = denidin_module.initialize_app(config_dict)
        monkeypatch.setattr(denidin_module, "denidin_app", app)
        app.green_api_bot = FakeBot()
        app.ai_client = MagicMock()
        monkeypatch.setattr(app.media_handler.media_file_manager, 'download_file',
                            lambda file_url: (b"fake_image_bytes", True))
        yield app
        app.session_manager.close()

    def _create_notification(self, chat_id: str, sender: str, sender_name: str, caption: str, msg_id: str):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1706601234,
            'senderData': {
                'chatId': chat_id,
                'sender': sender,
                'senderName': sender_name,
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/media.jpg',
                    'fileName': 'photo.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': caption,
                },
            },
        }
        notification._test_sent_messages = []
        notification.answer = lambda message: notification._test_sent_messages.append(message)
        return notification

    def test_group_image_reaches_the_model_and_its_reply_is_sent_and_stored_with_resolved_names(self, denidin_app):
        """A real image sent in a group is handed to the model with the file attached; the
        stored user message carries the sender's resolved display name (Feature 039), never
        a phone number or the retired "AI" sentinel, and the model's reply goes to the group."""
        from denidin import handle_image_message
        denidin_app.ai_client.responses.create.side_effect = [_send("זה עמוד חתום בחוזה."), _end()]

        notification = self._create_notification(
            chat_id=GROUP_CHAT_ID, sender=ADMIN_SENDER_ID, sender_name="Admin User", caption="",
            msg_id="G039_MEDIA_001")
        handle_image_message(notification)

        assert denidin_app.green_api_bot.sent == [(GROUP_CHAT_ID, "זה עמוד חתום בחוזה.")]
        first_call = denidin_app.ai_client.responses.create.call_args_list[0].kwargs
        assert "[ATTACHED MEDIA: image, file: photo.jpg]" in first_call["input"][-1]["content"]

        session_manager = denidin_app.session_manager
        session = session_manager.get_session(GROUP_CHAT_ID)
        messages_dir = session_manager.storage_dir / session.session_id / "messages"
        stored = []
        for message_id in session.message_ids:
            with open(messages_dir / f"{message_id}.json", encoding='utf-8') as f:
                stored.append(json.load(f))
        user_messages = [m for m in stored if m["ai_required_role"] == "user"]
        assistant_messages = [m for m in stored if m["role"] == "assistant"]
        assert user_messages and assistant_messages
        latest_user, latest_assistant = user_messages[-1], assistant_messages[-1]
        assert latest_user["sender_name"] == "Admin User"
        assert latest_user["sender"] == ADMIN_SENDER_ID
        # A group message is addressed to the group's own JID - same for DeniDin's reply.
        assert latest_user["recipient"] == GROUP_CHAT_ID
        assert latest_assistant["recipient"] == GROUP_CHAT_ID
        assert latest_assistant["sender_name"] == "DeniDin"

    def test_group_image_whose_caption_names_someone_else_is_left_to_the_model(self, denidin_app):
        """The app adds no etiquette filter of its own: a caption naming someone else still
        reaches the model, and if the model stays silent (a response with no tool call)
        nothing is sent and nothing breaks."""
        from denidin import handle_image_message
        denidin_app.ai_client.responses.create.side_effect = [_end("r1")]

        notification = self._create_notification(
            chat_id=GROUP_CHAT_ID, sender=ADMIN_SENDER_ID, sender_name="Admin User",
            caption="רותי, תראי את זה", msg_id="G039_MEDIA_002")
        handle_image_message(notification)

        call = denidin_app.ai_client.responses.create.call_args_list[0].kwargs
        assert "רותי, תראי את זה" in call["input"][-1]["content"]
        assert denidin_app.green_api_bot.sent == []
