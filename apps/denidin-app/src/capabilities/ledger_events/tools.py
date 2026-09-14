"""
New, standalone local-tool schema for the Ledger Events — Capture capability
(Feature 063). Deliberately NOT imported from `src/handlers/ai_handler.py`'s
LEDGER_EVENT_TOOL (REQ-063-07: zero coupling to the legacy module) - a
simplified, single-component-per-call schema (the legacy multi-component
`components` array design exists to cope with the model choosing to invoke the
tool only once per turn even for a multi-stage agreement; this capability's own
prompt (ledger_capture.md) already instructs "call it at most once per event",
so one flat call maps to exactly one event here).

Scope note: הסכם (fee agreement) and בנק (bank deposit) only - חשבונית
(Morning-document-sourced) capture is the accounting-reconciliation service's
own job (contracts/orchestration-loop.md's Non-goals - that service is
explicitly out of scope for this orchestrator), not a live-turn capability.
"""
import json
import logging
from typing import Any, Dict, Optional, cast

logger = logging.getLogger(__name__)

CAPTURE_LEDGER_EVENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "capture_ledger_event",
    "description": (
        "Capture a fee-agreement or bank-deposit event mentioned in this turn's "
        "text, for later review and merging into the bookkeeping ledger. Only call "
        "this when the content genuinely states, changes, or cancels a fee "
        "arrangement, or shows a bank-transfer/deposit confirmation - never for "
        "ordinary conversation or content unrelated to money/engagement terms, and "
        "never more than once for the same event."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": ["הסכם", "בנק"],
                "description": "הסכם for a fee-agreement event, בנק for a bank deposit/transfer.",
            },
            "client_name": {
                "type": ["string", "null"],
                "description": "The client/counterparty this event concerns, if named.",
            },
            "payer_name": {
                "type": ["string", "null"],
                "description": "Who actually paid/is paying, if different from client_name.",
            },
            "description": {
                "type": ["string", "null"],
                "description": "The matter/engagement, verbatim or closely paraphrased from the source text.",
            },
            "amount": {
                "type": ["string", "null"],
                "description": "The stated amount, verbatim (no currency conversion/normalization).",
            },
            "vat_status": {
                "type": "string",
                "enum": ["כולל מעמ", "לא כולל מעמ", "לא צוין"],
                "description": "Whether the stated amount includes VAT, if stated.",
            },
            "txn_date": {
                "type": ["string", "null"],
                "description": "The calendar date this event's own content concerns, if stated (YYYY-MM-DD).",
            },
            "agreement_id": {
                "type": ["string", "null"],
                "description": (
                    "For source_type=הסכם: a stable identifier for this matter, reused "
                    "verbatim for later components/messages referencing the same "
                    "agreement. Null for source_type=בנק (no agreement concept applies)."
                ),
            },
        },
        "required": [
            "source_type", "client_name", "payer_name", "description",
            "amount", "vat_status", "txn_date", "agreement_id",
        ],
        "additionalProperties": False,
    },
}


def extract_capture_call(response) -> Optional[Dict]:
    """Find a `capture_ledger_event` function_call item in a Responses API
    `response.output` and return its parsed arguments, or None if absent.
    Never raises."""
    for item in (getattr(response, "output", None) or []):
        if (getattr(item, "type", None) != "function_call"
                or getattr(item, "name", None) != CAPTURE_LEDGER_EVENT_TOOL["name"]):
            continue
        try:
            return cast(Dict, json.loads(item.arguments))
        except json.JSONDecodeError as exc:
            logger.warning("Malformed capture_ledger_event arguments discarded: %s", exc)
            return None
    return None


def to_call_arguments(flat_args: Dict[str, Any]) -> Dict[str, Any]:
    """Reshapes this capability's flat, single-component tool-call arguments
    into the `components`-array shape `LedgerEventManager.add_ledger_events_from_call`
    expects (the same flat merged shape LEDGER_EVENT_TOOL's legacy multi-component
    calls produce, just always exactly one component here)."""
    event_subtype = "יצירה" if flat_args.get("source_type") == "הסכם" else "הפקדה"
    component = {
        "component_label": None,
        "description": flat_args.get("description"),
        "amount": flat_args.get("amount"),
        "percent": None,
        "percent_base": None,
        "hours": None,
        "hourly_rate": None,
        "txn_date": flat_args.get("txn_date"),
        "vat_status": flat_args.get("vat_status", "לא צוין"),
    }
    return {
        "source_type": flat_args.get("source_type"),
        "event_subtype": event_subtype,
        "client_name": flat_args.get("client_name"),
        "payer_name": flat_args.get("payer_name"),
        "agreement_id": flat_args.get("agreement_id"),
        "reference_hint": None,
        "component_count": 1,
        "components": [component],
    }
