"""Unit tests for BackboneOrchestrator._build_instructions' fixed assembly order
(T022, contracts/prompt-assembly.md): backbone + one capability + accumulated
context + '---' + today."""
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "capabilities" / "reminders_read.md").write_text("REMINDERS_READ", encoding="utf-8")
    return base


def _orchestrator(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(MagicMock(), config)


def test_assembly_order_backbone_then_capability_then_context_then_date(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    instructions = orchestrator.build_instructions(
        CapabilityTag.REMINDERS_READ, accumulated_context="PRIOR CONTEXT",
    )
    backbone_idx = instructions.index("BACKBONE")
    capability_idx = instructions.index("REMINDERS_READ")
    context_idx = instructions.index("PRIOR CONTEXT")
    separator_idx = instructions.index("---")

    assert backbone_idx < capability_idx < context_idx < separator_idx


def test_assembly_omits_accumulated_context_when_empty(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    instructions = orchestrator.build_instructions(CapabilityTag.REMINDERS_READ, accumulated_context="")
    assert "BACKBONE" in instructions
    assert "REMINDERS_READ" in instructions
    assert "---" in instructions


def test_assembly_carries_exactly_one_active_capability(prompts_root):
    (prompts_root / "prompts" / "capabilities" / "ledger_query.md").write_text(
        "LEDGER_QUERY", encoding="utf-8"
    )
    orchestrator = _orchestrator(prompts_root)
    instructions = orchestrator.build_instructions(CapabilityTag.REMINDERS_READ)
    assert "REMINDERS_READ" in instructions
    assert "LEDGER_QUERY" not in instructions
