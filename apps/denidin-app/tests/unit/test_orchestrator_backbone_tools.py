"""Unit tests: the orchestration loop attaches BACKBONE_TOOLS every round and
resolves send_progress_update/react_to_message calls, submitting an output for
every function_call (bugfix-042's failure mode)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from tests.backbone_test_support import make_session_manager
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _orchestrator(prompts_root, client):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(client, config, session_manager=make_session_manager())


def _request():
    return AIRequest(
        user_prompt="שלח לי חשבונית", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
        original_message=SimpleNamespace(whatsapp_id_message="msg1"),
    )


def _function_call_item(name, call_id, args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = name
    item.call_id = call_id
    item.arguments = json.dumps(args_dict)
    return item


def _resp(items, rid, text=""):
    r = MagicMock()
    r.output = items
    r.output_text = text
    r.id = rid
    r.usage = None
    return r


def _run(orchestrator, progress_callback=None):
    return orchestrator.turn_with_rounds(_request(), chat_id="chat1", user_role="godfather",
                                     progress_callback=progress_callback)


def test_backbone_tools_attached_every_round(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _resp([], "r1", "תשובה.")
    _run(_orchestrator(prompts_root, client))
    kwargs = client.responses.create.call_args.kwargs
    names = {t["name"] for t in kwargs["tools"] if t.get("type") == "function"}
    assert {"send_progress_update", "react_to_message", "send_to_user"} <= names


def test_reaction_dispatched_and_output_submitted(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})], "resp_1"),
        _resp([_function_call_item("send_to_user", "call_2", {"text": "בוצע."})], "resp_2"),
    ]
    orchestrator = _orchestrator(prompts_root, client)
    orchestrator.green_api_bot = MagicMock()
    with patch("src.tool_actions.messaging_actions.send_reaction", return_value=True) as mock_send:
        response = _run(orchestrator)
    mock_send.assert_called_once_with(orchestrator.green_api_bot, "chat1", "msg1", "👍")
    assert response.response_text == "בוצע."
    follow = client.responses.create.call_args_list[1].kwargs
    assert follow["previous_response_id"] == "resp_1"
    assert follow["input"][0]["call_id"] == "call_1"
    assert follow["input"][0]["type"] == "function_call_output"


def test_progress_update_uses_active_callback(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("send_progress_update", "call_1", {"text": "רגע..."})], "resp_1"),
        _resp([_function_call_item("send_to_user", "call_2", {"text": "תשובה סופית."})], "resp_2"),
    ]
    cb = MagicMock()
    response = _run(_orchestrator(prompts_root, client), progress_callback=cb)
    cb.assert_called_once_with("רגע...")
    assert response.response_text == "תשובה סופית."


def test_no_tool_calls_returns_plain_text_single_call(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _resp([], "r1", "תשובה.")
    response = _run(_orchestrator(prompts_root, client))
    assert client.responses.create.call_count == 1
    assert response.response_text == "תשובה."


def test_follow_up_failure_falls_back_to_first_round_text(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})],
              "resp_1", "טקסט מקורי."),
        RuntimeError("network error"),
    ]
    orchestrator = _orchestrator(prompts_root, client)
    orchestrator.green_api_bot = MagicMock()
    with patch("src.tool_actions.messaging_actions.send_reaction", return_value=True):
        response = _run(orchestrator)
    assert response.response_text == "טקסט מקורי."
