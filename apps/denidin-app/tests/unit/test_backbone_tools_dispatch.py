"""Unit tests: the resolution loop attaches BACKBONE_TOOLS every round and
resolves send_progress_update/react_to_message calls, submitting an output for
every function_call (bugfix-042's failure mode)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.backbone import PLAIN_TEXT_REPLY_REMINDER
from src.constants.error_messages import BACKBONE_UNEXPECTED_ERROR
from tests.backbone_test_support import make_backbone, make_session_manager
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _backbone(prompts_root, client):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return make_backbone(client, config, session_manager=make_session_manager())


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


def _run(backbone):
    return backbone.single_turn(_request(), chat_id="chat1", user_role="godfather")


def test_backbone_tools_attached_every_round(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _resp([], "r1", "תשובה.")
    _run(_backbone(prompts_root, client))
    kwargs = client.responses.create.call_args.kwargs
    names = {t["name"] for t in kwargs["tools"] if t.get("type") == "function"}
    assert {"send_progress_update", "react_to_message", "send_to_user"} <= names


def test_reaction_dispatched_and_output_submitted(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})], "resp_1"),
        _resp([_function_call_item("send_to_user", "call_2", {"text": "בוצע."})], "resp_2"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.denidin.green_api_bot = MagicMock()
    with patch("src.handlers.whatsapp_handler.send_reaction", return_value=True) as mock_send:
        response = _run(backbone)
    mock_send.assert_called_once_with(backbone.denidin.green_api_bot, "chat1", "msg1", "👍")
    assert response.response_text == "בוצע."
    follow = client.responses.create.call_args_list[1].kwargs
    assert follow["previous_response_id"] == "resp_1"
    assert follow["input"][0]["call_id"] == "call_1"
    assert follow["input"][0]["type"] == "function_call_output"


def test_progress_update_is_sent_through_denidin(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("send_progress_update", "call_1", {"text": "רגע..."})], "resp_1"),
        _resp([_function_call_item("send_to_user", "call_2", {"text": "תשובה סופית."})], "resp_2"),
    ]
    backbone = _backbone(prompts_root, client)
    # REQ-063-08: DeniDin sends (and stores) it in the chat's turn in progress.
    backbone.denidin.send_progress_update = MagicMock(return_value=True)
    response = _run(backbone)
    backbone.denidin.send_progress_update.assert_called_once_with("chat1", "רגע...")
    assert response.response_text == "תשובה סופית."


def test_plain_text_is_never_sent_the_model_is_reminded_to_use_send_to_user(prompts_root):
    """2026-09-30: a reply reaches the user only through send_to_user - plain text gets
    one reminder round instead of being sent."""
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([], "r1", "תשובה בטקסט רגיל."),
        _resp([_function_call_item("send_to_user", "call_1", {"text": "תשובה."})], "r2", ""),
    ]
    response = _run(_backbone(prompts_root, client))
    assert client.responses.create.call_count == 2
    reminder_call = client.responses.create.call_args_list[1].kwargs
    assert reminder_call["previous_response_id"] == "r1"
    assert reminder_call["input"] == [{"role": "developer", "content": PLAIN_TEXT_REPLY_REMINDER}]
    assert response.response_text == "תשובה."


def test_plain_text_again_after_the_reminder_replies_with_an_error(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([], "r1", "טקסט רגיל."),
        _resp([], "r2", "שוב טקסט רגיל."),
    ]
    response = _run(_backbone(prompts_root, client))
    assert client.responses.create.call_count == 2
    assert response.response_text == BACKBONE_UNEXPECTED_ERROR


def test_follow_up_failure_falls_back_to_first_round_text(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _resp([_function_call_item("react_to_message", "call_1", {"emoji": "👍", "message_id": None})],
              "resp_1", "טקסט מקורי."),
        RuntimeError("network error"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.denidin.green_api_bot = MagicMock()
    with patch("src.handlers.whatsapp_handler.send_reaction", return_value=True):
        response = _run(backbone)
    assert response.response_text == "טקסט מקורי."
