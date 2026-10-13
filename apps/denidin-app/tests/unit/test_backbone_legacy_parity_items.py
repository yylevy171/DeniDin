"""Unit tests for the backbone's safeguards, updated for the no-turn redesign (Feature 067):
Item4 (an approved action runs with the SDK's own retries off), Item7 (a failure is told to the
user at once, in its own words; a malformed or unavailable tool call is answered), Item14
(group-only etiquette section), Item17 (DOCX analysis works through the backbone's extractor shim).
Every send goes out through the real DeniDin and WhatsAppHandler to a fake Green API bot."""
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docx import Document
from openai import APIStatusError

from src.capabilities.media_analysis.handler import (
    _build_extractor, _format_result,
)
from src.constants.error_messages import BACKBONE_UNEXPECTED_ERROR
from src.core.ai_manager import AIManager
is_affirmative_reply = AIManager.is_affirmative_reply
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest
from tests.backbone_test_support import FakeBot, make_backbone, make_session_manager

GROUP_MARKER = "Group Conversation Etiquette (this chat is a WhatsApp group)"


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "group_etiquette.md").write_text(f"## {GROUP_MARKER}", encoding="utf-8")
    return base


def _response(items, response_id="r", output_text=""):
    return SimpleNamespace(output=items, output_text=output_text, id=response_id, model="m",
                           incomplete_details=None,
                           usage=SimpleNamespace(total_tokens=1, input_tokens=1, output_tokens=0))


def _call(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _mcp(name, output="ok", error=None, arguments="{}"):
    return SimpleNamespace(type="mcp_call", name=name, arguments=arguments, output=output, error=error)


def _send(text, call_id="s1"):
    return _call("send_to_user", {"text": text}, call_id)


def _backbone(prompts_root, client):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(prompts_root)})
    backbone = make_backbone(client, config, session_manager=make_session_manager())
    backbone.denidin.green_api_bot = FakeBot()
    return backbone


def _said(backbone):
    """Every text that reached the user, in order."""
    return backbone.denidin.green_api_bot.sent_texts


def _request(text="שלום"):
    return AIRequest(user_prompt=text, constitution="", max_tokens=1000, model="m",
                     chat_id="chat1", message_id="msg1")


def _approved_turn(prompts_root, responses):
    """A "כן" answering outstanding approval buttons - the approved-write turn."""
    client = MagicMock()
    client.with_options.return_value.responses.create.side_effect = responses
    backbone = _backbone(prompts_root, client)
    backbone.session_manager.set_approval_message_id("chat1", "approval-msg")
    backbone.handle_message(_request("כן"), chat_id="chat1")
    return client, backbone


# --- Item4 -------------------------------------------------------------------

def test_approved_message_runs_with_the_sdk_retries_off(prompts_root):
    client, backbone = _approved_turn(prompts_root, [
        _response([_mcp("create_invoice"), _send("החשבונית הופקה")]),
        _response([]),
    ])
    assert _said(backbone) == ["החשבונית הופקה"]
    client.with_options.assert_called_with(max_retries=0)
    client.responses.create.assert_not_called()


def test_a_write_that_ran_twice_is_not_flagged_the_model_sees_both_results(prompts_root):
    """Decision 4 (no-turn redesign): the duplicate-write note is gone; the model's own report is
    sent as is."""
    _, backbone = _approved_turn(prompts_root, [
        _response([_mcp("create_invoice"), _mcp("create_invoice"), _send("הופקה")]),
        _response([]),
    ])
    assert _said(backbone) == ["הופקה"]


def test_failed_write_attempts_are_reported_by_the_model_untouched(prompts_root):
    not_found = {"type": "mcp_tool_execution_error",
                 "content": [{"type": "text", "text": "לא נמצא לקוח בשם \"עמינדב אנדריין\""}]}
    _, backbone = _approved_turn(prompts_root, [
        _response([_mcp("create_transaction_account", output=None, error=not_found),
                   _send("לא הצלחתי להפיק את חשבון העסקה. לא נוצר מסמך.")]),
        _response([]),
    ])
    assert _said(backbone) == ["לא הצלחתי להפיק את חשבון העסקה. לא נוצר מסמך."]


def test_a_yes_that_answers_an_offer_and_asks_the_next_approval_sends_it_as_buttons(prompts_root):
    """064: a yes to an offer starts a flow whose first step is its own approval; the new approval
    reaches the user as buttons and the chat remembers its message id."""
    approval_text = "📋 לאישור:\nפרטי המסמך\nלאישור — כן/לא?"
    client = MagicMock()
    client.with_options.return_value.responses.create.side_effect = [
        _response([_call("approval_with_yes_no_buttons", {"text": approval_text}, "a1")], "r1"),
        _response([], "r2"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.session_manager.set_approval_message_id("chat1", "offer-msg")
    backbone.handle_message(_request("כן"), chat_id="chat1")
    assert [b[1] for b in backbone.denidin.green_api_bot.buttons] == [approval_text]
    assert backbone.session_manager.get_session("chat1").approval_message_id == "BTN1"


def test_a_yes_without_outstanding_approval_buttons_is_an_ordinary_message(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [_response([_send("בסדר")]), _response([])]
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request("כן"), chat_id="chat1")
    assert _said(backbone) == ["בסדר"]
    client.with_options.assert_not_called()


def test_a_yes_is_recognised_however_it_is_written():
    assert is_affirmative_reply("‏כן") and not is_affirmative_reply("לא נכון, אל תפיק")


def test_approved_message_still_retries_once_on_a_424(prompts_root):
    """The shared explicit 424 retry applies on the approved message too (one ~2s backoff)."""
    client, backbone = _approved_turn(prompts_root, [
        APIStatusError("424", response=MagicMock(status_code=424), body=None),
        _response([_mcp("create_invoice"), _send("החשבונית הופקה")]),
        _response([]),
    ])
    assert _said(backbone) == ["החשבונית הופקה"]
    assert client.with_options.return_value.responses.create.call_count == 3


# --- Item7 -------------------------------------------------------------------

def test_a_send_with_no_text_sends_nothing_and_tells_the_model(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [_response([_send("   ")]), _response([])]
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")
    assert _said(backbone) == []
    follow_up_input = client.responses.create.call_args_list[1].kwargs["input"]
    assert follow_up_input[0]["output"].startswith("error:")  # the model is told it was not sent


def test_a_failed_follow_up_call_tells_the_user_at_once(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_call("record_planning_status", {"where_i_was": "x"}, "c1")]),
        RuntimeError("network down"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")
    assert _said(backbone) == [BACKBONE_UNEXPECTED_ERROR]


def test_hitting_the_round_limit_pauses_quietly(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response(
        [_call("record_planning_status", {"where_i_was": "x"}, "c1")])
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")
    assert client.responses.create.call_count == 100
    assert _said(backbone) == []


def _malformed_call(name, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments='{"text": "קטו', call_id=call_id)


def test_a_malformed_tool_call_gets_an_error_output_and_the_conversation_continues(prompts_root):
    """M3 (2026-10-04): a call whose arguments don't parse (cut off at the output limit) is answered
    with its own error - never left without an output, which OpenAI rejects on the next round."""
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_malformed_call("send_to_user", "bad1")], response_id="r1"),
        _response([_send("תשובה מלאה")], response_id="r2"),
        _response([], response_id="r3"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")

    assert _said(backbone) == ["תשובה מלאה"]
    follow_up_input = client.responses.create.call_args_list[1].kwargs["input"]
    [error_output] = [o for o in follow_up_input if o.get("call_id") == "bad1"]
    assert json.loads(error_output["output"])["status"] == "error"


def test_a_call_to_an_unattached_tool_gets_an_error_output(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_call("create_reminder", {"message_text": "x"}, "c1"),
                   _call("react_to_message", {"emoji": "👍"}, "c2")], response_id="r1"),
        _response([_send("בסדר")], response_id="r2"),
        _response([], response_id="r3"),
    ]
    _backbone(prompts_root, client).handle_message(_request(), chat_id="chat1")

    follow_up_input = client.responses.create.call_args_list[1].kwargs["input"]
    assert {o["call_id"] for o in follow_up_input} == {"c1", "c2"}
    [error_output] = [o for o in follow_up_input if o["call_id"] == "c1"]
    assert "not available" in json.loads(error_output["output"])["reason"]


def _http_request():
    import httpx
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


@pytest.mark.parametrize("make_error, expected", [
    (lambda: __import__("openai").APITimeoutError(request=_http_request()), "BACKBONE_AI_TIMEOUT"),
    (lambda: __import__("openai").RateLimitError(
        "rate", response=__import__("httpx").Response(429, request=_http_request()), body={}),
     "BACKBONE_AI_RATE_LIMITED"),
    (lambda: __import__("openai").APIStatusError(
        "boom", response=__import__("httpx").Response(500, request=_http_request()), body={}),
     "BACKBONE_AI_API_ERROR"),
    (lambda: RuntimeError("bug"), "BACKBONE_UNEXPECTED_ERROR"),
])
def test_each_kind_of_model_call_failure_is_told_to_the_user_in_its_own_words(prompts_root, make_error, expected):
    """C8 (2026-10-04): per-error replies - timeout, rate limit, any other API error, anything else."""
    from src.constants import error_messages
    client = MagicMock()
    client.responses.create.side_effect = make_error()
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")
    assert _said(backbone) == [getattr(error_messages, expected)]


def test_silence_is_a_response_with_no_tool_call_and_sends_nothing(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response([])
    backbone = _backbone(prompts_root, client)
    backbone.handle_message(_request(), chat_id="chat1")
    assert _said(backbone) == []
    assert client.responses.create.call_count == 1


# --- Item14 ------------------------------------------------------------------

@pytest.mark.parametrize("is_group", [True, False])
def test_group_etiquette_is_in_the_instructions_only_in_a_group(prompts_root, is_group):
    client = MagicMock()
    client.responses.create.return_value = _response([_send("שלום")])
    _backbone(prompts_root, client).handle_message(_request(), chat_id="chat1", is_group=is_group)
    instructions = client.responses.create.call_args.kwargs["instructions"]
    assert (GROUP_MARKER in instructions) is is_group


# --- Item17 ------------------------------------------------------------------

def _docx_media(*paragraphs):
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    data = io.BytesIO()
    doc.save(data)
    return Media.from_bytes(
        data=data.getvalue(),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="agreement.docx")


def test_docx_analysis_works_through_the_backbone_shim(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(output_text="סוג מסמך: הסכם שכר טרחה")
    backbone = _backbone(prompts_root, client)
    extractor = _build_extractor("docx", SimpleNamespace(config=backbone.config, ai_manager=backbone))

    result = extractor.analyze_media(_docx_media("הסכם שכר טרחה בין משה כהן לבין המשרד"))

    assert result["raw_response"] == "סוג מסמך: הסכם שכר טרחה"
    # One standalone call: the prompt as input, no tools, no conversation.
    kwargs = client.responses.create.call_args.kwargs
    assert "tools" not in kwargs and "previous_response_id" not in kwargs
    assert "הסכם שכר טרחה בין משה כהן" in kwargs["input"]
    payload = json.loads(_format_result(result)[0])
    assert payload["doc_type"] == "agreement"
    assert payload["document_analysis"]["summary"] == "סוג מסמך: הסכם שכר טרחה"
