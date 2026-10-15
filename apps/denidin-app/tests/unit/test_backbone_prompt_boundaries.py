"""Feature 067 (REQ-RMH-009/026/027/028): the prompts tell the model how to read messages that arrive while it works."""
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parents[2] / "config" / "prompts"
CAPABILITIES = ["cap_invoicing_write", "cap_reminders_write", "cap_ledger_query", "cap_approval_with_buttons",
                "cap_send_to_user"]
SECTION = "## Messages That Arrive While You Work"


@pytest.fixture(scope="module")
def backbone_text():
    return (CONFIG / "backbone.md").read_text(encoding="utf-8")


def test_backbone_has_the_section(backbone_text):
    assert SECTION in backbone_text


@pytest.mark.parametrize("phrase", [
    "sent before your last output",  # how to read the markers
    "sent after your last output",
    "[USER MESSAGE ·",
    "Finish a pending approval before starting the next request",
    "**ask**",                             # may ask when confused
    "never repeat it",                     # what was already done stays done
    "handled on its own right after",      # media
    "answers the most recent",             # short replies
])
def test_section_states_each_rule(backbone_text, phrase):
    section = backbone_text.split(SECTION)[1].split("\n## ")[0]
    assert phrase in section


@pytest.mark.parametrize("name", CAPABILITIES)
def test_each_tool_bearing_capability_points_back(name):
    text = (CONFIG / "capabilities" / f"{name}.md").read_text(encoding="utf-8")
    assert "Messages that arrive while you work" in text
