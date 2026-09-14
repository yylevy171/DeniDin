"""Unit test (Feature 063 write-approval-flow parity): every DOMAIN CapabilityTag
resolves to a real capability handler via BackboneOrchestrator._resolve_capability_handler
- none raise NotImplementedError any more, now that Invoicing - Write and Ledger
Events - Capture are wired up alongside the earlier read/query/write capabilities."""
from src.backbone.capability_tags import DOMAIN_CAPABILITY_TAGS
from src.backbone.orchestrator import BackboneOrchestrator


def test_every_domain_capability_resolves_to_a_real_handler():
    for tag in DOMAIN_CAPABILITY_TAGS:
        handler = BackboneOrchestrator._resolve_capability_handler(tag)  # pylint: disable=protected-access
        assert callable(handler), f"expected a callable handler for {tag.value}"


def test_invoicing_write_resolves_to_propose_write():
    from src.backbone.capability_tags import CapabilityTag
    from src.capabilities.invoicing.handler import propose_write

    handler = BackboneOrchestrator._resolve_capability_handler(CapabilityTag.INVOICING_WRITE)  # pylint: disable=protected-access
    assert handler is propose_write


def test_ledger_capture_resolves_to_capture():
    from src.backbone.capability_tags import CapabilityTag
    from src.capabilities.ledger_events.handler import capture

    handler = BackboneOrchestrator._resolve_capability_handler(CapabilityTag.LEDGER_CAPTURE)  # pylint: disable=protected-access
    assert handler is capture


def test_reminders_write_resolves_to_propose_write():
    from src.backbone.capability_tags import CapabilityTag
    from src.capabilities.reminders.handler import propose_write

    handler = BackboneOrchestrator._resolve_capability_handler(CapabilityTag.REMINDERS_WRITE)  # pylint: disable=protected-access
    assert handler is propose_write
