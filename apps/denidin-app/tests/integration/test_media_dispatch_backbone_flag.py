"""
Integration test (T049): flag-on media dispatch (denidin.py) reaches
BackboneOrchestrator instead of WhatsAppHandler.handle_media_message(); flag-off
dispatch is provably unchanged (REQ-063-04a).

Swaps the module-level `denidin.denidin_app` singleton for the duration of each
test (restored in a finally block) rather than mocking any internal component -
CONSTITUTION §V: real internal code paths, the only substitution is which real,
fully-constructed DeniDin instance the module currently points at.
"""
import pytest
from unittest.mock import MagicMock
from whatsapp_chatbot_python import Notification

import denidin as denidin_module


def _media_notification() -> Notification:
    notification = Notification.__new__(Notification)
    notification.event = {
        "senderData": {"chatId": "111@c.us", "sender": "111@c.us", "senderName": "Test"},
        "messageData": {
            "typeMessage": "imageMessage",
            "fileMessageData": {
                "downloadUrl": "https://example.com/fake.jpg",
                "caption": "", "mimeType": "image/jpeg", "fileName": "fake.jpg",
            },
        },
        "idMessage": "msg1", "timestamp": 1735689600,
    }
    notification._test_sent_messages = []

    def tracking_answer(message):
        notification._test_sent_messages.append(message)

    notification.answer = tracking_answer
    return notification


@pytest.mark.integration
def test_flag_on_media_dispatch_calls_backbone_orchestrator_not_legacy_handler():
    fake_denidin = MagicMock()
    fake_denidin.config.ai_reply_max_tokens = 1000
    fake_denidin.config.ai_vision_model = "gpt-5.6-luna"
    fake_denidin.green_api_bot = None
    fake_denidin.typing_keepalive_scheduler = None
    fake_denidin.ai_handler.user_manager.get_user.return_value.is_blocked = False
    # 2026-09-15: the flag-on path now only downloads+validates raw media (REQ-063-04a's
    # real design - see denidin.py's own comment) instead of running the full legacy
    # extraction pipeline, so these two MediaFileManager calls need real-shaped return
    # values for the dispatch to reach backbone_orchestrator.get_response at all.
    file_manager = fake_denidin.whatsapp_handler.media_handler.media_file_manager
    file_manager.download_file.return_value = (b"fake jpeg bytes", True)
    file_manager.validate_format.return_value = "image"

    from src.models.message import AIResponse
    fake_denidin.backbone_orchestrator.get_response.return_value = AIResponse(
        request_id="r1", response_text="נותח בהצלחה.", tokens_used=0,
        prompt_tokens=0, completion_tokens=0, model="gpt-5.6-luna",
        finish_reason="stop", timestamp=1735689600,
    )

    original_app = denidin_module.denidin_app
    denidin_module.denidin_app = fake_denidin
    try:
        denidin_module._process_media_message(_media_notification())  # pylint: disable=protected-access
    finally:
        denidin_module.denidin_app = original_app

    fake_denidin.backbone_orchestrator.get_response.assert_called_once()
    fake_denidin.whatsapp_handler.handle_media_message.assert_not_called()


@pytest.mark.integration
def test_flag_off_media_dispatch_is_unchanged():
    fake_denidin = MagicMock()
    fake_denidin.backbone_orchestrator = None
    fake_denidin.green_api_bot = None
    fake_denidin.typing_keepalive_scheduler = None
    fake_denidin.ai_handler.user_manager.get_user.return_value.is_blocked = False
    fake_denidin.whatsapp_handler.handle_media_message.return_value = {}

    original_app = denidin_module.denidin_app
    denidin_module.denidin_app = fake_denidin
    try:
        denidin_module._process_media_message(_media_notification())  # pylint: disable=protected-access
    finally:
        denidin_module.denidin_app = original_app

    fake_denidin.whatsapp_handler.handle_media_message.assert_called_once()
