"""Unit tests for the Backbone-level cross-cutting tools (Feature 063 remaining
Deferred item): send_progress_update / react_to_message extraction + dispatch."""
import json
from unittest.mock import MagicMock, patch

from src.backbone.backbone_tools import (
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
