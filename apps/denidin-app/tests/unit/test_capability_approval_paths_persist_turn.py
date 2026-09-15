"""Unit tests (Feature 063, 2026-09-15 gap fix): the pending-approval bypass paths
(resolve_button_tap/resolve_typed_reply in both reminders/handler.py and
invoicing/handler.py) construct AIResponse directly, bypassing
BackboneOrchestrator._finalize_response entirely - so they need their OWN explicit
calls to orchestrator._persist_turn to avoid a parallel persistence gap specifically
for approval-confirmation turns (mirrors legacy ai_handler.py's own
_resolve_pending_approval, which also persists separately from the main turn-
persistence block)."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import (
    resolve_button_tap as reminders_resolve_button_tap,
    resolve_typed_reply as reminders_resolve_typed_reply,
)
from src.capabilities.invoicing.handler import (
    resolve_button_tap as invoicing_resolve_button_tap,
    resolve_typed_reply as invoicing_resolve_typed_reply,
)
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.models.user import Role


def test_reminders_resolve_button_tap_persists_turn():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder", call_id="call_123",
        arguments={"message_text": "לשלם ספק", "one_time_due_at": "2026-10-01T09:00:00"},
        sent_message_id="stanza1",
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    orchestrator.reminder_manager.create_reminder.return_value = {
        "reminder_id": "abc-123", "due_at": "2026-10-01T09:00:00+03:00",
    }
    request = MagicMock(model="gpt-5.6-luna", timestamp=None)

    reminders_resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", request)

    orchestrator._persist_turn.assert_called_once()
    call_args = orchestrator._persist_turn.call_args[0]
    assert call_args[0] is request
    assert call_args[3] == "chat1"          # effective_chat_id
    assert call_args[4] == Role.GODFATHER   # role


def test_reminders_resolve_typed_reply_persists_turn():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder", call_id="call_123",
        arguments={"message_text": "לשלם ספק", "one_time_due_at": "2026-10-01T09:00:00"},
        sent_message_id="stanza1",
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    orchestrator.reminder_manager.create_reminder.return_value = {
        "reminder_id": "abc-123", "due_at": "2026-10-01T09:00:00+03:00",
    }
    request = MagicMock(model="gpt-5.6-luna", timestamp=None, request_id="r1")
    request.user_prompt = "כן"

    reminders_resolve_typed_reply(orchestrator, request, "chat1", "972501234567", "godfather")

    orchestrator._persist_turn.assert_called_once()
    call_args = orchestrator._persist_turn.call_args[0]
    assert call_args[3] == "chat1"
    assert call_args[4] == Role.GODFATHER


def test_reminders_resolve_button_tap_stale_never_persists():
    orchestrator = MagicMock()
    orchestrator.pending_local_tool_approval_manager.get.return_value = None
    result = reminders_resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", None)
    assert result is None
    orchestrator._persist_turn.assert_not_called()


def _fake_pending_mcp_approval(orchestrator, stanza_id="stanza1"):
    from src.managers.pending_approval_manager import PendingApproval
    pending = PendingApproval(
        response_id="resp1", approval_request_id="areq1", tool_name="create_invoice",
        arguments="{}", server_label="morning", created_at="2026-09-15T00:00:00+00:00",
        sent_message_id=stanza_id,
    )
    orchestrator.pending_approval_manager.get.return_value = pending
    return pending


def test_invoicing_resolve_button_tap_persists_turn():
    orchestrator = MagicMock()
    _fake_pending_mcp_approval(orchestrator)
    followup_response = MagicMock()
    followup_response.output = []
    followup_response.output_text = "הופקה חשבונית."
    orchestrator.client.responses.create.return_value = followup_response
    request = MagicMock(model="gpt-5.6-luna", timestamp=None)

    invoicing_resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", request)

    orchestrator._persist_turn.assert_called_once()
    call_args = orchestrator._persist_turn.call_args[0]
    assert call_args[3] == "chat1"
    assert call_args[4] == Role.GODFATHER


def test_invoicing_resolve_typed_reply_persists_turn():
    orchestrator = MagicMock()
    _fake_pending_mcp_approval(orchestrator)
    followup_response = MagicMock()
    followup_response.output = []
    followup_response.output_text = "הופקה חשבונית."
    orchestrator.client.responses.create.return_value = followup_response
    request = MagicMock(model="gpt-5.6-luna", timestamp=None, request_id="r1")
    request.user_prompt = "כן"

    invoicing_resolve_typed_reply(orchestrator, request, "chat1")

    orchestrator._persist_turn.assert_called_once()
    call_args = orchestrator._persist_turn.call_args[0]
    assert call_args[3] == "chat1"
    assert call_args[4] == Role.GODFATHER
