"""
Method B (research.md R7) — the AI-mediated candidate transform.

Adapts `accounting_reconciliation_service.py`'s `_build_reconciliation_prompt`/`LEDGER_EVENT_TOOL`
(Feature 025) to work from a single pre-fetched local document instead of a live MCP
`list_invoices` call — there's nothing to fetch, the data is already local (Pass 1's output), so
no MCP tool is attached at all, just a plain OpenAI Responses API call asking the model to
transcribe (never infer) the document's own fields via one `capture_ledger_event` call, exactly
matching the live sweep's own step 2 (`_build_reconciliation_prompt`, read directly).

**Does NOT import `ai_handler.py`'s real `LEDGER_EVENT_TOOL` directly**: that module's own
top-level imports (`openai`, `MemoryManager`, `SessionManager`, ...) are literal statements inside
`ai_handler.py` itself, not just inherited from a package `__init__.py` — so the bypass trick
`_ledger_event_manager_loader.py` uses doesn't apply here (there's no lightweight subset to load
around). Instead, this module defines its own minimal, self-contained tool schema covering only
the fields a `source_type=חשבונית` capture actually uses — faithful to `LEDGER_EVENT_TOOL`'s real
חשבונית-relevant fields (confirmed by reading `apps/denidin-app/src/handlers/ai_handler.py`
directly, not guessed), not the full multi-purpose schema (agreement/bank-deposit fields the
חשבונית path never touches are simply omitted here).

Real OpenAI dependency: only imported/called when `transform()` actually runs (Phase 2's real
sandbox experiment, or a real Phase 3 run if Method B is selected) — never during any unit-tested
path (research.md R7, REQ-BACKFILL-003).
"""
import json
from typing import Optional

_CHESHBONIT_CAPTURE_TOOL = {
    "type": "function",
    "name": "capture_ledger_event",
    "description": (
        "Capture this Morning accounting document's already-structured fields verbatim, for "
        "the ledger. Transcribe only — never infer, summarize, or fill anything in yourself."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "source_type": {"type": "string", "enum": ["חשבונית"]},
            "event_subtype": {
                "type": "string",
                "enum": ["הפקה"],
                "description": "Always 'הפקה' — a placeholder, overwritten by code.",
            },
            "accounting_document_json": {
                "type": "string",
                "description": (
                    "The document's ENTIRE JSON object, copied verbatim and unmodified from "
                    "the document data given to you, as a single string. Do not summarise, "
                    "reorder, translate, or drop any field."
                ),
            },
        },
        "required": ["source_type", "event_subtype", "accounting_document_json"],
        "additionalProperties": False,
    },
}


def _build_prompt(accounting_document_json: str) -> str:
    return (
        "Automated accounting-document capture task. Make exactly one tool call — never "
        "write a text reply, no human will read one.\n\n"
        "Call capture_ledger_event exactly once with:\n"
        "- source_type: \"חשבונית\"\n"
        "- event_subtype: \"הפקה\" (a placeholder — code overwrites it with the document's "
        "real Morning type)\n"
        "- accounting_document_json: the document JSON below, copied verbatim as a single "
        "string. Do not summarise it, reorder it, translate it, drop fields, or fill "
        "anything in yourself — every value is read out of it by code.\n\n"
        f"Document JSON:\n{accounting_document_json}"
    )


def _extract_first_tool_call_arguments(response) -> Optional[dict]:
    """Extracts the first capture_ledger_event call's arguments from a Responses API result."""
    for item in getattr(response, "output", None) or []:
        if (
            getattr(item, "type", None) == "function_call"
            and getattr(item, "name", None) == "capture_ledger_event"
        ):
            return json.loads(item.arguments)
    return None


def build_capture_envelope(raw_document: dict, openai_client=None) -> dict:
    """
    Maps one raw Morning document to the UN-expanded `{"source_type": "חשבונית",
    "accounting_document_json": ...}` envelope via a real OpenAI Responses API call — no MCP
    tool attached (the document is already local). This IS the envelope
    LedgerEventManager.add_ledger_event's own input contract expects (see method_a.py's
    build_capture_envelope docstring for why it's a separate step from transform() below).

    `openai_client` is injected for testability; a real `OpenAI()` client (requires a real API
    key) is constructed if not supplied — this is the one call site in this whole feature where
    that happens, and only when Method B is actually invoked.
    """
    from denidin_mcp_morning.formatters import format_invoice_json
    from denidin_mcp_morning.models import Invoice

    invoice = Invoice.model_validate(raw_document)
    accounting_document_json = format_invoice_json(invoice)

    if openai_client is None:
        from openai import OpenAI  # local import: no openai dependency unless Method B runs
        openai_client = OpenAI()

    response = openai_client.responses.create(
        model="gpt-4o-mini",
        instructions=_build_prompt(accounting_document_json),
        input="Capture this document.",
        tools=[_CHESHBONIT_CAPTURE_TOOL],
    )

    tool_call_args = _extract_first_tool_call_arguments(response)
    if tool_call_args is None:
        raise ValueError(
            f"Method B: model made no capture_ledger_event call for document "
            f"{raw_document.get('id')!r}"
        )
    return tool_call_args


def transform(raw_document: dict, openai_client=None) -> dict:
    """
    Maps one raw Morning document to a fully-expanded LedgerEvent-shaped dict via a real OpenAI
    call (build_capture_envelope above), then Stage-3-expands it the same way Method A does.
    Used only by select_method.py's Phase 2 comparison; Phase 3's real persist path (if Method B
    is ever selected) uses build_capture_envelope() directly instead — see method_a.py.
    """
    from _ledger_event_manager_loader import get_expand_accounting_document_json_function

    envelope = build_capture_envelope(raw_document, openai_client=openai_client)

    expand = get_expand_accounting_document_json_function()
    expanded = expand(envelope)
    if expanded is None:
        raise ValueError(
            f"Method B could not expand document {raw_document.get('id')!r} — "
            "accounting_document_json was empty or unparseable"
        )
    return expanded
