"""
Component-Integration Test: Reminder Conversation Routing (Feature 054, T009a; updated for the
no-turn redesign - Feature 067)

Verifies the full real path for creating a reminder: a real textMessage-shaped Green API
notification -> handle_text_message -> WhatsAppHandler -> Backbone -> the model loads
cap_reminders_write and asks for approval with the yes/no buttons tool -> a real
interactive-buttons send through the (faked) Green API bot, its message id kept on the chat for
the stale-tap guard - all real internal objects (CONSTITUTION SS V), only the OpenAI client and
the Green API bot are stood in for.

Does NOT exercise real conversational accuracy (whether the model decides to create a
reminder at the right time) - that needs the real OpenAI API and belongs in tests/billed/.
What this DOES prove: the real routing/handler/manager wiring turns a scripted
approval-then-create conversation into a buttons send, and creates the reminder only on the
approved call. (Client-role gating is not tested here: the backbone treats clients as out of
scope for now - see Backbone._resolve_role.)
"""
from datetime import timedelta

import pytest

from src.utils.time_utils import now_local
from tests.routing_test_support import (
    build_routing_app, function_call, nothing_more, send_to_user, text_notification,
)

GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"


@pytest.mark.integration
class TestReminderCreationRouting:

    @pytest.fixture
    def denidin_app(self, tmp_path, monkeypatch):
        app = build_routing_app(tmp_path, monkeypatch)
        yield app
        app.session_manager.close()

    def test_a_reminder_request_gets_an_approval_buttons_prompt_and_nothing_is_created_yet(self, denidin_app):
        from denidin import handle_text_message
        prompt = "📋 לאישור:\nתזכורת: להתקשר לרואה חשבון\nלאישור — כן/לא?"
        denidin_app.ai_client.responses.create.side_effect = [
            function_call("load_capabilities", {"capabilities": ["cap_reminders_write", "cap_approval_with_buttons"]},
                          rid="r1"),
            function_call("approval_with_yes_no_buttons", {"text": prompt}, rid="r2"),
            nothing_more("r3"),
        ]

        handle_text_message(text_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "תזכיר לי להתקשר לרואה חשבון בעוד שעה", "integration_msg_1"))

        buttons = denidin_app.green_api_bot.buttons
        assert [(chat, body) for chat, body, _ in buttons] == [(GODFATHER_CHAT_ID, prompt)]
        assert denidin_app.session_manager.get_session(GODFATHER_CHAT_ID).approval_message_id == "BTN1"
        assert denidin_app.reminder_manager.list_active() == []  # still waiting for the answer

    def test_the_approved_call_creates_the_reminder_and_confirms(self, denidin_app):
        from denidin import handle_text_message
        due_at = (now_local() + timedelta(hours=1)).isoformat()
        denidin_app.session_manager.set_active_capabilities(GODFATHER_CHAT_ID, ["cap_reminders_write"])
        denidin_app.session_manager.set_approval_message_id(GODFATHER_CHAT_ID, "BTN-OLD")
        # the typed "כן" answers the outstanding approval: an approved write, no SDK retries
        denidin_app.ai_client.with_options.return_value.responses.create.side_effect = [
            function_call("create_reminder", {
                "message_text": "להתקשר לרואה חשבון", "schedule_type": "one_time",
                "one_time_due_at": due_at, "recurrence": None}, rid="r1"),
            send_to_user("✅ התזכורת נוצרה", rid="r2"),
            nothing_more("r3"),
        ]

        handle_text_message(text_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather", "כן", "integration_msg_yes"))

        active = denidin_app.reminder_manager.list_active()
        assert [r["message_text"] for r in active] == ["להתקשר לרואה חשבון"]
        assert denidin_app.green_api_bot.sent == [(GODFATHER_CHAT_ID, "✅ התזכורת נוצרה")]
        assert denidin_app.session_manager.get_session(GODFATHER_CHAT_ID).approval_message_id is None
