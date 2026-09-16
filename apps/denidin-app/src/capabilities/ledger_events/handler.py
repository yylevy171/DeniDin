"""
Ledger Events capability (Feature 063) — Query + Capture steps. Wraps the existing,
unmodified `src/managers/ledger_event_manager.py` (REQ-063-03: `query_events` for
Query).

Capture (2026-09-15, revised — see `capture()`'s own docstring): no longer persists
directly. The real capture mechanism is `denidin.py`'s shared
`_run_post_turn_ledger_recognition` (the full, proven `AIHandler.recognize_ledger_event`
three-verdict flow, per `config/ledger_recognition_prompt.md`), which now correctly
sees flag-on turns too since they're persisted to the session. This step is a
documented no-op instead, to avoid double-capturing the same event.
"""
import logging
from typing import Any, Dict

from src.backbone.capability_tags import CapabilityTag
from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED
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
        return BACKBONE_CAPABILITY_NOT_CONFIGURED

    criteria = [{"text": note}] if note else []
    result = orchestrator.ledger_event_manager.query_events(criteria)

    return str(orchestrator.call_capability_step(
        tag=CapabilityTag.LEDGER_QUERY,
        request=request,
        accumulated_context=accumulated_context + f"\n\nQuery result: {result}",
    ))


def capture(orchestrator, request: AIRequest, accumulated_context: str, note: str,
            turn_context: Dict[str, Any]) -> str:
    """Ledger Events — Capture step (2026-09-15, revised - no longer persists
    directly, see below).

    A real, sophisticated ledger-recognition mechanism ALREADY runs for every
    godfather/admin turn under flag-on, text and media alike -
    `denidin.py`'s shared `_run_post_turn_ledger_recognition`, which calls the
    exact same production, already-proven `AIHandler.recognize_ledger_event`
    (the full three-verdict complete/none/declined flow, client-resolution
    evidence rules, amendment/correction/cancellation linking, and every
    money/date/name extraction rule in `config/ledger_recognition_prompt.md`)
    used by the flag-off path. This is real, shared infrastructure
    (REQ-063-03) - `denidin.py`'s own glue code calling into it, not this
    module reimplementing or duplicating it - and it now sees flag-on turns
    correctly because they're persisted to the session
    (`BackboneOrchestrator._persist_turn`).

    Having this in-plan step ALSO offer a capture tool and persist directly
    would risk capturing the SAME event twice - once here, once post-turn -
    since both would recognize it from the same conversation content. So this
    step deliberately does NOT offer `CAPTURE_LEDGER_EVENT_TOOL` or call
    `add_ledger_events_from_call` any more; it exists (and stays part of the
    9-capability taxonomy, `data-model.md`) as a documented no-op, explaining
    to Planning/Intent Identification that capture is handled automatically
    and needs no action from them, rather than leaving Planning free to
    (redundantly, riskily) select an undocumented dead end."""
    del note, turn_context
    if orchestrator.ledger_event_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED
    return str(orchestrator.call_capability_step(
        tag=CapabilityTag.LEDGER_CAPTURE,
        request=request,
        accumulated_context=accumulated_context,
    ))
