"""
Unit tests for Feature 084's react_to_message wiring in AIHandler:
- unconditional tool attachment (every role, not RBAC-gated)
- the message_id resolution fallback chain (data-model.md)
- single/multi-call dispatch against a stubbed send_reaction

Real conversational accuracy (does the model call the tool at the right time,
with a sensible emoji) is NOT unit-testable - that belongs to the
reaction-judgment-tuning harness (contracts/reaction-judgment-tuning.md), not
this file. What IS covered here: given a response that already contains one
or more react_to_message calls, does AIHandler correctly resolve the target
message and dispatch to send_reaction (stubbed - permitted at the unit tier,
CONSTITUTION §V), reporting every call's result back. Mirrors
test_ai_handler_ledger_query.py's established pattern.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.handlers.ai_handler import AIHandler, REACT_TO_MESSAGE_TOOL
from src.models.config import AppConfiguration
from src.models.message import AIRequest, WhatsAppMessage
from src.models.user import Role


def _function_call_item(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _response(output, resp_id="resp_1", text=""):
    return SimpleNamespace(
        id=resp_id, output=output, output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
    )


def _followup_response(text="בסדר", resp_id="resp_followup_1"):
    return SimpleNamespace(
        id=resp_id, output=[], output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=10, input_tokens=6, output_tokens=4),
    )


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
    handler = AIHandler(mock_ai_client, mock_config)
    handler.green_api_bot = Mock()  # stands in for the live bot
    return handler


GODFATHER_PHONE = '972500000002'
ADMIN_PHONE = '972500000001'
CLIENT_PHONE = '972500000003'
BLOCKED_PHONE = '972500000099'


def _request(chat_id="chat1", whatsapp_id_message="wamid.current"):
    original_message = WhatsAppMessage(
        message_id="internal-uuid-1", chat_id=chat_id, sender_id="972500000003@c.us",
        sender_name="Test", text_content="hi", timestamp=1000, message_type="textMessage",
        whatsapp_id_message=whatsapp_id_message,
    )
    return AIRequest(
        user_prompt="שאלה", constitution="", max_tokens=500, model="gpt-5.6-luna",
        chat_id=chat_id, message_id="m1", original_message=original_message,
    )


class TestToolAttachment:
    """react_to_message is attached unconditionally - unlike every other tool
    in this file, no RBAC gate applies."""

    def _user(self, role):
        return SimpleNamespace(role=role)

    def test_client_gets_the_tool(self, ai_handler):
        tools = ai_handler._assemble_tools(self._user(Role.CLIENT), "corr1")
        assert any(t.get("name") == "react_to_message" for t in tools)

    def test_godfather_gets_the_tool(self, ai_handler):
        tools = ai_handler._assemble_tools(self._user(Role.GODFATHER), "corr1")
        assert any(t.get("name") == "react_to_message" for t in tools)

    def test_none_user_still_gets_the_tool(self, ai_handler):
        tools = ai_handler._assemble_tools(None, "corr1")
        assert any(t.get("name") == "react_to_message" for t in tools)

    def test_schema_is_strict_with_required_emoji_and_message_id(self):
        assert REACT_TO_MESSAGE_TOOL["strict"] is True
        assert REACT_TO_MESSAGE_TOOL["parameters"]["required"] == ["emoji", "message_id"]


class TestMessageIdResolutionFallbackChain:
    """data-model.md: explicit arg -> Session.active_document_message_id ->
    current turn's Message.whatsapp_id_message."""

    def test_explicit_message_id_wins_over_everything(self, ai_handler):
        request = _request(whatsapp_id_message="wamid.current")
        ai_handler.session_manager.get_session(request.chat_id).active_document_message_id = "wamid.doc"
        target = ai_handler._resolve_react_to_message_target(request, request.chat_id, "wamid.explicit")
        assert target == "wamid.explicit"

    def test_active_document_message_id_wins_when_no_explicit_arg(self, ai_handler):
        request = _request(whatsapp_id_message="wamid.current")
        session = ai_handler.session_manager.get_session(request.chat_id)
        session.active_document_message_id = "wamid.doc"
        ai_handler.session_manager._save_session(session)
        target = ai_handler._resolve_react_to_message_target(request, request.chat_id, None)
        assert target == "wamid.doc"

    def test_falls_back_to_current_turn_whatsapp_id_message(self, ai_handler):
        request = _request(whatsapp_id_message="wamid.current")
        target = ai_handler._resolve_react_to_message_target(request, request.chat_id, None)
        assert target == "wamid.current"

    def test_returns_none_when_nothing_resolves(self, ai_handler):
        request = _request(whatsapp_id_message=None)
        target = ai_handler._resolve_react_to_message_target(request, request.chat_id, None)
        assert target is None


class TestSingleCallDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        assert ai_handler._handle_react_to_message(_request(), response, None) is None

    def test_current_message_reaction_calls_send_reaction_with_resolved_target(
        self, ai_handler, mock_ai_client
    ):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "🙏", "message_id": None}, "call_1"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction", return_value=True) as mock_send:
            result = ai_handler._handle_react_to_message(request, response, None, "chat1")

        mock_send.assert_called_once_with(ai_handler.green_api_bot, "chat1", "wamid.current", "🙏")
        assert result is not None
        sent_output = mock_ai_client.responses.create.call_args.kwargs["input"]
        assert json.loads(sent_output[0]["output"]) == {"status": "ok"}

    def test_explicit_message_id_flip_calls_send_reaction_with_that_id(self, ai_handler, mock_ai_client):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "✅", "message_id": "wamid.earlier"}, "call_1"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction", return_value=True) as mock_send:
            ai_handler._handle_react_to_message(request, response, None, "chat1")

        mock_send.assert_called_once_with(ai_handler.green_api_bot, "chat1", "wamid.earlier", "✅")

    def test_send_reaction_failure_reports_failed_status_never_raises(self, ai_handler, mock_ai_client):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": None}, "call_1"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction", return_value=False):
            result = ai_handler._handle_react_to_message(request, response, None, "chat1")

        assert result is not None
        sent_output = mock_ai_client.responses.create.call_args.kwargs["input"]
        assert json.loads(sent_output[0]["output"]) == {"status": "failed"}

    def test_no_green_api_bot_reports_failed_never_raises(self, ai_handler, mock_ai_client):
        ai_handler.green_api_bot = None
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": None}, "call_1"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction") as mock_send:
            result = ai_handler._handle_react_to_message(request, response, None, "chat1")

        mock_send.assert_not_called()
        sent_output = mock_ai_client.responses.create.call_args.kwargs["input"]
        assert json.loads(sent_output[0]["output"]) == {"status": "failed"}

    def test_followup_failure_returns_none(self, ai_handler, mock_ai_client):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": None}, "call_1"),
        ])
        mock_ai_client.responses.create.side_effect = RuntimeError("api down")

        with patch("src.handlers.ai_handler.send_reaction", return_value=True):
            result = ai_handler._handle_react_to_message(request, response, None, "chat1")

        assert result is None


class TestMultiCallDispatch:
    """A turn may legitimately call react_to_message more than once (e.g. react
    to the current message AND flip an earlier one) - extract_all_function_calls,
    not the single-call pattern."""

    def test_two_calls_both_execute_and_both_reported_in_one_followup(self, ai_handler, mock_ai_client):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": None}, "call_1"),
            _function_call_item("react_to_message", {"emoji": "✅", "message_id": "wamid.earlier"}, "call_2"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction", return_value=True) as mock_send:
            ai_handler._handle_react_to_message(request, response, None, "chat1")

        assert mock_send.call_count == 2
        sent_output = mock_ai_client.responses.create.call_args.kwargs["input"]
        assert len(sent_output) == 2
        assert {item["call_id"] for item in sent_output} == {"call_1", "call_2"}

    def test_one_unparseable_call_does_not_poison_a_second_well_formed_call(
        self, ai_handler, mock_ai_client
    ):
        request = _request(chat_id="chat1", whatsapp_id_message="wamid.current")
        response = _response(output=[
            SimpleNamespace(type="function_call", name="react_to_message", arguments="{bad json", call_id="call_1"),
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": None}, "call_2"),
        ])
        mock_ai_client.responses.create.return_value = _followup_response()

        with patch("src.handlers.ai_handler.send_reaction", return_value=True) as mock_send:
            ai_handler._handle_react_to_message(request, response, None, "chat1")

        mock_send.assert_called_once()
        sent_output = mock_ai_client.responses.create.call_args.kwargs["input"]
        payloads = {item["call_id"]: json.loads(item["output"]) for item in sent_output}
        assert payloads["call_1"]["status"] == "failed"
        assert payloads["call_2"]["status"] == "ok"
