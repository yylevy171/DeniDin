"""Unit test (Feature 063 write-approval-flow parity): BackboneOrchestrator.
resolve_button_tap checks BOTH pending-approval managers (invoicing's MCP
PendingApprovalManager and reminders' PendingLocalToolApprovalManager) - at most
one populated per chat in practice, mirroring denidin.py's own dual
attach_sent_message_id calls for the legacy AIHandler path."""
from unittest.mock import MagicMock, patch

from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration


def _orchestrator(tmp_path, **kwargs):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base)},
    )
    return BackboneOrchestrator(MagicMock(), config, **kwargs)


def test_resolve_button_tap_falls_through_to_reminders_when_no_mcp_pending(tmp_path):
    orchestrator = _orchestrator(
        tmp_path,
        pending_approval_manager=MagicMock(),
        pending_local_tool_approval_manager=MagicMock(),
    )
    orchestrator.pending_approval_manager.get.return_value = None

    with patch(
        "src.capabilities.reminders.handler.resolve_button_tap",
        return_value="reminders-resolved",
    ) as reminders_resolve:
        result = orchestrator.resolve_button_tap("chat1", "denidin_approve", "stanza1", None)

    reminders_resolve.assert_called_once()
    assert result == "reminders-resolved"


def test_resolve_button_tap_resolves_via_invoicing_when_mcp_pending_matches(tmp_path):
    orchestrator = _orchestrator(
        tmp_path,
        pending_approval_manager=MagicMock(),
        pending_local_tool_approval_manager=MagicMock(),
    )

    with patch(
        "src.capabilities.invoicing.handler.resolve_button_tap",
        return_value="invoicing-resolved",
    ) as invoicing_resolve, patch(
        "src.capabilities.reminders.handler.resolve_button_tap",
    ) as reminders_resolve:
        result = orchestrator.resolve_button_tap("chat1", "denidin_approve", "stanza1", None)

    invoicing_resolve.assert_called_once()
    reminders_resolve.assert_not_called()
    assert result == "invoicing-resolved"


def test_resolve_button_tap_returns_none_when_neither_manager_configured(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    result = orchestrator.resolve_button_tap("chat1", "denidin_approve", "stanza1", None)
    assert result is None
