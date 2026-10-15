"""bugfix-077: progress updates and replies are two distinct tools, unaware of each other.

Pins the PM's decided structure (specs/repo/bugfixes/bugfix-077-progress-updates-and-typing-dots.md), not
its wording: neither tool's prompt or tool description names the other, the backbone says what each is for,
and every flow tells the model it can send progress updates between its steps.
"""
from pathlib import Path

import pytest

from src.backbone.resolution_tools import SEND_TO_USER_TOOL
from src.tool_actions.tool_schemas import SEND_PROGRESS_UPDATE_TOOL

PROMPTS = Path(__file__).resolve().parents[2] / "config" / "prompts"
FLOWS = sorted((PROMPTS / "flows").glob("flow_*.md"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_progress_tool_is_unaware_of_send_to_user():
    for text in (_read(PROMPTS / "capabilities" / "cap_send_progress_update.md"),
                 SEND_PROGRESS_UPDATE_TOOL["description"]):
        assert "send_to_user" not in text


def test_the_reply_tool_is_unaware_of_progress_updates():
    for text in (_read(PROMPTS / "capabilities" / "cap_send_to_user.md"),
                 SEND_TO_USER_TOOL["description"]):
        assert "progress" not in text.lower()


def test_each_tool_description_is_a_single_line():
    for tool in (SEND_PROGRESS_UPDATE_TOOL, SEND_TO_USER_TOOL):
        assert "\n" not in tool["description"] and len(tool["description"]) < 120


def test_the_backbone_says_what_each_is_for():
    text = _read(PROMPTS / "backbone.md")
    assert "## Progress updates and replies" in text
    section = text.split("## Progress updates and replies", 1)[1].split("\n## ", 1)[0]
    assert "send_progress_update" in section and "send_to_user" in section


@pytest.mark.parametrize("flow", FLOWS, ids=lambda p: p.name)
def test_every_flow_mentions_progress_updates_at_the_top(flow):
    top = "\n".join(_read(flow).splitlines()[:12])
    assert "cap_send_progress_update" in top
