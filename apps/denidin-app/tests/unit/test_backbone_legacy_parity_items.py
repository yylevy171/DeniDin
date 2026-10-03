"""Unit tests (2026-10-01) for the backbone legacy-parity items:
Item4 (approved-write safeguards: SDK retries off, duplicate execution, write never ran - the
shared core.write_guards, also legacy's), Item7 (a turn is never left silent by
accident), Item14 (group-only etiquette section), Item17 (DOCX analysis works through
the backbone's extractor shim)."""
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
from src.constants.error_messages import (
    APPROVAL_POSSIBLY_DUPLICATED, BACKBONE_UNEXPECTED_ERROR, LEDGER_FOLLOWUP_FAILED_TRY_AGAIN,
)
from src.core.ai_manager import AIManager
approved_write_not_run_message = AIManager.approved_write_not_run_message
is_affirmative_reply = AIManager.is_affirmative_reply
tally_write_executions = AIManager.tally_write_executions
write_subject = AIManager.write_subject
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest, NO_REPLY_SENTINEL
from tests.backbone_test_support import make_backbone, make_session_manager

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


def _mcp(name, output="ok", error=None):
    return SimpleNamespace(type="mcp_call", name=name, arguments="{}", output=output, error=error)


def _send(text, call_id="s1"):
    return _call("send_to_user", {"text": text}, call_id)


def _backbone(prompts_root, client):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(prompts_root)})
    return make_backbone(client, config, session_manager=make_session_manager())


def _request(text="שלום"):
    return AIRequest(user_prompt=text, constitution="", max_tokens=1000, model="m",
                     chat_id="chat1", message_id="msg1")


def _approved_turn(prompts_root, responses):
    """A "כן" answering outstanding approval buttons - the approved-write turn."""
    client = MagicMock()
    client.with_options.return_value.responses.create.side_effect = responses
    backbone = _backbone(prompts_root, client)
    backbone.session_manager.set_approval_message_id("chat1", "approval-msg")
    return client, backbone.single_turn(_request("כן"), chat_id="chat1")


# --- Item4 -------------------------------------------------------------------

def test_approved_turn_that_ran_the_write_once_keeps_its_reply_sdk_retries_off(prompts_root):
    client, response = _approved_turn(prompts_root, [
        _response([_mcp("create_invoice"), _send("החשבונית הופקה")]),
    ])
    assert response.response_text == "החשבונית הופקה"
    client.with_options.assert_called_with(max_retries=0)
    client.responses.create.assert_not_called()


def test_approved_write_that_ran_twice_is_reported_as_possibly_duplicated(prompts_root):
    _, response = _approved_turn(prompts_root, [
        _response([_mcp("create_invoice"), _mcp("create_invoice"), _send("הופקה")]),
    ])
    assert response.response_text == APPROVAL_POSSIBLY_DUPLICATED
    assert response.offer_approval_buttons is False


def test_approved_turn_where_no_write_ran_tells_the_user_nothing_was_done(prompts_root):
    _, response = _approved_turn(prompts_root, [
        _response([_mcp("get_invoice_details", output=None,
                        error={"content": [{"type": "text", "text": "המסמך לא נמצא"}]}),
                   _send("הופקה בהצלחה")]),
    ])
    assert response.response_text == approved_write_not_run_message(" (המסמך לא נמצא)")
    assert "המסמך לא נמצא" in response.response_text


def test_never_ran_message_names_a_reminder_when_the_approval_was_about_a_reminder(prompts_root):
    client = MagicMock()
    client.with_options.return_value.responses.create.side_effect = [
        _response([_call("load_capabilities", {"capabilities": ["cap_reminders_write"]}, "c1")], "r1"),
        _response([_send("נוצרה")], "r2"),
    ]
    backbone = _backbone(prompts_root, client)
    backbone.session_manager.set_approval_message_id("chat1", "approval-msg")
    response = backbone.single_turn(_request("כן"), chat_id="chat1")
    assert "לא נוצרה, לא שונתה ולא נמחקה שום תזכורת" in response.response_text
    assert "מסמך" not in response.response_text


def test_never_ran_message_is_hebrew_only():
    message = approved_write_not_run_message(' ({"error": "Client not found"})', "document")
    assert "Client not found" not in message and "error" not in message
    assert message == "אישרת, אבל הפעולה לא בוצעה בפועל. לא נוצר שום מסמך. נסי שוב או ספרי לי איך להמשיך."
    assert write_subject(["add_client"]) == "client"
    assert write_subject(["create_invoice", "create_reminder"]) == ""


def test_a_yes_without_outstanding_approval_buttons_is_an_ordinary_turn(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response([_send("בסדר")])
    response = _backbone(prompts_root, client).single_turn(_request("כן"), chat_id="chat1")
    assert response.response_text == "בסדר"
    client.with_options.assert_not_called()


def test_shared_tally_counts_local_writes_and_takes_the_first_failure_text():
    executions = tally_write_executions(
        [{"name": "list_reminders", "output": "", "error": "boom"},
         {"name": "create_reminder", "output": "נוצרה", "error": None}],
        {"create_reminder"})
    assert executions.counts == {"create_reminder": 1}
    assert executions.failure_detail == " (boom)"
    assert is_affirmative_reply("‏כן") and not is_affirmative_reply("לא נכון, אל תפיק")


def test_approved_turn_still_retries_once_on_a_424(prompts_root):
    """The shared explicit 424 retry applies on the approved turn too (one ~2s backoff)."""
    client, response = _approved_turn(prompts_root, [
        APIStatusError("424", response=MagicMock(status_code=424), body=None),
        _response([_mcp("create_invoice"), _send("החשבונית הופקה")]),
    ])
    assert response.response_text == "החשבונית הופקה"
    assert client.with_options.return_value.responses.create.call_count == 2


# --- Item7 -------------------------------------------------------------------

def test_empty_send_to_user_text_replies_with_an_error_not_silence(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response([_send("   ")])
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")
    assert response.response_text == BACKBONE_UNEXPECTED_ERROR
    assert response.should_reply is True


def test_failed_follow_up_call_replies_with_try_again(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_call("record_planning_status", {"where_i_was": "x"}, "c1")]),
        RuntimeError("network down"),
    ]
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")
    assert response.response_text == LEDGER_FOLLOWUP_FAILED_TRY_AGAIN


def test_hitting_the_round_limit_replies_with_an_error(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response(
        [_call("record_planning_status", {"where_i_was": "x"}, "c1")])
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")
    assert response.response_text == BACKBONE_UNEXPECTED_ERROR


def test_a_deliberate_no_reply_stays_silent(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response([_send(NO_REPLY_SENTINEL)])
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")
    assert response.should_reply is False


# --- Item14 ------------------------------------------------------------------

@pytest.mark.parametrize("is_group", [True, False])
def test_group_etiquette_is_in_the_instructions_only_in_a_group(prompts_root, is_group):
    client = MagicMock()
    client.responses.create.return_value = _response([_send("שלום")])
    _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1", is_group=is_group)
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
