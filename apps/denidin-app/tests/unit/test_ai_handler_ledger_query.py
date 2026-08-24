"""
Unit tests for Feature 044's ledger-querying wiring in AIHandler: RBAC gating
of the query_ledger_events tool, and its multi-call dispatch (research.md
Decision 10 - deliberately NOT list_reminders' single-call pattern, since
several query_ledger_events calls in one turn are expected and safe,
read-only, unlike capture_ledger_event's bugfix-018 single-call rule).

Covers tasks.md T005a/T006a. Real conversational accuracy (does the model
call the tool at the right time, with sensible arguments) is NOT
unit-testable - that needs the real OpenAI API and belongs in tests/billed/.
What IS covered here: given a response that already contains one or more
query_ledger_events calls (constructed directly, no real API), does
AIHandler correctly dispatch to a REAL LedgerEventManager.query_events and
report every call's result back - only the OpenAI client is a stand-in
(external service, per CONSTITUTION SS I). Mirrors
test_ai_handler_reminders.py's established Mock(spec=AppConfiguration)
pattern.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler, LEDGER_QUERY_AUTHORIZED_ROLES
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.models.user import Role


def _function_call_item(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _response(output, resp_id="resp_1", text=""):
    return SimpleNamespace(
        id=resp_id, output=output, output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
    )


def _followup_response(text="נמצאו התוצאות", resp_id="resp_followup_1"):
    return SimpleNamespace(
        id=resp_id, output=[], output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=10, input_tokens=6, output_tokens=4),
    )


NO_FILTER_ARGS = {
    "client_name": None, "date_from": None, "date_to": None,
    "amount_min": None, "amount_max": None, "source_type": None,
    "event_subtype": None, "free_text": None,
}


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


def _request(chat_id="chat1"):
    return AIRequest(user_prompt="שאלה", constitution="", max_tokens=500,
                      model="gpt-5.6-luna", chat_id=chat_id, message_id="m1")


class TestToolAttachment:
    def test_godfather_gets_the_query_tool(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._build_ledger_query_tools(user_obj)
        assert {t["name"] for t in tools} == {"query_ledger_events"}

    def test_admin_gets_the_query_tool(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(ADMIN_PHONE)
        tools = ai_handler._build_ledger_query_tools(user_obj)
        assert {t["name"] for t in tools} == {"query_ledger_events"}

    def test_client_does_not_get_the_query_tool(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        assert ai_handler._build_ledger_query_tools(user_obj) == []

    def test_blocked_does_not_get_the_query_tool(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(BLOCKED_PHONE)
        assert ai_handler._build_ledger_query_tools(user_obj) == []

    def test_none_user_does_not_get_tool(self, ai_handler):
        assert ai_handler._build_ledger_query_tools(None) == []

    def test_assemble_tools_includes_query_ledger_events_for_godfather(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1")
        names = [t.get("name") for t in tools]
        assert "query_ledger_events" in names

    def test_assemble_tools_excludes_query_ledger_events_for_client(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1")
        names = [t.get("name") for t in (tools or [])]
        assert "query_ledger_events" not in names

    def test_authorized_roles_are_exactly_godfather_and_admin(self):
        assert set(LEDGER_QUERY_AUTHORIZED_ROLES) == {Role.GODFATHER, Role.ADMIN}

    def test_authorized_roles_is_its_own_distinct_constant(self):
        """Not accidentally the SAME tuple object as the other RBAC constants
        - an independent future RBAC change to one must never silently
        affect this one."""
        from src.handlers import ai_handler as ai_handler_module
        assert LEDGER_QUERY_AUTHORIZED_ROLES is not ai_handler_module.MORNING_MCP_AUTHORIZED_ROLES
        assert LEDGER_QUERY_AUTHORIZED_ROLES is not ai_handler_module.REMINDER_AUTHORIZED_ROLES


class TestSingleCallDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response([SimpleNamespace(type="message")], text="hi")
        assert ai_handler._handle_query_ledger_events(_request(), response, tools=None) is None

    def test_single_call_dispatches_and_returns_followup(self, ai_handler, mock_ai_client):
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "דוד כהן",
                "payer_name": None, "description": "תביעה", "amount": "5,000₪",
                "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
                "txn_date": None, "vat_status": "לא צוין", "trigger_condition": None,
                "reference_hint": None, "agreement_label": "תיק", "component_label": "בסיס",
            },
            message_id="m1", message_timestamp=1753693200,
        )
        args = {**NO_FILTER_ARGS, "client_name": "דוד כהן"}
        response = _response([_function_call_item("query_ledger_events", args, "call_q1")])
        mock_ai_client.responses.create.return_value = _followup_response("נמצא סכום 5,000")

        result = ai_handler._handle_query_ledger_events(_request(), response, tools=None)

        assert result is not None
        assert result.output_text == "נמצא סכום 5,000"
        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert call_kwargs["previous_response_id"] == "resp_1"
        assert len(call_kwargs["input"]) == 1
        assert call_kwargs["input"][0]["call_id"] == "call_q1"
        payload = json.loads(call_kwargs["input"][0]["output"])
        assert payload["count"] == 1

    def test_vague_query_guard_shape_passed_through_unmodified(self, ai_handler, mock_ai_client):
        response = _response([_function_call_item("query_ledger_events", dict(NO_FILTER_ARGS), "call_q1")])
        mock_ai_client.responses.create.return_value = _followup_response()

        ai_handler._handle_query_ledger_events(_request(), response, tools=None)

        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        payload = json.loads(call_kwargs["input"][0]["output"])
        assert payload["error"] == "no_search_criteria"

    def test_followup_failure_returns_none(self, ai_handler, mock_ai_client):
        response = _response([_function_call_item("query_ledger_events", dict(NO_FILTER_ARGS), "call_q1")])
        mock_ai_client.responses.create.side_effect = Exception("network error")
        assert ai_handler._handle_query_ledger_events(_request(), response, tools=None) is None


class TestMultiCallDispatch:
    """research.md Decision 10: a turn may contain SEVERAL query_ledger_events
    calls (e.g. 'client A or client B') - deliberately the OPPOSITE of
    capture_ledger_event's bugfix-018 whole-turn rejection, since nothing is
    written here."""

    def test_two_calls_both_execute_and_both_reported_in_one_followup(self, ai_handler, mock_ai_client):
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "דוד כהן",
                "payer_name": None, "description": "תביעה", "amount": "5,000₪",
                "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
                "txn_date": None, "vat_status": "לא צוין", "trigger_condition": None,
                "reference_hint": None, "agreement_label": "תיק", "component_label": "בסיס",
            },
            message_id="m1", message_timestamp=1753693200,
        )
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "שרה לוי",
                "payer_name": None, "description": "ייעוץ", "amount": "3,000₪",
                "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
                "txn_date": None, "vat_status": "לא צוין", "trigger_condition": None,
                "reference_hint": None, "agreement_label": "תיק", "component_label": "בסיס",
            },
            message_id="m2", message_timestamp=1753693200,
        )
        args_a = {**NO_FILTER_ARGS, "client_name": "דוד כהן"}
        args_b = {**NO_FILTER_ARGS, "client_name": "שרה לוי"}
        response = _response([
            _function_call_item("query_ledger_events", args_a, "call_a"),
            _function_call_item("query_ledger_events", args_b, "call_b"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response("שני לקוחות נמצאו")

        result = ai_handler._handle_query_ledger_events(_request(), response, tools=None)

        assert result is not None
        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert len(call_kwargs["input"]) == 2
        by_call_id = {item["call_id"]: json.loads(item["output"]) for item in call_kwargs["input"]}
        assert by_call_id["call_a"]["count"] == 1
        assert by_call_id["call_a"]["matches"][0]["client_name"] == "דוד כהן"
        assert by_call_id["call_b"]["count"] == 1
        assert by_call_id["call_b"]["matches"][0]["client_name"] == "שרה לוי"

    def test_one_unparseable_call_does_not_poison_a_second_well_formed_call(self, ai_handler, mock_ai_client):
        """The deliberate OPPOSITE of capture_ledger_event's bugfix-018
        whole-turn rejection - per-call failure isolation only."""
        good_args = {**NO_FILTER_ARGS, "source_type": "הסכם"}
        response = _response([
            SimpleNamespace(type="function_call", name="query_ledger_events",
                             arguments="{not valid json", call_id="call_bad"),
            _function_call_item("query_ledger_events", good_args, "call_good"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response("תוצאה")

        ai_handler._handle_query_ledger_events(_request(), response, tools=None)

        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        by_call_id = {item["call_id"]: json.loads(item["output"]) for item in call_kwargs["input"]}
        assert len(by_call_id) == 2
        assert by_call_id["call_bad"]["status"] == "error"
        # The well-formed call still executed normally (a real matches/count
        # shape, not swallowed by the other call's failure).
        assert "matches" in by_call_id["call_good"] or "error" not in by_call_id["call_good"]
