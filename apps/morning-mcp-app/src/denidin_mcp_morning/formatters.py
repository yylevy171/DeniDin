"""₪/VAT/date value helpers + the machine-readable JSON response shapes for
every MCP tool.

**JSON-only contract (2026-09-04)**: every tool in this app returns a single
machine-readable JSON object/array as its result string - there is no prose
format any more, and no `format`/`output_format` parameter anywhere. The
calling model (denidin-app) is responsible for composing whatever
Hebrew, bullet-style reply the operator actually sees; nothing in this file
is user-facing text. This replaces the old dual "prose is the default,
`format='json'` is an opt-in for automated tasks" contract (Feature 025
Phase 9) - abandoned rather than kept alongside prose so there is exactly
ONE way every tool's result is shaped, not "some tools like this, others
like that" (2026-09-04 user decision, made while investigating Feature 069's
US2 gap: create_combo_document's old prose output could not be
deterministically translated into a ledger event the way get_invoice_details'
`format="json"` output already was).

Values remain ₪/DD-MM-YYYY-formatted *inside informational fields* only
where that's genuinely the value's home representation (e.g.
`format_currency_ils` is still used to build display strings embedded in a
JSON field where relevant); dates in the JSON shapes themselves are ISO
8601, translated Hebrew labels (status/document type) are still resolved
here since this app owns those tables, per spec.md §REQ-I18N-001.
"""
import json
from datetime import date
from typing import List, Optional

from .models import _DOCUMENT_TYPE_NAMES, _PAYMENT_TYPE_NAMES, Client, FinancialSummary, Invoice
from .utils.time_utils import local_from_timestamp

_STATUS_HE = {
    "paid": "שולם",
    "unpaid": "לא שולם",
    "overdue": "פג תוקף",
    "cancelled": "בוטל",
}


def format_currency_ils(amount: float) -> str:
    """Format a number as an Israeli New Shekel amount, e.g. 5000 -> '₪5,000.00'."""
    return f"₪{amount:,.2f}"


def format_date_il(value: date) -> str:
    """Format a date in the Israeli DD/MM/YYYY convention."""
    return value.strftime("%d/%m/%Y")


def translate_status(status: str) -> str:
    """Translate an invoice status to Hebrew; unknown statuses pass through unchanged."""
    return _STATUS_HE.get(status, status)


def translate_document_type(type_code: Optional[int]) -> str:
    """Translate a Morning document-type code to its real Hebrew name.

    Table confirmed live against GET /documents/types (2026-07-21/22,
    bugfix-014) - deterministic 1:1 label lookup, not interpretation. Lets
    the model tell a receipt/credit apart from a real invoice in
    list_invoices' own text output, and reason about Morning's document
    flows itself (per runtime_constitution.md) instead of the tool guessing.
    Unknown codes fall back to the raw code as a string; None to "".
    """
    if type_code is None:
        return ""
    return _DOCUMENT_TYPE_NAMES.get(type_code, str(type_code))


def translate_payment_type(payment_type_code: Optional[int]) -> str:
    """Translate a Morning payment-method code to its real Hebrew name.

    Table confirmed live against GET /payments/types (2026-07-22, bugfix-014).
    Unknown codes fall back to the raw code as a string; None to "".
    """
    if payment_type_code is None:
        return ""
    return _PAYMENT_TYPE_NAMES.get(payment_type_code, str(payment_type_code))


def _client_dict(client: Client) -> dict:
    """The one canonical machine-readable shape for a client - never includes
    the internal client_id (REQ-CLIENT-018): unlike invoices, client tools
    resolve by name, so there's no legitimate reason to surface it."""
    return {
        "name": client.name,
        "email": client.email,
        "phone": client.phone,
        "tax_id": client.tax_id,
    }


def format_financial_summary(summary: FinancialSummary) -> str:
    """Machine-readable JSON view of a financial summary (2026-09-04 JSON-only
    contract change - see the module docstring). The model composes the
    Hebrew bullet-style reply the operator sees from these fields; nothing
    here is shown to a person verbatim."""
    return json.dumps(
        {
            "period_start": summary.period_start.isoformat(),
            "period_end": summary.period_end.isoformat(),
            "total_invoiced": summary.total_invoiced,
            "total_paid": summary.total_paid,
            "total_unpaid": summary.total_unpaid,
            "invoice_count": summary.invoice_count,
            "paid_invoice_count": summary.paid_invoice_count,
            "unpaid_invoice_count": summary.unpaid_invoice_count,
            "average_invoice_amount": summary.average_invoice_amount,
        },
        ensure_ascii=False,
    )


def format_client_list(clients: List[Client]) -> str:
    """Machine-readable JSON view of a client list (2026-09-04 JSON-only
    contract change)."""
    return json.dumps(
        {"count": len(clients), "clients": [_client_dict(c) for c in clients]},
        ensure_ascii=False,
    )


def format_client_details(client: Client, is_exact_match: bool = True) -> str:
    """Machine-readable JSON view of one client (2026-09-04 JSON-only
    contract change). `is_exact_match` tells the model whether the name it
    passed in was resolved via a partial/prefix reference - it must then say
    so explicitly to the operator rather than presenting the details as
    certain, exactly as the prose version used to."""
    return json.dumps(
        {"client": _client_dict(client), "exact_match": is_exact_match},
        ensure_ascii=False,
    )


def format_client_not_found() -> str:
    """Machine-readable JSON for a zero-match client lookup (2026-09-04
    JSON-only contract change)."""
    return json.dumps({"found": False}, ensure_ascii=False)


def format_client_name_confirmation_question(candidate_name: str) -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) for ANY
    tool - read or write - that resolves a client_name to exactly one real
    client whose stored name isn't the literal spelling given. The model
    must compose a closed yes/no question from `candidate_name` (ending
    "אישור - כן/לא?" so a later reply parses reliably, per bugfix-028 B1) -
    never silently proceed under the guessed name (a write tool would create
    a real Morning document against a possibly-wrong client before the
    operator ever sees which one was picked) and never silently refuse
    "not found" either."""
    return json.dumps(
        {"status": "needs_confirmation", "candidate_name": candidate_name},
        ensure_ascii=False,
    )


def format_client_name_resolved(resolved_name: str) -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) for
    resolve_client_name's EXACT-match case - the model should copy
    `resolved_name` verbatim into whichever tool it calls next, together
    with name_resolved=True."""
    return json.dumps({"status": "resolved", "name": resolved_name}, ensure_ascii=False)


def format_name_not_resolved() -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) for a
    client-resolving tool called with name_resolved not True. This is a
    PROCEDURAL instruction for the calling model to act on immediately in
    the same turn (call resolve_client_name, then retry) - never shown to
    the operator."""
    return json.dumps(
        {
            "status": "error",
            "reason": "name_not_resolved",
            "instruction": (
                "call resolve_client_name with the client's name first, use the exact "
                "name it returns, then retry this tool with name_resolved=true"
            ),
        },
        ensure_ascii=False,
    )


def format_original_not_linked_to_client() -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) for a
    Group B tool whose linked original document has no real client attached
    (feature 027, REQ-INV-013) - a pre-feature, bare-name-only document. No
    remediation path exists (spec.md Clarifications 2026-08-06) - the model
    must not imply one when composing its reply."""
    return json.dumps(
        {"status": "error", "reason": "original_not_linked_to_client"}, ensure_ascii=False
    )


def format_transaction_account_cancelled(document: dict) -> str:
    """Machine-readable JSON confirmation for cancel_transaction_account
    (feature 056, REQ-INV-026; 2026-09-04 JSON-only contract change).

    Deliberately carries its own `status: "cancelled"` rather than Morning's
    raw status code - get_invoice_details' status translation renders
    Morning's manually-closed status (2) as "שולם" (paid), which research.md
    confirmed live is actively misleading here: this account's money never
    moved, so nothing was "paid". The model must not say "paid" when
    composing its reply from this. Used identically for both the
    real-cancellation path and the idempotent no-op path (already
    cancelled/already fulfilled, REQ-INV-021/025).

    `document` is the raw Morning document dict - either close_invoice's
    response (real cancellation) or the original fetched via get_invoice
    (no-op path)."""
    number = document.get("number") or document.get("id", "")
    client_name = (document.get("client") or {}).get("name")
    return json.dumps(
        {"status": "cancelled", "display_number": number, "client_name": client_name},
        ensure_ascii=False,
    )


def format_too_many_invoices_message(total: int) -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) when
    list_invoices' real Morning total exceeds the fetch cap (user-stories.md
    US2, REQ-INVOICE-003) - the real total is always stated (never silently
    truncated); the model must ask the operator to narrow the search rather
    than fetching further pages or dumping a huge, unusable reply."""
    return json.dumps({"status": "too_many", "total": total, "kind": "invoices"}, ensure_ascii=False)


def format_too_many_clients_message(total: int) -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) when a
    client search/list matches more results than can reasonably be
    returned - the real total is always stated; the model must ask the
    operator to narrow the search."""
    return json.dumps({"status": "too_many", "total": total, "kind": "clients"}, ensure_ascii=False)


def format_ambiguous_clients_message(candidates: List[Client]) -> str:
    """Machine-readable JSON (2026-09-04 JSON-only contract change) when a
    name lookup matches more than one client (REQ-CLIENT-003/007) - lists
    each candidate (never the internal client_id, REQ-CLIENT-018). The
    model must ask the operator to be more specific, without disclosing
    full details for either candidate."""
    return json.dumps(
        {"status": "ambiguous", "candidates": [_client_dict(c) for c in candidates]},
        ensure_ascii=False,
    )


def format_invoice_json(invoice: Invoice) -> str:
    """Machine-readable JSON view of one document (Feature 025 Phase 9; the
    canonical shape every document-returning tool now uses unconditionally,
    per the 2026-09-04 JSON-only contract - see this module's docstring).

    Why JSON rather than prose (see
    specs/in-progress/025-morning-sourced-ledger-events/
    proposal-full-document-capture.md): the prose view is lossy and ambiguous
    for a machine consumer - "סכום: ₪51.92" hides whether VAT is included,
    "18:52" has dropped the seconds, and an absent field is simply not
    printed, so a model cannot distinguish "no VAT" from "VAT not shown" and
    guesses. That is exactly what produced a fabricated 00:00 creation time in
    a real live sweep. This format carries native types and explicit nulls, so
    the model transcribes rather than interprets, and denidin-app's own code
    owns every derived value.

    Keys are named for what they are, not for Morning's raw spelling, and the
    document type / linked-document type are translated here because this app
    owns the type table - denidin-app never needs one.
    """
    payment = invoice.payments[0] if invoice.payments else None
    linked = invoice.linked_documents[0] if invoice.linked_documents else None

    doc = {
        "display_number": invoice.number,
        "internal_morning_id": invoice.id,
        "type": invoice.type,
        "type_name": translate_document_type(invoice.type) or None,
        "status": invoice.status,
        "status_code": invoice.status_code,
        "status_label": invoice.status_label,
        "client_name": invoice.client_name,
        "description": invoice.description,
        "amount": invoice.total_amount if invoice.total_amount is not None else invoice.amount,
        "amount_excl_vat": invoice.amount_excl_vat,
        "vat_amount": invoice.vat_amount,
        "vat_rate": invoice.vat_rate,
        "currency": invoice.currency,
        "document_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "creation_date": (
            local_from_timestamp(invoice.creation_timestamp.timestamp()).isoformat()
            if invoice.creation_timestamp else None
        ),
        "payment": None if payment is None else {
            "method": payment.method,
            "type": payment.payment_type,
            "date": payment.payment_date.isoformat() if payment.payment_date else None,
            "amount": payment.amount,
            "bank_number": payment.bank_name,
            "bank_branch": payment.bank_branch,
            "bank_account": payment.bank_account,
        },
        # Line items. denidin-app uses ONLY the first and warns if there are
        # more (user decision, 2026-08-23) - surfaced as a real array rather
        # than pre-flattened so that rule is enforceable and the extra entries
        # are visibly there to warn about.
        "line_items": [
            {
                "description": line.get("description"),
                "quantity": line.get("quantity"),
                "price": line.get("price"),
                "amount": line.get("amountTotal", line.get("amount")),
            }
            for line in (invoice.income or [])
        ],
        "linked_document": None if linked is None else {
            "number": linked.number,
            "type": linked.type,
            "type_name": translate_document_type(linked.type) or None,
        },
    }
    return json.dumps(doc, ensure_ascii=False)


def format_invoice_list_json(invoices: List[Invoice], total_matched: int) -> str:
    """Machine-readable JSON view of a document list - see
    format_invoice_json for why this format exists. `total_matched` is stated
    explicitly so a consumer can detect truncation rather than infer it."""
    return json.dumps(
        {
            "total_matched": total_matched,
            "shown": len(invoices),
            "documents": [json.loads(format_invoice_json(inv)) for inv in invoices],
        },
        ensure_ascii=False,
    )
