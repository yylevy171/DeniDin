"""Unit tests for the Reminders — Write capability handler's modify/delete branch
(Feature 063 write-approval-flow parity): propose -> pending -> approve/decline,
for both modify_reminder and delete_reminder."""
import json
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import propose_write, resolve_button_tap, resolve_typed_reply
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval


def _fake_function_call_response(tool_name, args_dict):
    item = MagicMock()
    item.type = "function_call"
    item.name = tool_name
    item.arguments = json.dumps(args_dict)
    item.call_id = "call_123"
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    response.id = "resp_1"
    return response


def _reminder_row(rrule=None):
    return {"reminder_id": "rem-1", "message_text": "תשלום שכ\"ט", "rrule": rrule, "dtstart": "2026-10-01T09:00:00"}


def test_propose_modify_whole_series_creates_pending_approval():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = []
    orchestrator.reminder_manager.get_reminder.return_value = _reminder_row()
    orchestrator.client.responses.create.return_value = _fake_function_call_response(
        "modify_reminder",
        {
            "reminder_id": "rem-1", "scope": "whole_series", "occurrence_date_hint": None,
            "new_message_text": "תשלום שכ\"ט מעודכן", "new_due_at": None,
        },
    )
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "תשני את התזכורת של שכ\"ט"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "לשנות" in result
    orchestrator.pending_local_tool_approval_manager.set.assert_called_once()
    chat_id_arg, pending_arg = orchestrator.pending_local_tool_approval_manager.set.call_args[0]
    assert chat_id_arg == "chat1"
    assert pending_arg.tool_name == "modify_reminder"


def test_propose_modify_single_occurrence_requires_hint_on_recurring_reminder():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = []
    orchestrator.reminder_manager.get_reminder.return_value = _reminder_row(rrule="FREQ=WEEKLY")
    orchestrator.client.responses.create.return_value = _fake_function_call_response(
        "modify_reminder",
        {
            "reminder_id": "rem-1", "scope": "single_occurrence", "occurrence_date_hint": "2026-10-08",
            "new_message_text": None, "new_due_at": "2026-10-08T10:00:00",
        },
    )
    orchestrator.reminder_manager.resolve_occurrence_datetime.return_value = MagicMock()
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "רק את התזכורת של שבוע הבא"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "לשנות" in result
    orchestrator.reminder_manager.resolve_occurrence_datetime.assert_called_once()
    orchestrator.pending_local_tool_approval_manager.set.assert_called_once()


def test_propose_delete_reminder_not_found_returns_friendly_error():
    orchestrator = MagicMock()
    orchestrator.reminder_manager.list_active.return_value = []
    orchestrator.reminder_manager.get_reminder.return_value = None
    orchestrator.client.responses.create.return_value = _fake_function_call_response(
        "delete_reminder", {"reminder_id": "does-not-exist", "scope": "whole_series", "occurrence_date_hint": None},
    )
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "תבטל את התזכורת"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "לא נמצאה" in result
    orchestrator.pending_local_tool_approval_manager.set.assert_not_called()


def test_resolve_button_tap_approve_modifies_whole_series():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="modify_reminder", sent_message_id="stanza1",
        arguments={
            "reminder_id": "rem-1", "scope": "whole_series",
            "new_message_text": "עודכן", "new_due_at": None,
        },
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending

    response = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", None)

    orchestrator.reminder_manager.modify_whole_series.assert_called_once_with(
        "rem-1", new_message_text="עודכן", new_due_at=None,
    )
    orchestrator.pending_local_tool_approval_manager.clear.assert_called_once_with("chat1")
    assert "עודכנה" in response.response_text


def test_resolve_typed_reply_approve_deletes_single_occurrence():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="delete_reminder",
        arguments={"reminder_id": "rem-1", "scope": "single_occurrence", "occurrence_date_hint": "2026-10-08"},
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    request = MagicMock(user_prompt="כן", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    orchestrator.reminder_manager.delete_single_occurrence.assert_called_once_with(
        "rem-1", occurrence_date_hint="2026-10-08",
    )
    assert "בוטלה" in result.response_text
    assert result.should_reply is True


def test_resolve_typed_reply_decline_does_not_execute_and_returns_none():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="delete_reminder",
        arguments={"reminder_id": "rem-1", "scope": "whole_series", "occurrence_date_hint": None},
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    request = MagicMock(user_prompt="לא", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    assert result is None
    orchestrator.reminder_manager.delete_whole_series.assert_not_called()
    orchestrator.pending_local_tool_approval_manager.clear.assert_called_once_with("chat1")
