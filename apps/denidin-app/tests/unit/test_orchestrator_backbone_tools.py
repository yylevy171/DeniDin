"""Unit tests (Feature 063 remaining Deferred item): BackboneOrchestrator.
call_capability_step attaches BACKBONE_TOOLS to every step and resolves any
send_progress_update/react_to_message calls via one follow-up round, closing
bugfix-042's exact failure mode (every function_call gets its output submitted)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "capabilities" / "intent_identification.md").write_text("INTENT", encoding="utf-8")
    return base


def _orchestrator(prompts_root, client):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(client, config)


def _request():
    return AIRequest(
        user_prompt="שלח לי חשבונית", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def _function_call_item(name, call_id, args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = name
    item.call_id = call_id
    item.arguments = json.dumps(args_dict)
    return item


def test_call_capability_step_attaches_backbone_tools(prompts_root):
    client = MagicMock()
    response = MagicMock()
    response.output = []
    response.output_text = "תשובה."
    client.responses.create.return_value = response
    orchestrator = _orchestrator(prompts_root, client)

    orchestrator.call_capability_step(CapabilityTag.INTENT_IDENTIFICATION, _request())

    kwargs = client.responses.create.call_args.kwargs
    tool_names = {t["name"] for t in kwargs["tools"] if t.get("type") == "function"}
    assert "send_progress_update" in tool_names
    assert "react_to_message" in tool_names


def test_call_capability_step_dispatches_reaction_and_resolves_follow_up(prompts_root):
    client = MagicMock()
    first_response = MagicMock()
    first_response.id = "resp_1"
    first_response.output = [_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})]
    first_response.output_text = ""
    follow_up_response = MagicMock()
    follow_up_response.output = []
    follow_up_response.output_text = "בוצע."
    client.responses.create.side_effect = [first_response, follow_up_response]

    orchestrator = _orchestrator(prompts_root, client)
    orchestrator.green_api_bot = MagicMock()
    orchestrator._turn_chat_id = "chat1"  # pylint: disable=protected-access

    with patch("src.utils.green_api_bot.send_reaction", return_value=True) as mock_send:
        result = orchestrator.call_capability_step(CapabilityTag.INTENT_IDENTIFICATION, _request())

    mock_send.assert_called_once_with(orchestrator.green_api_bot, "chat1", "msg1", "👍")
    assert result == "בוצע."

    follow_up_kwargs = client.responses.create.call_args_list[1].kwargs
    assert follow_up_kwargs["previous_response_id"] == "resp_1"
    assert follow_up_kwargs["input"][0]["call_id"] == "call_1"
    assert follow_up_kwargs["input"][0]["type"] == "function_call_output"


def test_call_capability_step_progress_update_uses_active_callback(prompts_root):
    client = MagicMock()
    first_response = MagicMock()
    first_response.id = "resp_1"
    first_response.output = [_function_call_item("send_progress_update", "call_1", {"text": "רגע..."})]
    first_response.output_text = ""
    follow_up_response = MagicMock()
    follow_up_response.output = []
    follow_up_response.output_text = "תשובה סופית."
    client.responses.create.side_effect = [first_response, follow_up_response]

    orchestrator = _orchestrator(prompts_root, client)
    progress_callback = MagicMock()
    orchestrator._turn_progress_callback = progress_callback  # pylint: disable=protected-access

    result = orchestrator.call_capability_step(CapabilityTag.INTENT_IDENTIFICATION, _request())

    progress_callback.assert_called_once_with("רגע...")
    assert result == "תשובה סופית."


def test_call_capability_step_no_backbone_tool_calls_skips_follow_up(prompts_root):
    client = MagicMock()
    response = MagicMock()
    response.output = []
    response.output_text = "תשובה."
    client.responses.create.return_value = response
    orchestrator = _orchestrator(prompts_root, client)

    result = orchestrator.call_capability_step(CapabilityTag.INTENT_IDENTIFICATION, _request())

    assert client.responses.create.call_count == 1
    assert result == "תשובה."


def test_call_capability_step_follow_up_failure_falls_back_to_original_response(prompts_root):
    client = MagicMock()
    first_response = MagicMock()
    first_response.id = "resp_1"
    first_response.output = [_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})]
    first_response.output_text = "טקסט מקורי."
    client.responses.create.side_effect = [first_response, RuntimeError("network error")]

    orchestrator = _orchestrator(prompts_root, client)

    result = orchestrator.call_capability_step(CapabilityTag.INTENT_IDENTIFICATION, _request())

    assert result == "טקסט מקורי."
