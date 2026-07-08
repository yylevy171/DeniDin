"""MCP tool implementations wrapping MorningClient for invoice management.

Each function here corresponds 1:1 to an MCP tool registered in server.py
(see contracts/<tool>.json and user-stories.md for the tool contract and
acceptance criteria). Tools receive a MorningClient by dependency injection
(no globals, no monkey-patching per CONSTITUTION.md §XVII) and return a
human-readable, Hebrew-formatted string.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .formatters import format_invoice_confirmation, format_invoice_details, format_invoice_list
from .models import Invoice
from .morning_client import MorningClient

logger = logging.getLogger(__name__)

_TAX_INVOICE_DOCUMENT_TYPE = 305
_CREDIT_INVOICE_DOCUMENT_TYPE = 330  # "חשבונית זיכוי" — confirmed live via GET /documents/types
_LIST_INVOICES_MAX_ITEMS = 10
_STATUS_ALIASES = {
    "unpaid": {"unpaid", "open"},
    "paid": {"paid", "closed"},
    "overdue": {"overdue"},
    "cancelled": {"cancelled"},
}


def _build_create_invoice_payload(
    client_name: str,
    amount: float,
    description: str,
    due_date: Optional[str] = None,
    vat_included: bool = True,
    currency: str = "ILS",
) -> dict:
    """Map friendly create_invoice inputs onto a real Morning /documents payload.

    Mirrors the shape the sandbox is known to accept (see the passing
    tests/integration/test_morning_sandbox_invoices_crud.py fixture): a single
    income line and a single payment line — the sandbox requires at least one
    payment line (תקבולים) to accept a document.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    vat_type = 1 if vat_included else 0

    payload = {
        "type": _TAX_INVOICE_DOCUMENT_TYPE,
        "date": today,
        "lang": "he",
        "vatType": vat_type,
        "currency": currency,
        "rounding": False,
        "signed": False,
        "description": description,
        "client": {
            "self": False,
            "name": client_name,
        },
        "income": [
            {
                "catalogNum": "",
                "description": description,
                "quantity": 1,
                "price": amount,
                "currency": currency,
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": vat_type,
            }
        ],
        "payment": [
            {
                "type": 1,
                "price": amount,
                "date": today,
            }
        ],
    }
    if due_date:
        payload["dueDate"] = due_date
    return payload


def create_invoice(
    client: MorningClient,
    client_name: str,
    amount: float,
    description: str,
    due_date: Optional[str] = None,
    vat_included: bool = True,
) -> str:
    """Create an invoice in Morning and return a Hebrew confirmation message.

    MCP tool: create_invoice (contracts/create_invoice.json, user-stories.md US1).

    Args:
        client: An authenticated MorningClient (injected).
        client_name: Client name (Morning resolves/creates the client record).
        amount: Invoice amount in NIS.
        description: Service/product description.
        due_date: Optional due date, ISO format YYYY-MM-DD.
        vat_included: Whether VAT is included in the amount (default True).

    Returns:
        A Hebrew confirmation string with the invoice number, amount, and status.
    """
    payload = _build_create_invoice_payload(client_name, amount, description, due_date, vat_included)
    response = client.create_invoice(payload)

    invoice_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    invoice = Invoice(
        id=invoice_id,
        number=response.get("number"),
        client_name=client_name,
        amount=amount,
        total_amount=response.get("total", amount),
        currency=response.get("currency", "ILS"),
        due_date=due_date,
        status=response.get("status"),
    )
    return format_invoice_confirmation(invoice)


def _map_list_invoices_filters(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Map friendly list_invoices filters onto Morning's real /documents/search params.

    Key names (fromDate/toDate/clientName) are proven against the sandbox by
    tests/integration/test_morning_sandbox_invoices_crud.py. `status` is
    deliberately NOT sent server-side — see _matches_status.
    """
    params: Dict[str, Any] = {}
    if from_date:
        params["fromDate"] = from_date
    if to_date:
        params["toDate"] = to_date
    if client_name:
        params["clientName"] = client_name
    return params


def _extract_items(response: Any) -> List[dict]:
    """Morning's /documents/search response may be a dict with items/data, or a bare list."""
    if isinstance(response, dict):
        return response.get("items") or response.get("data") or []
    if isinstance(response, list):
        return response
    return []


def _matches_status(item: dict, status: Optional[str]) -> bool:
    """Client-side status filter — Morning's server-side filter param name for
    status is not confirmed in the available API docs/Postman collection, so
    we filter locally rather than guess and risk silently-wrong results."""
    if not status or status == "all":
        return True

    item_status = str(item.get("status", "")).lower()
    return item_status in _STATUS_ALIASES.get(status, {status})


def list_invoices(
    client: MorningClient,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
) -> str:
    """List/search invoices and return a Hebrew, human-readable result.

    MCP tool: list_invoices (contracts/list_invoices.json, user-stories.md US2).

    Args:
        client: An authenticated MorningClient (injected).
        status: Optional filter — "paid", "unpaid", "overdue", "cancelled", or "all".
        from_date: Optional start date, ISO format YYYY-MM-DD.
        to_date: Optional end date, ISO format YYYY-MM-DD.
        client_name: Optional client-name filter.

    Returns:
        A Hebrew string listing up to 10 matching invoices, or a friendly
        "no results" message. Notes when more results exist beyond the cap.
    """
    params = _map_list_invoices_filters(from_date, to_date, client_name)
    response = client.list_invoices(params=params)
    raw_items = _extract_items(response)

    matching_items = [item for item in raw_items if _matches_status(item, status)]

    invoices: List[Invoice] = []
    for item in matching_items:
        try:
            invoices.append(Invoice.model_validate(item))
        except ValidationError as exc:
            logger.warning("Skipping unparseable invoice in list_invoices result: %s", exc)

    has_more = len(invoices) > _LIST_INVOICES_MAX_ITEMS
    page = invoices[:_LIST_INVOICES_MAX_ITEMS]

    return format_invoice_list(page, has_more=has_more)


def get_invoice_details(client: MorningClient, invoice_id: str) -> str:
    """Fetch full details for one invoice and return a Hebrew, human-readable view.

    MCP tool: get_invoice_details (contracts/get_invoice_details.json,
    user-stories.md US3).

    Args:
        client: An authenticated MorningClient (injected).
        invoice_id: Morning document id.

    Returns:
        A Hebrew string with status, dates, and any recorded payments.
    """
    response = client.get_invoice(invoice_id)
    invoice = Invoice.model_validate(response)
    return format_invoice_details(invoice)


def _build_cancellation_payload(original: dict) -> dict:
    """Build a Morning credit-invoice (type 330) payload that cancels `original`.

    Israeli law does not allow deleting/voiding an issued tax invoice — the
    correct mechanism (confirmed live via GET /documents/types: 330 =
    "חשבונית זיכוי") is to issue a linked credit invoice that offsets it.
    Mirrors the original's client and line items rather than guessing, since
    this produces a real financial document.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    client_info = original.get("client") or {}
    income_items = original.get("income") or []
    original_id = str(original.get("id") or original.get("documentId") or "")
    original_number = original.get("number")
    total_amount = original.get("total")
    if total_amount is None:
        total_amount = sum(
            float(item.get("price", 0)) * float(item.get("quantity", 1)) for item in income_items
        )

    return {
        "type": _CREDIT_INVOICE_DOCUMENT_TYPE,
        "date": today,
        "lang": original.get("lang", "he"),
        "vatType": original.get("vatType", 1),
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": False,
        "description": f"ביטול חשבונית מספר {original_number or original_id}",
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {
            "self": False,
            "name": client_info.get("name"),
        },
        "income": income_items
        or [
            {
                "catalogNum": "",
                "description": f"ביטול חשבונית מספר {original_number or original_id}",
                "quantity": 1,
                "price": total_amount,
                "currency": original.get("currency", "ILS"),
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": original.get("vatType", 1),
            }
        ],
        "payment": [{"type": 1, "price": total_amount, "date": today}],
    }


def _cancel_invoice(client: MorningClient, invoice_id: str) -> str:
    """Cancel an invoice by issuing a linked credit invoice against it.

    Use case: the user made a mistake creating the original invoice (wrong
    amount, typo, etc.) and wants it voided so a corrected one can be created.
    """
    original = client.get_invoice(invoice_id)
    payload = _build_cancellation_payload(original)
    credit_response = client.create_invoice(payload)

    original_number = original.get("number", invoice_id)
    credit_number = credit_response.get("number", credit_response.get("id", ""))

    return (
        f"חשבונית מספר {original_number} בוטלה.\n"
        f"הופקה חשבונית זיכוי מספר {credit_number} לקיזוז הסכום."
    )


_CLOSED_STATUS_CODES = {1, 2}  # closed (via payment) / manually closed — see models._MORNING_STATUS_CODES


def _build_payment_receipt_payload(original: dict) -> dict:
    """Build a Morning receipt (type 400) payload that marks `original` paid.

    Real mechanism (confirmed live): POST /documents/{id}/close returns 400
    (errorCode 3000) for tax invoices — close/open only apply to documents
    that were manually closed via that same endpoint (its own error message:
    "לא ניתן לפתוח מסמך שאינו סגור ידנית", i.e. "cannot open a document that
    wasn't manually closed"). A tax invoice is instead marked paid by issuing
    a linked Receipt (type 400) referencing it via linkedDocumentIds; Morning
    then flips the original's status automatically (verified live: None -> 1).
    """
    today = datetime.now(timezone.utc).date().isoformat()
    client_info = original.get("client") or {}
    original_id = str(original.get("id") or original.get("documentId") or "")
    original_number = original.get("number")
    total_amount = original.get("total")
    if total_amount is None:
        total_amount = original.get("amount")

    return {
        "type": 400,
        "date": today,
        "lang": original.get("lang", "he"),
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": False,
        "description": f"תשלום עבור חשבונית מספר {original_number or original_id}",
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {"self": False, "name": client_info.get("name")},
        "payment": [{"type": 1, "price": total_amount, "date": today}],
    }


def _mark_invoice_paid(client: MorningClient, invoice_id: str) -> str:
    original = client.get_invoice(invoice_id)

    if original.get("status") in _CLOSED_STATUS_CODES:
        # Already paid — idempotent no-op, avoid creating a duplicate receipt.
        return format_invoice_confirmation(Invoice.model_validate(original))

    payload = _build_payment_receipt_payload(original)
    client.create_invoice(payload)  # generic POST /documents; type=400 makes it a receipt

    updated = client.get_invoice(invoice_id)
    return format_invoice_confirmation(Invoice.model_validate(updated))


def _mark_invoice_unpaid(client: MorningClient, invoice_id: str) -> str:
    original = client.get_invoice(invoice_id)

    if original.get("status") not in _CLOSED_STATUS_CODES:
        # Already unpaid — idempotent no-op.
        return format_invoice_confirmation(Invoice.model_validate(original))

    raise ValueError(
        "Cannot reopen an already-paid invoice: Morning has no reversal for a "
        "payment recorded via a linked receipt (confirmed live — /documents/"
        "{id}/open only works on documents manually closed via /close, which "
        "does not apply to tax invoices). Issue a credit invoice instead if "
        "the payment needs to be undone."
    )


def update_invoice_status(
    client: MorningClient,
    invoice_id: str,
    status: str,
    payment_date: Optional[str] = None,
) -> str:
    """Update an invoice's payment status and return a Hebrew confirmation.

    MCP tool: update_invoice_status (contracts/update_invoice_status.json,
    user-stories.md US3/US8).

    Real mechanisms (the contract's original assumption of a generic
    `PUT /documents/{id}/status`, and this tool's original `/close`+`/open`
    design, both turned out not to apply to tax invoices — see
    _build_payment_receipt_payload and _mark_invoice_unpaid docstrings):
    - "paid" -> issue a linked Receipt (type 400); idempotent if already paid.
    - "unpaid" -> idempotent no-op if not yet paid; raises ValueError if
      already paid (no supported reversal).
    - "cancelled" -> issue a linked Credit Invoice (type 330); see
      _cancel_invoice. Real use case: the user made a mistake creating the
      invoice (wrong amount, typo) and needs it voided so a corrected one can
      be created instead — Israeli law forbids deleting/voiding a tax invoice
      outright, so a credit invoice is the correct mechanism.

    Args:
        client: An authenticated MorningClient (injected).
        invoice_id: Morning document id.
        status: One of "paid", "unpaid", "cancelled".
        payment_date: Currently unused — Morning's receipt/credit-invoice
            payloads use today's date; reserved for backdating support.

    Returns:
        A Hebrew confirmation string.

    Raises:
        ValueError: if `status` is not one of the supported values, or if
            "unpaid" is requested for an already-paid invoice.
    """
    if status == "paid":
        return _mark_invoice_paid(client, invoice_id)
    elif status == "unpaid":
        return _mark_invoice_unpaid(client, invoice_id)
    elif status == "cancelled":
        return _cancel_invoice(client, invoice_id)
    else:
        raise ValueError(f"Unsupported status: {status!r}. Expected 'paid', 'unpaid', or 'cancelled'.")

    updated = client.get_invoice(invoice_id)
    invoice = Invoice.model_validate(updated)
    return format_invoice_confirmation(invoice)
