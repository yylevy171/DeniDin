"""
Regression test for a real production incident (2026-09-13): a single OpenAI
response can carry pending calls of MORE THAN ONE immediate-dispatch local
tool type at once (query_ledger_events, list_reminders, send_progress_update,
react_to_message) - react_to_message is unconditionally attached to every
turn (Feature 084, REQ-084), so it can co-occur with any other tool's call in
the same response. Before the fix, each tool type resolved its own calls via
its own siloed follow-up call, submitting ONLY its own call_id(s) - OpenAI's
Responses API rejects a follow-up outright ("No tool output found for
function call ...") unless EVERY pending call from that response gets an
output, so a response containing e.g. a list_reminders call AND two
react_to_message calls always failed: whichever handler ran first left the
other's call_id(s) unaddressed.

AIHandler._dispatch_all_local_tools is the fix - it collects outputs from
EVERY known tool type present in a response and submits them together in ONE
follow-up. This file tests that method directly (unit tier, real internal
code, only the OpenAI client itself stubbed - CONSTITUTION §V).
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import AIRequest, WhatsAppMessage


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
    handler.green_api_bot.api.request.return_value = SimpleNamespace(code=200)
    return handler


def _request(chat_id="chat1"):
    original_message = WhatsAppMessage(
        message_id="internal-uuid-1", chat_id=chat_id, sender_id="972500000003@c.us",
        sender_name="Test", text_content="hi", timestamp=1000, message_type="textMessage",
        whatsapp_id_message="wamid.current",
    )
    return AIRequest(
        user_prompt="שאלה", constitution="", max_tokens=500, model="gpt-5.6-luna",
        chat_id=chat_id, message_id="m1", original_message=original_message,
    )


class TestCombinedDispatchAcrossToolTypes:
    """The exact shape that broke live: list_reminders + 2x react_to_message
    in one response."""

    def test_list_reminders_and_two_reactions_resolve_in_one_followup(self, ai_handler, mock_ai_client):
        response = _response([
            _function_call_item("list_reminders", {}, call_id="call_reminders"),
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": "wamid.a"}, call_id="call_react_1"),
            _function_call_item("react_to_message", {"emoji": "✅", "message_id": "wamid.b"}, call_id="call_react_2"),
        ], resp_id="resp_multi")
        mock_ai_client.responses.create.return_value = _followup_response()

        result = ai_handler._dispatch_all_local_tools(
            _request(), response, tools=[], effective_chat_id="chat1",
        )

        assert result is not None
        # Exactly ONE combined follow-up call was made (not one per tool type).
        assert mock_ai_client.responses.create.call_count == 1
        sent_kwargs = mock_ai_client.responses.create.call_args.kwargs
        sent_call_ids = {item["call_id"] for item in sent_kwargs["input"]}
        assert sent_call_ids == {"call_reminders", "call_react_1", "call_react_2"}
        assert sent_kwargs["previous_response_id"] == "resp_multi"

    def test_query_ledger_events_and_send_progress_update_resolve_together(self, ai_handler, mock_ai_client):
        ai_handler.ledger_event_manager.query_events = Mock(return_value=[])
        response = _response([
            _function_call_item(
                "query_ledger_events", {"criteria": [{"text": "X", "hint": "identity"}]}, call_id="call_ledger",
            ),
            _function_call_item("send_progress_update", {"text": "בודק..."}, call_id="call_progress"),
        ], resp_id="resp_multi_2")
        mock_ai_client.responses.create.return_value = _followup_response()

        result = ai_handler._dispatch_all_local_tools(
            _request(), response, tools=[], effective_chat_id="chat1",
        )

        assert result is not None
        assert mock_ai_client.responses.create.call_count == 1
        sent_kwargs = mock_ai_client.responses.create.call_args.kwargs
        sent_call_ids = {item["call_id"] for item in sent_kwargs["input"]}
        assert sent_call_ids == {"call_ledger", "call_progress"}

    def test_no_local_tool_calls_returns_none(self, ai_handler, mock_ai_client):
        response = _response([], resp_id="resp_empty", text="just a plain reply")
        result = ai_handler._dispatch_all_local_tools(
            _request(), response, tools=[], effective_chat_id="chat1",
        )
        assert result is None
        mock_ai_client.responses.create.assert_not_called()

    def test_single_tool_type_still_works_through_combined_dispatch(self, ai_handler, mock_ai_client):
        response = _response([
            _function_call_item("react_to_message", {"emoji": "👍", "message_id": "wamid.a"}, call_id="call_react_1"),
        ], resp_id="resp_single")
        mock_ai_client.responses.create.return_value = _followup_response()

        result = ai_handler._dispatch_all_local_tools(
            _request(), response, tools=[], effective_chat_id="chat1",
        )

        assert result is not None
        sent_kwargs = mock_ai_client.responses.create.call_args.kwargs
        sent_call_ids = {item["call_id"] for item in sent_kwargs["input"]}
        assert sent_call_ids == {"call_react_1"}
