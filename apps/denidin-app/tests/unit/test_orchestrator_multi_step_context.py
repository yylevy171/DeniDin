"""Unit test (T048, US3): a 2-step Plan threads an earlier step's output into the
next step's accumulated context."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.backbone.orchestrator import BackboneOrchestrator
from src.backbone.planning import Plan, PlanStep
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _orchestrator(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(MagicMock(), config)


def _request():
    return AIRequest(
        user_prompt="[media message]", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def test_second_step_sees_first_steps_output(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    plan = Plan(steps=[
        PlanStep(CapabilityTag.MEDIA_ANALYSIS, "extract the incoming image"),
        PlanStep(CapabilityTag.LEDGER_CAPTURE, "check for a fee agreement"),
    ])

    seen_contexts = []

    def fake_media_handler(_orch, _req, accumulated_context, _note, _turn_context):
        seen_contexts.append(("media_analysis", accumulated_context))
        return "Extracted text: Bank transfer 500 NIS to Yossi"

    def fake_ledger_handler(_orch, _req, accumulated_context, _note, _turn_context):
        seen_contexts.append(("ledger_capture", accumulated_context))
        return "Recognized as a bank deposit event."

    with patch.object(
        BackboneOrchestrator, "_resolve_capability_handler",
        side_effect=lambda tag: fake_media_handler if tag == CapabilityTag.MEDIA_ANALYSIS else fake_ledger_handler,
    ):
        final_output = orchestrator._execute_plan(  # pylint: disable=protected-access
            plan, _request(), "the user sent an image", {},
        )

    assert final_output == "Recognized as a bank deposit event."
    # The second step's accumulated_context must contain the first step's output.
    ledger_context = seen_contexts[1][1]
    assert "Bank transfer 500 NIS to Yossi" in ledger_context
