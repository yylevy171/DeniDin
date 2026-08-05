"""
Component-Integration Test: Media Path Stays Outside Group Etiquette (Feature 039, Phase 11/US6)

Verifies the architectural boundary documented in HANDOFF.md and denidin.py's
handle_image_message: media messages route straight to
WhatsAppHandler.handle_media_message -> MediaHandler, NEVER through
_process_conversational_message / AIHandler.get_response - so none of US1
(no-mention-gate), US4a (should_reply sentinel), or US5/US7 (named-addressee
etiquette) can apply to media, regardless of what the caption says.

Uses the real bot.router-registered handler (handle_image_message), the real
WhatsAppHandler/MediaHandler/SessionManager - only the two genuine external
boundaries are stood in for: the Green API file download (media_file_manager)
and the OpenAI vision call (image_extractor.analyze_media), the same two points
tests/unit/test_media_handler.py already treats as the seam - no internal
component (SessionManager, WhatsAppHandler, MediaHandler orchestration) is
mocked.
"""

import json
import pytest
from pathlib import Path
from src.models.config import AppConfiguration


ADMIN_SENDER_ID = "972509999999@c.us"
GROUP_CHAT_ID = "120363999999999999@g.us"


@pytest.mark.integration
class TestMediaPathBypassesGroupEtiquette:
    """US6: media messages in groups are processed identically to today and never
    gain any of the etiquette/no-reply machinery Feature 039 added to the text path."""

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
                'user_roles': config.user_roles
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)

        return denidin_module.denidin_app

    def _stub_external_boundaries(self, denidin_app, raw_response: str, monkeypatch):
        """Stand in for the two real external calls a successful media turn makes
        (Green API file download, OpenAI vision analysis) - everything else
        (SessionManager, WhatsAppHandler, MediaHandler orchestration) stays real.

        Uses pytest's `monkeypatch` (auto-reverted at the end of each test) rather than
        a raw attribute assignment - `denidin_app`/`media_handler` are process-global
        singletons reused across test FILES within one pytest session (guarded by
        `if denidin_module.denidin_app is None`), so a raw assignment here previously
        leaked into unrelated later tests under random test ordering (found 2026-08-05:
        it caused tests/integration/test_media_webhook_routing.py's
        test_image_message_user_gets_response to observe this stub's canned response
        instead of its own expected download-failure error)."""
        media_handler = denidin_app.whatsapp_handler.media_handler
        monkeypatch.setattr(
            media_handler.media_file_manager, 'download_file',
            lambda file_url: (b"fake_image_bytes", True)
        )
        monkeypatch.setattr(
            media_handler.image_extractor, 'analyze_media',
            lambda media, caption="": {
                "raw_response": raw_response,
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-5.6-luna",
            }
        )

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

    def test_group_image_processed_normally_with_resolved_sender_name(self, denidin_app, monkeypatch):
        """A real image sent in a group is processed exactly as today (extraction +
        reply), and the resulting stored user-turn message carries the sender's
        resolved display name (Feature 039), never a phone number or the retired
        "AI" sentinel - mirroring T006a's rule for the text path."""
        from denidin import handle_image_message

        self._stub_external_boundaries(
            denidin_app, raw_response="Photo shows a signed contract page.", monkeypatch=monkeypatch
        )

        notification = self._create_notification(
            chat_id=GROUP_CHAT_ID,
            sender=ADMIN_SENDER_ID,
            sender_name="Admin User",
            caption="",
            msg_id="G039_MEDIA_001",
        )

        handle_image_message(notification)

        sent = notification._test_sent_messages[0] if notification._test_sent_messages else None
        assert sent == "Photo shows a signed contract page.", (
            f"Expected the real analysis summary to be sent back, got: {sent}"
        )

        session_manager = denidin_app.ai_handler.session_manager
        session = session_manager.get_session(GROUP_CHAT_ID)
        messages_dir = session_manager.storage_dir / session.session_id / "messages"
        stored = []
        for message_id in session.message_ids:
            with open(messages_dir / f"{message_id}.json", encoding='utf-8') as f:
                stored.append(json.load(f))

        user_messages = [m for m in stored if m["role"] == "user"]
        assistant_messages = [m for m in stored if m["role"] == "assistant"]
        assert user_messages, "Expected the media turn's user message to be stored in the session"
        assert assistant_messages, "Expected the media turn's assistant reply to be stored in the session"

        latest_user = user_messages[-1]
        latest_assistant = assistant_messages[-1]
        assert latest_user["sender"] == "Admin User", (
            f"Expected the resolved display name as sender, got: {latest_user['sender']!r}"
        )
        assert latest_user["recipient"] is None
        assert latest_assistant["recipient"] == "Admin User"
        assert latest_assistant["sender"] is None

    def test_group_image_with_named_addressee_caption_still_gets_full_reply(self, denidin_app, monkeypatch):
        """A caption that would trigger US5/US7's [[NO_REPLY]] path if it were plain
        text (naming someone other than DeniDin) is NOT etiquette-filtered on the
        media path - proving the scope boundary from research.md Sec 9: media never
        reaches AIHandler.get_response / the no-reply sentinel at all."""
        from denidin import handle_image_message

        self._stub_external_boundaries(
            denidin_app, raw_response="Full document analysis: invoice for services rendered.",
            monkeypatch=monkeypatch
        )

        notification = self._create_notification(
            chat_id=GROUP_CHAT_ID,
            sender=ADMIN_SENDER_ID,
            sender_name="Admin User",
            caption="רותי, תראי את זה",  # would read as "clearly for someone else" as plain text
            msg_id="G039_MEDIA_002",
        )

        handle_image_message(notification)

        sent = notification._test_sent_messages[0] if notification._test_sent_messages else None
        assert sent == "Full document analysis: invoice for services rendered.", (
            "Media path must always return the real analysis, never [[NO_REPLY]] or "
            f"silence, regardless of caption content. Got: {sent!r}"
        )
