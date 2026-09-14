"""
Ledger Events capability (Feature 063) — Query step. Wraps the existing, unmodified
`src/managers/ledger_event_manager.py::query_events` (REQ-063-03).

Capture (the write side — the three-verdict recognition flow + הסכם/בנק specifics
split out of `config/ledger_recognition_prompt.md`) is tracked in tasks.md's Deferred
section.
"""
import logging
from typing import Any, Dict

from src.backbone.capability_tags import CapabilityTag
from src.models.message import AIRequest

logger = logging.getLogger(__name__)


def query(orchestrator, request: AIRequest, accumulated_context: str, note: str,
          turn_context: Dict[str, Any]) -> str:
    """Ledger Events — Query step: fuzzy-searches the ledger via the unmodified
    LedgerEventManager.query_events, then asks the model (Backbone + ledger_query.md)
    to reason over the raw results and phrase a natural reply — same "retrieve
    broadly, let the model reason" principle the legacy query_ledger_events tool
    already uses."""
    del turn_context
    if orchestrator.ledger_event_manager is None:
        return "Ledger manager not configured."

    criteria = [{"text": note}] if note else []
    result = orchestrator.ledger_event_manager.query_events(criteria)

    return str(orchestrator.call_capability_step(
        tag=CapabilityTag.LEDGER_QUERY,
        request=request,
        accumulated_context=accumulated_context + f"\n\nQuery result: {result}",
    ))
