"""Unit tests for the Ledger Events — Query capability's `query_ledger_events`
direct tool (2026-09-24 "resolution" redesign)."""
import json
from unittest.mock import MagicMock

from src.capabilities.ledger_events.handler import dispatch_direct_tool_call
from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED


def test_query_searches_and_returns_raw_events_as_json():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager.query_events.return_value = {
        "matches": [{"client_name": "יוסי", "amount": 500}], "count": 1,
    }
    args = {"criteria": [{"text": "יוסי", "hint": "identity"}]}

    result = dispatch_direct_tool_call(orchestrator, "query_ledger_events", args, {})

    orchestrator.ledger_event_manager.query_events.assert_called_once_with(
        criteria=[{"text": "יוסי", "hint": "identity"}]
    )
    assert json.loads(result)["count"] == 1
    assert "יוסי" in result  # ensure_ascii=False: Hebrew stays readable


def test_query_without_manager_configured():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager = None
    result = dispatch_direct_tool_call(
        orchestrator, "query_ledger_events", {"criteria": [{"text": "x", "hint": None}]}, {},
    )
    assert result == BACKBONE_CAPABILITY_NOT_CONFIGURED


def test_unknown_tool_name_is_an_error():
    assert dispatch_direct_tool_call(MagicMock(), "nope", {}, {}).startswith("error:")
