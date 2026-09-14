"""Unit tests for the Ledger Events — Capture capability handler (Feature 063):
a recognized event persists via the unmodified LedgerEventManager, no approval
gate (immediate dispatch, mirrors list_reminders/query_ledger_events)."""
import json
from unittest.mock import MagicMock

from src.capabilities.ledger_events.handler import capture
from src.capabilities.ledger_events.tools import to_call_arguments


def _fake_capture_response(args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = "capture_ledger_event"
    item.arguments = json.dumps(args_dict)
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    return response


def test_capture_persists_agreement_event():
    orchestrator = MagicMock()
    orchestrator.session_manager.get_session.return_value.session_id = "sess-1"
    orchestrator.ledger_event_manager.add_ledger_events_from_call.return_value = ["A1409260900"]
    orchestrator.client.responses.create.return_value = _fake_capture_response({
        "source_type": "הסכם", "client_name": "עמיר כץ", "payer_name": None,
        "description": "ייצוג בתביעה", "amount": "5000", "vat_status": "לא צוין",
        "txn_date": None, "agreement_id": "AGR-1",
    })
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=123, message_id="m1")
    request.user_prompt = "סוכם עם עמיר כץ 5000 שח על ייצוג"

    result = capture(orchestrator, request, "", "", {"chat_id": "chat1"})

    orchestrator.ledger_event_manager.add_ledger_events_from_call.assert_called_once()
    kwargs = orchestrator.ledger_event_manager.add_ledger_events_from_call.call_args.kwargs
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["call_arguments"]["source_type"] == "הסכם"
    assert kwargs["call_arguments"]["components"][0]["amount"] == "5000"
    assert "✅" in result


def test_capture_no_tool_call_returns_model_text():
    orchestrator = MagicMock()
    response = MagicMock()
    response.output = []
    response.output_text = "אין כאן אירוע כספי."
    orchestrator.client.responses.create.return_value = response
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=1, message_id="m1")
    request.user_prompt = "מה שלומך?"

    result = capture(orchestrator, request, "", "", {"chat_id": "chat1"})
    assert result == "אין כאן אירוע כספי."
    orchestrator.ledger_event_manager.add_ledger_events_from_call.assert_not_called()


def test_capture_persist_failure_reports_friendly_error():
    orchestrator = MagicMock()
    orchestrator.session_manager.get_session.return_value.session_id = "sess-1"
    orchestrator.ledger_event_manager.add_ledger_events_from_call.return_value = []
    orchestrator.client.responses.create.return_value = _fake_capture_response({
        "source_type": "בנק", "client_name": None, "payer_name": "יוסי כהן",
        "description": "הפקדה", "amount": "1200", "vat_status": "לא צוין",
        "txn_date": None, "agreement_id": None,
    })
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=1, message_id="m1")
    request.user_prompt = "יוסי כהן הפקיד 1200 שח"

    result = capture(orchestrator, request, "", "", {"chat_id": "chat1"})
    assert "נכשל" in result


def test_to_call_arguments_reshapes_flat_args_to_components_array():
    flat = {
        "source_type": "הסכם", "client_name": "X", "payer_name": None,
        "description": "d", "amount": "100", "vat_status": "לא צוין",
        "txn_date": None, "agreement_id": "AGR-1",
    }
    reshaped = to_call_arguments(flat)
    assert reshaped["component_count"] == 1
    assert reshaped["event_subtype"] == "יצירה"
    assert reshaped["components"][0]["amount"] == "100"


def test_to_call_arguments_bank_event_subtype():
    flat = {"source_type": "בנק", "client_name": None, "payer_name": "Y",
            "description": "d", "amount": "50", "vat_status": "לא צוין",
            "txn_date": None, "agreement_id": None}
    reshaped = to_call_arguments(flat)
    assert reshaped["event_subtype"] == "הפקדה"
