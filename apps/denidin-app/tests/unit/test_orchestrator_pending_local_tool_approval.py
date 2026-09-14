"""Unit tests: BackboneOrchestrator.get_response resolves a pending
reminders_write local-tool approval (a typed "כן"/"לא" reply) BEFORE Intent
Identification/Planning run at all - the backbone's own equivalent of
AIHandler.get_response's pending-approval gate
(contracts/local-tool-approval-gate.md), added after a real billed-test
failure (2026-09-14) showed a typed reply was never resolved at all once
denidin.py started routing text turns to the backbone."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse


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
    return BackboneOrchestrator(
        MagicMock(), config, pending_local_tool_approval_manager=MagicMock(),
    )


def _request():
    return AIRequest(
        user_prompt="כן", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def test_resolved_pending_approval_short_circuits_before_intent_identification(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    resolved = AIResponse(
        request_id="r1", response_text="✅ נוצרה תזכורת", tokens_used=0,
        prompt_tokens=0, completion_tokens=0, model="gpt-5.6-luna",
        finish_reason="stop", timestamp=1,
    )
    with patch(
        "src.capabilities.reminders.handler.resolve_typed_reply", return_value=resolved
    ) as mock_resolve, patch.object(orchestrator, "call_capability_step") as mock_call:
        response = orchestrator.get_response(_request(), user_role="godfather")

    assert response is resolved
    mock_resolve.assert_called_once()
    mock_call.assert_not_called()  # Intent Identification/Planning never ran


def test_unresolved_pending_approval_falls_through_to_a_normal_turn(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    with patch(
        "src.capabilities.reminders.handler.resolve_typed_reply", return_value=None
    ) as mock_resolve, patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = ["intent text", '{"steps": []}']
        response = orchestrator.get_response(_request(), user_role="godfather")

    mock_resolve.assert_called_once()
    assert mock_call.call_count == 2  # Intent Identification + Planning both ran
    assert response.response_text == "intent text"


def test_no_pending_local_tool_approval_manager_skips_the_check_entirely(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    orchestrator = BackboneOrchestrator(MagicMock(), config)  # manager=None (default)

    with patch("src.capabilities.reminders.handler.resolve_typed_reply") as mock_resolve, \
            patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = ["intent text", '{"steps": []}']
        response = orchestrator.get_response(_request(), user_role="godfather")

    mock_resolve.assert_not_called()
    assert response.response_text == "intent text"
