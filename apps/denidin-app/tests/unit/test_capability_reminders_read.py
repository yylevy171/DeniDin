"""Unit tests for the Reminders — Read capability handler (updated 2026-09-24
for the "resolution" redesign: `dispatch_direct_tool_call`'s `list_reminders`
branch reads ReminderManager directly, deterministic, no AI call)."""
import json
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import dispatch_direct_tool_call


def test_list_reminders_lists_active_reminders():
    backbone = MagicMock()
    backbone.reminder_manager.list_active.return_value = [
        {"reminder_id": "rem-1", "message_text": "לשלם לספק", "rrule": None,
         "dtstart": "2026-10-01T09:00:00+03:00"},
        {"reminder_id": "rem-2", "message_text": "לשתות מים", "rrule": "FREQ=DAILY;INTERVAL=1",
         "dtstart": "2026-10-01T09:00:00+03:00"},
    ]

    result = dispatch_direct_tool_call(backbone, "list_reminders", {}, {})

    reminders = json.loads(result)["reminders"]
    assert [r["reminder_id"] for r in reminders] == ["rem-1", "rem-2"]
    assert reminders[0]["message_text"] == "לשלם לספק" and reminders[0]["schedule"].startswith("חד-פעמי")
    assert "יומי" in reminders[1]["schedule"]  # the recurrence is visible, not just the first occurrence
    backbone.reminder_manager.list_active.assert_called_once()


def test_list_reminders_no_active_reminders():
    backbone = MagicMock()
    backbone.reminder_manager.list_active.return_value = []

    result = dispatch_direct_tool_call(backbone, "list_reminders", {}, {})
    assert json.loads(result) == {"reminders": []}


def test_list_reminders_without_manager_configured():
    backbone = MagicMock()
    backbone.reminder_manager = None

    result = dispatch_direct_tool_call(backbone, "list_reminders", {}, {})
    assert "אינו זמין" in result
