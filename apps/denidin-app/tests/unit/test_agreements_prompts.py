"""Feature 089 US5: the Agreement Management boundaries are written down, both ways
(CLAUDE.md: every tool-bearing feature needs explicit constitution boundaries)."""
from pathlib import Path

CONFIG = Path(__file__).parent.parent.parent / "config"
CONSTITUTION = (CONFIG / "runtime_constitution.md").read_text(encoding="utf-8")


def _section(title):
    start = CONSTITUTION.index(f"## {title}")
    nxt = CONSTITUTION.find("\n## ", start + 3)
    return CONSTITUTION[start: nxt if nxt != -1 else len(CONSTITUTION)]


def test_agreement_section_defines_when_and_when_not():
    section = _section("Agreement Management")
    assert "### When these tools apply" in section
    assert "### When these tools do NOT apply" in section
    assert "ASK" in section and "CANCELS its Pending" in section


def test_other_tool_sections_exclude_agreement_management_back():
    for title in ("Reminder Management", "Ledger Event Querying", "Fee Agreement Document Generation",
                  "Ledger Event Recognition", "Invoice Management Context"):
        assert "Agreement Management" in _section(title), title


def test_write_prompt_lists_approval_data_points_and_cascade():
    text = (CONFIG / "prompts" / "capabilities" / "cap_agreements_write.md").read_text(encoding="utf-8")
    assert "Approval data points" in text and "CANCELS its Pending" in text
    flow = (CONFIG / "prompts" / "flows" / "flow_agreement_management.md").read_text(encoding="utf-8")
    assert "cap_approval_with_buttons" in flow
