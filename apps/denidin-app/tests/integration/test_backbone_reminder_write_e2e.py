"""
Integration test (T054): a full flag-on turn (AIRequest in -> AIResponse out)
proposing a reminder creation, asserting the returned AIResponse shape matches
what denidin.py's callers already expect from the legacy path. Mocked OpenAI
client (the SDK boundary itself, per CONSTITUTION §I/§V - internal code paths are
all real: real BackboneOrchestrator, real ReminderManager, real
PendingLocalToolApprovalManager), no `billed` cost.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApprovalManager
from src.managers.reminder_manager import ReminderManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse


def _fake_intent_response(text: str):
    response = MagicMock()
    response.output_text = text
    response.output = []
    response.usage = None
    return response


def _fake_plan_response(plan_json: str):
    response = MagicMock()
    response.output_text = plan_json
    response.output = []
    response.usage = None
    return response


def _fake_create_reminder_call_response(args: dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = "create_reminder"
    item.arguments = json.dumps(args)
    item.call_id = "call_abc"
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    response.id = "resp_propose"
    response.usage = None
    return response


@pytest.mark.integration
def test_flag_on_turn_proposes_reminder_and_response_shape_matches_legacy(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(Path(__file__).parent.parent.parent / "config")},
    )

    ai_client = MagicMock()
    ai_client.responses.create.side_effect = [
        _fake_intent_response("The user wants to be reminded to pay a supplier tomorrow."),
        _fake_plan_response(json.dumps({"steps": [{"capability": "reminders_write", "note": "propose it"}]})),
        _fake_create_reminder_call_response(
            {"message_text": "לשלם לספק", "one_time_due_at": "2099-01-01T09:00:00"}
        ),
    ]

    reminder_manager = ReminderManager(storage_dir=str(tmp_path / "data" / "reminders"))
    orchestrator = BackboneOrchestrator(
        ai_client, config,
        reminder_manager=reminder_manager,
        pending_local_tool_approval_manager=PendingLocalToolApprovalManager(),
    )

    request = AIRequest(
        user_prompt="תזכיר לי מחר לשלם לספק", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )

    response = orchestrator.get_response(request, chat_id="chat1", user_role="godfather")

    # Same AIResponse shape denidin.py's existing callers already expect.
    assert isinstance(response, AIResponse)
    assert isinstance(response.response_text, str)
    assert isinstance(response.should_reply, bool)
    assert "לשלם לספק" in response.response_text
    assert orchestrator.pending_local_tool_approval_manager.get("chat1") is not None
