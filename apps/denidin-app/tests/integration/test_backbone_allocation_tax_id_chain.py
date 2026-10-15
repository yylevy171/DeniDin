"""
Integration tests (Feature 098 on the Backbone, NOT billed): saving a client's ID
and then issuing the document are two separate approvals, chained. The "yes" that
saves the ID runs update_client AND offers the document's approval straight away;
that approval reaches the user as buttons, and the next "yes" is again an approved
write. Real Backbone, DeniDin, WhatsAppHandler and SessionManager; only the OpenAI SDK
and the Green API bot are faked (CONSTITUTION §I/§V).
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.models.config import AppConfiguration
from src.models.message import AIRequest
from tests.backbone_test_support import FakeBot, make_backbone
from tests.denidin_test_support import make_session_manager

pytestmark = pytest.mark.integration

PROMPTS = Path(__file__).parent.parent.parent / "config"
CHAT = "chat098"
SAVE_ID_PROMPT = "לשמור ת.ז 308253681 על לקוח בדיקה?"
DOC_PROMPT = "להפיק חשבונית מס/קבלה ללקוח בדיקה על 12,000 ₪ (מע\"מ: כלול)?"


def _fc(name, args, call_id="c"):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)


def _response(rid, *items):
    return SimpleNamespace(output=list(items), output_text="", id=rid, usage=None)


def _mcp_call(name, output):
    return SimpleNamespace(type="mcp_call", name=name, arguments="{}", output=json.dumps(output), error=None)


def _request(text):
    return AIRequest(user_prompt=text, constitution="", max_tokens=500, model="m",
                     chat_id=CHAT, message_id=f"m-{text}")


def _tap():
    return SimpleNamespace(chat_id=CHAT, sender_id=CHAT, message_id="TAP", sender_display_name="Tester",
                           is_group=False, chat_name=None)


@pytest.fixture
def env(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(PROMPTS)},
        mcp={"morning_auth_token": "tok"},
    )
    sessions = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    client = MagicMock()
    locator = SimpleNamespace(current_server_url=lambda: "https://morning.example/mcp")
    backbone = make_backbone(client, config, session_manager=sessions, morning_mcp_locator=locator)
    backbone.denidin.green_api_bot = FakeBot()
    return SimpleNamespace(client=client, sessions=sessions, backbone=backbone,
                           bot=backbone.denidin.green_api_bot,
                           approved=client.with_options.return_value.responses.create)


def _end(rid="r-end"):
    return _response(rid)


def _id_given_offers_save_approval(env):
    """The user typed the ID: the model loads modify-client and asks to save it."""
    env.client.responses.create.side_effect = [
        _response("r1", _fc("load_flows", {"flows": ["flow_modify_client"]})),
        _response("r2", _fc("load_capabilities", {"capabilities": ["cap_client_write",
                                                                   "cap_approval_with_buttons"]})),
        _response("r3", _fc("approval_with_yes_no_buttons", {"text": SAVE_ID_PROMPT})),
        _end("r3b"),
    ]
    env.backbone.handle_message(_request("308253681"), chat_id=CHAT, user_role="godfather")
    assert [b[1] for b in env.bot.buttons] == [SAVE_ID_PROMPT]
    assert env.sessions.get_session(CHAT).approval_message_id == "BTN1"


def _save_turn_replies():
    """The approved save: update_client ran, then the document's own approval is asked at once."""
    return [_response("r4", _mcp_call("update_client", {"status": "updated", "tax_id": "308253681"}),
                      _fc("approval_with_yes_no_buttons", {"text": DOC_PROMPT}, call_id="c-doc")),
            _end("r4b")]


def _assert_document_approval_offered(env, saved):
    assert [b[1] for b in env.bot.buttons] == [SAVE_ID_PROMPT, DOC_PROMPT]
    assert [c["name"] for c in saved.mcp_calls] == ["update_client"]
    assert env.sessions.get_session(CHAT).approval_message_id == "BTN2"  # the document's buttons are the live ones


@pytest.mark.parametrize("answer", ["tap", "typed"])
def test_yes_on_id_save_chains_into_the_document_approval_then_issues_it(env, answer):
    _id_given_offers_save_approval(env)
    env.approved.side_effect = _save_turn_replies() + [
        _response("r5", _mcp_call("create_combo_document", {"number": 98, "amount": 12000}),
                  _fc("send_to_user", {"text": "הופקה חשבונית מס/קבלה 98."})),
        _end("r5b"),
    ]

    if answer == "tap":
        saved = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "BTN1", user_role="godfather")
    else:
        saved = env.backbone.handle_message(_request("כן"), chat_id=CHAT, user_role="godfather")

    _assert_document_approval_offered(env, saved)

    if answer == "tap":
        # The ID-save buttons are spent; only the document's buttons are live.
        assert env.backbone.resolve_button_tap(_tap(), "denidin_approve", "BTN1", user_role="godfather") is None
        issued = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "BTN2", user_role="godfather")
    else:
        issued = env.backbone.handle_message(_request("כן"), chat_id=CHAT, user_role="godfather")

    assert env.bot.sent[-1][1] == "הופקה חשבונית מס/קבלה 98."
    assert [c["name"] for c in issued.mcp_calls] == ["create_combo_document"]
    assert env.approved.call_count == 4  # both answers were approved-write conversations (no SDK retries)
    env.client.with_options.assert_called_with(max_retries=0)


def test_declining_the_document_after_saving_the_id_issues_nothing(env):
    _id_given_offers_save_approval(env)
    env.approved.side_effect = _save_turn_replies()
    saved = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "BTN1", user_role="godfather")
    _assert_document_approval_offered(env, saved)

    env.client.responses.create.side_effect = [
        _response("r6", _fc("send_to_user", {"text": "בסדר, המסמך לא הופק."})),
        _end("r6b"),
    ]
    declined = env.backbone.resolve_button_tap(_tap(), "denidin_decline", "BTN2", user_role="godfather")

    assert env.bot.sent[-1][1] == "בסדר, המסמך לא הופק."
    assert declined.mcp_calls == []
    assert env.approved.call_count == 2  # a "no" is not an approved-write conversation
    assert env.sessions.get_session(CHAT).approval_message_id is None
