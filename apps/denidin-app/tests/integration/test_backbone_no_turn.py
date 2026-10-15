"""Feature 067 (no-turn redesign): there is no turn. Every tool the model calls acts at once (a send is
sent, approval buttons are sent), the app pauses only when a model response carries no tool call, output text is
ignored, and the chat's model chain survives between messages. Real Backbone, SessionManager and WhatsAppHandler;
only the OpenAI SDK and the Green API bot boundary are faked (CONSTITUTION §I/§V)."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import BadRequestError

from src.backbone.backbone import PLAIN_TEXT_IGNORED_NOTE
from src.constants.error_messages import BACKBONE_UNEXPECTED_ERROR
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.utils.time_utils import now_local
from tests.backbone_test_support import FakeBot, make_backbone
from tests.denidin_test_support import make_session_manager

pytestmark = pytest.mark.integration

PROMPTS = Path(__file__).parent.parent.parent / "config"
CHAT = "972522968679@c.us"


def _fc(name, args=None, call_id="c", rid="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None)


def _send(text, rid="r", call_id="c"):
    return _fc("send_to_user", {"text": text}, call_id=call_id, rid=rid)


def _nothing(rid="r-end"):
    return SimpleNamespace(output=[], output_text="", id=rid, usage=None)


def _text_only(text, rid="r-text"):
    return SimpleNamespace(output=[], output_text=text, id=rid, usage=None)


@pytest.fixture
def env(tmp_path):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(PROMPTS)}, mcp={"morning_auth_token": "tok"},
                              godfather_phone=CHAT)
    sessions = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    client = MagicMock()
    backbone = make_backbone(client, config, session_manager=sessions)
    app = backbone.denidin
    app.green_api_bot = FakeBot()

    def request(text="שלום", message_id="m0"):
        return AIRequest(user_prompt=text, constitution="", max_tokens=500, model="m", chat_id=CHAT,
                         message_id=message_id, timestamp=int(now_local().timestamp()))

    def handle(text="שלום", message_id="m0"):
        return backbone.handle_message(request(text, message_id), chat_id=CHAT, user_role="godfather")

    yield SimpleNamespace(backbone=backbone, app=app, client=client, bot=app.green_api_bot,
                          sessions=sessions, handle=handle)
    sessions.close()


def _calls(env):
    return [c.kwargs for c in env.client.responses.create.call_args_list]


def test_a_send_goes_out_at_once_and_the_app_pauses_on_a_response_with_no_tool_call(env):
    env.client.responses.create.side_effect = [_send("הנה התשובה", rid="r1"), _nothing("r2")]
    env.handle()
    assert env.bot.sent == [(CHAT, "הנה התשובה")]
    assert len(_calls(env)) == 2  # the send's result was handed back; the empty response paused
    assert _calls(env)[1]["input"][0]["type"] == "function_call_output"


def test_output_text_is_ignored_with_one_more_call_and_never_sent(env):
    env.client.responses.create.side_effect = [_text_only("שלום לך"), _nothing("r2")]
    env.handle()
    assert env.bot.sent == []
    second = _calls(env)[1]["input"]
    assert second == [{"role": "developer", "content": PLAIN_TEXT_IGNORED_NOTE}]


def test_text_again_after_the_note_pauses_without_another_call(env):
    env.client.responses.create.side_effect = [_text_only("א"), _text_only("ב", rid="r2")]
    env.handle()
    assert env.bot.sent == []
    assert len(_calls(env)) == 2


def test_approval_buttons_are_sent_at_once_and_their_id_is_stored_on_the_chat(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_approval_with_buttons"]}, rid="r1"),
        _fc("approval_with_yes_no_buttons", {"text": "📋 לאישור:\nלאשר?\nלאישור — כן/לא?"}, rid="r2"),
        _nothing("r3")]
    response = env.handle()
    assert [b[1] for b in env.bot.buttons] == ["📋 לאישור:\nלאשר?\nלאישור — כן/לא?"]
    assert env.sessions.get_session(CHAT).approval_message_id == "BTN1"
    assert response.offer_approval_buttons is True


def test_the_chain_continues_with_just_the_new_message_and_survives_between_messages(env):
    env.client.responses.create.side_effect = [_send("ראשון", rid="r1"), _nothing("r2"), _nothing("r3")]
    env.handle("הודעה 1", "m1")
    assert env.sessions.get_session(CHAT).ai_chain_id == "r2"
    env.handle("הודעה 2", "m2")
    third = _calls(env)[2]
    assert third["previous_response_id"] == "r2"
    assert [i["role"] for i in third["input"]] == ["user"]
    assert "הודעה 2" in third["input"][0]["content"]


def test_a_chain_openai_no_longer_knows_is_replaced_by_a_new_one_from_the_window(env):
    env.sessions.set_ai_chain_id(CHAT, "gone")
    unknown = BadRequestError(
        "no such response", response=httpx.Response(400, request=httpx.Request("POST", "https://x")),
        body={"code": "previous_response_not_found"})
    unknown.code = "previous_response_not_found"
    env.client.responses.create.side_effect = [unknown, _send("בסדר", rid="r1"), _nothing("r2")]
    env.handle("הודעה")
    calls = _calls(env)
    assert calls[0]["previous_response_id"] == "gone"
    assert "previous_response_id" not in calls[1]
    assert env.bot.sent == [(CHAT, "בסדר")]
    assert env.sessions.get_session(CHAT).ai_chain_id == "r2"


def test_a_failed_call_sends_the_friendly_error_at_once_pauses_and_drops_the_chain(env):
    env.sessions.set_ai_chain_id(CHAT, "r0")
    env.client.responses.create.side_effect = RuntimeError("boom")
    env.handle()
    assert env.bot.sent == [(CHAT, BACKBONE_UNEXPECTED_ERROR)]
    assert env.sessions.get_session(CHAT).ai_chain_id is None


def test_a_long_message_is_cut_in_the_send_itself(env):
    env.client.responses.create.side_effect = [_send("א" * 4500, rid="r1"), _nothing("r2")]
    env.handle()
    assert len(env.bot.sent[0][1]) == 4003 and env.bot.sent[0][1].endswith("...")


def test_the_same_write_run_twice_is_not_flagged_or_annotated(env):
    env.client.responses.create.side_effect = [_send("אחד", rid="r1", call_id="a"),
                                               _send("שניים", rid="r2", call_id="b"), _nothing("r3")]
    env.handle()
    assert [text for _chat, text in env.bot.sent] == ["אחד", "שניים"]
