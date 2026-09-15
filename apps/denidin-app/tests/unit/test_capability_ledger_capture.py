"""Unit tests for the Ledger Events — Capture capability handler (Feature 063,
revised 2026-09-15): this step is now a documented no-op delegating to
`call_capability_step` — it no longer offers a capture tool or persists directly,
since the real, proven three-verdict recognition mechanism
(`denidin.py`'s shared `_run_post_turn_ledger_recognition` ->
`AIHandler.recognize_ledger_event`) already runs post-turn for every godfather/admin
turn under flag-on (text and media alike), and this step running its own capture
alongside it would risk double-capturing the same event. See handler.py's `capture()`
docstring for the full reasoning."""
from unittest.mock import MagicMock

from src.capabilities.ledger_events.handler import capture
from src.capabilities.ledger_events.tools import to_call_arguments


def test_capture_never_persists_directly():
    """The step must never call add_ledger_events_from_call itself - that would
    double-capture whatever the shared post-turn mechanism also recognizes."""
    orchestrator = MagicMock()
    orchestrator.call_capability_step.return_value = "אין צורך בפעולה נוספת."
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=1, message_id="m1")
    request.user_prompt = "סוכם עם עמיר כץ 5000 שח על ייצוג"

    result = capture(orchestrator, request, "", "", {"chat_id": "chat1"})

    orchestrator.ledger_event_manager.add_ledger_events_from_call.assert_not_called()
    orchestrator.client.responses.create.assert_not_called()
    assert result == "אין צורך בפעולה נוספת."


def test_capture_delegates_to_call_capability_step_with_ledger_capture_tag():
    from src.backbone.capability_tags import CapabilityTag

    orchestrator = MagicMock()
    orchestrator.call_capability_step.return_value = "noted."
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=1, message_id="m1")
    request.user_prompt = "text"

    capture(orchestrator, request, "prior context", "a note", {"chat_id": "chat1"})

    orchestrator.call_capability_step.assert_called_once_with(
        tag=CapabilityTag.LEDGER_CAPTURE, request=request, accumulated_context="prior context",
    )


def test_capture_reports_manager_not_configured():
    orchestrator = MagicMock()
    orchestrator.ledger_event_manager = None
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=1, message_id="m1")
    request.user_prompt = "text"

    result = capture(orchestrator, request, "", "", {"chat_id": "chat1"})
    assert result == "Ledger manager not configured."
    orchestrator.call_capability_step.assert_not_called()


def test_to_call_arguments_reshapes_flat_args_to_components_array():
    """to_call_arguments itself still exists (kept for a future real
    implementation, src/capabilities/ledger_events/tools.py) and is still correct
    - only the handler's own use of it was removed."""
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
