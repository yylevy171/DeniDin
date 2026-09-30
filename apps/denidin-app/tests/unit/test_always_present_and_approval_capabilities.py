"""Unit tests for the always-present capabilities, cap_approval_with_buttons as an
on-demand capability, the read/write split (cap_invoicing_read never resolves
names; flow_invoicing_query does the resolution through cap_client_read), and
the real shipped prompt files (config/prompts) matching the code's catalogs."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import ALWAYS_PRESENT_CAPABILITIES, CapabilityTag
from src.backbone.flow_tags import FlowTag
from src.backbone.resolution_tools import RESOLUTION_TOOLS
from src.backbone.backbone import Backbone
from src.capabilities.toolsets import (
    MORNING_MCP_TOOL_NAMES, build_capability_tools, local_tool_owners,
)
from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration

PROMPTS = Path(__file__).parent.parent.parent / "config" / "prompts"


@pytest.fixture
def orch(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(PROMPTS.parent)},
    )
    return Backbone(MagicMock(), config,
                                session_manager=SessionManager(storage_dir=str(tmp_path / "s")))


def test_every_tag_flow_and_always_present_capability_has_a_real_prompt_file():
    for tag in CapabilityTag:
        assert tag.value.startswith("cap_") and (PROMPTS / "capabilities" / f"{tag.value}.md").is_file()
    for name in ALWAYS_PRESENT_CAPABILITIES:
        assert name.startswith("cap_") and (PROMPTS / "capabilities" / f"{name}.md").is_file()
    for flow in FlowTag:
        assert flow.value.startswith("flow_") and (PROMPTS / "flows" / f"{flow.value}.md").is_file()


def test_no_orphan_prompt_files():
    shipped_caps = {p.stem for p in (PROMPTS / "capabilities").glob("*.md")}
    assert shipped_caps == {t.value for t in CapabilityTag} | set(ALWAYS_PRESENT_CAPABILITIES)
    assert {p.stem for p in (PROMPTS / "flows").glob("*.md")} == {f.value for f in FlowTag}


def test_always_present_capabilities_are_not_loadable_tags():
    assert not set(ALWAYS_PRESENT_CAPABILITIES) & {t.value for t in CapabilityTag}


def test_always_present_prompts_render_in_fixed_order_right_after_the_backbone(orch):
    plain = orch.build_instructions([])
    loaded = orch.build_instructions([CapabilityTag.CLIENT_READ], active_flows=[FlowTag.ADD_CLIENT])
    positions = [plain.index(f"# Capability: {title}") for title in
                 ("Send to user", "React to message", "Send progress update", "Record planning status")]
    assert positions == sorted(positions)
    assert positions[-1] < plain.index("## Flows\n")
    # Byte-identical prefix up to the catalogs, whatever is loaded (cache stability).
    cut = plain.index("## Flows\n")
    assert plain[:cut] == loaded[:cut]


def test_loaded_flows_and_capabilities_render_in_canonical_order_not_load_order(orch):
    a = orch.build_instructions([CapabilityTag.REMINDERS_WRITE, CapabilityTag.CLIENT_READ],
                                active_flows=[FlowTag.USER_QUESTION, FlowTag.ADD_CLIENT])
    b = orch.build_instructions([CapabilityTag.CLIENT_READ, CapabilityTag.REMINDERS_WRITE],
                                active_flows=[FlowTag.ADD_CLIENT, FlowTag.USER_QUESTION])
    assert a == b


def test_approval_tool_is_attached_only_while_cap_approval_with_buttons_is_loaded(orch):
    assert "approval_with_yes_no_buttons" not in {t["name"] for t in RESOLUTION_TOOLS}
    names = lambda tags: {t["name"] for t in build_capability_tools(orch, tags, {})}  # noqa: E731
    assert "approval_with_yes_no_buttons" not in names([CapabilityTag.CLIENT_WRITE])
    assert "approval_with_yes_no_buttons" in names([CapabilityTag.APPROVAL_WITH_BUTTONS])
    # The backbone executes it itself (it ends the turn) - never a domain-dispatched tool.
    assert local_tool_owners(orch, [CapabilityTag.APPROVAL_WITH_BUTTONS], {}) == {}


def test_invoicing_read_no_longer_owns_name_resolution():
    assert "resolve_client_name" not in MORNING_MCP_TOOL_NAMES[CapabilityTag.INVOICING_READ]
    assert "resolve_client_name" in MORNING_MCP_TOOL_NAMES[CapabilityTag.CLIENT_READ]
    text = (PROMPTS / "capabilities" / "cap_invoicing_read.md").read_text(encoding="utf-8")
    assert "`resolve_client_name`" not in text


def test_flow_invoicing_query_loads_client_read_then_invoicing_read():
    text = (PROMPTS / "flows" / "flow_invoicing_query.md").read_text(encoding="utf-8")
    assert "Capabilities: `cap_client_read`, `cap_invoicing_read`." in text
    assert text.index("cap_client_read") < text.rindex("cap_invoicing_read")


def test_flows_that_look_up_documents_go_through_flow_invoicing_query():
    for flow_file in (PROMPTS / "flows").glob("flow_*.md"):
        if flow_file.stem == "flow_invoicing_query":
            continue
        assert "cap_invoicing_read" not in flow_file.read_text(encoding="utf-8"), flow_file.name


def test_no_prompt_or_tool_invents_a_progress_update_limit():
    from src.backbone.backbone_tools import SEND_PROGRESS_UPDATE_TOOL
    haystack = (SEND_PROGRESS_UPDATE_TOOL["description"]
                + (PROMPTS / "backbone.md").read_text(encoding="utf-8")
                + (PROMPTS / "capabilities" / "cap_send_progress_update.md").read_text(encoding="utf-8")).lower()
    assert "more than one progress" not in haystack and "one per turn" not in haystack
    assert "one progress update" not in haystack


# cap_docx_write is deliberately absent: its flow has no approval step today
# (open question with the user), so it is not asserted here.
_WRITE_CAPABILITIES = ("cap_reminders_write", "cap_client_write", "cap_invoicing_write")


def _capabilities_line(flow_file):
    for line in flow_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("Capabilities:"):
            return line
    return ""


@pytest.mark.parametrize("write_cap", _WRITE_CAPABILITIES)
def test_every_write_capability_is_only_reached_through_flows_that_also_load_approval(write_cap):
    users = [f for f in (PROMPTS / "flows").glob("flow_*.md") if f"`{write_cap}`" in _capabilities_line(f)]
    assert users, f"no flow wraps {write_cap}"
    for flow_file in users:
        assert "`cap_approval_with_buttons`" in _capabilities_line(flow_file), flow_file.name


def test_write_capability_prompts_and_catalog_say_to_use_them_from_a_flow():
    from src.backbone.capability_tags import CAPABILITY_INFO
    for write_cap in _WRITE_CAPABILITIES + ("cap_docx_write",):
        text = (PROMPTS / "capabilities" / f"{write_cap}.md").read_text(encoding="utf-8")
        assert "from within a flow" in text, write_cap
        description = next(i.description for i in CAPABILITY_INFO if i.tag.value == write_cap)
        assert "flow_" in description and "directly" in description, write_cap
    assert "never loaded on their own" in (PROMPTS / "backbone.md").read_text(encoding="utf-8")


def test_reminders_have_a_create_flow_and_a_modify_flow():
    assert FlowTag.CREATE_REMINDER.value == "flow_create_reminder"
    create = (PROMPTS / "flows" / "flow_create_reminder.md").read_text(encoding="utf-8")
    assert "MUST be approved" in create and "`cap_approval_with_buttons`" in create
