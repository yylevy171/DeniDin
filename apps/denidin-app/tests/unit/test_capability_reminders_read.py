"""Unit tests for the Reminders — Read capability handler (T047)."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import read


def test_read_lists_active_reminders():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = [
        {"message_text": "לשלם לספק", "dtstart": "2026-10-01T09:00:00+03:00"},
    ]
    orchestrator.call_capability_step.return_value = "יש לך תזכורת אחת."
    request = MagicMock()

    result = read(orchestrator, request, "", "", {})

    assert "לשלם לספק" in result
    orchestrator.reminder_manager.list_active.assert_called_once()


def test_read_no_active_reminders():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = []
    orchestrator.call_capability_step.return_value = "אין תזכורות."
    request = MagicMock()

    result = read(orchestrator, request, "", "", {})
    assert "אין תזכורות פעילות" in result


def test_read_without_manager_configured():
    orchestrator = MagicMock()
    orchestrator.reminder_manager = None
    request = MagicMock()

    result = read(orchestrator, request, "", "", {})
    assert "not configured" in result
