"""
Unit tests for Ledger Event Recognition's function-call extraction (runtime_constitution.md)
and, since Feature 033, LedgerEventManager wiring in AIHandler._handle_ledger_event_capture/
_finalize_response.

Real classification/extraction accuracy (does the model call the tool at the right time,
with the right fields) is NOT unit-testable - that needs the real OpenAI API and is covered
by tests/billed/test_ledger_event_capture_billed.py (text flow) and
tests/expensive/test_ledger_event_capture_e2e.py (image flow) instead. What IS covered here:
given a response that already contains capture_ledger_event call(s) (constructed directly,
no real API), does AIHandler correctly persist them via a REAL LedgerEventManager and thread
the resulting event_id(s) into the stored message - only the OpenAI client itself is a
stand-in (external service, per CONSTITUTION SS I's testing guidance), never any internal
component.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import (
    AIHandler, extract_function_call, extract_function_call_id, extract_all_function_calls,
    LEDGER_EVENT_TOOL
)
from src.models.config import AppConfiguration
from src.models.message import AIRequest


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


class TestLedgerEventToolBankPaymentFields:
    """Phase 11 (tasks.md, 043-production-data-setup-tooling), T027a/T027b.

    Gap: bugfix-028/038 (A2/A3/A3b) added payment_date/payment_method/
    bank_number/bank_branch/bank_account/transaction_reference as arguments on
    the Morning invoicing tools (create_combo_document et al.), extracted from
    the same bank-deposit screenshot LEDGER_EVENT_TOOL captures - but
    LEDGER_EVENT_TOOL itself never mirrored them, so the ledger's own
    בנק-source-type record has no way to state where the money came from.
    payment_date is NOT duplicated here - txn_date (already on every component)
    already serves that role for a בנק event, see its own description.

    Revised same-day (2026-08-16, real-data-grounded follow-up review, human
    decision): payment_method/transaction_reference REMOVED - no payment-app
    support exists yet, and payment_method was redundant with bank_number/
    bank_branch/bank_account's own presence already implying a bank transfer.
    Only the three bank-detail fields remain. See data-model.md §1b.

    Field-level placement: call-level (like source_type/payer_name), not
    per-component - a single בנק capture describes one underlying transfer,
    never a different bank account per component (mirrors where bugfix-028
    itself placed the equivalent arguments: top-level tool args, not per
    invoice line).
    """

    NEW_FIELDS = {"bank_number", "bank_branch", "bank_account"}

    def test_all_three_fields_present_in_schema_properties(self):
        properties = LEDGER_EVENT_TOOL["parameters"]["properties"]
        assert self.NEW_FIELDS <= set(properties.keys())

    def test_all_three_fields_are_nullable_strings(self):
        """Never a bare 'string' type - always applicable-but-unstated (ask the
        user) vs. genuinely not applicable (a הסכם event) must both be
        representable, same convention as payer_name/agreement_label."""
        properties = LEDGER_EVENT_TOOL["parameters"]["properties"]
        for field in self.NEW_FIELDS:
            assert properties[field]["type"] == ["string", "null"], (
                f"{field} must be a nullable string, matching payer_name's convention"
            )

    def test_all_three_fields_have_non_empty_descriptions(self):
        properties = LEDGER_EVENT_TOOL["parameters"]["properties"]
        for field in self.NEW_FIELDS:
            assert properties[field].get("description"), f"{field} needs a real description"

    def test_call_level_not_nested_in_component_items(self):
        """Placement check (see class docstring): these three must live on the
        call's own top-level properties, never inside components.items - a
        single בנק capture has one bank account, not one per component."""
        properties = LEDGER_EVENT_TOOL["parameters"]["properties"]
        component_properties = properties["components"]["items"]["properties"]
        assert self.NEW_FIELDS.isdisjoint(component_properties.keys())

    def test_payment_method_and_transaction_reference_removed(self):
        """Reversed in the same-day follow-up review (2026-08-16) - see class
        docstring. Locks the reversal in against silent re-addition."""
        properties = LEDGER_EVENT_TOOL["parameters"]["properties"]
        assert "payment_method" not in properties
        assert "transaction_reference" not in properties


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

    def test_malformed_arguments_kept_as_none_not_dropped(self):
        """bugfix-018: a call whose arguments fail to parse (most often a
        truncated response from hitting max_output_tokens) must NOT be dropped
        - OpenAI still considers its call_id pending regardless of whether we
        could parse it, so silently discarding it here left a follow-up
        submission missing that call_id's output, which OpenAI's real API
        rejects with 400 ("No tool output found for function call ..."),
        which in turn left the user with a silently empty reply (the actual
        2026-07-30 incident, req_0f4656c9bd90)."""
        args = {"source_type": "בנק"}
        response = _response([
            _function_call_item("capture_ledger_event", "{not valid json", call_id="call_bad"),
            _function_call_item("capture_ledger_event", json.dumps(args), call_id="call_good"),
        ])

        result = extract_all_function_calls(response, "capture_ledger_event")

        assert result == [
            {"arguments": None, "call_id": "call_bad"},
            {"arguments": args, "call_id": "call_good"},
        ]


# 2026-07-30 (REQ-DATA-004's components-array redesign): agreement-level fields stay
# top-level, per-component fields (description/amount/percent/.../component_label)
# move into a `components` list - one call now normally carries ALL of one
# agreement's components, instead of the model making N separate calls.
SAMPLE_EVENT = {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "ישראל ישראלי",
    "payer_name": None,
    "agreement_label": "תיק בדיקה",
    "replaces_hint": None,
    "reference_hint": None,
    "raw_message_excerpt": "ישראל ישראלי 5,000₪ כתב הגנה",
    "component_count": 1,
    "components": [
        {
            "component_label": "בסיס",
            "description": "כתב הגנה",
            "amount": "5,000₪",
            "percent": None,
            "percent_base": None,
            "hours": None,
            "hourly_rate": None,
            "txn_date": None,
            "vat_status": "לא צוין",
            "notes": None,
        },
    ],
}


def _with_component_override(event, **component_overrides):
    """Returns a copy of `event` with its single component's fields overridden -
    convenience for tests that used to override top-level fields like `amount`
    before the components-array redesign."""
    new_event = dict(event)
    new_event["components"] = [dict(event["components"][0], **component_overrides)]
    return new_event


def _ledger_call_response(events, resp_id="resp_original_1"):
    """A response whose .output contains one function_call item per event dict."""
    items = [
        _function_call_item("capture_ledger_event", json.dumps(event), call_id=f"call_{i}")
        for i, event in enumerate(events)
    ]
    return SimpleNamespace(
        id=resp_id, output=items, output_text="", model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
    )


def _followup_response(text="הרשומה נקלטה", input_tokens=10, output_tokens=5, resp_id="resp_followup_1"):
    return SimpleNamespace(
        id=resp_id,
        output_text=text,
        output=[],
        model="gpt-5.6-luna",
        usage=SimpleNamespace(
            total_tokens=input_tokens + output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )


@pytest.fixture
def mock_config(tmp_path):
    """Mirrors the established Mock(spec=AppConfiguration) pattern used by
    test_ai_handler_retry.py - config itself and the AI client are the only
    stand-ins (external-service/data-holder), LedgerEventManager/SessionManager
    stay real, isolated to tmp_path."""
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
        'longterm': {'enabled': False}
    }
    config.user_roles = {}
    config.godfather_phone = None
    return config


@pytest.fixture
def mock_ai_client():
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_ai_client):
    return AIHandler(mock_ai_client, mock_config)


class TestCaptureLedgerEventsFromText:
    """Regression guard (found 2026-07-30): capture_ledger_event_from_text (the
    image path's classification call) used to call the single-result
    extract_function_call, silently dropping every ledger-event component
    after the first whenever a document image genuinely warranted more than
    one (e.g. a multi-stage/conditional fee agreement). Renamed to the plural
    capture_ledger_events_from_text, using extract_all_function_calls - same
    fix already proven correct for the text path (TestExtractAllFunctionCalls
    above)."""

    def test_empty_text_returns_empty_list(self, ai_handler):
        assert ai_handler.capture_ledger_events_from_text("") == []

    def test_single_call_returns_list_of_one(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _ledger_call_response([SAMPLE_EVENT])

        result = ai_handler.capture_ledger_events_from_text("some extracted document text")

        assert result == [SAMPLE_EVENT]

    def test_multiple_calls_all_returned_not_just_the_first(self, ai_handler, mock_ai_client):
        event2 = _with_component_override(SAMPLE_EVENT, amount="4,000₪")
        event3 = _with_component_override(SAMPLE_EVENT, amount="8,000₪")
        mock_ai_client.responses.create.return_value = _ledger_call_response(
            [SAMPLE_EVENT, event2, event3]
        )

        result = ai_handler.capture_ledger_events_from_text("a multi-stage fee agreement")

        assert result == [SAMPLE_EVENT, event2, event3]

    def test_no_call_returns_empty_list(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response()

        result = ai_handler.capture_ledger_events_from_text("ordinary document text")

        assert result == []


class TestCaptureLedgerEventsFromTextRetry:
    """REQ-DATA-008 (added 2026-08-02, real billed incident 2026-07-31): a call
    that reports source_type/etc. but an empty components array (or a
    component_count mismatch) is invalid - capture_ledger_events_from_text must
    retry once with corrective feedback before giving up. See spec.md's fifth
    addendum for the real failure this guards against (Mor ben-Shaya 6-component
    test: ledger_events_captured=1, components=[], 0 persisted, 0 errors)."""

    def test_complete_first_response_does_not_retry(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _ledger_call_response([SAMPLE_EVENT])

        result = ai_handler.capture_ledger_events_from_text("a clean single-component agreement")

        assert result == [SAMPLE_EVENT]
        assert mock_ai_client.responses.create.call_count == 1

    def test_empty_components_triggers_one_retry_and_uses_retry_result(
        self, ai_handler, mock_ai_client
    ):
        incomplete = dict(SAMPLE_EVENT, component_count=0, components=[])
        mock_ai_client.responses.create.side_effect = [
            _ledger_call_response([incomplete], resp_id="resp_incomplete"),
            _ledger_call_response([SAMPLE_EVENT], resp_id="resp_retry_complete"),
        ]

        result = ai_handler.capture_ledger_events_from_text("a 6-component agreement image text")

        assert result == [SAMPLE_EVENT]
        assert mock_ai_client.responses.create.call_count == 2
        retry_call_kwargs = mock_ai_client.responses.create.call_args_list[1].kwargs
        retry_messages = [m["content"] for m in retry_call_kwargs["input"]]
        assert any("zero components" in m or "component_count" in m for m in retry_messages), (
            "the retry call must include an explicit corrective message naming the defect"
        )

    def test_component_count_mismatch_triggers_retry(self, ai_handler, mock_ai_client):
        partial = dict(SAMPLE_EVENT, component_count=6)  # components still has only 1
        mock_ai_client.responses.create.side_effect = [
            _ledger_call_response([partial], resp_id="resp_partial"),
            _ledger_call_response([SAMPLE_EVENT], resp_id="resp_retry_complete"),
        ]

        result = ai_handler.capture_ledger_events_from_text("a 6-component agreement image text")

        assert result == [SAMPLE_EVENT]
        assert mock_ai_client.responses.create.call_count == 2

    def test_still_incomplete_after_retry_returns_retry_result_without_a_third_call(
        self, ai_handler, mock_ai_client
    ):
        incomplete = dict(SAMPLE_EVENT, component_count=0, components=[])
        mock_ai_client.responses.create.side_effect = [
            _ledger_call_response([incomplete], resp_id="resp_incomplete_1"),
            _ledger_call_response([incomplete], resp_id="resp_incomplete_2"),
        ]

        result = ai_handler.capture_ledger_events_from_text("a genuinely ambiguous document")

        assert result == [incomplete], (
            "no third call - LedgerEventManager.add_ledger_events_from_call owns the "
            "final never-silently-drop fallback, this method just returns what it got"
        )
        assert mock_ai_client.responses.create.call_count == 2


class TestHandleLedgerEventCaptureWiring:
    """T008a/T012a: AIHandler._handle_ledger_event_capture -> LedgerEventManager
    (Feature 033), replacing the removed SessionManager.add_pending_ledger_event."""

    def test_single_call_persisted_via_ledger_event_manager(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response()
        response = _ledger_call_response([SAMPLE_EVENT])
        request = AIRequest(
            user_prompt="ישראל ישראלי 5,000₪ כתב הגנה", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-abc",
            timestamp=1770000000,
        )

        followup = ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        assert followup is not None
        events_dir = ai_handler.ledger_event_manager.storage_dir
        files = list(events_dir.glob("*.json"))
        assert len(files) == 1
        with files[0].open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["source_type"] == "הסכם"
        assert data["message_id"] == "msg-abc"
        assert data["amount"] == 5000

    def test_two_calls_in_one_turn_are_rejected_not_persisted(self, ai_handler, mock_ai_client):
        """bugfix-018: runtime_constitution.md's Ledger Event Recognition (Step 4)
        instructs the model to call capture_ledger_event AT MOST ONCE per message,
        covering every genuinely distinct component of that message's event in
        that one call - there is no legitimate case where more than one call in a
        single turn is correct. The real 2026-07-30 incident (req_0f4656c9bd90)
        had the model emit 17 near-identical calls for a message that needed
        zero; more than one call in a turn is always a protocol violation, not a
        multi-client edge case, so NONE of the calls are trusted - not even a
        well-formed one - once more than one appears. Both must be rejected and
        NOTHING persisted (previously this test asserted the opposite: that two
        calls were legitimate and both got persisted - that assumption is what
        let a 17-call protocol violation reach the persistence layer at all)."""
        mock_ai_client.responses.create.return_value = _followup_response()
        event2 = _with_component_override(
            dict(SAMPLE_EVENT, client_name="דנה כהן"), amount="2,000₪"
        )
        response = _ledger_call_response([SAMPLE_EVENT, event2])
        request = AIRequest(
            user_prompt="two components", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-multi",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        events_dir = ai_handler.ledger_event_manager.storage_dir
        files = sorted(events_dir.glob("*.json"))
        assert files == [], (
            "more than one capture_ledger_event call in a turn is always a "
            "protocol violation (at-most-once rule) - nothing should ever be "
            "persisted from it, regardless of how well-formed each call looks"
        )

    def test_multiple_components_in_one_call_share_identical_agreement_id(
        self, ai_handler, mock_ai_client
    ):
        """REQ-DATA-004 (2026-07-30 components-array redesign): the PRIMARY way to
        get multiple components of one agreement is now a single capture_ledger_event
        call whose `components` array has multiple entries - not the model making N
        separate calls (proven unreliable even with a materially stronger model - see
        spec.md). All components from that ONE call must share byte-for-byte the same
        agreement_id, computed once by add_ledger_events_from_call, with distinct
        component_ids."""
        mock_ai_client.responses.create.return_value = _followup_response()
        multi_component_event = dict(SAMPLE_EVENT, component_count=2)
        multi_component_event["components"] = [
            dict(SAMPLE_EVENT["components"][0]),
            dict(SAMPLE_EVENT["components"][0], description="שלב שני", amount="2,000₪", component_label="שלב שני"),
        ]
        response = _ledger_call_response([multi_component_event])
        request = AIRequest(
            user_prompt="one agreement, two components", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-batch",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        events_dir = ai_handler.ledger_event_manager.storage_dir
        files = sorted(events_dir.glob("*.json"))
        assert len(files) == 2
        agreement_ids = set()
        component_ids = set()
        for f in files:
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            agreement_ids.add(data["agreement_id"])
            component_ids.add(data["component_id"])
        assert None not in agreement_ids
        assert len(agreement_ids) == 1, "both components must share one identical agreement_id"
        assert len(component_ids) == 2, "component_id must still differ per component"

    def test_two_calls_in_one_turn_both_get_rejected_status_in_followup(
        self, ai_handler, mock_ai_client
    ):
        """bugfix-018: rejecting a multi-call turn must not just skip persistence
        (proven above) - the follow-up sent back to OpenAI must still resolve
        EVERY call_id from the turn (OpenAI requires an output for every pending
        function call, regardless of whether we intend to honor it), each
        explicitly marked "rejected" so the model is told plainly it broke the
        at-most-once rule - never left silently believing its calls succeeded,
        and never left with an unresolved call_id (the exact mechanism that
        caused the real 400 in the first place)."""
        mock_ai_client.responses.create.return_value = _followup_response()
        event2 = dict(SAMPLE_EVENT, client_name="דנה כהן")
        response = _ledger_call_response([SAMPLE_EVENT, event2])
        request = AIRequest(
            user_prompt="two unrelated clients", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-separate",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        followup_call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        outputs_by_call_id = {
            item["call_id"]: json.loads(item["output"]) for item in followup_call_kwargs["input"]
        }
        assert set(outputs_by_call_id.keys()) == {"call_0", "call_1"}
        for call_id, payload in outputs_by_call_id.items():
            assert payload["status"] == "rejected", (
                f"{call_id} must be explicitly rejected, not silently treated as captured"
            )

    def test_morning_mcp_sourced_turn_suppressed_not_persisted(self, ai_handler, mock_ai_client):
        """Feature 024/025 suppression must still hold after the storage-layer
        swap: when the same turn's response.output contains a real mcp_call
        item, nothing is persisted."""
        mock_ai_client.responses.create.return_value = _followup_response()
        items = [
            SimpleNamespace(type="mcp_call", name="list_invoices", arguments="{}", output="{}", error=None),
            _function_call_item("capture_ledger_event", json.dumps(SAMPLE_EVENT), call_id="call_0"),
        ]
        response = SimpleNamespace(id="resp_mcp", output=items, output_text="")
        request = AIRequest(
            user_prompt="show me invoices", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-mcp",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        events_dir = ai_handler.ledger_event_manager.storage_dir
        assert list(events_dir.glob("*.json")) == []

    def test_morning_mcp_pending_approval_turn_suppressed_not_persisted(self, ai_handler, mock_ai_client):
        """Real billed incident (2026-08-02): an approval-required Morning tool
        (create_combo_document, add_client, etc.) shows up as mcp_approval_request
        on the turn that proposes it - NOT mcp_call, since nothing has executed
        yet. The mcp_call-only check missed this: a real run had a two-word
        field-filling reply ("עבור ייעוץ") sent mid-approval-flow misclassified as
        two spurious capture_ledger_event calls, entangled with (and breaking) the
        pending-approval round-trip itself. User directive: Morning-involved turns
        must never produce a ledger event, full stop."""
        mock_ai_client.responses.create.return_value = _followup_response()
        items = [
            SimpleNamespace(
                type="mcp_approval_request", name="create_combo_document",
                arguments='{"client_name":"בטא צפון","amount":34,"description":"ייעוץ"}',
            ),
            _function_call_item("capture_ledger_event", json.dumps(SAMPLE_EVENT), call_id="call_0"),
        ]
        response = SimpleNamespace(id="resp_mcp_approval", output=items, output_text="")
        request = AIRequest(
            user_prompt="עבור ייעוץ", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-mcp-approval",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        events_dir = ai_handler.ledger_event_manager.storage_dir
        assert list(events_dir.glob("*.json")) == []


class TestMaxOutputTokensTruncationCausesEmptyReply:
    """bugfix-018 root cause (confirmed via logs/test_logs/test_denidin_morning_mcp_e2e.log,
    req_0f4656c9bd90, 2026-07-30): the model spuriously emitted 17 near-identical
    parallel capture_ledger_event calls for a plain client-lookup message. That much
    parallel large-schema output exceeded max_output_tokens mid-generation. OpenAI's
    Responses API does NOT error in that case - it returns HTTP 200 with
    response.status="incomplete"/response.incomplete_details.reason="max_output_tokens"
    (this exact contract is already read elsewhere in this file, see
    _finalize_response's finish_reason derivation), and `output` includes whatever was
    mid-generation at the cutoff - including a function_call item whose `arguments`
    string is truncated (unterminated) JSON, not semantically corrupt, just cut off
    where the model happened to be. extract_all_function_calls silently drops that
    unparseable call by design, so the follow-up submission omits a
    function_call_output for its call_id - which OpenAI's real API rejects with 400
    ("No tool output found for function call ...") since that call_id is still
    pending on its side, having actually been emitted (just not finished). Today
    that follow-up failure is caught, but nothing substitutes fallback text, so the
    user gets a silently empty WhatsApp reply despite billed tokens. These tests
    construct exactly that response shape (no real OpenAI call) and prove both the
    mechanical cause and its user-facing impact against the current code."""

    @staticmethod
    def _truncated_response():
        """Two well-formed capture_ledger_event calls, plus a THIRD whose
        `arguments` string was cut off mid-stream by the token budget -
        unterminated JSON, the same shape as the real incident's parse error
        (`Expecting value: line 1 column 124 (char 123)`), not a
        semantically-malformed payload."""
        good1 = _function_call_item(
            "capture_ledger_event",
            json.dumps({"source_type": "הסכם", "event_subtype": "יצירה", "client_name": "א"}),
            call_id="call_good_1",
        )
        good2 = _function_call_item(
            "capture_ledger_event",
            json.dumps({"source_type": "הסכם", "event_subtype": "יצירה", "client_name": "ב"}),
            call_id="call_good_2",
        )
        truncated = _function_call_item(
            "capture_ledger_event",
            '{"source_type": "הסכם", "event_subtype": "יצירה", "client_name": "ג", "notes": "חלק מהטקסט שנ',
            call_id="call_truncated_by_token_limit",
        )
        return SimpleNamespace(
            id="resp_original_truncated",
            output=[good1, good2, truncated],
            output_text="",
            model="gpt-5.6-luna",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=SimpleNamespace(total_tokens=2500, input_tokens=2000, output_tokens=500),
        )

    def test_truncated_call_is_dropped_leaving_its_call_id_unresolved_in_followup(
        self, ai_handler, mock_ai_client
    ):
        """Proves the mechanical cause of OpenAI's real 400: the follow-up request
        built from a truncated original response never includes a
        function_call_output for the truncated call's call_id, even though that
        call_id is still pending on OpenAI's side (it was emitted, just not fully
        written) - this is exactly what a real follow-up submission would get
        rejected for."""
        mock_ai_client.responses.create.return_value = _followup_response()
        response = self._truncated_response()
        request = AIRequest(
            user_prompt="פרטים על הלקוח דוד גרוזדוביץ'", constitution="", max_tokens=2500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-trunc",
            timestamp=1770000000,
        )

        ai_handler._handle_ledger_event_capture(
            request, response, effective_chat_id="972500000000@c.us",
            sender="972500000000@c.us", tools=None
        )

        followup_call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        submitted_call_ids = {item["call_id"] for item in followup_call_kwargs["input"]}
        assert "call_truncated_by_token_limit" in submitted_call_ids, (
            "the truncated call's call_id must still get a function_call_output - "
            "OpenAI still considers it pending even though we couldn't parse its "
            "arguments, so omitting it is exactly what triggers the real 400"
        )

    def test_followup_rejection_from_truncation_leaves_user_with_empty_reply(
        self, ai_handler, mock_ai_client
    ):
        """End-to-end reproduction of the actual incident: once OpenAI rejects the
        follow-up (because of the dropped call_id proven above), _finalize_response
        must not leave the user with a silently empty WhatsApp message - it should
        fall back to a friendly message, the same pattern already used for the
        pending-approval gap (_build_pending_approval_fallback_text). Today it
        doesn't, and response_text stays ''."""
        mock_ai_client.responses.create.side_effect = Exception(
            "Error code: 400 - {'error': {'message': 'No tool output found for "
            "function call call_truncated_by_token_limit.', 'type': "
            "'invalid_request_error', 'param': 'input', 'code': None}}"
        )
        response = self._truncated_response()
        request = AIRequest(
            user_prompt="פרטים על הלקוח דוד גרוזדוביץ'", constitution="", max_tokens=2500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-trunc-2",
            timestamp=1770000000,
        )

        ai_response = ai_handler._finalize_response(
            request, response, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None, tools=None,
        )

        assert ai_response.response_text.strip() != "", (
            "the follow-up failed (as it does for real, per bugfix-018's root "
            "cause: a truncated capture_ledger_event call from hitting "
            "max_output_tokens leaves an unresolved call_id, which OpenAI rejects "
            "with 400) - the user must never receive a silently empty reply"
        )


class TestFinalizeResponseThreadsLedgerEventIds:
    """T008a: the stored user message must carry ledger_event_ids at creation
    time (Feature 033's Message.ledger_event_ids, REQ-TRACE-003)."""

    def test_captured_event_id_threaded_into_stored_user_message(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response()
        response = _ledger_call_response([SAMPLE_EVENT])
        request = AIRequest(
            user_prompt="ישראל ישראלי 5,000₪ כתב הגנה", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-thread",
            timestamp=1770000000,
        )

        ai_response = ai_handler._finalize_response(
            request, response, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="client", sender="972500000000@c.us",
            recipient="AI", tools=None
        )

        assert ai_response is not None
        events_dir = ai_handler.ledger_event_manager.storage_dir
        event_files = list(events_dir.glob("*.json"))
        assert len(event_files) == 1
        with event_files[0].open(encoding="utf-8") as f:
            event_record = json.load(f)
        event_id = event_record["event_id"]

        session = ai_handler.session_manager.get_session("972500000000@c.us")
        session_dir = ai_handler.session_manager.storage_dir / session.session_id
        user_messages = []
        for message_id in session.message_ids:
            with (session_dir / "messages" / f"{message_id}.json").open(encoding="utf-8") as f:
                msg = json.load(f)
            if msg["role"] == "user":
                user_messages.append(msg)

        assert len(user_messages) == 1
        assert user_messages[0]["ledger_event_ids"] == [event_id]

        # Confirmed design (2026-07-30): the id decided at message-arrival time
        # (AIRequest.message_id, from WhatsAppMessage.from_notification) MUST be
        # identical across the persisted message's own message_id field, its
        # filename, the session's message_ids entry, AND LedgerEvent.message_id -
        # never independently regenerated at storage time.
        assert user_messages[0]["message_id"] == "msg-thread"
        assert "msg-thread" in session.message_ids
        assert (session_dir / "messages" / "msg-thread.json").exists()
        assert event_record["message_id"] == "msg-thread"

    def test_no_capture_leaves_ledger_event_ids_empty(self, ai_handler, mock_ai_client):
        response = SimpleNamespace(
            id="resp_no_capture", output=[], output_text="שלום, איך אפשר לעזור?",
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=10, input_tokens=5, output_tokens=5),
        )
        request = AIRequest(
            user_prompt="מה קורה?", constitution="", max_tokens=500,
            model="gpt-5.6-luna", chat_id="972500000000@c.us", message_id="msg-none",
            timestamp=1770000000,
        )

        ai_handler._finalize_response(
            request, response, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="client", sender="972500000000@c.us",
            recipient="AI", tools=None
        )

        session = ai_handler.session_manager.get_session("972500000000@c.us")
        session_dir = ai_handler.session_manager.storage_dir / session.session_id
        with (session_dir / "messages" / f"{session.message_ids[0]}.json").open(encoding="utf-8") as f:
            msg = json.load(f)
        assert msg["ledger_event_ids"] == []
