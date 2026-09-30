"""Unit tests for the Reminders — Write capability handler's modify/delete
branch (updated 2026-09-24 for the "resolution" redesign:
`dispatch_direct_tool_call` executes one real tool call made directly on the
ongoing resolution-loop chain, no pending-approval state of its own), for
both modify_reminder and delete_reminder."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import dispatch_direct_tool_call


def _reminder_row(rrule=None):
    return {"reminder_id": "rem-1", "message_text": "תשלום שכ\"ט", "rrule": rrule, "dtstart": "2026-10-01T09:00:00"}


def test_dispatch_modify_whole_series_executes_immediately():
    backbone = MagicMock()
    backbone.reminder_manager.get_reminder.return_value = _reminder_row()
    args = {
        "reminder_id": "rem-1", "scope": "whole_series", "occurrence_date_hint": None,
        "new_message_text": "תשלום שכ\"ט מעודכן", "new_due_at": None,
    }

    result = dispatch_direct_tool_call(
        backbone, "modify_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.modify_whole_series.assert_called_once()
    assert "עודכנה" in result


def test_dispatch_modify_single_occurrence_requires_hint_on_recurring_reminder():
    backbone = MagicMock()
    backbone.reminder_manager.get_reminder.return_value = _reminder_row(rrule="FREQ=WEEKLY")
    backbone.reminder_manager.resolve_occurrence_datetime.return_value = MagicMock()
    args = {
        "reminder_id": "rem-1", "scope": "single_occurrence", "occurrence_date_hint": "2026-10-08",
        "new_message_text": None, "new_due_at": "2026-10-08T10:00:00",
    }

    result = dispatch_direct_tool_call(
        backbone, "modify_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.resolve_occurrence_datetime.assert_called_once()
    backbone.reminder_manager.modify_single_occurrence.assert_called_once()
    assert "עודכנה" in result


def test_dispatch_delete_reminder_not_found_returns_friendly_error():
    backbone = MagicMock()
    backbone.reminder_manager.get_reminder.return_value = None
    args = {"reminder_id": "does-not-exist", "scope": "whole_series", "occurrence_date_hint": None}

    result = dispatch_direct_tool_call(
        backbone, "delete_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    assert "לא נמצאה" in result
    backbone.reminder_manager.delete_whole_series.assert_not_called()


def test_dispatch_delete_single_occurrence_executes_immediately():
    backbone = MagicMock()
    backbone.reminder_manager.get_reminder.return_value = _reminder_row(rrule="FREQ=WEEKLY")
    backbone.reminder_manager.resolve_occurrence_datetime.return_value = MagicMock()
    args = {"reminder_id": "rem-1", "scope": "single_occurrence", "occurrence_date_hint": "2026-10-08"}

    result = dispatch_direct_tool_call(
        backbone, "delete_reminder", args, {"chat_id": "chat1", "role": "GODFATHER"},
    )

    backbone.reminder_manager.delete_single_occurrence.assert_called_once_with(
        reminder_id="rem-1", occurrence_date_hint="2026-10-08",
    )
    assert "בוטלה" in result
