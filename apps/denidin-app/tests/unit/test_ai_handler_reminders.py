"""
Unit tests for Feature 054's reminder wiring in AIHandler: tool attachment,
the create_reminder proposal path (_handle_reminder_creation_proposal), and
the approval-resolution path (_resolve_pending_local_tool_approval), plus the
dual-check dispatch added to get_response/resolve_button_tap.

Covers tasks.md T007a/T008a. Real conversational accuracy (does the model
call the tool at the right time, with the right fields) is NOT unit-testable
- that needs the real OpenAI API and belongs in tests/billed/. What IS
covered here: given a response that already contains a create_reminder call
(constructed directly, no real API), does AIHandler correctly create a
PendingLocalToolApproval / dispatch to a REAL ReminderManager on approval -
only the OpenAI client is a stand-in (external service, per CONSTITUTION SS I),
never any internal component. Mirrors test_ai_handler_ledger_events.py's
established Mock(spec=AppConfiguration) pattern.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import (
    AIHandler, CREATE_REMINDER_TOOL, REMINDER_AUTHORIZED_ROLES,
    _build_reminder_approval_details, _format_reminder_schedule,
)
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.models.user import Role
from src.constants.error_messages import (
    REMINDER_ACTION_FAILED_TRY_AGAIN, REMINDER_PAST_DATE_REJECTED, REMINDER_CAP_EXCEEDED,
)
from src.utils.time_utils import now_local
from datetime import timedelta


def _function_call_item(name, arguments, call_id="call_reminder_1"):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _response(output, resp_id="resp_1", text=""):
    return SimpleNamespace(
        id=resp_id, output=output, output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
    )


def _followup_response(text="התזכורת נוצרה בהצלחה", resp_id="resp_followup_1"):
    return SimpleNamespace(
        id=resp_id, output=[], output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=10, input_tokens=6, output_tokens=4),
    )


def _future_iso(minutes=60):
    return (now_local() + timedelta(minutes=minutes)).isoformat()


def _create_args(**overrides):
    base = {
        "message_text": "call the accountant",
        "schedule_type": "one_time",
        "one_time_due_at": _future_iso(),
        "recurrence": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
        'longterm': {'enabled': False},
    }
    config.user_roles = {
        'admin_phones': ['972500000001'],
        'blocked_phones': ['972500000099'],
    }
    config.godfather_phone = '972500000002'
    config.reminders = {'max_active_reminders': 20}
    return config


@pytest.fixture
def mock_ai_client():
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_ai_client):
    return AIHandler(mock_ai_client, mock_config)


GODFATHER_PHONE = '972500000002'
ADMIN_PHONE = '972500000001'
CLIENT_PHONE = '972500000003'
BLOCKED_PHONE = '972500000099'


class TestToolAttachment:
    def test_godfather_gets_all_four_reminder_tools(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._build_reminder_tools(user_obj)
        names = {t["name"] for t in tools}
        assert names == {"create_reminder", "list_reminders", "modify_reminder", "delete_reminder"}

    def test_admin_gets_all_four_reminder_tools(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(ADMIN_PHONE)
        tools = ai_handler._build_reminder_tools(user_obj)
        names = {t["name"] for t in tools}
        assert names == {"create_reminder", "list_reminders", "modify_reminder", "delete_reminder"}

    def test_client_does_not_get_create_reminder_tool(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        assert ai_handler._build_reminder_tools(user_obj) == []

    def test_none_user_does_not_get_tool(self, ai_handler):
        assert ai_handler._build_reminder_tools(None) == []

    def test_assemble_tools_includes_create_reminder_for_godfather(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1")
        names = [t.get("name") for t in tools]
        assert "create_reminder" in names

    def test_assemble_tools_excludes_create_reminder_for_client(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1")
        names = [t.get("name") for t in (tools or [])]
        assert "create_reminder" not in names

    def test_authorized_roles_are_exactly_godfather_and_admin(self):
        assert set(REMINDER_AUTHORIZED_ROLES) == {Role.GODFATHER, Role.ADMIN}


class TestReminderCreationProposal:
    """T007a/T008a: _handle_reminder_creation_proposal - detection, validation,
    PendingLocalToolApproval creation. Never dispatches immediately (unlike
    capture_ledger_event)."""

    def test_no_create_reminder_call_returns_none_false(self, ai_handler):
        response = _response([SimpleNamespace(type="message")], text="just a normal reply")
        text, created = ai_handler._handle_reminder_creation_proposal(
            AIRequest(user_prompt="hi", constitution="", max_tokens=500, model="gpt-5.6-luna",
                      chat_id="chat1", message_id="m1"),
            response, "chat1",
        )
        assert text is None
        assert created is False

    def test_valid_proposal_creates_pending_approval(self, ai_handler):
        args = _create_args()
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_creation_proposal(request, response, "chat1")

        assert created is True
        assert "לאישור" in text
        assert "כן/לא" in text
        pending = ai_handler.pending_local_tool_approval_manager.get("chat1")
        assert pending is not None
        assert pending.tool_name == "create_reminder"
        assert pending.response_id == "resp_1"
        assert pending.call_id == "call_reminder_1"
        assert pending.arguments == args

    def test_no_reminder_created_in_db_at_proposal_time(self, ai_handler):
        """Proposal only ever creates a PendingLocalToolApproval - never touches
        ReminderManager's storage until approval."""
        args = _create_args()
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        ai_handler._handle_reminder_creation_proposal(request, response, "chat1")
        assert ai_handler.reminder_manager.list_active() == []

    def test_past_date_rejected_with_friendly_message_no_pending(self, ai_handler):
        args = _create_args(one_time_due_at=(now_local() - timedelta(hours=1)).isoformat())
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_creation_proposal(request, response, "chat1")

        assert text == REMINDER_PAST_DATE_REJECTED
        assert created is False
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None

    def test_invalid_recurrence_rejected(self, ai_handler):
        args = _create_args(
            schedule_type="recurring", one_time_due_at=None,
            recurrence={
                "interval": 1, "freq": "yearly", "weekdays": None, "month_day": None,
                "month_nth_weekday": None, "first_occurrence_at": _future_iso(),
                "end_condition": "never", "end_count": None, "end_until": None,
            },
        )
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_creation_proposal(request, response, "chat1")

        assert text == REMINDER_ACTION_FAILED_TRY_AGAIN
        assert created is False

    def test_cap_exceeded_rejected_with_friendly_message(self, ai_handler):
        for i in range(20):
            ai_handler.reminder_manager.create_reminder(
                message_text=f"r{i}", schedule_type="one_time", one_time_due_at=_future_iso(60 + i),
                recurrence=None, created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
            )
        args = _create_args(one_time_due_at=_future_iso(500))
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_creation_proposal(request, response, "chat1")

        assert text == REMINDER_CAP_EXCEEDED
        assert created is False

    def test_none_effective_chat_id_returns_none_false(self, ai_handler):
        args = _create_args()
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        text, created = ai_handler._handle_reminder_creation_proposal(request, response, None)
        assert (text, created) == (None, False)


class TestApprovalDetailsFormatting:
    def test_one_time_schedule_format(self):
        summary = _format_reminder_schedule(None, "2026-08-20T10:00:00+03:00")
        assert "20/08/2026" in summary
        assert "10:00" in summary

    def test_weekly_schedule_format(self):
        summary = _format_reminder_schedule("FREQ=WEEKLY;BYDAY=MO,TH", "2026-08-17T10:00:00+03:00")
        assert "שבועי" in summary
        assert "MO,TH" in summary

    def test_create_reminder_details_contains_message_and_question(self):
        details = _build_reminder_approval_details(
            "create_reminder", {"message_text": "לקנות חלב"}, "2026-08-20T10:00:00+03:00", None
        )
        assert "לקנות חלב" in details
        assert "כן/לא" in details


class TestResolvePendingLocalToolApproval:
    """T008a: approve/decline paths, TOCTOU re-check, follow-up confirmation call."""

    def _propose(self, ai_handler, chat_id="chat1", **arg_overrides):
        args = _create_args(**arg_overrides)
        response = _response([_function_call_item("create_reminder", args)])
        request = AIRequest(user_prompt="remind me", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id=chat_id, message_id="m1")
        ai_handler._handle_reminder_creation_proposal(request, response, chat_id)
        return ai_handler.pending_local_tool_approval_manager.get(chat_id)

    def test_approve_creates_reminder_and_returns_followup_text(self, ai_handler, mock_ai_client):
        pending = self._propose(ai_handler)
        mock_ai_client.responses.create.return_value = _followup_response("התזכורת שלך נקבעה")
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result is not None
        assert result.response_text == "התזכורת שלך נקבעה"
        assert result.offer_approval_buttons is False
        assert len(ai_handler.reminder_manager.list_active()) == 1
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None

    def test_approve_chains_followup_via_previous_response_id(self, ai_handler, mock_ai_client):
        pending = self._propose(ai_handler)
        mock_ai_client.responses.create.return_value = _followup_response()
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert call_kwargs["previous_response_id"] == "resp_1"
        assert call_kwargs["input"][0]["call_id"] == "call_reminder_1"
        assert call_kwargs["input"][0]["type"] == "function_call_output"

    def test_decline_clears_pending_and_returns_none(self, ai_handler, mock_ai_client):
        pending = self._propose(ai_handler)
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="לא", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result is None
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None
        assert ai_handler.reminder_manager.list_active() == []
        mock_ai_client.responses.create.assert_not_called()

    def test_toctou_cap_failure_at_approval_time_returns_fallback(self, ai_handler, mock_ai_client):
        pending = self._propose(ai_handler)
        # Fill the cap AFTER proposing but BEFORE approving - simulates a
        # concurrent proposal winning the race.
        for i in range(20):
            ai_handler.reminder_manager.create_reminder(
                message_text=f"r{i}", schedule_type="one_time", one_time_due_at=_future_iso(60 + i),
                recurrence=None, created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
            )
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result is not None
        assert result.response_text == REMINDER_ACTION_FAILED_TRY_AGAIN
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None
        mock_ai_client.responses.create.assert_not_called()

    def test_followup_call_failure_falls_back_to_generic_text(self, ai_handler, mock_ai_client):
        pending = self._propose(ai_handler)
        mock_ai_client.responses.create.side_effect = Exception("network error")
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        # The reminder WAS created despite the confirmation call failing.
        assert len(ai_handler.reminder_manager.list_active()) == 1
        assert result.response_text == REMINDER_ACTION_FAILED_TRY_AGAIN


class TestDualCheckDispatch:
    """Dual-check dispatch order in get_response: MCP pending checked first,
    then local-tool pending (contracts/local-tool-approval-gate.md)."""

    def test_local_pending_routes_to_resolution_not_normal_turn(self, ai_handler, mock_ai_client):
        pending = PendingLocalToolApproval(
            tool_name="create_reminder", response_id="resp_x", call_id="call_x",
            arguments=_create_args(), created_at=now_local().isoformat(),
        )
        ai_handler.pending_local_tool_approval_manager.set(GODFATHER_PHONE, pending)
        mock_ai_client.responses.create.return_value = _followup_response("נוצר")

        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id=GODFATHER_PHONE, message_id="m2")
        result = ai_handler.get_response(
            request, chat_id=GODFATHER_PHONE, user_role="GODFATHER",
            sender=GODFATHER_PHONE, recipient=None, user_phone=GODFATHER_PHONE,
        )

        assert result.response_text == "נוצר"
        # Did NOT fall through to a normal turn (which would have called the
        # API with tools/instructions, not a function_call_output).
        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert call_kwargs.get("previous_response_id") == "resp_x"

    def test_mcp_pending_takes_precedence_over_local_pending(self, ai_handler, mock_ai_client):
        """If (in the real world, an edge case) both were somehow populated,
        MCP is checked first - deterministic order, not a real expected state."""
        from src.managers.pending_approval_manager import PendingApproval
        mcp_pending = PendingApproval(
            response_id="resp_mcp", approval_request_id="ar_1", tool_name="create_invoice",
            arguments="{}", server_label="morning-invoices", created_at=now_local().isoformat(),
        )
        ai_handler.pending_approval_manager.set(GODFATHER_PHONE, mcp_pending)
        local_pending = PendingLocalToolApproval(
            tool_name="create_reminder", response_id="resp_local", call_id="call_local",
            arguments=_create_args(), created_at=now_local().isoformat(),
        )
        ai_handler.pending_local_tool_approval_manager.set(GODFATHER_PHONE, local_pending)
        # Decline the MCP one (cheapest path to observe which one got picked -
        # a decline returns None from _resolve_pending_approval and falls
        # through, whereas the local-tool decline path is also None but
        # clears ONLY the local manager if IT were picked instead).
        request = AIRequest(user_prompt="לא", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id=GODFATHER_PHONE, message_id="m2")
        mock_ai_client.responses.create.return_value = _response([], text="")

        ai_handler.get_response(
            request, chat_id=GODFATHER_PHONE, user_role="GODFATHER",
            sender=GODFATHER_PHONE, recipient=None, user_phone=GODFATHER_PHONE,
        )

        # MCP pending was resolved (cleared); local pending was never touched.
        assert ai_handler.pending_approval_manager.get(GODFATHER_PHONE) is None
        assert ai_handler.pending_local_tool_approval_manager.get(GODFATHER_PHONE) is not None


def _function_call_item_with_id(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


class TestListReminders:
    def test_no_call_returns_none(self, ai_handler):
        response = _response([SimpleNamespace(type="message")], text="hi")
        request = AIRequest(user_prompt="hi", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        assert ai_handler._handle_list_reminders(request, response, tools=None) is None

    def test_dispatches_immediately_and_returns_followup(self, ai_handler, mock_ai_client):
        ai_handler.reminder_manager.create_reminder(
            message_text="call the accountant", schedule_type="one_time",
            one_time_due_at=_future_iso(60), recurrence=None,
            created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        response = _response([_function_call_item_with_id("list_reminders", {}, "call_list_1")])
        mock_ai_client.responses.create.return_value = _followup_response("יש לך תזכורת אחת")
        request = AIRequest(user_prompt="מה התזכורות שלי", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        result = ai_handler._handle_list_reminders(request, response, tools=None)

        assert result is not None
        assert result.output_text == "יש לך תזכורת אחת"
        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert call_kwargs["previous_response_id"] == "resp_1"
        payload = json.loads(call_kwargs["input"][0]["output"])
        assert len(payload["reminders"]) == 1
        assert payload["reminders"][0]["message_text"] == "call the accountant"

    def test_followup_failure_returns_none(self, ai_handler, mock_ai_client):
        response = _response([_function_call_item_with_id("list_reminders", {}, "call_list_1")])
        mock_ai_client.responses.create.side_effect = Exception("network error")
        request = AIRequest(user_prompt="מה התזכורות שלי", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        assert ai_handler._handle_list_reminders(request, response, tools=None) is None


class TestModifyDeleteProposal:
    def _existing_reminder(self, ai_handler, recurring=False):
        if recurring:
            return ai_handler.reminder_manager.create_reminder(
                message_text="daily standup", schedule_type="recurring", one_time_due_at=None,
                recurrence={
                    "interval": 1, "freq": "daily", "weekdays": None, "month_day": None,
                    "month_nth_weekday": None, "first_occurrence_at": _future_iso(60),
                    "end_condition": "never", "end_count": None, "end_until": None,
                },
                created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
            )
        return ai_handler.reminder_manager.create_reminder(
            message_text="call the accountant", schedule_type="one_time",
            one_time_due_at=_future_iso(60), recurrence=None,
            created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )

    def _modify_args(self, reminder_id, **overrides):
        base = {
            "reminder_id": reminder_id, "scope": "whole_series", "occurrence_date_hint": None,
            "new_message_text": "updated text", "new_due_at": None, "new_recurrence": None,
        }
        base.update(overrides)
        return base

    def test_modify_whole_series_creates_pending_approval(self, ai_handler):
        r = self._existing_reminder(ai_handler)
        response = _response([_function_call_item_with_id("modify_reminder", self._modify_args(r["reminder_id"]), "call_m1")])
        request = AIRequest(user_prompt="שנה את התזכורת", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_modify_or_delete_proposal(request, response, "chat1")

        assert created is True
        assert "עדכון תזכורת" in text
        assert "call the accountant" in text
        pending = ai_handler.pending_local_tool_approval_manager.get("chat1")
        assert pending.tool_name == "modify_reminder"

    def test_modify_nonexistent_reminder_rejected(self, ai_handler):
        response = _response([_function_call_item_with_id(
            "modify_reminder", self._modify_args("does-not-exist"), "call_m1"
        )])
        request = AIRequest(user_prompt="שנה", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        text, created = ai_handler._handle_reminder_modify_or_delete_proposal(request, response, "chat1")
        assert created is False
        assert text == REMINDER_ACTION_FAILED_TRY_AGAIN

    def test_modify_single_occurrence_on_one_time_reminder_rejected(self, ai_handler):
        r = self._existing_reminder(ai_handler, recurring=False)
        args = self._modify_args(r["reminder_id"], scope="single_occurrence", occurrence_date_hint=_future_iso(60))
        response = _response([_function_call_item_with_id("modify_reminder", args, "call_m1")])
        request = AIRequest(user_prompt="שנה", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        text, created = ai_handler._handle_reminder_modify_or_delete_proposal(request, response, "chat1")
        assert created is False
        assert text == REMINDER_ACTION_FAILED_TRY_AGAIN

    def test_modify_single_occurrence_missing_date_hint_rejected(self, ai_handler):
        r = self._existing_reminder(ai_handler, recurring=True)
        args = self._modify_args(r["reminder_id"], scope="single_occurrence", occurrence_date_hint=None)
        response = _response([_function_call_item_with_id("modify_reminder", args, "call_m1")])
        request = AIRequest(user_prompt="שנה", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")
        text, created = ai_handler._handle_reminder_modify_or_delete_proposal(request, response, "chat1")
        assert created is False

    def test_delete_whole_series_creates_pending_approval(self, ai_handler):
        r = self._existing_reminder(ai_handler)
        args = {"reminder_id": r["reminder_id"], "scope": "whole_series", "occurrence_date_hint": None}
        response = _response([_function_call_item_with_id("delete_reminder", args, "call_d1")])
        request = AIRequest(user_prompt="מחק את התזכורת", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m1")

        text, created = ai_handler._handle_reminder_modify_or_delete_proposal(request, response, "chat1")

        assert created is True
        assert "מחיקת תזכורת" in text
        pending = ai_handler.pending_local_tool_approval_manager.get("chat1")
        assert pending.tool_name == "delete_reminder"


class TestModifyDeleteResolution:
    def _propose_modify(self, ai_handler, reminder_id, chat_id="chat1", **overrides):
        args = {
            "reminder_id": reminder_id, "scope": "whole_series", "occurrence_date_hint": None,
            "new_message_text": "updated text", "new_due_at": None, "new_recurrence": None,
        }
        args.update(overrides)
        response = _response([_function_call_item_with_id("modify_reminder", args, "call_m1")])
        request = AIRequest(user_prompt="שנה", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id=chat_id, message_id="m1")
        ai_handler._handle_reminder_modify_or_delete_proposal(request, response, chat_id)
        return ai_handler.pending_local_tool_approval_manager.get(chat_id)

    def _propose_delete(self, ai_handler, reminder_id, scope="whole_series", occurrence_date_hint=None, chat_id="chat1"):
        args = {"reminder_id": reminder_id, "scope": scope, "occurrence_date_hint": occurrence_date_hint}
        response = _response([_function_call_item_with_id("delete_reminder", args, "call_d1")])
        request = AIRequest(user_prompt="מחק", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id=chat_id, message_id="m1")
        ai_handler._handle_reminder_modify_or_delete_proposal(request, response, chat_id)
        return ai_handler.pending_local_tool_approval_manager.get(chat_id)

    def test_approve_modify_whole_series_updates_reminder(self, ai_handler, mock_ai_client):
        r = ai_handler.reminder_manager.create_reminder(
            message_text="old text", schedule_type="one_time", one_time_due_at=_future_iso(60),
            recurrence=None, created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        pending = self._propose_modify(ai_handler, r["reminder_id"])
        mock_ai_client.responses.create.return_value = _followup_response("עודכן")
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result.response_text == "עודכן"
        updated = ai_handler.reminder_manager.get_reminder(r["reminder_id"])
        assert updated["message_text"] == "updated text"

    def test_approve_delete_whole_series_cancels_reminder(self, ai_handler, mock_ai_client):
        r = ai_handler.reminder_manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future_iso(60),
            recurrence=None, created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        pending = self._propose_delete(ai_handler, r["reminder_id"])
        mock_ai_client.responses.create.return_value = _followup_response("נמחק")
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result.response_text == "נמחק"
        assert ai_handler.reminder_manager.get_reminder(r["reminder_id"]) is None

    def test_approve_delete_single_occurrence_dispatches_correctly(self, ai_handler, mock_ai_client):
        r = ai_handler.reminder_manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence={
                "interval": 1, "freq": "daily", "weekdays": None, "month_day": None,
                "month_nth_weekday": None, "first_occurrence_at": _future_iso(60),
                "end_condition": "never", "end_count": None, "end_until": None,
            },
            created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        pending = self._propose_delete(
            ai_handler, r["reminder_id"], scope="single_occurrence",
            occurrence_date_hint=_future_iso(60),
        )
        mock_ai_client.responses.create.return_value = _followup_response("דולג")
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", user_obj, "GODFATHER", sender=GODFATHER_PHONE, recipient=None
        )

        assert result.response_text == "דולג"
        # Whole series still active, only the one occurrence was affected.
        assert ai_handler.reminder_manager.get_reminder(r["reminder_id"]) is not None

    def test_admin_can_modify_a_godfather_created_reminder(self, ai_handler, mock_ai_client):
        """FR-011: there is exactly one reminder list - no owner-matching filter
        anywhere in the dispatch path. An ADMIN-role request targeting a
        reminder created by GODFATHER must succeed unmodified."""
        r = ai_handler.reminder_manager.create_reminder(
            message_text="godfather's reminder", schedule_type="one_time",
            one_time_due_at=_future_iso(60), recurrence=None,
            created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        pending = self._propose_modify(ai_handler, r["reminder_id"], new_message_text="admin edited this")
        mock_ai_client.responses.create.return_value = _followup_response("עודכן")
        admin_user = ai_handler.user_manager.get_user(ADMIN_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", admin_user, "ADMIN", sender=ADMIN_PHONE, recipient=None
        )

        assert result.response_text == "עודכן"
        updated = ai_handler.reminder_manager.get_reminder(r["reminder_id"])
        assert updated["message_text"] == "admin edited this"

    def test_admin_can_delete_a_godfather_created_reminder(self, ai_handler, mock_ai_client):
        """FR-011, delete side of the same guarantee."""
        r = ai_handler.reminder_manager.create_reminder(
            message_text="godfather's reminder", schedule_type="one_time",
            one_time_due_at=_future_iso(60), recurrence=None,
            created_by_phone=GODFATHER_PHONE, created_by_role="GODFATHER", delivery_chat_id=f"{GODFATHER_PHONE}@c.us",
        )
        pending = self._propose_delete(ai_handler, r["reminder_id"])
        mock_ai_client.responses.create.return_value = _followup_response("נמחק")
        admin_user = ai_handler.user_manager.get_user(ADMIN_PHONE)
        request = AIRequest(user_prompt="כן", constitution="", max_tokens=500,
                             model="gpt-5.6-luna", chat_id="chat1", message_id="m2")

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, request, "chat1", admin_user, "ADMIN", sender=ADMIN_PHONE, recipient=None
        )

        assert result.response_text == "נמחק"
        assert ai_handler.reminder_manager.get_reminder(r["reminder_id"]) is None
