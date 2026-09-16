"""Unit tests for the Ledger Events — Query capability handler (T047)."""
from unittest.mock import MagicMock

from src.capabilities.ledger_events.handler import query
from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED


def test_query_searches_and_reasons_over_results():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager.query_events.return_value = {
        "matches": [{"client_name": "יוסי", "amount": 500}], "count": 1,
    }
    orchestrator.call_capability_step.return_value = "יוסי שילם 500 ש\"ח."
    request = MagicMock()

    result = query(orchestrator, request, "", "האם יוסי שילם", {})

    orchestrator.ledger_event_manager.query_events.assert_called_once_with(
        [{"text": "האם יוסי שילם"}]
    )
    assert result == 'יוסי שילם 500 ש"ח.'


def test_query_without_manager_configured():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager = None
    request = MagicMock()

    result = query(orchestrator, request, "", "note", {})
    assert result == BACKBONE_CAPABILITY_NOT_CONFIGURED


def test_query_empty_note_produces_empty_criteria():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager.query_events.return_value = {"error": "no_search_criteria"}
    orchestrator.call_capability_step.return_value = "not sure what to search for."
    request = MagicMock()

    query(orchestrator, request, "", "", {})
    orchestrator.ledger_event_manager.query_events.assert_called_once_with([])
