"""Unit tests for recurring reminder CREATION (Feature 063 remaining Deferred
item): create_reminder's schedule_type=recurring branch, propose -> pending ->
approve, threading a full recurrence object through to ReminderManager.create_reminder
unmodified."""
import json
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import propose_write, resolve_typed_reply
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval

_RECURRENCE = {
    "interval": 1, "freq": "weekly", "weekdays": ["MO"], "month_day": None,
    "month_nth_weekday": None, "first_occurrence_at": "2026-10-05T09:00:00",
    "end_condition": "never", "end_count": None, "end_until": None,
}


def _fake_function_call_response(args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = "create_reminder"
    item.arguments = json.dumps(args_dict)
    item.call_id = "call_123"
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    response.id = "resp_1"
    return response


def test_propose_recurring_reminder_creates_pending_approval_with_recurrence():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = []
    orchestrator.client.responses.create.return_value = _fake_function_call_response({
        "message_text": "פגישת צוות", "schedule_type": "recurring",
        "one_time_due_at": None, "recurrence": _RECURRENCE,
    })
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "תזכיר לי כל יום שני בבוקר על פגישת צוות"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "חוזרת" in result
    orchestrator.pending_local_tool_approval_manager.set.assert_called_once()
    _, pending_arg = orchestrator.pending_local_tool_approval_manager.set.call_args[0]
    assert pending_arg.arguments["schedule_type"] == "recurring"
    assert pending_arg.arguments["recurrence"] == _RECURRENCE


def test_resolve_typed_reply_approve_creates_recurring_reminder():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder",
        arguments={
            "message_text": "פגישת צוות", "schedule_type": "recurring",
            "one_time_due_at": None, "recurrence": _RECURRENCE,
        },
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    orchestrator.reminder_manager.create_reminder.return_value = {
        "reminder_id": "rec-1", "due_at": "2026-10-05T09:00:00+03:00",
    }
    request = MagicMock(user_prompt="כן", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    orchestrator.reminder_manager.create_reminder.assert_called_once()
    call_kwargs = orchestrator.reminder_manager.create_reminder.call_args.kwargs
    assert call_kwargs["schedule_type"] == "recurring"
    assert call_kwargs["recurrence"] == _RECURRENCE
    assert call_kwargs["one_time_due_at"] is None
    assert "rec-1" in result.response_text
