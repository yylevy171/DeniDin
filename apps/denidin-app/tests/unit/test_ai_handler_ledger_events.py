"""
Unit tests for Ledger Event Recognition's function-call extraction (runtime_constitution.md).

Tests the pure `extract_function_call` helper in src.handlers.ai_handler - it operates
purely on a Responses API `response.output` list, no OpenAI/filesystem access. Shared by
the text path (AIHandler._finalize_response) and the image path (ImageExtractor).

Real classification/extraction accuracy (does the model call the tool at the right time,
with the right fields) is NOT unit-testable - that needs the real OpenAI API and is covered
by tests/billed/test_ledger_event_capture_billed.py (text flow) and
tests/expensive/test_ledger_event_capture_e2e.py (image flow) instead.
"""
import json
from types import SimpleNamespace

from src.handlers.ai_handler import (
    extract_function_call, extract_function_call_id, extract_all_function_calls, LEDGER_EVENT_TOOL
)


def _function_call_item(name, arguments, call_id=None):
    return SimpleNamespace(type="function_call", name=name, arguments=arguments, call_id=call_id)


def _other_item(item_type="message"):
    return SimpleNamespace(type=item_type)


def _response(output):
    return SimpleNamespace(output=output)


class TestExtractFunctionCall:

    def test_no_output_items_returns_none(self):
        assert extract_function_call(_response([]), "capture_ledger_event") is None

    def test_output_is_none_returns_none(self):
        """A response with no `.output` attribute at all (getattr default) must not raise."""
        assert extract_function_call(SimpleNamespace(), "capture_ledger_event") is None

    def test_matching_function_call_returns_parsed_arguments(self):
        args = {"source_type": "הסכם", "event_subtype": "יצירה", "client_name": "דני כהן"}
        response = _response([_function_call_item("capture_ledger_event", json.dumps(args))])

        result = extract_function_call(response, "capture_ledger_event")

        assert result == args

    def test_non_matching_tool_name_ignored(self):
        response = _response([_function_call_item("some_other_tool", '{"x": 1}')])
        assert extract_function_call(response, "capture_ledger_event") is None

    def test_non_function_call_items_ignored(self):
        response = _response([_other_item("message"), _other_item("mcp_call")])
        assert extract_function_call(response, "capture_ledger_event") is None

    def test_finds_the_right_item_among_others(self):
        args = {"source_type": "בנק"}
        response = _response([
            _other_item("message"),
            _function_call_item("capture_ledger_event", json.dumps(args)),
        ])

        assert extract_function_call(response, "capture_ledger_event") == args

    def test_malformed_arguments_json_returns_none_not_raises(self):
        response = _response([_function_call_item("capture_ledger_event", "{not valid json")])
        assert extract_function_call(response, "capture_ledger_event") is None

    def test_tool_schema_name_matches_what_finalize_response_uses(self):
        """Guards against the schema's own "name" field drifting out of sync with the
        string AIHandler/ImageExtractor actually pass to extract_function_call."""
        assert LEDGER_EVENT_TOOL["name"] == "capture_ledger_event"

    def test_tool_schema_is_strict_with_all_fields_required(self):
        """OpenAI's strict function-calling mode requires every property to be listed
        in `required` (nullable ones just allow null) - a drift here would silently
        stop being enforced server-side."""
        params = LEDGER_EVENT_TOOL["parameters"]
        assert LEDGER_EVENT_TOOL["strict"] is True
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"].keys())


class TestExtractFunctionCallId:
    """extract_function_call_id - the companion helper needed for the ledger-event
    follow-up round-trip (reasoning models emit a function_call OR a message, never
    both in one turn, so AIHandler._finalize_response must report the call's result
    back via previous_response_id + function_call_output to get the real reply)."""

    def test_no_output_items_returns_none(self):
        assert extract_function_call_id(_response([]), "capture_ledger_event") is None

    def test_output_is_none_returns_none(self):
        assert extract_function_call_id(SimpleNamespace(), "capture_ledger_event") is None

    def test_matching_function_call_returns_call_id(self):
        response = _response([
            _function_call_item("capture_ledger_event", "{}", call_id="call_abc123"),
        ])

        assert extract_function_call_id(response, "capture_ledger_event") == "call_abc123"

    def test_non_matching_tool_name_ignored(self):
        response = _response([
            _function_call_item("some_other_tool", "{}", call_id="call_abc123"),
        ])
        assert extract_function_call_id(response, "capture_ledger_event") is None

    def test_finds_the_right_item_among_others(self):
        response = _response([
            _other_item("message"),
            _function_call_item("capture_ledger_event", "{}", call_id="call_xyz789"),
        ])

        assert extract_function_call_id(response, "capture_ledger_event") == "call_xyz789"


class TestExtractAllFunctionCalls:
    """extract_all_function_calls - needed because a single turn can legitimately contain
    MORE THAN ONE capture_ledger_event call (e.g. several hourly work-log entries in one
    message - the constitution says never aggregate them). A real godfather/Morning-MCP
    conversation (2026-07-28) had two capture_ledger_event calls in one turn; resolving
    only the first via extract_function_call/extract_function_call_id got the whole
    follow-up round-trip rejected by OpenAI ("No tool output found for function call
    ...") since the second call's output was never supplied."""

    def test_no_output_items_returns_empty_list(self):
        assert extract_all_function_calls(_response([]), "capture_ledger_event") == []

    def test_output_is_none_returns_empty_list(self):
        assert extract_all_function_calls(SimpleNamespace(), "capture_ledger_event") == []

    def test_single_matching_call_returns_one_item(self):
        args = {"source_type": "הסכם", "event_subtype": "יצירה"}
        response = _response([
            _function_call_item("capture_ledger_event", json.dumps(args), call_id="call_1"),
        ])

        result = extract_all_function_calls(response, "capture_ledger_event")

        assert result == [{"arguments": args, "call_id": "call_1"}]

    def test_two_matching_calls_returns_both_in_order(self):
        args1 = {"source_type": "הסכם", "event_subtype": "יצירה", "hours": "3"}
        args2 = {"source_type": "הסכם", "event_subtype": "יצירה", "hours": "2"}
        response = _response([
            _function_call_item("capture_ledger_event", json.dumps(args1), call_id="call_1"),
            _function_call_item("capture_ledger_event", json.dumps(args2), call_id="call_2"),
        ])

        result = extract_all_function_calls(response, "capture_ledger_event")

        assert result == [
            {"arguments": args1, "call_id": "call_1"},
            {"arguments": args2, "call_id": "call_2"},
        ]

    def test_non_matching_tool_calls_ignored(self):
        response = _response([
            _function_call_item("some_other_tool", "{}", call_id="call_x"),
            _function_call_item("capture_ledger_event", "{}", call_id="call_1"),
        ])

        result = extract_all_function_calls(response, "capture_ledger_event")

        assert result == [{"arguments": {}, "call_id": "call_1"}]

    def test_malformed_arguments_skipped_but_others_kept(self):
        args = {"source_type": "בנק"}
        response = _response([
            _function_call_item("capture_ledger_event", "{not valid json", call_id="call_bad"),
            _function_call_item("capture_ledger_event", json.dumps(args), call_id="call_good"),
        ])

        result = extract_all_function_calls(response, "capture_ledger_event")

        assert result == [{"arguments": args, "call_id": "call_good"}]
