"""Unit tests: BackboneOrchestrator.get_response sets AIResponse.offer_approval_buttons
whenever a reminders_write step just created a NEW pending local-tool approval this
turn - the backbone's own equivalent of AIHandler's `new_pending_approval_created`
(Feature 047 parity). Added after a real billed-test failure (2026-09-14) showed
WhatsAppHandler.send_response() never sent an interactive-buttons approval prompt
for a backbone-proposed reminder - only the plain-text prompt went out, so a button
tap could never resolve anything (nothing was ever sent to tap)."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _orchestrator(prompts_root, pending_manager):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(
        MagicMock(), config, pending_local_tool_approval_manager=pending_manager,
    )


def _request():
    return AIRequest(
        user_prompt="תזכיר לי בעוד שעה לשלוח חשבונית", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def test_offer_approval_buttons_true_when_a_new_pending_approval_was_just_created(prompts_root):
    pending_manager = MagicMock()
    # No pending approval at the START of this turn (_resolve_pending_local_tool_approval
    # finds nothing) - simulated via the reminders handler resolve_typed_reply patch below
    # returning None (no pending). AFTER the plan executes, one now exists (propose_write's
    # real effect) - simulated by pending_manager.get returning a real approval by the time
    # _finalize_response checks it.
    pending_manager.get.return_value = PendingLocalToolApproval(
        tool_name="create_reminder",
        arguments={"message_text": "לשלוח חשבונית", "one_time_due_at": "2026-10-01T09:00:00"},
    )
    orchestrator = _orchestrator(prompts_root, pending_manager)

    with patch(
        "src.capabilities.reminders.handler.resolve_typed_reply", return_value=None
    ), patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = [
            "intent: create reminder",
            '{"steps": [{"capability": "reminders_write", "note": ""}]}',
        ]
        with patch.object(orchestrator, "_resolve_capability_handler") as mock_resolve_handler:
            mock_resolve_handler.return_value = lambda *a, **kw: "📋 לאישור — תזכורת חדשה..."
            response = orchestrator.get_response(_request(), chat_id="chat1", user_role="godfather")

    assert response.offer_approval_buttons is True


def test_offer_approval_buttons_false_when_no_pending_approval_exists(prompts_root):
    pending_manager = MagicMock()
    pending_manager.get.return_value = None  # nothing pending, before or after
    orchestrator = _orchestrator(prompts_root, pending_manager)

    with patch(
        "src.capabilities.reminders.handler.resolve_typed_reply", return_value=None
    ), patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = ["בוקר טוב!", '{"steps": []}']
        response = orchestrator.get_response(_request(), chat_id="chat1", user_role="godfather")

    assert response.offer_approval_buttons is False


def test_offer_approval_buttons_false_when_no_manager_configured(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    orchestrator = BackboneOrchestrator(MagicMock(), config)  # manager=None (default)

    with patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = ["בוקר טוב!", '{"steps": []}']
        response = orchestrator.get_response(_request(), chat_id="chat1", user_role="godfather")

    assert response.offer_approval_buttons is False
