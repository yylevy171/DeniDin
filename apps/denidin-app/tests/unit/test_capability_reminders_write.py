"""Unit tests for the Reminders — Write capability handler (updated 2026-09-24
for the "resolution" redesign: `dispatch_direct_tool_call` executes one real
tool call made directly on the ongoing resolution-loop chain — no
separate write step/PendingLocalToolApproval dance of its own)."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import dispatch_direct_tool_call


def test_dispatch_executes_create_reminder_immediately():
    backbone = MagicMock()
    backbone.reminder_manager.create_reminder.return_value = {
        "reminder_id": "abc-123", "due_at": "2026-10-01T09:00:00+03:00",
    }
    args = {"message_text": "לשלם ספק", "one_time_due_at": "2026-10-01T09:00:00"}

    result = dispatch_direct_tool_call(
        backbone, "create_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.create_reminder.assert_called_once()
    assert "abc-123" in result


def test_dispatch_executes_modify_immediately():
    backbone = MagicMock()
    backbone.reminder_manager.get_reminder.return_value = {"message_text": "ישן", "rrule": "FREQ=DAILY"}
    args = {"reminder_id": "abc-123", "scope": "whole_series", "new_message_text": "תזכורת חדשה"}

    result = dispatch_direct_tool_call(
        backbone, "modify_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.modify_whole_series.assert_called_once()
    assert "עודכנה" in result


def test_dispatch_list_reminders_reads_directly_no_ai_call():
    backbone = MagicMock()
    backbone.reminder_manager.list_active.return_value = []

    result = dispatch_direct_tool_call(
        backbone, "list_reminders", {}, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.list_active.assert_called_once()
    assert isinstance(result, str)
