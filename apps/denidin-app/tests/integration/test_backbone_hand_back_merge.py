"""Feature 067 (REQ-RMH-001/013/014/017/019): at every hand-back the model's next input carries its tool
results AND the user messages that arrived meanwhile. Real Backbone, SessionManager, IntakeCoordinator and
handlers; only the OpenAI SDK boundary is faked (CONSTITUTION §I/§V)."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.intake.intake_coordinator import IntakeCoordinator
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.utils.time_utils import now_local
from tests.backbone_test_support import make_backbone
from tests.denidin_test_support import make_session_manager

pytestmark = pytest.mark.integration

PROMPTS = Path(__file__).parent.parent.parent / "config"
CHAT = "972522968679@c.us"


def _fc(name, args=None, call_id="c", rid="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None)


def _reply(text, rid="rt"):
    return _fc("send_to_user", {"text": text}, call_id="c-reply", rid=rid)


def _event(n, type_message="textMessage", text=None, seconds_ahead=5):
    data = {"textMessage": {"textMessageData": {"textMessage": text or f"msg {n}"}},
            "imageMessage": {"fileMessageData": {"caption": f"cap {n}", "fileName": "slip.jpg"}}}[type_message]
    return {"typeWebhook": "incomingMessageReceived", "idMessage": f"ID{n}",
            "timestamp": int(now_local().timestamp()) + seconds_ahead,
            "senderData": {"chatId": CHAT, "sender": CHAT, "senderName": "Dana"},
            "messageData": {"typeMessage": type_message, **data}}


@pytest.fixture
def env(tmp_path):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(PROMPTS)}, mcp={"morning_auth_token": "tok"},
                              godfather_phone=CHAT)
    sessions = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    client = MagicMock()
    backbone = make_backbone(client, config, session_manager=sessions)
    app = backbone.denidin
    app.intake = IntakeCoordinator(app)

    def queue(event):
        app.intake.submit(app.intake.prepare(SimpleNamespace(event=event)))

    def request(text="תפיק חשבונית"):
        return AIRequest(user_prompt=text, constitution="", max_tokens=500, model="m", chat_id=CHAT,
                         message_id="m0", timestamp=int(now_local().timestamp()))
    yield SimpleNamespace(backbone=backbone, app=app, client=client, queue=queue, request=request, sessions=sessions)
    sessions.close()


def _inputs(env):
    return [c.kwargs["input"] for c in env.client.responses.create.call_args_list]


def _load_then_reply(env, reply="סבבה"):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_ledger_query"]}), _reply(reply, rid="r2")]


def test_messages_waiting_at_a_hand_back_join_the_tool_results_in_order(env):
    _load_then_reply(env)
    env.queue(_event(1, text="ללקוח דנה"))
    env.queue(_event(2, text="על 500 שקל"))
    env.backbone.handle_message(env.request(), chat_id=CHAT, user_role="godfather")
    follow_up = _inputs(env)[1]
    assert follow_up[0]["type"] == "function_call_output"
    assert [i["role"] for i in follow_up[1:]] == ["user", "user"]
    assert "ללקוח דנה" in follow_up[1]["content"] and "על 500 שקל" in follow_up[2]["content"]
    assert all("נשלחה אחרי הפלט האחרון שלך" in i["content"] for i in follow_up[1:])


def test_the_first_message_and_history_carry_timestamps(env):
    _load_then_reply(env)
    env.backbone.handle_message(env.request("שלום"), chat_id=CHAT, user_role="godfather")
    first_input = _inputs(env)[0]
    import re
    assert re.match(r"\[\d\d:\d\d:\d\d \d\d/\d\d\] שלום", first_input[-1]["content"])


def test_nothing_is_attached_on_the_round_that_sends_the_reply(env):
    env.client.responses.create.side_effect = [_reply("תשובה")]
    env.queue(_event(1))
    env.backbone.handle_message(env.request(), chat_id=CHAT, user_role="godfather")
    assert len(_inputs(env)) == 1
    assert env.app.intake.next_work_item(0.01).id_message == "ID1"  # still waiting: handled next


def test_without_an_intake_the_follow_up_input_is_just_the_tool_results(env):
    env.app.intake = None
    _load_then_reply(env)
    env.backbone.handle_message(env.request(), chat_id=CHAT, user_role="godfather")
    follow_up = _inputs(env)[1]
    assert [i.get("type") for i in follow_up] == ["function_call_output"]


def test_media_is_mentioned_to_the_model_and_left_for_its_own_handling(env):
    _load_then_reply(env)
    env.queue(_event(1, "imageMessage"))
    env.backbone.handle_message(env.request(), chat_id=CHAT, user_role="godfather")
    follow_up = _inputs(env)[1]
    assert follow_up[1]["content"].startswith("[קובץ התקבל")
    assert env.app.intake.next_work_item(0.01).id_message == "ID1"  # handled on its own right after


def test_an_approved_write_is_not_interrupted_by_waiting_messages(env):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    # an approved-write handling calls the model without retries (with_options), so that is the client to fake
    create = env.client.with_options.return_value.responses.create
    create.side_effect = [_fc("load_capabilities", {"capabilities": ["cap_ledger_query"]}), _reply("סבבה", rid="r2")]
    env.queue(_event(1, text="רגע, תבטל"))
    env.backbone.handle_message(env.request("כן"), chat_id=CHAT, user_role="godfather")
    follow_up = create.call_args_list[1].kwargs["input"]
    assert [i.get("type") for i in follow_up] == ["function_call_output"]
    assert env.app.intake.next_work_item(0.01).id_message == "ID1"  # handled after


def test_a_no_does_not_block_attaching(env):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    _load_then_reply(env)
    env.queue(_event(1, text="ובעצם משהו אחר"))
    env.backbone.handle_message(env.request("לא"), chat_id=CHAT, user_role="godfather")
    assert len(_inputs(env)[1]) == 2


def test_approval_guard_survives_unrelated_messages(env):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    env.client.responses.create.side_effect = [_reply("אין בעיה")]
    env.backbone.handle_message(env.request("מה השעה?"), chat_id=CHAT, user_role="godfather")
    assert env.sessions.get_session(CHAT).approval_message_id == "BTN-1"


@pytest.mark.parametrize("answer", ["כן", "לא", "yes", "no"])
def test_approval_guard_is_cleared_when_answered(env, answer):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    env.client.responses.create.side_effect = [_reply("בסדר")]
    env.backbone.handle_message(env.request(answer), chat_id=CHAT, user_role="godfather")
    assert env.sessions.get_session(CHAT).approval_message_id is None


def test_a_newer_approval_supersedes_the_old_guard(env):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    env.backbone.record_sent_message_id(CHAT, "BTN-2")
    assert env.sessions.get_session(CHAT).approval_message_id == "BTN-2"


# ---------------------------------------------------------------- long burst (US2)

def test_a_burst_reaches_the_model_once_each_in_order_and_nothing_is_left_behind(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_ledger_query"]}, rid="r1"),
        _fc("load_capabilities", {"capabilities": ["cap_reminders_read"]}, call_id="c2", rid="r2"),
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_read"]}, call_id="c3", rid="r3"),
        _reply("סיימתי", rid="r4"),
    ]
    for n in range(1, 5):
        env.queue(_event(n, text=f"fact {n}"))
    env.backbone.handle_message(env.request("fact 0"), chat_id=CHAT, user_role="godfather")
    # more arrive while the model is still working: queue the rest before its next hand-back
    inputs = _inputs(env)
    first_wave = [i["content"] for i in inputs[1][1:]]
    assert [c.splitlines()[1] for c in first_wave] == ["fact 1", "fact 2", "fact 3", "fact 4"]
    # nothing is attached twice, nothing is left behind
    assert [i.get("type") for i in inputs[2]] == ["function_call_output"]
    assert env.app.intake.next_work_item(0.01) is None


def test_messages_arriving_after_the_reply_become_the_next_handling_not_lost(env):
    env.client.responses.create.side_effect = [_reply("תשובה")]
    env.backbone.handle_message(env.request("א"), chat_id=CHAT, user_role="godfather")
    env.queue(_event(9, text="עוד אחד"))
    item = env.app.intake.next_work_item(0.01)
    assert item.id_message == "ID9" and item.message.text_content == "עוד אחד"


# ---------------------------------------------------------------- history timestamps (REQ-RMH-007)

def test_history_user_items_carry_their_clock_time_assistant_items_do_not(env):
    env.app.store_inbound(SimpleNamespace(
        chat_id=CHAT, sender_id=CHAT, sender_display_name="Dana", text_content="הודעה ישנה", is_group=False,
        chat_name=None, message_id="old-1", whatsapp_id_message="W1", timestamp=int(now_local().timestamp()) - 60))
    env.app.store_outbound(SimpleNamespace(chat_id=CHAT, sender_id=CHAT, sender_display_name="Dana",
                                           is_group=False, chat_name=None), "תשובה ישנה")
    env.client.responses.create.side_effect = [_reply("טוב")]
    env.backbone.handle_message(env.request("חדש"), chat_id=CHAT, user_role="godfather")
    history = _inputs(env)[0][:-1]
    import re
    users = [h["content"] for h in history if h["role"] == "user"]
    assistants = [h["content"] for h in history if h["role"] == "assistant"]
    assert users and re.match(r"\[\d\d:\d\d:\d\d \d\d/\d\d\] הודעה ישנה", users[0])
    assert assistants == ["תשובה ישנה"]


# ---------------------------------------------------------------- group chats (US7)

def test_a_second_group_member_is_attached_with_their_name(env):
    group = "120363000000000000@g.us"
    ev = _event(1, text="עוד פרט")
    ev["senderData"] = {"chatId": group, "sender": CHAT, "senderName": "Yossi"}
    env.app.intake.submit(env.app.intake.prepare(SimpleNamespace(event=ev)))
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_ledger_query"]}), _reply("ok", rid="r2")]
    request = AIRequest(user_prompt="בקשה", constitution="", max_tokens=500, model="m", chat_id=group,
                        message_id="m0", timestamp=int(now_local().timestamp()))
    env.backbone.handle_message(request, chat_id=group, user_role="godfather", is_group=True)
    assert _inputs(env)[1][1]["content"].endswith("[Yossi] עוד פרט")


# ---------------------------------------------------------------- stale-tap guard (US9)

def test_a_button_tap_after_unrelated_chatter_is_honoured_once_then_ignored(env):
    env.sessions.set_approval_message_id(CHAT, "BTN-1")
    env.client.responses.create.side_effect = [_reply("שיחה"), _reply("בוצע")]
    env.backbone.handle_message(env.request("שאלה אחרת"), chat_id=CHAT, user_role="godfather")
    tap = SimpleNamespace(chat_id=CHAT, sender_id=CHAT, message_id="TAP-1", sender_display_name="Dana",
                          is_group=False, chat_name=None)
    first = env.backbone.resolve_button_tap(tap, "denidin_decline", "BTN-1", user_role="godfather")
    second = env.backbone.resolve_button_tap(tap, "denidin_decline", "BTN-1", user_role="godfather")
    assert first is not None and second is None
