"""Unit tests for recurring reminder CREATION (updated 2026-09-24 for the
"resolution" redesign: `dispatch_direct_tool_call` executes one real
create_reminder call made directly on the ongoing orchestration-loop chain,
no pending-approval state): create_reminder's schedule_type=recurring
branch, threading a full recurrence object through to
ReminderManager.create_reminder unmodified."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import dispatch_direct_tool_call

_RECURRENCE = {
    "interval": 1, "freq": "weekly", "weekdays": ["MO"], "month_day": None,
    "month_nth_weekday": None, "first_occurrence_at": "2026-10-05T09:00:00",
    "end_condition": "never", "end_count": None, "end_until": None,
}


def test_dispatch_executes_recurring_reminder_creation_immediately():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.create_reminder.return_value = {
        "reminder_id": "rec-1", "due_at": "2026-10-05T09:00:00+03:00",
    }
    args = {
        "message_text": "פגישת צוות", "schedule_type": "recurring",
        "one_time_due_at": None, "recurrence": _RECURRENCE,
    }

    result = dispatch_direct_tool_call(orchestrator, "create_reminder", args, {
        "chat_id": "chat1", "role": "GODFATHER", "user_phone": "+972500000000",
    })

    orchestrator.reminder_manager.create_reminder.assert_called_once()
    call_kwargs = orchestrator.reminder_manager.create_reminder.call_args.kwargs
    assert call_kwargs["schedule_type"] == "recurring"
    assert call_kwargs["recurrence"] == _RECURRENCE
    assert call_kwargs["one_time_due_at"] is None
    assert call_kwargs["created_by_phone"] == "+972500000000"
    assert "rec-1" in result
