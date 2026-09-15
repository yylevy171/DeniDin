"""Unit tests for the Backbone-level cross-cutting tools (Feature 063 remaining
Deferred item): send_progress_update / react_to_message extraction + dispatch."""
import json
from unittest.mock import MagicMock, patch

from src.backbone.backbone_tools import (
    dispatch_react_to_message,
    dispatch_send_progress_update,
    extract_backbone_tool_calls,
)


def _function_call_item(name, call_id, args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = name
    item.call_id = call_id
    item.arguments = json.dumps(args_dict)
    return item


def test_extract_backbone_tool_calls_finds_both_kinds():
    response = MagicMock()
    response.output = [
        _function_call_item("send_progress_update", "c1", {"text": "עובד על זה..."}),
        _function_call_item("react_to_message", "c2", {"emoji": "👍", "message_id": None}),
        _function_call_item("create_reminder", "c3", {"message_text": "x"}),  # not a backbone tool
    ]
    calls = extract_backbone_tool_calls(response)
    assert [c[1] for c in calls] == ["send_progress_update", "react_to_message"]
    assert calls[0][0] == "c1"
    assert calls[1][2]["emoji"] == "👍"


def test_extract_backbone_tool_calls_empty_when_none_present():
    response = MagicMock()
    response.output = [_function_call_item("create_reminder", "c1", {})]
    assert extract_backbone_tool_calls(response) == []


def test_extract_backbone_tool_calls_skips_malformed_arguments():
    item = MagicMock()
    item.type = "function_call"
    item.name = "send_progress_update"
    item.call_id = "c1"
    item.arguments = "{not valid json"
    response = MagicMock()
    response.output = [item]
    assert extract_backbone_tool_calls(response) == []


def test_dispatch_send_progress_update_calls_callback_and_reports_sent():
    callback = MagicMock()
    result = dispatch_send_progress_update(callback, "chat1", {"text": "רגע..."})
    callback.assert_called_once_with("רגע...")
    assert result == {"sent": True}


def test_dispatch_send_progress_update_no_callback_reports_not_sent():
    result = dispatch_send_progress_update(None, "chat1", {"text": "רגע..."})
    assert result == {"sent": False}


def test_dispatch_send_progress_update_callback_failure_is_swallowed():
    callback = MagicMock(side_effect=RuntimeError("boom"))
    result = dispatch_send_progress_update(callback, "chat1", {"text": "רגע..."})
    assert result == {"sent": False}


def test_dispatch_react_to_message_calls_send_reaction():
    bot = MagicMock()
    with patch("src.utils.green_api_bot.send_reaction", return_value=True) as mock_send:
        result = dispatch_react_to_message(bot, "chat1", "default_msg", {"emoji": "✅", "message_id": None})
    mock_send.assert_called_once_with(bot, "chat1", "default_msg", "✅")
    assert result == {"success": True}


def test_dispatch_react_to_message_uses_explicit_message_id_over_default():
    bot = MagicMock()
    with patch("src.utils.green_api_bot.send_reaction", return_value=True) as mock_send:
        dispatch_react_to_message(bot, "chat1", "default_msg", {"emoji": "✅", "message_id": "explicit_msg"})
    mock_send.assert_called_once_with(bot, "chat1", "explicit_msg", "✅")


def test_dispatch_react_to_message_no_bot_reports_failure_without_raising():
    result = dispatch_react_to_message(None, "chat1", "default_msg", {"emoji": "✅", "message_id": None})
    assert result == {"success": False}


def test_dispatch_react_to_message_send_failure_is_swallowed():
    bot = MagicMock()
    with patch("src.utils.green_api_bot.send_reaction", side_effect=RuntimeError("boom")):
        result = dispatch_react_to_message(bot, "chat1", "default_msg", {"emoji": "✅", "message_id": None})
    assert result == {"success": False}
