"""
Feature 069 (mechanism move) — Task A / T003a.

The redesign moves ledger capture OFF the main conversational turn: it is no
longer an inline `capture_ledger_event` function tool the model calls mid-reply,
it is a dedicated post-turn recognition call (see `test_recognition_call.py`) plus
a zero-AI ledgerer (see `test_ledgerer.py`).

This file pins the *deletion* half of that move (contract
`contracts/recognition-and-logging.md` C5):

  - `_call_openai_ledger_followup_api` — gone (the recognition call never touches
    the reply, so the second round-trip that recovered it is unnecessary).
  - `_handle_ledger_event_capture` — gone (replaced by recognition + ledgerer).
  - the bugfix-018 MCP-suppression guard (`morning_mcp_used_this_turn`) and the
    `>1 call` / unparseable-args protocol-violation whole-turn rejection — gone
    (structurally unreachable with no inline capture tool).
  - `LEDGER_EVENT_TOOL` / `capture_ledger_event` is NOT attached to the main
    conversational turn for ANY role.

Kept, unchanged:
  - `query_ledger_events` — still attached for godfather/admin (read/search only).
  - `LEDGER_EVENT_TOOL` the *constant* — reused by the recognition call.

Only the OpenAI client is a stand-in (external service, CONSTITUTION §I); the
`AIHandler` / `UserManager` are real.
"""
import inspect

from unittest.mock import Mock, MagicMock

import pytest

from src.handlers import ai_handler as ai_handler_module
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration


GODFATHER_PHONE = "972500000002"
ADMIN_PHONE = "972500000001"
CLIENT_PHONE = "972500000003"


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        "session": {"storage_dir": str(tmp_path / "data" / "sessions")},
        "longterm": {"enabled": False},
    }
    config.user_roles = {
        "admin_phones": [ADMIN_PHONE],
        "blocked_phones": ["972500000099"],
    }
    config.godfather_phone = GODFATHER_PHONE
    config.reminders = {"max_active_reminders": 20}
    return config


@pytest.fixture
def ai_handler(mock_config):
    return AIHandler(MagicMock(), mock_config)


class TestDeletedInlineCaptureMachinery:
    def test_ledger_followup_api_method_is_gone(self):
        assert not hasattr(AIHandler, "_call_openai_ledger_followup_api")

    def test_handle_ledger_event_capture_method_is_gone(self):
        assert not hasattr(AIHandler, "_handle_ledger_event_capture")

    def test_build_ledger_event_tool_helper_is_gone(self):
        assert not hasattr(AIHandler, "_build_ledger_event_tool")

    def test_mcp_suppression_guard_symbol_is_gone_from_module_source(self):
        src = inspect.getsource(ai_handler_module)
        assert "morning_mcp_used_this_turn" not in src

    def test_protocol_violation_branch_is_gone_from_module_source(self):
        src = inspect.getsource(ai_handler_module)
        assert "protocol_violation" not in src
        assert "single_call_unparseable" not in src

    def test_local_tool_dispatch_loop_no_longer_calls_ledger_capture(self):
        assert hasattr(AIHandler, "_run_local_tool_dispatch_loop")
        src = inspect.getsource(AIHandler._run_local_tool_dispatch_loop)
        assert "_handle_ledger_event_capture" not in src


class TestLedgerEventToolConstantKept:
    def test_schema_constant_still_exists_for_the_recognition_call(self):
        assert hasattr(ai_handler_module, "LEDGER_EVENT_TOOL")
        assert ai_handler_module.LEDGER_EVENT_TOOL["name"] == "capture_ledger_event"


class TestMainTurnToolAttachment:
    def test_godfather_turn_has_query_ledger_events_but_not_capture(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1") or []
        names = [t.get("name") for t in tools]
        assert "query_ledger_events" in names
        assert "capture_ledger_event" not in names

    def test_admin_turn_has_query_ledger_events_but_not_capture(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(ADMIN_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1") or []
        names = [t.get("name") for t in tools]
        assert "query_ledger_events" in names
        assert "capture_ledger_event" not in names

    def test_client_turn_gets_no_ledger_tools_at_all(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "req1") or []
        names = [t.get("name") for t in tools]
        assert "capture_ledger_event" not in names
        assert "query_ledger_events" not in names
