"""Unit tests for the flows level (Feature 063): load_flows/unload_flows and the
plural load_capabilities/unload_capabilities mutate SESSION-PERSISTED sets, every
round rebuilds instructions (flow blueprints + capability prompts) and tools from
them, reset_to_backbone and the idle sweep clear BOTH sets, and every
load/unload/reset is audit- and debug-logged with the resulting sets."""
import json
import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import ALWAYS_PRESENT_CAPABILITIES, CapabilityTag
from src.backbone.flow_tags import FLOW_INFO, FlowTag, flow_catalog_text
from src.backbone.orchestration_tools import ORCHESTRATION_TOOLS
from src.backbone.orchestrator import BackboneOrchestrator
from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.services.capability_reset_service import sweep_idle_capabilities
from src.utils.time_utils import now_local


@pytest.fixture
def env(tmp_path):
    base = tmp_path / "config"
    prompts = base / "prompts"
    (prompts / "capabilities").mkdir(parents=True)
    (prompts / "flows").mkdir(parents=True)
    (prompts / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    for tag in CapabilityTag:
        (prompts / "capabilities" / f"{tag.value}.md").write_text(f"CAP[{tag.value}]", encoding="utf-8")
    for name in ALWAYS_PRESENT_CAPABILITIES:
        (prompts / "capabilities" / f"{name}.md").write_text(f"ALWAYS[{name}]", encoding="utf-8")
    for flow in FlowTag:
        (prompts / "flows" / f"{flow.value}.md").write_text(f"FLOW[{flow.value}]", encoding="utf-8")
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base)},
    )
    return SimpleNamespace(config=config, sessions=SessionManager(storage_dir=str(tmp_path / "sessions")))


def _call(name, args=None, resp_id="r"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=f"c-{resp_id}")
    return SimpleNamespace(output=[item], output_text="", id=resp_id, usage=None)


def _request():
    return AIRequest(user_prompt="שלום", constitution="", max_tokens=500, model="m", chat_id="chat1", message_id="m1")


def _orch(env, client=None):
    return BackboneOrchestrator(client or MagicMock(), env.config, session_manager=env.sessions)


def test_flow_tools_are_offered_and_plural():
    by_name = {t["name"]: t for t in ORCHESTRATION_TOOLS}
    assert {"load_flows", "unload_flows", "load_capabilities", "unload_capabilities"} <= set(by_name)
    assert "load_capability" not in by_name and "unload_capability" not in by_name
    assert by_name["load_flows"]["parameters"]["properties"]["flows"]["type"] == "array"
    assert by_name["load_capabilities"]["parameters"]["properties"]["capabilities"]["type"] == "array"


def test_every_flow_has_a_multi_sentence_description_and_a_prompt_file():
    from pathlib import Path
    flows_dir = Path(__file__).parent.parent.parent / "config" / "prompts" / "flows"
    assert {i.tag for i in FLOW_INFO} == set(FlowTag)
    for info in FLOW_INFO:
        assert info.description.count(".") >= 2, info.tag
        assert (flows_dir / f"{info.tag.value}.md").is_file(), info.tag
    assert flow_catalog_text(list(FlowTag)).count("\n") == len(FlowTag) - 1


def test_load_several_flows_and_capabilities_at_once_and_persist(env):
    orch = _orch(env)
    result = orch._dispatch_orchestration_tool(
        "load_flows", {"flows": ["flow_add_client", "flow_issue_invoice_for_payment_due", "flow_add_client"]}, "c")
    assert "flow_add_client, flow_issue_invoice_for_payment_due" in result
    orch._dispatch_orchestration_tool("load_capabilities", {"capabilities": ["cap_client_read", "cap_client_write"]}, "c")
    session = env.sessions.get_session("c")
    assert session.active_flows == ["flow_add_client", "flow_issue_invoice_for_payment_due"]
    assert session.active_capabilities == ["cap_client_read", "cap_client_write"]


def test_unknown_names_are_reported_not_silently_dropped(env):
    orch = _orch(env)
    result = orch._dispatch_orchestration_tool("load_flows", {"flows": ["bogus", "flow_add_client"]}, "c")
    assert "unknown flow(s) ignored: bogus" in result
    assert orch._get_active_flows("c") == [FlowTag.ADD_CLIENT]


def test_unload_flows_and_capabilities_only_touch_their_own_set(env):
    orch = _orch(env)
    orch._dispatch_orchestration_tool("load_flows", {"flows": ["flow_add_client", "flow_modify_client"]}, "c")
    orch._dispatch_orchestration_tool("load_capabilities", {"capabilities": ["cap_client_read"]}, "c")
    orch._dispatch_orchestration_tool("unload_flows", {"flows": ["flow_add_client"]}, "c")
    assert orch._get_active_flows("c") == [FlowTag.MODIFY_CLIENT]
    assert orch._get_active_tags("c") == [CapabilityTag.CLIENT_READ]
    orch._dispatch_orchestration_tool("unload_capabilities", {"capabilities": ["cap_client_read"]}, "c")
    assert orch._get_active_flows("c") == [FlowTag.MODIFY_CLIENT] and orch._get_active_tags("c") == []


def test_reset_to_backbone_clears_both_sets(env):
    orch = _orch(env)
    orch._dispatch_orchestration_tool("load_flows", {"flows": ["flow_user_question"]}, "c")
    orch._dispatch_orchestration_tool("load_capabilities", {"capabilities": ["cap_ledger_query"]}, "c")
    orch._dispatch_orchestration_tool("reset_to_backbone", {}, "c")
    session = env.sessions.get_session("c")
    assert session.active_flows == [] and session.active_capabilities == []


def test_instructions_carry_flow_catalog_loaded_flow_blueprints_and_lines(env):
    orch = _orch(env)
    plain = orch.build_instructions(None)
    assert "## Flows" in plain and "flow_issue_invoice_for_payment_due:" in plain and "FLOW[" not in plain
    assert "## Loaded flows\n\n(none)" in plain
    loaded = orch.build_instructions([CapabilityTag.CLIENT_READ], active_flows=[FlowTag.ADD_CLIENT])
    assert "FLOW[flow_add_client]" in loaded and "CAP[cap_client_read]" in loaded
    assert loaded.index("FLOW[flow_add_client]") < loaded.index("CAP[cap_client_read]")
    assert "## Loaded flows\n\nflow_add_client" in loaded


def test_flows_persist_across_turns_and_rebuild_every_round(env):
    client = MagicMock()
    client.responses.create.side_effect = [
        _call("load_flows", {"flows": ["flow_add_client"]}, "r1"),
        _call("send_to_user", {"text": "x"}, "r2"),
    ]
    _orch(env, client).get_response(_request(), chat_id="chat1", user_role="godfather")
    first, second = (c.kwargs for c in client.responses.create.call_args_list)
    assert "FLOW[flow_add_client]" not in first["instructions"] and "FLOW[flow_add_client]" in second["instructions"]

    client2 = MagicMock()
    client2.responses.create.return_value = _call("send_to_user", {"text": "y"})
    _orch(env, client2).get_response(_request(), chat_id="chat1", user_role="godfather")
    assert "FLOW[flow_add_client]" in client2.responses.create.call_args.kwargs["instructions"]


def test_idle_sweep_clears_flows_too(env):
    env.sessions.get_session("idle")
    env.sessions.set_active_flows("idle", ["flow_add_client"])
    assert sweep_idle_capabilities(env.sessions, 60, now=now_local() + timedelta(minutes=120)) == 1
    assert env.sessions.get_session("idle").active_flows == []


def test_loading_actions_are_audit_and_debug_logged_with_reasoning(env, caplog):
    caplog.set_level(logging.DEBUG)
    orch = _orch(env)
    orch._dispatch_orchestration_tool(
        "record_planning_status",
        {"where_i_was": "start", "this_turns_purpose": "invoice for X", "expectation": "resolve X"}, "c")
    orch._dispatch_orchestration_tool("load_flows", {"flows": ["flow_issue_invoice_for_payment_due"]}, "c")
    orch._dispatch_orchestration_tool("load_capabilities", {"capabilities": ["cap_client_read"]}, "c")
    orch._dispatch_orchestration_tool("reset_to_backbone", {}, "c")
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and "[FLOW-AUDIT]" in r.getMessage()]
    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG and "[FLOW-DEBUG]" in r.getMessage()]
    assert len(info) == 3 and len(debug) == 3
    assert "action='load' kind='flow' requested=['flow_issue_invoice_for_payment_due']" in info[0]
    assert "invoice for X" in info[0]
    assert "capabilities_now=['cap_client_read']" in info[1]
    assert "action='reset' kind='all'" in info[2]
    assert "loaded flows (1)=['flow_issue_invoice_for_payment_due']" in debug[0]
