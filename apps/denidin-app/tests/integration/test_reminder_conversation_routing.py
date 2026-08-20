"""
Component-Integration Test: Reminder Creation Conversation Routing (Feature 054, T009a)

Verifies the full real router-dispatch path for creating a reminder: a real
textMessage-shaped Green API notification -> bot.router -> handle_text_message ->
WhatsAppHandler -> AIHandler.get_response -> _finalize_response ->
_handle_reminder_creation_proposal -> a PendingLocalToolApproval is set and an
interactive-buttons approval prompt is sent - all real internal objects and
real router dispatch (CONSTITUTION SS V), only the OpenAI client's
responses.create is stood in for (the genuine external boundary), same
convention as tests/integration/test_group_conversation_routing.py's media-path
stubs.

Does NOT exercise real conversational accuracy (whether the model decides to
call create_reminder at the right time) - that needs the real OpenAI API and
belongs in tests/billed/. What this DOES prove: given a response that already
contains a create_reminder call, the real routing/handler/manager wiring
correctly turns it into a pending approval and a real interactive-buttons send,
not just that the isolated unit pieces behave correctly (already covered by
tests/unit/test_ai_handler_reminders.py).
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models.config import AppConfiguration


GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"


@pytest.mark.integration
class TestReminderCreationRouting:

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
                'reminders': {'max_active_reminders': 20},
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)

        return denidin_module.denidin_app

    def _create_notification(self, chat_id: str, sender: str, sender_name: str, text: str, msg_id: str):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1755331200,
            'senderData': {
                'chatId': chat_id,
                'sender': sender,
                'senderName': sender_name,
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': text},
            },
        }
        notification._test_sent_messages = []
        notification._test_button_sends = []

        def track_answer(message):
            notification._test_sent_messages.append(message)

        _next_id = [0]

        def track_answer_with_interactive_buttons(body, buttons, header=None, footer=None):
            _next_id[0] += 1
            id_message = f"TEST_BUTTONS_{msg_id}_{_next_id[0]}"
            notification._test_button_sends.append({
                'body': body, 'buttons': buttons, 'idMessage': id_message,
            })
            notification._test_sent_messages.append(body)
            return SimpleNamespace(code=200, data={'idMessage': id_message}, error=None)

        notification.answer = track_answer
        notification.answer_with_interactive_buttons = track_answer_with_interactive_buttons
        return notification

    def _stub_create_reminder_response(self, denidin_app, monkeypatch, args: dict):
        """Stand in for the one genuine external boundary (OpenAI) - everything
        else (router, WhatsAppHandler, AIHandler, ReminderManager,
        PendingLocalToolApprovalManager) stays real."""
        response = SimpleNamespace(
            id="resp_integration_1",
            output=[SimpleNamespace(
                type="function_call", name="create_reminder",
                arguments=json.dumps(args), call_id="call_integration_1",
            )],
            output_text="",
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
        )
        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', lambda **kwargs: response)

    def test_create_reminder_call_produces_pending_approval_and_button_prompt(self, denidin_app, monkeypatch):
        """
        **Scenario**: Godfather asks for a reminder; the model calls create_reminder.

        Given: a real textMessage notification from the godfather's own chat
        When: dispatched through the real handle_text_message router entry
        Then: a PendingLocalToolApproval is set for that chat, the sent reply is an
              interactive-buttons approval prompt (not plain text), and no
              Reminder was actually persisted yet (still pending approval).
        """
        from datetime import timedelta
        from src.utils.time_utils import now_local
        from denidin import handle_text_message

        # Ensure a clean pending-state (process-global denidin_app is reused
        # across test files within one pytest session).
        denidin_app.ai_handler.pending_local_tool_approval_manager.clear(GODFATHER_CHAT_ID)
        denidin_app.ai_handler.pending_approval_manager.clear(GODFATHER_CHAT_ID)

        due_at = (now_local() + timedelta(hours=1)).isoformat()
        self._stub_create_reminder_response(denidin_app, monkeypatch, {
            "message_text": "להתקשר לרואה חשבון",
            "schedule_type": "one_time",
            "one_time_due_at": due_at,
            "recurrence": None,
        })

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "תזכיר לי להתקשר לרואה חשבון בעוד שעה", "integration_msg_1",
        )

        handle_text_message(notification)

        pending = denidin_app.ai_handler.pending_local_tool_approval_manager.get(GODFATHER_CHAT_ID)
        assert pending is not None
        assert pending.tool_name == "create_reminder"
        assert pending.response_id == "resp_integration_1"
        assert pending.call_id == "call_integration_1"

        button_send = notification._test_button_sends[0] if notification._test_button_sends else None
        assert button_send is not None, "expected an interactive-buttons approval prompt, got plain text"
        assert "לאישור" in button_send["body"]
        assert "כן/לא" in button_send["body"]

        # Nothing persisted yet - only pending.
        assert denidin_app.ai_handler.reminder_manager.list_active() == []

        denidin_app.ai_handler.pending_local_tool_approval_manager.clear(GODFATHER_CHAT_ID)

    def test_client_role_never_receives_create_reminder_tool_over_the_real_route(self, denidin_app, monkeypatch):
        """RBAC gate (FR-001), exercised through the real router/handler/RBAC-
        resolution path rather than calling _build_reminder_tools directly
        (already covered at the unit tier) - captures what `tools` the REAL
        _assemble_tools call actually handed to the (stubbed) OpenAI request
        for a genuine CLIENT-role dispatch, and confirms create_reminder is
        structurally absent, not just "not called this time"."""
        client_chat_id = "972500009999@c.us"
        captured_kwargs = {}

        def capture_and_respond(**kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                id="resp_client_1", output=[], output_text="בסדר",
                model="gpt-5.6-luna",
                usage=SimpleNamespace(total_tokens=4, input_tokens=3, output_tokens=1),
            )

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', capture_and_respond)

        notification = self._create_notification(
            client_chat_id, client_chat_id, "Test Client",
            "תזכיר לי משהו", "integration_msg_2",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        tool_names = [t.get("name") for t in (captured_kwargs.get("tools") or [])]
        assert "create_reminder" not in tool_names
        assert denidin_app.ai_handler.pending_local_tool_approval_manager.get(client_chat_id) is None
