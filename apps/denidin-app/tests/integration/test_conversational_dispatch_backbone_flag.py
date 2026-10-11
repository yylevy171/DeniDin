"""
Integration test: text-message dispatch (denidin.py's _process_conversational_message)
reaches the one AI implementation's single_turn (REQ-063-08: denidin_app.ai_manager -
the Backbone with the flag on, AIHandler with it off; which one is decided once, in
initialize_app - see test_initialize_app_backbone_flag.py).

Added 2026-09-14 (Feature 063) after a real billed test showed text turns were
NEVER routed to the backbone at all - only media dispatch and button-tap
resolution checked `denidin_app.backbone`. Mirrors
test_media_dispatch_backbone_flag.py's pattern exactly: swaps the module-level
`denidin.denidin_app` singleton for the duration of each test (restored in a
finally block) rather than mocking any internal component - CONSTITUTION §V:
real internal code paths, the only substitution is which real, fully-
constructed DeniDin instance the module currently points at.
"""
from unittest.mock import MagicMock

import pytest
from whatsapp_chatbot_python import Notification

import denidin as denidin_module
from src.models.message import AIResponse
from src.models.user import Role


def _text_notification() -> Notification:
    notification = Notification.__new__(Notification)
    notification.event = {
        "senderData": {"chatId": "111@c.us", "sender": "111@c.us", "senderName": "Test Godfather"},
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": "תזכיר לי בעוד שעה להתקשר לרואה חשבון"},
        },
        "idMessage": "msg1", "timestamp": 1735689600,
    }
    notification._test_sent_messages = []

    def tracking_answer(message):
        notification._test_sent_messages.append(message)

    notification.answer = tracking_answer
    return notification


def _fake_message():
    message = MagicMock()
    message.chat_id = "111@c.us"
    message.sender_id = "111@c.us"
    message.sender_name = "Test Godfather"
    message.sender_display_name = "Test Godfather"
    message.text_content = "תזכיר לי בעוד שעה להתקשר לרואה חשבון"
    message.is_group = False
    message.chat_name = None
    return message


def _base_fake_denidin():
    fake_denidin = MagicMock()
    fake_denidin.green_api_bot = None
    fake_denidin.typing_keepalive_scheduler = None
    fake_denidin.group_membership_resolver = None
    fake_denidin.whatsapp_handler.validate_message_type.return_value = True
    fake_denidin.whatsapp_handler.process_notification.return_value = _fake_message()
    fake_denidin.receive.return_value = _fake_message()  # REQ-063-08: DeniDin parses + stores
    fake_denidin.user_manager.get_user.return_value.is_blocked = False
    fake_denidin.user_manager.get_user.return_value.role = Role.GODFATHER
    return fake_denidin


@pytest.mark.integration
def test_text_dispatch_calls_the_ai_managers_single_turn_once():
    fake_denidin = _base_fake_denidin()
    response = AIResponse(
        request_id="r1", response_text="לאישור — תזכורת חדשה...", tokens_used=0,
        prompt_tokens=0, completion_tokens=0, model="gpt-5.6-luna",
        finish_reason="stop", timestamp=1735689600,
    )
    fake_denidin.ai_manager.single_turn.return_value = response

    original_app = denidin_module.denidin_app
    denidin_module.denidin_app = fake_denidin
    try:
        denidin_module._process_conversational_message(_text_notification())  # pylint: disable=protected-access
    finally:
        denidin_module.denidin_app = original_app

    fake_denidin.ai_manager.single_turn.assert_called_once()
    # The RBAC phone is passed; each implementation resolves the role from it itself.
    call_kwargs = fake_denidin.ai_manager.single_turn.call_args.kwargs
    assert call_kwargs["user_phone"] == "111@c.us"
    assert call_kwargs["chat_id"] == "111@c.us"
    assert "user_role" not in call_kwargs
    # The turn's AIResponse is kept on DeniDin (observability / E2E tests).
    assert fake_denidin.last_response is response
