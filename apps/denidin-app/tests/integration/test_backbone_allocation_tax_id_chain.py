"""
Integration tests (Feature 098 on the Backbone, NOT billed): saving a client's ID
and then issuing the document are two separate approvals, chained. The "yes" that
saves the ID runs update_client AND offers the document's approval in the same
turn; that turn must reach the user with buttons and no "nothing was performed"
note, and the next "yes" is again an approved write. Real Backbone and
SessionManager; only the OpenAI SDK boundary is mocked (CONSTITUTION §I/§V).
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.constants.error_messages import (
    APPROVED_WRITE_NOT_PERFORMED_NOTE, APPROVED_WRITE_POSSIBLY_DUPLICATED_NOTE,
)
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from tests.backbone_test_support import make_backbone
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
    return SimpleNamespace(client=client, sessions=sessions, backbone=backbone,
                           approved=client.with_options.return_value.responses.create)


def _id_given_offers_save_approval(env):
    """The user typed the ID: the model loads modify-client and asks to save it."""
    env.client.responses.create.side_effect = [
        _response("r1", _fc("load_flows", {"flows": ["flow_modify_client"]})),
        _response("r2", _fc("load_capabilities", {"capabilities": ["cap_client_write",
                                                                   "cap_approval_with_buttons"]})),
        _response("r3", _fc("approval_with_yes_no_buttons", {"text": SAVE_ID_PROMPT})),
    ]
    response = env.backbone.single_turn(_request("308253681"), chat_id=CHAT, user_role="godfather")
    assert response.offer_approval_buttons is True
    assert response.response_text == SAVE_ID_PROMPT
    env.backbone.record_sent_message_id(CHAT, "STANZA-SAVE")


def _save_turn_reply():
    """The approved save: update_client ran, then the document's own approval."""
    return _response("r4", _mcp_call("update_client", {"status": "updated", "tax_id": "308253681"}),
                     _fc("approval_with_yes_no_buttons", {"text": DOC_PROMPT}, call_id="c-doc"))


def _assert_document_approval_offered(response):
    assert response.offer_approval_buttons is True
    assert response.response_text == DOC_PROMPT
    assert APPROVED_WRITE_NOT_PERFORMED_NOTE not in response.response_text
    assert APPROVED_WRITE_POSSIBLY_DUPLICATED_NOTE not in response.response_text
    assert [c["name"] for c in response.mcp_calls] == ["update_client"]


@pytest.mark.parametrize("answer", ["tap", "typed"])
def test_yes_on_id_save_chains_into_the_document_approval_then_issues_it(env, answer):
    _id_given_offers_save_approval(env)
    env.approved.side_effect = [
        _save_turn_reply(),
        _response("r5", _mcp_call("create_combo_document", {"number": 98, "amount": 12000}),
                  _fc("send_to_user", {"text": "הופקה חשבונית מס/קבלה 98."})),
    ]

    if answer == "tap":
        saved = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "STANZA-SAVE", user_role="godfather")
    else:
        saved = env.backbone.single_turn(_request("כן"), chat_id=CHAT, user_role="godfather")

    _assert_document_approval_offered(saved)
    env.backbone.record_sent_message_id(CHAT, "STANZA-DOC")  # what denidin.py does after sending

    if answer == "tap":
        # The ID-save buttons are spent; only the document's buttons are live.
        assert env.backbone.resolve_button_tap(_tap(), "denidin_approve", "STANZA-SAVE",
                                               user_role="godfather") is None
        issued = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "STANZA-DOC", user_role="godfather")
    else:
        issued = env.backbone.single_turn(_request("כן"), chat_id=CHAT, user_role="godfather")

    assert issued.response_text == "הופקה חשבונית מס/קבלה 98."
    assert [c["name"] for c in issued.mcp_calls] == ["create_combo_document"]
    assert issued.offer_approval_buttons is False
    assert env.approved.call_count == 2  # both answers were approved-write turns (no retries)
    env.client.with_options.assert_called_with(max_retries=0)


def test_declining_the_document_after_saving_the_id_issues_nothing(env):
    _id_given_offers_save_approval(env)
    env.approved.side_effect = [_save_turn_reply()]
    saved = env.backbone.resolve_button_tap(_tap(), "denidin_approve", "STANZA-SAVE", user_role="godfather")
    _assert_document_approval_offered(saved)
    env.backbone.record_sent_message_id(CHAT, "STANZA-DOC")

    env.client.responses.create.side_effect = [
        _response("r6", _fc("send_to_user", {"text": "בסדר, המסמך לא הופק."})),
    ]
    declined = env.backbone.resolve_button_tap(_tap(), "denidin_decline", "STANZA-DOC", user_role="godfather")

    assert declined.response_text == "בסדר, המסמך לא הופק."
    assert declined.mcp_calls == []
    assert declined.offer_approval_buttons is False
    assert env.approved.call_count == 1  # a "no" is not an approved-write turn
    assert env.sessions.get_session(CHAT).approval_message_id is None
