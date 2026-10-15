"""
Integration tests (Feature 063, "resolution" redesign - NOT billed): the
flag-on capability-loading loop end to end with REAL internal components
(Backbone, DeniDin, WhatsAppHandler, SessionManager, ReminderManager, LedgerEventManager,
the real idle-reset scheduler) and only the OpenAI SDK boundary mocked
(CONSTITUTION §I/§V). Also proves the idle-reset scheduler starts only when configured.
"""
import json
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

import denidin as denidin_module
from src.backbone.capability_tags import CapabilityTag
from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.reminder_manager import ReminderManager
from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest
from src.services.capability_reset_service import (
    CAPABILITY_RESET_JOB_ID, start_capability_reset_scheduler, sweep_idle_capabilities,
)
from src.utils.time_utils import now_local
from tests.backbone_test_support import FakeBot, make_backbone
from tests.denidin_test_support import make_ledger_event_manager, make_reminder_manager, make_session_manager

pytestmark = pytest.mark.integration

PROMPTS = Path(__file__).parent.parent.parent / "config"


# ------------------------------------------------------------------ helpers

def _fc(name, args=None, call_id="c", rid="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None)


def _text(text, rid="rt"):
    """The model's final reply - always a send_to_user call (2026-09-30: plain text is
    never sent to the user)."""
    return _fc("send_to_user", {"text": text}, call_id="c-reply", rid=rid)


def _end(rid="r-end"):
    """A model response with no tool call: the app pauses."""
    return SimpleNamespace(output=[], output_text="", id=rid, usage=None)


def _tap(chat="chat1"):
    """The tapped buttons message's sender/chat details, as WhatsAppMessage carries them."""
    return SimpleNamespace(chat_id=chat, sender_id=chat, message_id="TAP-1",
                           sender_display_name="Tester", is_group=False, chat_name=None)


def _request(text="שלום", chat="chat1"):
    return AIRequest(user_prompt=text, constitution="", max_tokens=500, model="m",
                     chat_id=chat, message_id="m1")


def _tool_names(kwargs):
    return {t.get("name") or t.get("type") for t in kwargs["tools"]}


def _mcp_entry(kwargs):
    return next((t for t in kwargs["tools"] if t.get("type") == "mcp"), None)


@pytest.fixture
def env(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(PROMPTS)},
        mcp={"morning_auth_token": "tok"},
    )
    sessions = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    reminders = make_reminder_manager(storage_dir=str(tmp_path / "reminders"))
    ledger = make_ledger_event_manager(storage_dir=str(tmp_path / "events"))
    locator = SimpleNamespace(current_server_url=lambda: "https://morning.example/mcp")
    client = MagicMock()

    def make(**extra):
        backbone = make_backbone(
            client, config, reminder_manager=reminders, ledger_event_manager=ledger,
            session_manager=sessions, morning_mcp_locator=locator, **extra,
        )
        backbone.denidin.green_api_bot = FakeBot()
        return backbone
    return SimpleNamespace(config=config, sessions=sessions, reminders=reminders, ledger=ledger,
                           client=client, make=make, tmp_path=tmp_path)


def _sent_kwargs(env):
    return [c.kwargs for c in env.client.responses.create.call_args_list]


# ------------------------------------------- each capability, real components

def test_ledger_query_loaded_then_real_manager_queried(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_ledger_query"]}),
        _fc("query_ledger_events", {"criteria": [{"text": "יוסי", "hint": "identity"}]}, rid="r2"),
        _fc("send_to_user", {"text": "לא נמצא"}, rid="r3"),
        _end("r4"),
    ]
    orch = env.make()
    response = orch.handle_message(_request(), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert "query_ledger_events" not in _tool_names(kws[0]) and "query_ledger_events" in _tool_names(kws[1])
    tool_output = kws[2]["input"][0]
    assert tool_output["type"] == "function_call_output"
    json.loads(tool_output["output"])  # real LedgerEventManager result is valid JSON
    assert orch.denidin.green_api_bot.sent_texts == ["לא נמצא"]
    assert response.response_text == "לא נמצא"


def test_reminders_read_lists_real_reminders(env):
    env.reminders.create_reminder(
        message_text="לשלם לספק", schedule_type="one_time", one_time_due_at="2099-01-01T09:00:00+02:00",
        recurrence=None, created_by_phone="972500000000", created_by_role="godfather",
        delivery_chat_id="chat1",
    )
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_reminders_read"]}),
        _fc("list_reminders", {}, rid="r2"),
        _fc("send_to_user", {"text": "הנה"}, rid="r3"),
        _end("r4"),
    ]
    env.make().handle_message(_request(), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert "list_reminders" in _tool_names(kws[1])
    assert kws[2]["input"][0]["type"] == "function_call_output"
    assert "לשלם לספק" in kws[2]["input"][0]["output"]


def test_invoicing_write_attaches_its_never_approval_mcp_entry(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}),
        _fc("approval_with_yes_no_buttons", {"text": "להפיק חשבונית?"}, rid="r2"),
        _end("r3"),
    ]
    orch = env.make()
    response = orch.handle_message(_request("תפיק חשבונית"), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert _mcp_entry(kws[0]) is None
    entry = _mcp_entry(kws[1])
    assert entry["require_approval"] == "never" and "create_invoice" in entry["allowed_tools"]
    assert entry["headers"]["Authorization"] == "Bearer tok"
    # approval is the plain buttons tool: sent at once, its message id kept on the chat
    assert [b[1] for b in orch.denidin.green_api_bot.buttons] == ["להפיק חשבונית?"]
    assert response.offer_approval_buttons is True


def test_live_button_tap_resolves_as_an_approved_write_and_capability_stays_loaded(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}),
        _fc("approval_with_yes_no_buttons", {"text": "להפיק?"}, rid="r2"),
        _end("r2b"),
    ]
    # After "כן" - the approved-write call: never retried, so it goes through
    # client.with_options(max_retries=0); create_invoice ran server-side once and the
    # model reports it.
    reply = _text("הופקה חשבונית 123.", rid="r3")
    reply.output.insert(0, SimpleNamespace(type="mcp_call", name="create_invoice", arguments="{}",
                                           output="{\"number\": 123}", error=None))
    approved_create = env.client.with_options.return_value.responses.create
    approved_create.side_effect = [reply, _end("r4")]
    orch = env.make()
    orch.handle_message(_request("תפיק"), chat_id="chat1", user_role="godfather")
    assert env.sessions.get_session("chat1").approval_message_id == "BTN1"  # set when the buttons were sent
    tap = orch.resolve_button_tap(_tap("chat1"), "denidin_approve", "BTN1", user_role="godfather")
    assert orch.denidin.green_api_bot.sent_texts[0] == "הופקה חשבונית 123."
    assert [c["name"] for c in tap.mcp_calls] == ["create_invoice"]
    env.client.with_options.assert_called_with(max_retries=0)
    last = approved_create.call_args_list[0].kwargs
    assert "create_invoice" in _mcp_entry(last)["allowed_tools"]  # still loaded on the tap
    assert env.sessions.get_session("chat1").active_capabilities == ["cap_invoicing_write"]


def test_stale_wrong_stanza_tap_is_ignored_with_no_model_call(env):
    orch = env.make()
    env.sessions.set_approval_message_id("chat1", "STANZA-1")
    assert orch.resolve_button_tap(_tap("chat1"), "denidin_approve", "OTHER", user_role="godfather") is None
    env.client.responses.create.assert_not_called()


def test_tap_with_no_outstanding_approval_is_ignored(env):
    assert env.make().resolve_button_tap(_tap("chat1"), "denidin_approve", "ANY", user_role="godfather") is None
    env.client.responses.create.assert_not_called()


def test_a_second_tap_on_the_same_message_is_stale(env):
    # A live "כן" tap is an approved-write call - it goes through
    # client.with_options(max_retries=0).
    approved_create = env.client.with_options.return_value.responses.create
    approved_create.side_effect = [_text("בוצע", rid="r1"), _end("r2")]
    orch = env.make()
    env.sessions.set_approval_message_id("chat1", "STANZA-1")
    assert orch.resolve_button_tap(_tap("chat1"), "denidin_approve", "STANZA-1", user_role="godfather") is not None
    assert orch.resolve_button_tap(_tap("chat1"), "denidin_approve", "STANZA-1", user_role="godfather") is None
    assert approved_create.call_count == 2  # the one tap's two calls (the reply, then the pause)


def test_a_typed_yes_answers_the_outstanding_approval_so_its_buttons_go_stale(env):
    approved_create = env.client.with_options.return_value.responses.create
    approved_create.side_effect = [_text("אוקיי", rid="r1"), _end("r2")]
    orch = env.make()
    env.sessions.set_approval_message_id("chat1", "STANZA-1")
    orch.handle_message(_request("כן"), chat_id="chat1", user_role="godfather")  # typed reply
    assert env.sessions.get_session("chat1").approval_message_id is None
    assert orch.resolve_button_tap(_tap("chat1"), "denidin_approve", "STANZA-1", user_role="godfather") is None


def test_buttons_sent_by_deni_din_store_their_message_id_on_the_chat(env):
    orch = env.make()
    assert orch.denidin.send_approval_buttons("chat1", "לאשר?") is True
    assert env.sessions.get_session("chat1").approval_message_id == "BTN1"


def test_approval_message_id_persists_across_restart(env):
    env.sessions.set_approval_message_id("chat1", "STANZA-1")
    restarted = make_session_manager(storage_dir=str(env.tmp_path / "sessions"))
    assert restarted.get_session("chat1").approval_message_id == "STANZA-1"


def test_each_morning_capability_gets_its_own_fixed_mcp_entry(env):
    """2026-10-01 (T1): a Morning capability loaded mid-turn adds its OWN entry
    (own server_label, fixed tools); entries already sent never change - OpenAI
    lists a label's tools only once per chain."""
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}, rid="r1"),
        _fc("load_capabilities", {"capabilities": ["cap_client_write"]}, rid="r2"),
        _text("סיימתי", rid="r3"),
        _end("r4"),
    ]
    env.make().handle_message(_request(), chat_id="chat1", user_role="godfather")
    sent = _sent_kwargs(env)
    second = {t["server_label"]: t for t in sent[1]["tools"] if t.get("type") == "mcp"}
    last = {t["server_label"]: t for t in sent[-1]["tools"] if t.get("type") == "mcp"}
    assert set(second) == {"morning-invoices-invoicing-write"}
    assert set(last) == {"morning-invoices-invoicing-write", "morning-invoices-client-write"}
    assert last["morning-invoices-invoicing-write"] == second["morning-invoices-invoicing-write"]
    assert set(last["morning-invoices-client-write"]["allowed_tools"]) == {"add_client", "update_client"}


def test_media_analysis_reads_the_file_attached_to_the_request(env):
    """A media turn's file travels on request.media; analyze_media runs the real
    ImageExtractor on it (its vision call is the third model call) and hands the
    model what was read."""
    vision_reply = SimpleNamespace(
        output=[], id="rv", usage=None,
        output_text=json.dumps({"doc_type": "unknown", "extracted_text": "קבלה 500", "fields": {}}),
    )
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_media_analysis"]}),
        _fc("analyze_media", {}, rid="r2"),
        vision_reply,
        _fc("send_to_user", {"text": "זה קבלה"}, rid="r3"),
        _end("r4"),
    ]
    request = _request("מה זה")
    request.media = Media(data=b"fake jpeg bytes", mime_type="image/jpeg",
                          filename="slip.jpg", media_type="image")
    env.make().handle_message(request, chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert kws[0]["input"][-1]["content"] == "[ATTACHED MEDIA: image, file: slip.jpg]\nמה זה"
    assert "analyze_media" in _tool_names(kws[1])
    assert kws[2]["input"][0]["content"][1]["type"] == "input_image"  # the vision call got the file
    assert "קבלה 500" in kws[3]["input"][0]["output"]


def test_docx_write_tools_attached_when_loaded(env):
    fee = MagicMock()
    fee.build_tools.return_value = [{"type": "function", "name": "get_fee_agreement_template"}]
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_docx_write"]}),
        _text("ok", rid="r2"),
        _end("r3"),
    ]
    env.make(fee_agreement_tools=fee, whatsapp_handler=MagicMock()).handle_message(
        _request(), chat_id="chat1", user_role="godfather")
    assert "get_fee_agreement_template" in _tool_names(_sent_kwargs(env)[1])


# ------------------------------------------------- persistence + idle reset

def test_loaded_set_survives_restart_then_idle_reset_clears_it_for_the_next_turn(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_reminders_write"]}),
        _fc("send_to_user", {"text": "נטען"}, rid="r2"),
        _end("r2b"),
    ]
    env.make().handle_message(_request(), chat_id="chat1", user_role="godfather")

    restarted = make_session_manager(storage_dir=str(env.tmp_path / "sessions"))
    assert restarted.get_session("chat1").active_capabilities == ["cap_reminders_write"]

    assert sweep_idle_capabilities(restarted, 60, now=now_local() + timedelta(minutes=61)) == 1

    env.client.responses.create.side_effect = [_fc("send_to_user", {"text": "שלום"}, rid="r3"), _end("r3b")]
    make_backbone(env.client, env.config, session_manager=restarted).handle_message(
        _request("היי"), chat_id="chat1", user_role="godfather")
    kw = _sent_kwargs(env)[-1]
    assert "(none - plain backbone)" in kw["instructions"] and "create_reminder" not in _tool_names(kw)


def test_real_scheduler_fires_and_clears_idle_chat_but_not_active_one(env):
    env.sessions.set_active_capabilities("idle", ["cap_reminders_write"])
    env.sessions.set_active_capabilities("active", ["cap_ledger_query"])
    idle = env.sessions.get_session("idle")
    idle.last_active = (now_local() - timedelta(minutes=90)).isoformat()
    env.sessions._save_session(idle)  # pylint: disable=protected-access

    ctx = SimpleNamespace(session_manager=env.sessions)
    scheduler = start_capability_reset_scheduler(ctx, 60, trigger=IntervalTrigger(seconds=1))
    try:
        assert [j.id for j in scheduler.get_jobs()] == [CAPABILITY_RESET_JOB_ID]
        deadline = time.time() + 10
        while time.time() < deadline and env.sessions.get_session("idle").active_capabilities:
            time.sleep(0.2)
    finally:
        scheduler.shutdown(wait=False)
    assert env.sessions.get_session("idle").active_capabilities == []
    assert env.sessions.get_session("active").active_capabilities == ["cap_ledger_query"]
    # durable: a fresh manager on the same directory agrees
    fresh = make_session_manager(storage_dir=str(env.tmp_path / "sessions"))
    assert fresh.get_session("idle").active_capabilities == []


# ------------------------------------------------ the idle-reset scheduler

def _app_config(tmp_path, reset_minutes):
    return {
        "green_api_instance_id": "1234567890", "green_api_token": "t", "ai_api_key": "sk-test",
        "ai_model": "gpt-5.6-luna", "ai_vision_model": "gpt-5.6-luna",
        "ai_embedding_model": "text-embedding-3-large", "ai_reply_max_tokens": 1000,
        "log_level": "INFO", "data_root": str(tmp_path / "data"),
        "capabilities_reset_minutes": reset_minutes,
        # longterm storage_dir does not follow data_root - keep ChromaDB in tmp too
        "memory": {"longterm": {"storage_dir": str(tmp_path / "data" / "memory")}},
        "backbone_config": {}, "user_roles": {},
    }


def test_zero_minutes_starts_nothing(tmp_path):
    app = denidin_module.initialize_app(_app_config(tmp_path, 0))
    assert denidin_module.start_capability_reset_if_enabled(app) is None


def test_minutes_configured_starts_the_single_sweep_job(tmp_path):
    app = denidin_module.initialize_app(_app_config(tmp_path, 30))
    scheduler = denidin_module.start_capability_reset_if_enabled(app)
    try:
        assert scheduler is not None
        assert [j.id for j in scheduler.get_jobs()] == [CAPABILITY_RESET_JOB_ID]
    finally:
        scheduler.shutdown(wait=False)


def test_every_capability_tag_is_loadable_end_to_end(env):
    """Each tag can be loaded through the real loop and lands in the persisted set."""
    for tag in CapabilityTag:
        env.client.responses.create.side_effect = [_fc("load_capabilities", {"capabilities": [tag.value]}), _text("ok"), _end()]
        env.make(fee_agreement_tools=MagicMock(build_tools=lambda u: []),
                 whatsapp_handler=MagicMock()).handle_message(_request(chat=f"c-{tag.value}"),
                                                            chat_id=f"c-{tag.value}", user_role="godfather")
        assert env.sessions.get_session(f"c-{tag.value}").active_capabilities == [tag.value]


# ------------------------------------------- flows (real prompt files)

def test_flow_then_its_capabilities_loaded_together_end_to_end(env):
    """The model loads a flow, then the capabilities it names, in ONE call (plural):
    the real flow blueprint and the real capability prompts/tools are all attached,
    and both sets persist in the session."""
    env.client.responses.create.side_effect = [
        _fc("load_flows", {"flows": ["flow_issue_invoice_for_payment_due"]}, rid="r1"),
        _fc("load_capabilities", {"capabilities": ["cap_client_read", "cap_invoicing_write"]}, rid="r2"),
        _text("ok"),
        _end(),
    ]
    env.make().handle_message(_request(), chat_id="chat1", user_role="godfather")
    first, second, third = _sent_kwargs(env)[:3]
    assert "# Flow: Issue invoice for payment due" not in first["instructions"]
    assert "# Flow: Issue invoice for payment due" in second["instructions"]
    assert "## Loaded flows\n\nflow_issue_invoice_for_payment_due" in third["instructions"]
    assert "cap_invoicing_write, cap_client_read" in third["instructions"]
    assert _mcp_entry(third) is not None
    session = env.sessions.get_session("chat1")
    assert session.active_flows == ["flow_issue_invoice_for_payment_due"]
    assert session.active_capabilities == ["cap_client_read", "cap_invoicing_write"]


def test_every_flow_tag_is_loadable_end_to_end(env):
    from src.backbone.flow_tags import FlowTag
    for flow in FlowTag:
        env.client.responses.create.side_effect = [_fc("load_flows", {"flows": [flow.value]}), _text("ok"), _end()]
        env.make().handle_message(
            _request(chat=f"f-{flow.value}"), chat_id=f"f-{flow.value}", user_role="godfather")
        assert env.sessions.get_session(f"f-{flow.value}").active_flows == [flow.value]
        assert f"# Flow:" in _sent_kwargs(env)[-1]["instructions"]
