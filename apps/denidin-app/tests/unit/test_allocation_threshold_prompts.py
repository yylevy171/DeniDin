"""Feature 098: the {{ALLOCATION_THRESHOLD_NIS}} placeholder is filled from
config.allocation_threshold_nis in the Backbone's assembled instructions, so it
works in any capability or flow prompt. Real Backbone, real prompt files."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.flow_tags import FlowTag
from src.models.config import AppConfiguration
from src.utils.allocation_threshold import (
    ALLOCATION_THRESHOLD_PLACEHOLDER,
    fill_allocation_threshold,
    format_nis_amount,
)
from tests.backbone_test_support import make_backbone
from tests.denidin_test_support import make_session_manager

PROMPTS = Path(__file__).parent.parent.parent / "config" / "prompts"
ISSUING_FLOWS = (
    FlowTag.ISSUE_INVOICE_FOR_PAYMENT_DUE,
    FlowTag.ISSUE_INVOICE_RECEIPT_COMBO,
    FlowTag.ISSUE_PAYMENT_RECEIVED_WITH_REFERENCE_DOC,
)


def _backbone(tmp_path, base_dir=PROMPTS.parent, threshold=5000):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base_dir)},
        allocation_threshold_nis=threshold,
    )
    return make_backbone(MagicMock(), config,
                         session_manager=make_session_manager(storage_dir=str(tmp_path / "s")))


@pytest.mark.parametrize(
    "value, expected",
    [(5000, "5,000"), (12500, "12,500"), (5000.5, "5,000.5"), (5000.0, "5,000"), (999, "999")],
)
def test_format_nis_amount(value, expected):
    assert format_nis_amount(value) == expected


def test_fill_replaces_every_occurrence():
    text = f"above {ALLOCATION_THRESHOLD_PLACEHOLDER}, exactly {ALLOCATION_THRESHOLD_PLACEHOLDER} is fine"
    assert fill_allocation_threshold(text, 12500) == "above 12,500, exactly 12,500 is fine"


@pytest.mark.parametrize("threshold, expected", [(5000, "5,000"), (12500, "12,500")])
def test_invoicing_write_rule_carries_the_configured_threshold(tmp_path, threshold, expected):
    text = _backbone(tmp_path, threshold=threshold).build_instructions(
        [CapabilityTag.INVOICING_WRITE], active_flows=[FlowTag.ISSUE_INVOICE_RECEIPT_COMBO])

    assert ALLOCATION_THRESHOLD_PLACEHOLDER not in text
    assert f"more than\n{expected} ₪" in text or f"more than {expected} ₪" in text


def test_placeholder_in_a_flow_prompt_is_filled_too(tmp_path):
    """The fill runs on the assembled text, not on one file, so a flow or any
    other capability may use the placeholder."""
    prompts = tmp_path / "config" / "prompts"
    for sub in ("capabilities", "flows"):
        (prompts / sub).mkdir(parents=True)
        for src in (PROMPTS / sub).glob("*.md"):
            (prompts / sub / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (prompts / "backbone.md").write_text((PROMPTS / "backbone.md").read_text(encoding="utf-8"), encoding="utf-8")
    flow = prompts / "flows" / f"{FlowTag.MODIFY_CLIENT.value}.md"
    flow.write_text(flow.read_text(encoding="utf-8") + f"\nLIMIT {ALLOCATION_THRESHOLD_PLACEHOLDER}\n",
                    encoding="utf-8")

    text = _backbone(tmp_path, base_dir=prompts.parent, threshold=7000).build_instructions(
        [], active_flows=[FlowTag.MODIFY_CLIENT])

    assert "LIMIT 7,000" in text
    assert ALLOCATION_THRESHOLD_PLACEHOLDER not in text


def test_no_unfilled_placeholder_with_everything_loaded(tmp_path):
    text = _backbone(tmp_path).build_instructions(list(CapabilityTag), active_flows=list(FlowTag))
    assert ALLOCATION_THRESHOLD_PLACEHOLDER not in text


def test_every_issuing_flow_has_the_allocation_step_and_may_load_modify_client():
    for flow in ISSUING_FLOWS:
        body = (PROMPTS / "flows" / f"{flow.value}.md").read_text(encoding="utf-8")
        assert "**The allocation number**" in body, flow
        assert "get_client_details" in body, flow
        assert "flow_modify_client" in body.split("Follow these steps")[0], flow
