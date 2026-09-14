"""
Ledger Events capability (Feature 063) — Query + Capture steps. Wraps the existing,
unmodified `src/managers/ledger_event_manager.py` (REQ-063-03: `query_events` for
Query, `add_ledger_events_from_call` for Capture).

Capture scope: הסכם (fee agreement) / בנק (bank deposit) only, no approval gate
(mirrors the legacy `capture_ledger_event` local tool - persists immediately, same
as `list_reminders`/`query_ledger_events`). חשבונית (Morning-document-sourced)
capture stays the accounting-reconciliation service's own job - out of scope here
per contracts/orchestration-loop.md's Non-goals.
"""
import logging
from typing import Any, Dict

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.ledger_events.tools import (
    CAPTURE_LEDGER_EVENT_TOOL,
    extract_capture_call,
    to_call_arguments,
)
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


def capture(orchestrator, request: AIRequest, accumulated_context: str, note: str,
            turn_context: Dict[str, Any]) -> str:
    """Ledger Events — Capture step: one Responses API call (Backbone +
    ledger_capture.md's prompt + accumulated context) offering the capture tool;
    if the model calls it, persists directly via the unmodified
    `LedgerEventManager.add_ledger_events_from_call` - no approval gate, mirrors
    the legacy `capture_ledger_event` local tool's immediate-dispatch shape."""
    del note
    if orchestrator.ledger_event_manager is None:
        return "Ledger manager not configured."

    response = orchestrator.client.responses.create(
        model=request.model,
        instructions=orchestrator.build_instructions(
            CapabilityTag.LEDGER_CAPTURE, accumulated_context, request.timestamp,
        ),
        input=[{"role": "user", "content": request.user_prompt}],
        max_output_tokens=request.max_tokens,
        tools=[CAPTURE_LEDGER_EVENT_TOOL],
    )

    flat_args = extract_capture_call(response)
    if not flat_args:
        return getattr(response, "output_text", "") or "לא זוהה אירוע לרישום."

    chat_id = turn_context.get("chat_id") or request.chat_id
    session_id = ""
    if chat_id and orchestrator.session_manager is not None:
        try:
            session_id = orchestrator.session_manager.get_session(chat_id).session_id
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to resolve session for ledger capture, chat=%r: %s", chat_id, exc)

    try:
        event_ids = orchestrator.ledger_event_manager.add_ledger_events_from_call(
            session_id=session_id,
            call_arguments=to_call_arguments(flat_args),
            message_id=request.message_id,
            message_timestamp=request.timestamp,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Ledger capture failed: %s", exc)
        return "⚠️ רישום האירוע נכשל."

    if not event_ids:
        return "⚠️ רישום האירוע נכשל."
    return f"✅ נרשם אירוע בספר ({', '.join(event_ids)})."
