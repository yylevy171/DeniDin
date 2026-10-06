"""Unit tests for the "resolution" capability-loading mechanism (2026-09-24):
load_capabilities/unload_capabilities/reset_to_backbone mutate a SESSION-PERSISTED
set; every API round (first AND follow-up) rebuilds BOTH instructions and tools
from it; it survives across separate get_response() calls; and there is no
a separate "use" step anywhere."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.managers.reminder_manager import ReminderManager
from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.services.capability_reset_service import sweep_idle_capabilities
from src.utils.time_utils import now_local
from tests.backbone_test_support import make_backbone
from tests.denidin_test_support import make_reminder_manager, make_session_manager


@pytest.fixture
def env(tmp_path):
    base = tmp_path / "config"
    caps = base / "prompts" / "capabilities"
    caps.mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    for tag in CapabilityTag:
        (caps / f"{tag.value}.md").write_text(f"PROMPT[{tag.value}]", encoding="utf-8")
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base)},
    )
    sessions = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    reminders = make_reminder_manager(storage_dir=str(tmp_path / "reminders"))
    return SimpleNamespace(config=config, sessions=sessions, reminders=reminders)


def _call(name, args=None, call_id="c1", resp_id="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=resp_id, usage=None)


def _request(text="שלום"):
    return AIRequest(user_prompt=text, constitution="", max_tokens=500, model="m", chat_id="chat1", message_id="m1")


def _orch(env, client):
    return make_backbone(
        client, env.config, reminder_manager=env.reminders, session_manager=env.sessions,
    )


def _tool_names(kwargs):
    return {t.get("name") or t.get("type") for t in kwargs["tools"]}


def test_load_attaches_prompt_and_tools_to_the_very_next_round(env):
    client = MagicMock()
    client.responses.create.side_effect = [
        _call("load_capabilities", {"capabilities": ["cap_reminders_write"]}),
        _call("create_reminder", {"message_text": "לשלם", "schedule_type": "one_time", "one_time_due_at": "2099-01-01T09:00:00", "recurrence": None}, resp_id="r2"),
        _call("send_to_user", {"text": "בוצע"}, resp_id="r3"),
    ]
    orch = _orch(env, client)
    response = orch.single_turn(_request(), chat_id="chat1", user_role="godfather")

    first, second, third = [c.kwargs for c in client.responses.create.call_args_list]
    assert "PROMPT[cap_reminders_write]" not in first["instructions"] and "create_reminder" not in _tool_names(first)
    assert "(none - plain backbone)" in first["instructions"]
    # round 2 AND 3: BOTH prompt and tools present (rebuilt each round, not just once)
    for kw in (second, third):
        assert "PROMPT[cap_reminders_write]" in kw["instructions"]
        assert "create_reminder" in _tool_names(kw)
    assert response.response_text == "בוצע"
    assert len(env.reminders.list_active()) == 1


def test_loaded_set_persists_on_the_session_and_across_turns(env):
    client = MagicMock()
    client.responses.create.side_effect = [
        _call("load_capabilities", {"capabilities": ["cap_reminders_write"]}),
        _call("send_to_user", {"text": "נטען"}, resp_id="r2"),
        # second, separate get_response(): the model does NOT re-load anything
        _call("send_to_user", {"text": "שוב"}, resp_id="r3"),
    ]
    orch = _orch(env, client)
    orch.single_turn(_request(), chat_id="chat1", user_role="godfather")
    assert env.sessions.get_session("chat1").active_capabilities == ["cap_reminders_write"]

    orch.single_turn(_request("עוד"), chat_id="chat1", user_role="godfather")
    third = client.responses.create.call_args_list[2].kwargs
    assert "PROMPT[cap_reminders_write]" in third["instructions"] and "create_reminder" in _tool_names(third)


def test_state_survives_a_process_restart(env, tmp_path):
    env.sessions.set_active_capabilities("chat1", ["cap_ledger_query"])
    restarted = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    client = MagicMock()
    client.responses.create.return_value = _call("send_to_user", {"text": "ok"})
    make_backbone(client, env.config, session_manager=restarted).single_turn(
        _request(), chat_id="chat1", user_role="godfather")
    first = client.responses.create.call_args_list[0].kwargs
    assert "PROMPT[cap_ledger_query]" in first["instructions"] and "query_ledger_events" in _tool_names(first)


def test_capabilities_accumulate_then_unload_one_then_reset_all(env):
    client = MagicMock()
    client.responses.create.side_effect = [
        _call("load_capabilities", {"capabilities": ["cap_reminders_write"]}, resp_id="r1"),
        _call("load_capabilities", {"capabilities": ["cap_ledger_query"]}, resp_id="r2"),
        _call("unload_capabilities", {"capabilities": ["cap_reminders_write"]}, resp_id="r3"),
        _call("reset_to_backbone", {}, resp_id="r4"),
        _call("send_to_user", {"text": "סיימתי"}, resp_id="r5"),
    ]
    orch = _orch(env, client)
    orch.single_turn(_request(), chat_id="chat1", user_role="godfather")
    kws = [c.kwargs for c in client.responses.create.call_args_list]

    assert "create_reminder" in _tool_names(kws[2]) and "query_ledger_events" in _tool_names(kws[2])  # both loaded
    assert "cap_ledger_query, cap_reminders_write" in kws[2]["instructions"]
    assert "create_reminder" not in _tool_names(kws[3]) and "query_ledger_events" in _tool_names(kws[3])  # one unloaded
    assert "create_reminder" not in _tool_names(kws[4]) and "query_ledger_events" not in _tool_names(kws[4])  # reset
    assert env.sessions.get_session("chat1").active_capabilities == []


def test_load_is_idempotent_and_rejects_unknown_tags(env):
    orch = _orch(env, MagicMock())
    assert "loaded" in orch._dispatch_resolution_tool("load_capabilities", {"capabilities": ["cap_reminders_read"]}, "c")
    orch._dispatch_resolution_tool("load_capabilities", {"capabilities": ["cap_reminders_read"]}, "c")
    assert orch._get_active_tags("c") == [CapabilityTag.REMINDERS_READ]
    assert orch._dispatch_resolution_tool("load_capabilities", {"capabilities": ["bogus"]}, "c")
    assert orch._dispatch_resolution_tool("unload_capabilities", {"capabilities": ["cap_ledger_query"]}, "c").startswith("unloaded")
    assert orch._get_active_tags("c") == [CapabilityTag.REMINDERS_READ]


def test_no_use_capability_tool_is_ever_offered(env):
    client = MagicMock()
    client.responses.create.return_value = _call("send_to_user", {"text": "x"})
    _orch(env, client).single_turn(_request(), chat_id="chat1", user_role="godfather")
    names = _tool_names(client.responses.create.call_args.kwargs)
    assert "use_capability" not in names
    assert {"load_capabilities", "unload_capabilities", "reset_to_backbone"} <= names


# --- idle reset sweep ---------------------------------------------------------

def test_idle_sweep_clears_only_idle_chats_with_loaded_capabilities(env):
    sm = env.sessions
    for chat in ("idle", "fresh", "empty"):
        sm.get_session(chat)
    sm.set_active_capabilities("idle", ["cap_reminders_write"])
    sm.set_active_capabilities("fresh", ["cap_ledger_query"])

    later = now_local() + timedelta(minutes=61)
    # 'fresh' had activity just now relative to `later`
    fresh = sm.get_session("fresh")
    fresh.last_active = (later - timedelta(minutes=5)).isoformat()
    sm._save_session(fresh)  # pylint: disable=protected-access

    assert sweep_idle_capabilities(sm, 60, now=later) == 1
    assert sm.get_session("idle").active_capabilities == []
    assert sm.get_session("fresh").active_capabilities == ["cap_ledger_query"]
    assert sm.get_session("empty").active_capabilities == []


def test_next_turn_after_idle_reset_sees_a_plain_backbone_no_notice_needed(env):
    env.sessions.set_active_capabilities("chat1", ["cap_reminders_write"])
    sweep_idle_capabilities(env.sessions, 60, now=now_local() + timedelta(minutes=120))
    client = MagicMock()
    client.responses.create.return_value = _call("send_to_user", {"text": "hi"})
    _orch(env, client).single_turn(_request(), chat_id="chat1", user_role="godfather")
    first = client.responses.create.call_args.kwargs
    assert "(none - plain backbone)" in first["instructions"] and "create_reminder" not in _tool_names(first)


def test_message_activity_restarts_the_idle_clock(env):
    sm = env.sessions
    sm.set_active_capabilities("chat1", ["cap_reminders_write"])
    session = sm.get_session("chat1")
    session.last_active = (now_local() - timedelta(minutes=90)).isoformat()
    sm._save_session(session)  # pylint: disable=protected-access
    sm.add_message_with_tokens(chat_id="chat1", role="user", content="hello", user_role=None)
    assert sweep_idle_capabilities(sm, 60) == 0
    assert sm.get_session("chat1").active_capabilities == ["cap_reminders_write"]


# --- scheduler wiring + session field ----------------------------------------

def test_reset_scheduler_inactive_at_zero_minutes_and_registers_one_job_otherwise():
    from src.services.capability_reset_service import CAPABILITY_RESET_JOB_ID, start_capability_reset_scheduler
    assert start_capability_reset_scheduler(MagicMock(), 0) is None
    scheduler = start_capability_reset_scheduler(MagicMock(), 60)
    try:
        assert [j.id for j in scheduler.get_jobs()] == [CAPABILITY_RESET_JOB_ID]
    finally:
        scheduler.shutdown(wait=False)


def test_capabilities_reset_minutes_is_a_plain_top_level_config_field_not_a_feature_flag():
    cfg = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        capabilities_reset_minutes=45,
    )
    assert cfg.capabilities_reset_minutes == 45
    assert "capabilities_reset_minutes" not in cfg.feature_flags


def test_old_session_files_without_the_field_load_with_an_empty_set(env):
    session = env.sessions.get_session("legacy")
    assert session.active_capabilities == []
