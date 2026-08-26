"""
Method A (research.md R7) — the deterministic candidate transform.

**Corrected during implementation (2026-08-25)**: rather than hand-rolling a second field
mapping (as originally sketched in research.md's first draft — and which used field names,
`accounting_document_type`/`accounting_document_client_name`/`accounting_document_creation_timestamp`,
that turned out not to exist anywhere in the real schema), this reuses two pieces of already-
existing, already-tested code verbatim:

- `denidin_mcp_morning.models.Invoice` + `.formatters.format_invoice_json`
  (apps/morning-mcp-app) — parses Morning's raw `GET /documents/{id}` response (exactly what
  `MorningClient.get_invoice()` returns — confirmed live, research.md R1) and builds the same
  machine-readable JSON shape (`display_number`/`type_name`/`status_label`/`creation_date`/
  `payment`/...) Feature 025's live pipeline already produces via `morning-mcp-app`'s own tools.
- `ledger_event_manager._expand_accounting_document_json` (apps/denidin-app, reached via
  `_ledger_event_manager_loader.py`) — the exact same code-derived field expansion (never
  AI-transcribed) `LedgerEventManager.add_ledger_event` itself already depends on for every real
  field this ledger persists (`event_subtype`, `accounting_document_display_number`,
  `accounting_document_status*`, `accounting_document_creation_date`,
  `accounting_document_payment_method`, `client_name`, `description`, `amount`, `txn_date`,
  `bank_*`, `vat_status` — the REAL field list, confirmed by reading the function directly).

The two apps' machine-readable-JSON contract (Feature 025 Phase 9) IS the reuse boundary: no new
mapping logic is written here at all — just glue.
"""
from denidin_mcp_morning.formatters import format_invoice_json
from denidin_mcp_morning.models import Invoice

from _ledger_event_manager_loader import get_expand_accounting_document_json_function


def compute_canonical_json(raw_document: dict) -> str:
    """
    Stage 1+2 only (research.md R7, 2026-08-26 redesign): raw Morning document ->
    Invoice.model_validate -> format_invoice_json, i.e. the canonical machine-readable JSON
    string, WITHOUT Stage 3's LedgerEvent expansion. This is the actual "our manipulation of the
    raw data" the Phase 2 sandbox experiment compares against Method B's real live-MCP-relayed
    version of the same document — not the final LedgerEvent shape, which is Phase 3's concern.
    """
    invoice = Invoice.model_validate(raw_document)
    return format_invoice_json(invoice)


def build_capture_envelope(raw_document: dict) -> dict:
    """
    Maps one raw Morning document (MorningClient.get_invoice()'s shape) to the UN-expanded
    `{"source_type": "חשבונית", "accounting_document_json": ...}` envelope —
    LedgerEventManager.add_ledger_event's own real input contract (it does the Stage-3 expansion
    itself, via `_expand_accounting_document_json`).

    Used directly by transform.py (Phase 3's real persist path), so the manager's own event_id
    generation and tri-state new/duplicate/anomaly dedup guard run for real, never re-derived
    here. `transform()` below expands one step further, only for Phase 2's side-by-side
    comparison against Method B.
    """
    return {
        "source_type": "חשבונית",
        "accounting_document_json": compute_canonical_json(raw_document),
    }


def transform(raw_document: dict) -> dict:
    """
    Maps one raw Morning document to a fully-expanded LedgerEvent-shaped dict — the exact same
    fields the live reconciliation sweep would produce for the same document. No AI call
    anywhere in this path. Used only by select_method.py's Phase 2 comparison; Phase 3's real
    persist path uses build_capture_envelope() above instead (see its docstring for why).
    """
    envelope = build_capture_envelope(raw_document)
    expand = get_expand_accounting_document_json_function()
    expanded = expand(envelope)
    if expanded is None:
        raise ValueError(
            f"Method A could not expand document {raw_document.get('id')!r} — "
            "accounting_document_json was empty or unparseable"
        )
    return expanded
