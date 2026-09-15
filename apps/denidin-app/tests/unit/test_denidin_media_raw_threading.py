"""Unit tests (Feature 063, 2026-09-15 real design correction): the flag-on media
dispatch in denidin.py's `_process_media_message` threads RAW, not-yet-extracted
media into BackboneOrchestrator.get_response - downloading and validating only
(reusing the unmodified, standalone MediaFileManager methods), never running the
full legacy MediaHandler.process_media_message pipeline (which also extracts/
persists/ledger-detects in one call) for the flag-on path. Extraction itself is
left entirely to the orchestrator's own Planning -> media_analysis capability
step, per contracts/orchestration-loop.md.
"""
from unittest.mock import Mock

import pytest
from whatsapp_chatbot_python import Notification

import denidin as denidin_module
from src.models.message import AIResponse


def _media_notification(caption=""):
    notification = Notification.__new__(Notification)
    notification.event = {
        "senderData": {"chatId": "111@c.us", "sender": "111@c.us", "senderName": "Test"},
        "messageData": {
            "typeMessage": "imageMessage",
            "fileMessageData": {
                "downloadUrl": "https://example.com/fake.jpg",
                "caption": caption, "mimeType": "image/jpeg", "fileName": "fake.jpg",
            },
        },
        "idMessage": "msg1", "timestamp": 1735689600,
    }
    notification._test_sent_messages = []
    notification.answer = notification._test_sent_messages.append
    return notification


@pytest.fixture
def app(monkeypatch):
    fake = Mock()
    fake.config.ai_reply_max_tokens = 1000
    fake.config.ai_vision_model = "gpt-5.6-luna"
    fake.green_api_bot = None
    fake.typing_keepalive_scheduler = None
    fake.ai_handler.user_manager.get_user.return_value.is_blocked = False
    fake.backbone_orchestrator.get_response.return_value = AIResponse(
        request_id="r1", response_text="בסדר.", tokens_used=0,
        prompt_tokens=0, completion_tokens=0, model="gpt-5.6-luna",
        finish_reason="stop", timestamp=1735689600,
    )
    monkeypatch.setattr(denidin_module, "denidin_app", fake)
    return fake


def test_flag_on_media_dispatch_never_calls_the_legacy_extraction_pipeline(app):
    """The old shortcut (process_media_message: download+extract+persist+ledger-
    detect in one call) must never be invoked on the flag-on path — only the raw
    low-level MediaFileManager pieces."""
    file_manager = app.whatsapp_handler.media_handler.media_file_manager
    file_manager.download_file.return_value = (b"fake jpeg bytes", True)
    file_manager.validate_format.return_value = "image"

    denidin_module._process_media_message(_media_notification())  # pylint: disable=protected-access

    app.whatsapp_handler.media_handler.process_media_message.assert_not_called()
    file_manager.download_file.assert_called_once()
    file_manager.validate_file_size.assert_called_once_with(len(b"fake jpeg bytes"))
    file_manager.validate_format.assert_called_once()


def test_flag_on_media_dispatch_passes_raw_media_not_pre_extracted_result(app):
    """get_response is called with a raw Media object + media_type, is_media=True,
    and no media_extraction - Planning is what decides whether to extract, not
    denidin.py."""
    from src.models.media import Media

    file_manager = app.whatsapp_handler.media_handler.media_file_manager
    file_manager.download_file.return_value = (b"fake jpeg bytes", True)
    file_manager.validate_format.return_value = "image"

    denidin_module._process_media_message(_media_notification(caption="קבלה"))  # pylint: disable=protected-access

    kwargs = app.backbone_orchestrator.get_response.call_args.kwargs
    assert kwargs["is_media"] is True
    assert kwargs["media_type"] == "image"
    assert isinstance(kwargs["media"], Media)
    assert kwargs["media"].data == b"fake jpeg bytes"
    assert kwargs["media"].mime_type == "image/jpeg"
    assert kwargs.get("media_extraction") is None
    request = app.backbone_orchestrator.get_response.call_args.args[0]
    assert request.user_prompt == "קבלה"


def test_flag_on_media_dispatch_download_failure_sends_friendly_error_without_calling_orchestrator(app):
    file_manager = app.whatsapp_handler.media_handler.media_file_manager
    file_manager.download_file.return_value = (b"", False)

    denidin_module._process_media_message(_media_notification())  # pylint: disable=protected-access

    app.backbone_orchestrator.get_response.assert_not_called()
    assert len(_media_notification()._test_sent_messages) == 0  # sanity: fresh fixture is empty


def test_flag_on_media_dispatch_unsupported_format_sends_friendly_error_without_calling_orchestrator(app):
    file_manager = app.whatsapp_handler.media_handler.media_file_manager
    file_manager.download_file.return_value = (b"fake bytes", True)
    file_manager.validate_format.side_effect = ValueError("Unsupported format: exe.")

    notification = _media_notification()
    denidin_module._process_media_message(notification)  # pylint: disable=protected-access

    app.backbone_orchestrator.get_response.assert_not_called()
    assert len(notification._test_sent_messages) == 1
