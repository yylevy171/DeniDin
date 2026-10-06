"""Unit tests for src/capabilities/toolsets.py - the uniform per-capability
tool attachment every domain CapabilityTag goes through (2026-09-24)."""
import functools
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.core.ai_manager import AIManager
from src.capabilities.toolsets import (
    MORNING_MCP_TOOL_NAMES,
    build_capability_tools,
    build_morning_mcp_tools,
    dispatch_local_tool,
    extract_local_calls,
    local_tool_owners,
    local_tools_for,
)


def _orch(with_mcp=True, fee_tools=None):
    orch = MagicMock()
    orch.config.mcp = {"morning_auth_token": "tok"} if with_mcp else {}
    orch.morning_mcp_locator.current_server_url.return_value = "https://x.example/mcp" if with_mcp else None
    orch.fee_agreement_tools = fee_tools
    # The real shared Morning MCP connection/entry builders (AIManager) over the mocks.
    orch.morning_mcp_connection = functools.partial(AIManager.morning_mcp_connection, orch)
    orch.morning_mcp_entry = AIManager.morning_mcp_entry
    return orch


def test_every_domain_tag_has_a_defined_toolset():
    """No tag is left "loadable but not actionable": each is either
    Morning-MCP-backed or has local tools."""
    orch = _orch(fee_tools=MagicMock(build_tools=lambda user: [{"type": "function", "name": "get_fee_agreement_template"}]))
    tool_less = []
    for tag in CapabilityTag:
        if tag in MORNING_MCP_TOOL_NAMES:
            continue
        if not local_tools_for(orch, tag, {"role": "GODFATHER"}):
            tool_less.append(tag)
    assert tool_less == []


def test_morning_mcp_one_never_approval_entry_per_loaded_capability_same_server():
    """2026-10-01 (T1): OpenAI lists an MCP server's tools once per chain per
    server_label, so each capability needs its own label with a FIXED tool set -
    one shared, widening entry hid tools loaded mid-turn."""
    tools = build_morning_mcp_tools(
        _orch(), [CapabilityTag.CLIENT_READ, CapabilityTag.INVOICING_READ, CapabilityTag.CLIENT_READ])
    assert [t["server_label"] for t in tools] == [
        "morning-invoices-client-read", "morning-invoices-invoicing-read"]
    for tool, tag in zip(tools, (CapabilityTag.CLIENT_READ, CapabilityTag.INVOICING_READ)):
        assert tool["type"] == "mcp"
        assert tool["require_approval"] == "never"
        assert tool["server_url"] == "https://x.example/mcp"
        assert tool["allowed_tools"] == list(MORNING_MCP_TOOL_NAMES[tag])


def test_morning_mcp_entry_for_a_capability_never_changes_with_what_else_is_loaded():
    alone = build_morning_mcp_tools(_orch(), [CapabilityTag.CLIENT_READ])
    with_more = build_morning_mcp_tools(_orch(), [CapabilityTag.CLIENT_READ, CapabilityTag.INVOICING_WRITE])
    assert with_more[0] == alone[0]


def test_morning_mcp_entries_absent_when_no_morning_capability_loaded_or_server_unavailable():
    assert build_morning_mcp_tools(_orch(), [CapabilityTag.REMINDERS_WRITE]) == []
    assert build_morning_mcp_tools(_orch(with_mcp=False), [CapabilityTag.INVOICING_READ]) == []


def test_build_capability_tools_grows_with_the_loaded_set():
    orch = _orch()
    assert build_capability_tools(orch, [], {}) == []
    one = build_capability_tools(orch, [CapabilityTag.REMINDERS_WRITE], {})
    two = build_capability_tools(orch, [CapabilityTag.REMINDERS_WRITE, CapabilityTag.LEDGER_QUERY], {})
    names_one = {t["name"] for t in one}
    names_two = {t["name"] for t in two}
    assert "create_reminder" in names_one and "query_ledger_events" not in names_one
    assert names_one < names_two and "query_ledger_events" in names_two


def test_owners_and_extraction_route_a_call_to_its_capability():
    orch = _orch()
    owners = local_tool_owners(orch, [CapabilityTag.REMINDERS_WRITE, CapabilityTag.LEDGER_QUERY], {})
    assert owners["create_reminder"] == CapabilityTag.REMINDERS_WRITE
    assert owners["query_ledger_events"] == CapabilityTag.LEDGER_QUERY
    item = SimpleNamespace(type="function_call", name="query_ledger_events",
                           arguments=json.dumps({"criteria": []}), call_id="c1")
    other = SimpleNamespace(type="function_call", name="send_to_user", arguments="{}", call_id="c2")
    calls = extract_local_calls(SimpleNamespace(output=[item, other]), owners)
    assert calls == [("c1", "query_ledger_events", {"criteria": []}, CapabilityTag.LEDGER_QUERY)]


def test_malformed_arguments_are_skipped_not_fatal():
    owners = {"create_reminder": CapabilityTag.REMINDERS_WRITE}
    bad = SimpleNamespace(type="function_call", name="create_reminder", arguments="{not json", call_id="c1")
    assert extract_local_calls(SimpleNamespace(output=[bad]), owners) == []


def test_dispatch_local_tool_routes_to_the_owning_capability_handler():
    orch = MagicMock()
    orch.reminder_manager.list_active.return_value = []
    result = dispatch_local_tool(orch, CapabilityTag.REMINDERS_READ, "list_reminders", {}, {})
    assert isinstance(result, str)
    orch.reminder_manager.list_active.assert_called_once()


def test_dispatch_local_tool_for_a_morning_backed_capability_is_an_error():
    assert dispatch_local_tool(MagicMock(), CapabilityTag.INVOICING_READ, "x", {}, {}).startswith("error:")


def test_docx_tools_attach_only_through_fee_agreement_handler():
    fee = MagicMock()
    fee.build_tools.return_value = [{"type": "function", "name": "get_fee_agreement_template"}]
    orch = _orch(fee_tools=fee)
    assert [t["name"] for t in local_tools_for(orch, CapabilityTag.DOCX_WRITE, {"role": "GODFATHER"})] == [
        "get_fee_agreement_template"
    ]
    assert local_tools_for(_orch(fee_tools=None), CapabilityTag.DOCX_WRITE, {}) == []


@pytest.mark.parametrize("tag", list(CapabilityTag))
def test_every_capability_prompt_file_exists(tag):
    from pathlib import Path
    prompt = Path(__file__).parent.parent.parent / "config" / "prompts" / "capabilities" / f"{tag.value}.md"
    assert prompt.exists() and prompt.read_text(encoding="utf-8").strip()


def test_write_capabilities_carry_only_write_tools_never_read_tools():
    read_names = set(MORNING_MCP_TOOL_NAMES[CapabilityTag.INVOICING_READ]) | set(
        MORNING_MCP_TOOL_NAMES[CapabilityTag.CLIENT_READ])
    for write_tag in (CapabilityTag.INVOICING_WRITE, CapabilityTag.CLIENT_WRITE):
        assert not set(MORNING_MCP_TOOL_NAMES[write_tag]) & read_names
    (tool,) = build_morning_mcp_tools(_orch(), [CapabilityTag.CLIENT_WRITE])
    assert set(tool["allowed_tools"]) == {"add_client", "update_client"}


def test_backbone_morning_tool_groups_cover_exactly_the_legacy_tool_lists():
    """The backbone groups Morning tools per capability; together they must be
    exactly the tools the legacy path lists (approval-required + no-approval)."""
    from src.capabilities.toolsets import MORNING_MCP_TOOL_NAMES  # pylint: disable=import-outside-toplevel
    from src.handlers.ai_handler import APPROVAL_REQUIRED_MCP_TOOLS, NO_APPROVAL_MCP_TOOLS  # pylint: disable=import-outside-toplevel
    backbone = {name for names in MORNING_MCP_TOOL_NAMES.values() for name in names}
    assert backbone == set(APPROVAL_REQUIRED_MCP_TOOLS) | set(NO_APPROVAL_MCP_TOOLS)
