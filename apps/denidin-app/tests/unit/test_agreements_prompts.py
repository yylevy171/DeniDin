"""Feature 089 US5: the Agreement Management boundaries are written down, both ways
(CLAUDE.md: every tool-bearing feature needs explicit constitution boundaries)."""
from pathlib import Path

CONFIG = Path(__file__).parent.parent.parent / "config"


def _flow_description(tag):
    from src.backbone.flow_tags import FLOW_INFO
    return next(i.description for i in FLOW_INFO if i.tag == tag)


def test_agreement_flow_defines_when_and_when_not():
    from src.backbone.flow_tags import FlowTag
    description = _flow_description(FlowTag.AGREEMENT_MANAGEMENT)
    assert "EXISTING" in description and "Not for" in description
    flow = (CONFIG / "prompts" / "flows" / "flow_agreement_management.md").read_text(encoding="utf-8")
    assert "more than one agreement" in flow and "ask" in flow


def test_neighbouring_flows_exclude_agreement_management_back():
    from src.backbone.flow_tags import FlowTag
    for tag in (FlowTag.FEE_AGREEMENT_PROVIDED_BY_USER, FlowTag.DEPOSIT_PROVIDED_BY_USER,
                FlowTag.USER_QUESTION, FlowTag.GENERATE_FEE_AGREEMENT_DOCX):
        assert "flow_agreement_management" in _flow_description(tag), tag


def test_write_prompt_lists_approval_data_points_and_cascade():
    text = (CONFIG / "prompts" / "capabilities" / "cap_agreements_write.md").read_text(encoding="utf-8")
    assert "Approval data points" in text and "CANCELS its Pending" in text
    flow = (CONFIG / "prompts" / "flows" / "flow_agreement_management.md").read_text(encoding="utf-8")
    assert "cap_approval_with_buttons" in flow
