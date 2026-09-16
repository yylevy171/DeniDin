"""Unit tests for the Reminders — Write capability handler (T053): propose →
pending → approve/decline."""
from unittest.mock import MagicMock

from src.capabilities.reminders.handler import propose_write, resolve_button_tap, resolve_typed_reply
from src.capabilities.reminders.tools import is_affirmative_reply
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval


def _fake_function_call_response(args_dict):
    import json
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


def test_propose_write_creates_pending_approval():
    orchestrator = MagicMock()
    # 2026-09-16: propose_write now goes through orchestrator.call_capability_step
    # (return_response=True) instead of calling client.responses.create directly.
    orchestrator.call_capability_step.return_value = _fake_function_call_response(
        {"message_text": "לשלם ספק", "one_time_due_at": "2026-10-01T09:00:00"}
    )
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "תזכיר לי מחר לשלם לספק"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "לשלם ספק" in result
    orchestrator.pending_local_tool_approval_manager.set.assert_called_once()
    chat_id_arg, pending_arg = orchestrator.pending_local_tool_approval_manager.set.call_args[0]
    assert chat_id_arg == "chat1"
    assert pending_arg.arguments["message_text"] == "לשלם ספק"


def test_propose_write_no_tool_call_returns_model_text():
    orchestrator = MagicMock()
    response = MagicMock()
    response.output = []
    response.output_text = "לא זוהתה בקשה."
    orchestrator.call_capability_step.return_value = response
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "מה שלומך?"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})
    assert result == "לא זוהתה בקשה."


def test_resolve_button_tap_stale_returns_none():
    orchestrator = MagicMock()
    orchestrator.pending_local_tool_approval_manager.get.return_value = None
    result = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", None)
    assert result is None


def test_resolve_button_tap_approve_creates_reminder():
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

    response = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", None)

    orchestrator.reminder_manager.create_reminder.assert_called_once()
    orchestrator.pending_local_tool_approval_manager.clear.assert_called_once_with("chat1")
    assert "abc-123" in response.response_text


def test_resolve_button_tap_decline_does_not_create_reminder():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder", sent_message_id="stanza1",
        arguments={"message_text": "x", "one_time_due_at": "2026-10-01T09:00:00"},
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending

    response = resolve_button_tap(orchestrator, "chat1", "denidin_decline", "stanza1", None)

    orchestrator.reminder_manager.create_reminder.assert_not_called()
    assert response.response_text == "בוטל."


# --- is_affirmative_reply (tools.py) -----------------------------------------

def test_is_affirmative_reply_recognizes_common_hebrew_and_english_replies():
    for text in ("כן", "אישור", "בסדר", "אוקיי", "מאשר", "yes", "ok", "OK", "  כן  "):
        assert is_affirmative_reply(text) is True, f"expected {text!r} to be affirmative"


def test_is_affirmative_reply_rejects_negative_and_unrelated_replies():
    for text in ("לא", "לא תודה", "מה השעה עכשיו?", "", "   "):
        assert is_affirmative_reply(text) is False, f"expected {text!r} to NOT be affirmative"


def test_is_affirmative_reply_matches_leading_word_only_not_a_longer_refusal():
    # A longer refusal that happens to start with a negative word must never
    # be misread as approval via a substring-anywhere check.
    assert is_affirmative_reply("לא, תבטל בבקשה") is False


# --- resolve_typed_reply (handler.py) ----------------------------------------

def test_resolve_typed_reply_no_pending_returns_none():
    orchestrator = MagicMock()
    orchestrator.pending_local_tool_approval_manager.get.return_value = None
    request = MagicMock(user_prompt="כן", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    assert result is None
    orchestrator.reminder_manager.create_reminder.assert_not_called()


def test_resolve_typed_reply_approve_creates_reminder():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder",
        arguments={"message_text": "לשלם ספק", "one_time_due_at": "2026-10-01T09:00:00"},
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    orchestrator.reminder_manager.create_reminder.return_value = {
        "reminder_id": "abc-123", "due_at": "2026-10-01T09:00:00+03:00",
    }
    request = MagicMock(user_prompt="כן", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    orchestrator.reminder_manager.create_reminder.assert_called_once()
    call_kwargs = orchestrator.reminder_manager.create_reminder.call_args.kwargs
    assert call_kwargs["created_by_phone"] == "+972500000000"
    assert call_kwargs["created_by_role"] == "GODFATHER"
    orchestrator.pending_local_tool_approval_manager.clear.assert_called_once_with("chat1")
    assert "abc-123" in result.response_text
    assert result.should_reply is True


def test_resolve_typed_reply_decline_clears_and_returns_none():
    orchestrator = MagicMock()
    pending = PendingLocalToolApproval(
        tool_name="create_reminder",
        arguments={"message_text": "x", "one_time_due_at": "2026-10-01T09:00:00"},
    )
    orchestrator.pending_local_tool_approval_manager.get.return_value = pending
    request = MagicMock(user_prompt="לא", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1", "+972500000000", "GODFATHER")

    assert result is None  # falls through to a normal fresh turn, same as legacy
    orchestrator.reminder_manager.create_reminder.assert_not_called()
    orchestrator.pending_local_tool_approval_manager.clear.assert_called_once_with("chat1")
