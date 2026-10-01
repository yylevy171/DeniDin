"""Unit tests (2026-10-01): the ONE shared tool-call telemetry (core/model_calls.py's
tool_call_span / timed_tool_call / record_mcp_tool_calls), used identically by the legacy
AIHandler and the backbone. The backbone used to record LLM calls only - every
backbone turn had tool_calls_count 0 and slowest_tool_name None, unlike legacy."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone
from src.core.model_calls import record_mcp_tool_calls, timed_tool_call, tool_call_span
from src.managers.telemetry_manager import TelemetryBuilder, TelemetryManager
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from tests.backbone_test_support import make_session_manager


def _builder():
    return TelemetryBuilder("req1", "chat1", "2026-10-01T10:00:00+03:00")


def test_timed_tool_call_records_one_call_and_returns_the_result():
    builder = _builder()
    assert timed_tool_call(builder, "local_tools", lambda: 42) == 42
    record = builder.finalize("2026-10-01T10:00:01+03:00")
    assert record.tool_calls_count == 1
    assert record.slowest_tool_name == "local_tools"
    assert record.morning_api_request_times_ms is None


def test_tool_call_span_records_even_when_the_block_raises():
    builder = _builder()
    with pytest.raises(RuntimeError):
        with tool_call_span(builder, "local_tools"):
            raise RuntimeError("boom")
    assert builder.finalize("t").tool_calls_count == 1


def test_no_builder_is_a_complete_no_op():
    assert timed_tool_call(None, "local_tools", lambda: "x") == "x"
    with tool_call_span(None, "local_tools"):
        pass
    record_mcp_tool_calls(None, [{"name": "create_invoice"}])


def test_record_mcp_tool_calls_records_each_call_as_a_morning_tool():
    builder = _builder()
    record_mcp_tool_calls(builder, [{"name": "resolve_client_name"}, {"name": "create_combo_document"},
                                    {"name": "resolve_client_name"}])
    record = builder.finalize("t")
    assert record.tool_calls_count == 3
    assert set(json.loads(record.morning_api_request_times_ms)) == {"resolve_client_name",
                                                                    "create_combo_document"}


# --- the backbone uses the same helpers --------------------------------------

@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _response(items, response_id):
    return SimpleNamespace(output=items, output_text="", id=response_id,
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15))


def _function_call(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _mcp_call(name):
    return SimpleNamespace(type="mcp_call", name=name, arguments="{}", output="ok", error=None,
                           server_label="morning-invoices-client-read", id=f"mcp_{name}")


def test_backbone_turn_records_round_spans_and_mcp_calls(prompts_root, tmp_path):
    telemetry_manager = TelemetryManager(str(tmp_path / "data"))
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_mcp_call("resolve_client_name"),
                   _function_call("record_planning_status", {"status": "checking"}, "c1")], "r1"),
        _response([_function_call("send_to_user", {"text": "שלום"}, "c2")], "r2"),
    ]
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(prompts_root)})
    backbone = Backbone(client, config, session_manager=make_session_manager(),
                        telemetry_manager=telemetry_manager)
    request = AIRequest(user_prompt="מי הלקוח?", constitution="", max_tokens=1000,
                        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1")

    backbone.turn_with_rounds(request, chat_id="chat1", user_role="godfather")

    row = telemetry_manager.get_latest_by_chat("chat1")
    assert row["llm_turns_count"] == 2
    # two resolution rounds ("local_tools", as legacy names its dispatch span) + one MCP call
    assert row["tool_calls_count"] == 3
    assert row["slowest_tool_name"] is not None
    assert json.loads(row["morning_api_request_times_ms"]) == {"resolve_client_name": 0}
