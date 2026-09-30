"""
Integration test (T054, updated 2026-09-24 for the "resolution" redesign): a
full flag-on turn (AIRequest in -> AIResponse out) creating a reminder
directly (cap_reminders_write is a direct-execute capability - no pending-
approval state of its own; approval, when the model wants it, is the model's
own separate use of the stateless `approval_with_yes_no_buttons` tool). There
is no separate "use" step — `load_capabilities` alone
attaches both the capability's prompt AND its real domain tools (e.g.
`create_reminder`) to the SAME ongoing chain, so the model calls the real
tool directly, starting the very next round. Mocked OpenAI client (the SDK
boundary itself, per CONSTITUTION §I/§V - internal code paths are all real:
real BackboneOrchestrator, real ReminderManager), no `billed` cost.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from tests.backbone_test_support import make_session_manager
from src.managers.reminder_manager import ReminderManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse


def _fake_function_call_response(name: str, arguments: dict, response_id: str = "resp"):
    item = MagicMock()
    item.type = "function_call"
    item.name = name
    item.arguments = json.dumps(arguments)
    item.call_id = "call_abc"
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    response.id = response_id
    response.usage = None
    return response


@pytest.mark.integration
def test_flag_on_turn_creates_reminder_directly_and_response_shape_matches_legacy(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(Path(__file__).parent.parent.parent / "config")},
    )

    ai_client = MagicMock()
    ai_client.responses.create.side_effect = [
        # Round 1 of the top-level orchestration loop: the model loads
        # cap_reminders_write - its prompt AND its create_reminder/modify/delete
        # tools are attached to the very next round in one step.
        _fake_function_call_response(
            "load_capabilities", {"capabilities": ["cap_reminders_write"]},
            response_id="resp_load_capabilities",
        ),
        # Round 2 (follow-up, chained via previous_response_id): the model
        # calls the now-attached create_reminder tool directly - no separate
        # "use" step, dispatched immediately by the orchestration loop.
        _fake_function_call_response(
            "create_reminder",
            {"message_text": "לשלם לספק", "schedule_type": "one_time", "one_time_due_at": "2099-01-01T09:00:00", "recurrence": None},
            response_id="resp_create",
        ),
        # Round 3: the model sends the confirmation to the user.
        _fake_function_call_response(
            "send_to_user", {"text": "✅ נוצרה תזכורת: לשלם לספק"},
            response_id="resp_send_to_user",
        ),
    ]

    reminder_manager = ReminderManager(storage_dir=str(tmp_path / "data" / "reminders"))
    orchestrator = BackboneOrchestrator(
        ai_client, config,
        reminder_manager=reminder_manager, session_manager=make_session_manager(),
    )

    request = AIRequest(
        user_prompt="תזכיר לי מחר לשלם לספק", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )

    response = orchestrator.turn_with_rounds(request, chat_id="chat1", user_role="godfather")

    # Same AIResponse shape denidin.py's existing callers already expect.
    assert isinstance(response, AIResponse)
    assert isinstance(response.response_text, str)
    assert isinstance(response.should_reply, bool)
    assert "לשלם לספק" in response.response_text

    # The reminder was actually created (direct-execute, no pending-approval
    # state left behind).
    active = reminder_manager.list_active()
    assert len(active) == 1
    assert active[0]["message_text"] == "לשלם לספק"
