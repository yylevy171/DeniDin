"""
Integration tests (Feature 063, "resolution" redesign - NOT billed): the
flag-on capability-loading loop end to end with REAL internal components
(Backbone, SessionManager, ReminderManager, LedgerEventManager,
the real idle-reset scheduler) and only the OpenAI SDK boundary mocked
(CONSTITUTION §I/§V). Also proves the FEATURE FLAG boundary: flag off means
no backbone and no reset scheduler; the legacy ai_handler.py never even
mentions the new tools.
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
from src.backbone.backbone import Backbone
from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.reminder_manager import ReminderManager
from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.services.capability_reset_service import (
    CAPABILITY_RESET_JOB_ID, start_capability_reset_scheduler, sweep_idle_capabilities,
)
from src.utils.time_utils import now_local

pytestmark = pytest.mark.integration

PROMPTS = Path(__file__).parent.parent.parent / "config"


# ------------------------------------------------------------------ helpers

def _fc(name, args=None, call_id="c", rid="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None)


def _text(text, rid="rt"):
    return SimpleNamespace(output=[], output_text=text, id=rid, usage=None)


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
    sessions = SessionManager(storage_dir=str(tmp_path / "sessions"))
    reminders = ReminderManager(storage_dir=str(tmp_path / "reminders"))
    ledger = LedgerEventManager(storage_dir=str(tmp_path / "events"))
    locator = SimpleNamespace(current_server_url=lambda: "https://morning.example/mcp")
    client = MagicMock()

    def make(**extra):
        return Backbone(
            client, config, reminder_manager=reminders, ledger_event_manager=ledger,
            session_manager=sessions, morning_mcp_locator=locator, **extra,
        )
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
    ]
    response = env.make().turn_with_rounds(_request(), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert "query_ledger_events" not in _tool_names(kws[0]) and "query_ledger_events" in _tool_names(kws[1])
    tool_output = kws[2]["input"][0]
    assert tool_output["type"] == "function_call_output"
    json.loads(tool_output["output"])  # real LedgerEventManager result is valid JSON
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
    ]
    env.make().turn_with_rounds(_request(), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert "list_reminders" in _tool_names(kws[1])
    assert kws[2]["input"][0]["type"] == "function_call_output"
    assert "לשלם לספק" in kws[2]["input"][0]["output"]


def test_invoicing_write_attaches_shared_never_approval_mcp_entry(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}),
        _fc("approval_with_yes_no_buttons", {"text": "להפיק חשבונית?"}, rid="r2"),
    ]
    response = env.make().turn_with_rounds(_request("תפיק חשבונית"), chat_id="chat1", user_role="godfather")
    kws = _sent_kwargs(env)
    assert _mcp_entry(kws[0]) is None
    entry = _mcp_entry(kws[1])
    assert entry["require_approval"] == "never" and "create_invoice" in entry["allowed_tools"]
    assert entry["headers"]["Authorization"] == "Bearer tok"
    # approval is the plain stateless buttons tool - no pending-approval record
    assert response.offer_approval_buttons is True
    assert response.response_text == "להפיק חשבונית?"


def test_live_button_tap_resolves_as_ordinary_turn_and_capability_stays_loaded(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}),
        _fc("approval_with_yes_no_buttons", {"text": "להפיק?"}, rid="r2"),
        _text("הופקה חשבונית 123.", rid="r3"),  # after "כן" - MCP ran server-side, model just reports
    ]
    orch = env.make()
    orch.turn_with_rounds(_request("תפיק"), chat_id="chat1", user_role="godfather")
    orch.record_approval_message_id("chat1", "STANZA-1")  # what denidin.py does after the buttons send
    tap = orch.resolve_button_tap("chat1", "STANZA-1", _request("כן"), user_role="godfather")
    assert tap.response_text == "הופקה חשבונית 123."
    last = _sent_kwargs(env)[-1]
    assert "create_invoice" in _mcp_entry(last)["allowed_tools"]  # still loaded on the tap turn
    assert env.sessions.get_session("chat1").active_capabilities == ["cap_invoicing_write"]


def test_stale_wrong_stanza_tap_is_ignored_with_no_model_call(env):
    orch = env.make()
    orch.record_approval_message_id("chat1", "STANZA-1")
    assert orch.resolve_button_tap("chat1", "OTHER", _request("כן"), user_role="godfather") is None
    env.client.responses.create.assert_not_called()


def test_tap_with_no_outstanding_approval_is_ignored(env):
    assert env.make().resolve_button_tap("chat1", "ANY", _request("כן"), user_role="godfather") is None
    env.client.responses.create.assert_not_called()


def test_a_second_tap_on_the_same_message_is_stale(env):
    env.client.responses.create.side_effect = [_text("בוצע", rid="r1")]
    orch = env.make()
    orch.record_approval_message_id("chat1", "STANZA-1")
    assert orch.resolve_button_tap("chat1", "STANZA-1", _request("כן"), user_role="godfather") is not None
    assert orch.resolve_button_tap("chat1", "STANZA-1", _request("כן"), user_role="godfather") is None
    assert env.client.responses.create.call_count == 1


def test_any_new_typed_turn_supersedes_outstanding_approval_buttons(env):
    env.client.responses.create.side_effect = [_text("אוקיי", rid="r1")]
    orch = env.make()
    orch.record_approval_message_id("chat1", "STANZA-1")
    orch.turn_with_rounds(_request("כן"), chat_id="chat1", user_role="godfather")  # typed reply
    assert orch.resolve_button_tap("chat1", "STANZA-1", _request("כן"), user_role="godfather") is None


def test_denidin_records_the_sent_buttons_message_id_for_the_backbone(env, monkeypatch):
    orch = env.make()
    sender = MagicMock()
    sender.send_response.return_value = "SENT-ID"
    fake_app = SimpleNamespace(whatsapp_handler=sender, ai_handler=MagicMock(), backbone=orch)
    monkeypatch.setattr(denidin_module, "denidin_app", fake_app)
    denidin_module._send_ai_response_and_attach(MagicMock(), "chat1", MagicMock())  # pylint: disable=protected-access
    assert env.sessions.get_session("chat1").approval_message_id == "SENT-ID"


def test_denidin_records_nothing_when_no_buttons_were_sent(env, monkeypatch):
    orch = env.make()
    sender = MagicMock()
    sender.send_response.return_value = None  # plain-text send
    monkeypatch.setattr(denidin_module, "denidin_app", SimpleNamespace(
        whatsapp_handler=sender, ai_handler=MagicMock(), backbone=orch))
    denidin_module._send_ai_response_and_attach(MagicMock(), "chat1", MagicMock())  # pylint: disable=protected-access
    assert env.sessions.get_session("chat1").approval_message_id is None


def test_approval_message_id_persists_across_restart(env):
    env.make().record_approval_message_id("chat1", "STANZA-1")
    restarted = SessionManager(storage_dir=str(env.tmp_path / "sessions"))
    assert restarted.get_session("chat1").approval_message_id == "STANZA-1"


def test_invoicing_and_client_capabilities_share_one_mcp_entry_with_union(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_invoicing_write"]}, rid="r1"),
        _fc("load_capabilities", {"capabilities": ["cap_client_write"]}, rid="r2"),
        _text("סיימתי", rid="r3"),
    ]
    env.make().turn_with_rounds(_request(), chat_id="chat1", user_role="godfather")
    last = _sent_kwargs(env)[-1]
    mcps = [t for t in last["tools"] if t.get("type") == "mcp"]
    assert len(mcps) == 1
    assert {"create_invoice", "add_client", "update_client"} <= set(mcps[0]["allowed_tools"])


def test_media_analysis_uses_already_extracted_result_without_real_ai(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_media_analysis"]}),
        _fc("analyze_media", {}, rid="r2"),
        _fc("send_to_user", {"text": "זה קבלה"}, rid="r3"),
    ]
    env.make().turn_with_rounds(
        _request("מה זה"), chat_id="chat1", user_role="godfather",
        is_media=True, media_extraction={"extracted_text": "קבלה 500", "document_analysis": {"k": 1}},
    )
    kws = _sent_kwargs(env)
    assert "analyze_media" in _tool_names(kws[1])
    assert "קבלה 500" in kws[2]["input"][0]["output"]


def test_docx_write_tools_attached_when_loaded(env):
    fee = MagicMock()
    fee.build_tools.return_value = [{"type": "function", "name": "get_fee_agreement_template"}]
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_docx_write"]}),
        _text("ok", rid="r2"),
    ]
    env.make(fee_agreement_tools=fee, whatsapp_handler=MagicMock()).turn_with_rounds(
        _request(), chat_id="chat1", user_role="godfather")
    assert "get_fee_agreement_template" in _tool_names(_sent_kwargs(env)[1])


# ------------------------------------------------- persistence + idle reset

def test_loaded_set_survives_restart_then_idle_reset_clears_it_for_the_next_turn(env):
    env.client.responses.create.side_effect = [
        _fc("load_capabilities", {"capabilities": ["cap_reminders_write"]}),
        _fc("send_to_user", {"text": "נטען"}, rid="r2"),
    ]
    env.make().turn_with_rounds(_request(), chat_id="chat1", user_role="godfather")

    restarted = SessionManager(storage_dir=str(env.tmp_path / "sessions"))
    assert restarted.get_session("chat1").active_capabilities == ["cap_reminders_write"]

    assert sweep_idle_capabilities(restarted, 60, now=now_local() + timedelta(minutes=61)) == 1

    env.client.responses.create.side_effect = [_fc("send_to_user", {"text": "שלום"}, rid="r3")]
    Backbone(env.client, env.config, session_manager=restarted).turn_with_rounds(
        _request("היי"), chat_id="chat1", user_role="godfather")
    kw = _sent_kwargs(env)[-1]
    assert "(none - plain backbone)" in kw["instructions"] and "create_reminder" not in _tool_names(kw)


def test_real_scheduler_fires_and_clears_idle_chat_but_not_active_one(env):
    env.sessions.set_active_capabilities("idle", ["cap_reminders_write"])
    env.sessions.set_active_capabilities("active", ["cap_ledger_query"])
    idle = env.sessions.get_session("idle")
    idle.last_active = (now_local() - timedelta(minutes=90)).isoformat()
    env.sessions._save_session(idle)  # pylint: disable=protected-access

    ctx = SimpleNamespace(ai_handler=SimpleNamespace(session_manager=env.sessions))
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
    fresh = SessionManager(storage_dir=str(env.tmp_path / "sessions"))
    assert fresh.get_session("idle").active_capabilities == []


# -------------------------------------------------------- the FEATURE FLAG

def _app_config(tmp_path, flag, reset_minutes):
    return {
        "green_api_instance_id": "1234567890", "green_api_token": "t", "ai_api_key": "sk-test",
        "ai_model": "gpt-5.6-luna", "ai_vision_model": "gpt-5.6-luna",
        "ai_embedding_model": "text-embedding-3-large", "ai_reply_max_tokens": 1000,
        "log_level": "INFO", "data_root": str(tmp_path / "data"),
        "feature_flags": {"enable_capability_backbone": flag},
        "capabilities_reset_minutes": reset_minutes,
        "memory": {}, "constitution_config": {}, "backbone_config": {}, "user_roles": {},
    }


def test_flag_off_never_starts_reset_scheduler_even_with_minutes_configured(tmp_path):
    app = denidin_module.initialize_app(_app_config(tmp_path, False, 30))
    assert app.backbone is None
    assert denidin_module.start_capability_reset_if_enabled(app) is None


def test_flag_on_with_zero_minutes_starts_nothing(tmp_path):
    app = denidin_module.initialize_app(_app_config(tmp_path, True, 0))
    assert app.backbone is not None
    assert denidin_module.start_capability_reset_if_enabled(app) is None


def test_flag_on_with_minutes_starts_the_single_sweep_job(tmp_path):
    app = denidin_module.initialize_app(_app_config(tmp_path, True, 30))
    scheduler = denidin_module.start_capability_reset_if_enabled(app)
    try:
        assert scheduler is not None
        assert [j.id for j in scheduler.get_jobs()] == [CAPABILITY_RESET_JOB_ID]
    finally:
        scheduler.shutdown(wait=False)


def test_legacy_ai_handler_source_is_untouched_by_the_new_mechanism():
    text = (Path(__file__).parent.parent.parent / "src" / "handlers" / "ai_handler.py").read_text(encoding="utf-8")
    for token in ("load_capabilities", "unload_capabilities", "reset_to_backbone", "active_capabilities",
                  "load_flows", "unload_flows", "active_flows", "capabilities_reset_minutes"):
        assert token not in text


def test_every_capability_tag_is_loadable_end_to_end(env):
    """Each tag can be loaded through the real loop and lands in the persisted set."""
    for tag in CapabilityTag:
        env.client.responses.create.side_effect = [_fc("load_capabilities", {"capabilities": [tag.value]}), _text("ok")]
        env.make(fee_agreement_tools=MagicMock(build_tools=lambda u: []),
                 whatsapp_handler=MagicMock()).turn_with_rounds(_request(chat=f"c-{tag.value}"),
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
    ]
    env.make(whatsapp_handler=MagicMock()).turn_with_rounds(_request(), chat_id="chat1", user_role="godfather")
    first, second, third = _sent_kwargs(env)
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
        env.client.responses.create.side_effect = [_fc("load_flows", {"flows": [flow.value]}), _text("ok")]
        env.make(whatsapp_handler=MagicMock()).turn_with_rounds(
            _request(chat=f"f-{flow.value}"), chat_id=f"f-{flow.value}", user_role="godfather")
        assert env.sessions.get_session(f"f-{flow.value}").active_flows == [flow.value]
        assert f"# Flow:" in _sent_kwargs(env)[-1]["instructions"]
