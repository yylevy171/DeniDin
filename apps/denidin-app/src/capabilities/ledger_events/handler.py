"""
Ledger capabilities (Feature 063, Feature 067 no-turn redesign) - real, directly-attachable
local tools wrapping the existing `src/managers/ledger_event_manager.py`:

- `query_ledger_events` (cap_ledger_query) - read-only lookup over recorded events.
- `report_ledger_recognition` (cap_ledger_capture) - the model reports a complete fee agreement,
  bank deposit, or a Morning document it just created (the flow's step right after the create
  call) from inside its flow; the zero-AI ledgerer (`persist_recognized_event`) persists it. The
  background reconciliation sweep is a separate safety net for documents made outside DeniDin;
  nothing here depends on it.
"""
import json
import logging
from typing import Any, Dict

from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED
from src.managers.ledger_event_recognizer import RECOGNITION_TOOL_NAME

logger = logging.getLogger(__name__)


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one ledger tool call directly - deterministic, no separate AI call. Returns
    JSON for the model to reason over."""
    if backbone.ledger_event_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED
    if tool_name == "query_ledger_events":
        # The raw matching events; arithmetic/aggregation is the model's job (cap_ledger_query.md).
        return json.dumps(backbone.ledger_event_manager.query_events(**args), ensure_ascii=False)
    if tool_name == RECOGNITION_TOOL_NAME:
        return _report_recognition(backbone, args, turn_context)
    return f"error: unknown ledger tool {tool_name!r}"


def _report_recognition(backbone, verdict: Dict[str, Any], turn_context: Dict[str, Any]) -> str:
    """Persists the model's `report_ledger_recognition` verdict for the message being handled
    (it is the completing message: it dates the event and is back-linked to it)."""
    chat_id = turn_context.get("chat_id")
    message_id = turn_context.get("message_id")
    if not (chat_id and message_id):
        return json.dumps({"status": "error", "reason": "no message to record against"})
    session = backbone.session_manager.get_session(chat_id)
    event_ids = backbone.ledger_event_manager.persist_recognized_event(verdict, session, message_id)
    logger.info("[069] model-reported ledger verdict=%s -> %d event(s) %s",
                verdict.get("verdict"), len(event_ids), event_ids)
    return json.dumps({"status": "ok", "event_ids": event_ids}, ensure_ascii=False)
