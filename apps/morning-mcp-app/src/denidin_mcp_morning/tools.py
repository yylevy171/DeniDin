"""MCP tool implementations wrapping MorningClient for invoice management.

Each function here corresponds 1:1 to an MCP tool registered in server.py
(see contracts/<tool>.json and user-stories.md for the tool contract and
acceptance criteria). Tools receive a MorningClient by dependency injection
(no globals, no monkey-patching per CONSTITUTION.md §XVII) and return a
human-readable, Hebrew-formatted string.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .formatters import (
    format_financial_summary,
    format_invoice_confirmation,
    format_invoice_details,
    format_invoice_list,
)
from .models import _MORNING_STATUS_CODES, FinancialSummary, Invoice
from .morning_client import MorningClient
from .utils.logger import get_logger

logger = get_logger(__name__)

_TAX_INVOICE_DOCUMENT_TYPE = 305
_TRANSACTION_ACCOUNT_DOCUMENT_TYPE = 300  # "חשבון עסקה" — confirmed live via GET /documents/types
_INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE = 320
_PRIMARY_INVOICE_DOCUMENT_TYPES = {
    _TRANSACTION_ACCOUNT_DOCUMENT_TYPE,
    _TAX_INVOICE_DOCUMENT_TYPE,
    _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
}
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
    we filter locally rather than guess and risk silently-wrong results.

    `item["status"]` here is Morning's raw /documents(/search) value: an int
    status code (see models._MORNING_STATUS_CODES), or None for a freshly
    created, not-yet-paid document (confirmed live: a brand-new tax invoice
    has no status code at all until it's closed - see
    _build_payment_receipt_payload's docstring). Both must be normalized onto
    this app's canonical vocabulary (paid/unpaid/cancelled) before comparing
    against `_STATUS_ALIASES` - comparing the raw code/None directly against
    those string aliases can never match anything.
    """
    if not status or status == "all":
        return True

    raw = item.get("status")
    if raw is None:
        item_status = "unpaid"  # no status code yet == not yet closed/paid
    elif isinstance(raw, int):
        item_status = _MORNING_STATUS_CODES.get(raw, str(raw)).lower()
    else:
        item_status = str(raw).lower()
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


def _build_combo_closing_payload(original: dict) -> dict:
    """Build a Morning invoice/receipt combo (type 320) payload that closes a
    type-300 ("חשבון עסקה") `original` as paid.

    Per bugfix-014's Flow 4 finding: a type-300 document is closed by a
    type-320 combo document, not the type-400 receipt used for type-305.
    A 320 document is self-contained and invoice-shaped (carries its own
    line items/VAT), unlike a bare receipt — mirrors _build_cancellation_payload's
    income/vatType/client/payment shape rather than _build_payment_receipt_payload's.
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
        if not income_items:
            total_amount = original.get("amount")

    return {
        "type": _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
        "date": today,
        "lang": original.get("lang", "he"),
        "vatType": original.get("vatType", 1),
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": False,
        "description": f"תשלום עבור חשבון עסקה מספר {original_number or original_id}",
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {
            "self": False,
            "name": client_info.get("name"),
        },
        "income": income_items
        or [
            {
                "catalogNum": "",
                "description": f"תשלום עבור חשבון עסקה מספר {original_number or original_id}",
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


def _mark_invoice_paid(client: MorningClient, invoice_id: str) -> str:
    original = client.get_invoice(invoice_id)

    if original.get("status") in _CLOSED_STATUS_CODES:
        # Already paid — idempotent no-op, avoid creating a duplicate closing document.
        return format_invoice_confirmation(Invoice.model_validate(original))

    original_type = original.get("type")
    if original_type == _TRANSACTION_ACCOUNT_DOCUMENT_TYPE:
        payload = _build_combo_closing_payload(original)
    elif original_type == _TAX_INVOICE_DOCUMENT_TYPE:
        payload = _build_payment_receipt_payload(original)
    else:
        raise ValueError(
            f"Cannot mark invoice paid: unsupported document type {original_type} "
            f"(only {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} and {_TAX_INVOICE_DOCUMENT_TYPE} are supported)"
        )
    client.create_invoice(payload)  # generic POST /documents; payload["type"] determines the document kind

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
    - "paid" -> the closing document depends on the original's own type
      (spec 020, bugfix-014 Flow 4): a type-305 tax invoice gets a linked
      Receipt (type 400); a type-300 transaction account gets a linked
      invoice/receipt combo (type 320); any other original type raises
      ValueError. Idempotent if already paid, regardless of type. See
      _build_payment_receipt_payload / _build_combo_closing_payload.
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


def _build_add_client_payload(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    tax_id: Optional[str] = None,
    address: Optional[str] = None,
) -> Dict[str, Any]:
    """Map friendly add_client inputs onto the real Morning /clients payload.

    Real field names (confirmed via the Postman collection's "Add Client"
    example): `emails` is a list, `taxId` is camelCase. `phone` does not
    appear anywhere in the Postman collection's client schemas/examples —
    it's sent optimistically; Morning may silently ignore it (see the
    real-sandbox test for what's actually observed).
    """
    payload: Dict[str, Any] = {"name": name}
    if email:
        payload["emails"] = [email]
    if phone:
        payload["phone"] = phone
    if tax_id:
        payload["taxId"] = tax_id
    if address:
        payload["address"] = address
    return payload


def add_client(
    client: MorningClient,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    tax_id: Optional[str] = None,
    address: Optional[str] = None,
) -> str:
    """Add a new client to Morning and return a Hebrew confirmation.

    MCP tool: add_client (contracts/add_client.json, user-stories.md US4).

    Args:
        client: An authenticated MorningClient (injected).
        name: Client/company name (required).
        email: Optional client email.
        phone: Optional client phone number.
        tax_id: Optional Israeli business tax ID (ע"מ).
        address: Optional client address.

    Returns:
        A Hebrew confirmation string with the created client's name and id.
    """
    payload = _build_add_client_payload(name, email, phone, tax_id, address)
    response = client.add_client(payload)
    client_id = response.get("id", "")
    return f"נוצר לקוח חדש: {name} (מזהה: {client_id})"


def _resolve_period_dates(
    period: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> tuple:
    """Resolve a friendly period name to a concrete (from_date, to_date) range."""
    today = datetime.now(timezone.utc).date()

    if period == "custom":
        if not (from_date and to_date):
            raise ValueError("period='custom' requires both from_date and to_date")
        return from_date, to_date

    if period == "month":
        start = today.replace(day=1)
    elif period == "quarter":
        quarter_start_month = 3 * ((today.month - 1) // 3) + 1
        start = today.replace(month=quarter_start_month, day=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
    else:
        raise ValueError(f"Unsupported period: {period!r}. Expected 'month', 'quarter', 'year', or 'custom'.")

    return start.isoformat(), today.isoformat()


def _display_amount(invoice: Invoice) -> float:
    return invoice.total_amount if invoice.total_amount is not None else invoice.amount


def get_financial_summary(
    client: MorningClient,
    period: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> str:
    """Aggregate totals/counts for a period and return a Hebrew summary.

    MCP tool: get_financial_summary (contracts/get_financial_summary.json,
    user-stories.md US5).

    Morning has no dedicated summary/aggregation endpoint (confirmed against
    the Postman collection) — this aggregates client-side over
    `/documents/search` results for the resolved date range.

    Known limitation (documented, not silently papered over): cancelling an
    invoice (see update_invoice_status status="cancelled") issues a linked
    Credit Invoice but does NOT change the original invoice's own `status`
    field (confirmed live), and Morning does not return `linkedDocumentIds`
    on read for either document — so a specific cancelled invoice cannot be
    excluded from the paid/unpaid tally without this app persisting that
    mapping itself, which it deliberately does not do (plan.md: stateless).
    As a defensible accounting approximation, this aggregates counts and
    paid/unpaid classification only over primary sale document types (300
    transaction account, 305 tax invoice, 320 invoice+receipt), and nets
    Credit Invoice (330) amounts
    out of `total_invoiced` so a cancelled invoice's face value doesn't
    inflate reported revenue — but its count still appears in
    invoice_count/unpaid_invoice_count since its own status is unchanged.

    Args:
        client: An authenticated MorningClient (injected).
        period: One of "month", "quarter", "year", "custom".
        from_date: Required if period="custom", ISO format YYYY-MM-DD.
        to_date: Required if period="custom", ISO format YYYY-MM-DD.

    Returns:
        A Hebrew financial summary string.

    Raises:
        ValueError: if `period` is invalid, or "custom" without both dates.
    """
    start, end = _resolve_period_dates(period, from_date, to_date)
    response = client.list_invoices(params={"fromDate": start, "toDate": end})
    raw_items = _extract_items(response)

    invoices: List[Invoice] = []
    credit_note_total = 0.0

    for item in raw_items:
        document_type = item.get("type")
        try:
            parsed = Invoice.model_validate(item)
        except ValidationError as exc:
            logger.warning("Skipping unparseable document in get_financial_summary: %s", exc)
            continue

        if document_type == _CREDIT_INVOICE_DOCUMENT_TYPE:
            credit_note_total += _display_amount(parsed)
            continue
        if document_type not in _PRIMARY_INVOICE_DOCUMENT_TYPES:
            continue  # skip receipts/orders/other non-sale document types

        invoices.append(parsed)

    paid_invoices = [invoice for invoice in invoices if invoice.status == "paid"]
    unpaid_invoices = [invoice for invoice in invoices if invoice.status != "paid"]

    total_invoiced = sum(_display_amount(invoice) for invoice in invoices) - credit_note_total
    total_paid = sum(_display_amount(invoice) for invoice in paid_invoices)
    total_unpaid = sum(_display_amount(invoice) for invoice in unpaid_invoices)
    invoice_count = len(invoices)
    average = total_invoiced / invoice_count if invoice_count else 0.0

    summary = FinancialSummary(
        period_start=start,
        period_end=end,
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        total_unpaid=total_unpaid,
        invoice_count=invoice_count,
        paid_invoice_count=len(paid_invoices),
        unpaid_invoice_count=len(unpaid_invoices),
        average_invoice_amount=average,
    )
    return format_financial_summary(summary)


def download_invoice_pdf(client: MorningClient, invoice_id: str, lang: str = "he") -> str:
    """Return a PDF download link for an invoice, in a Hebrew confirmation string.

    MCP tool: download_invoice_pdf (contracts/download_invoice_pdf.json,
    user-stories.md US7).

    Real mechanism (confirmed live): no separate download endpoint call is
    needed — `GET /documents/{id}` (the existing `MorningClient.get_invoice`)
    already returns a `url: {he, origin}` object with ready-to-use, pre-signed
    PDF download links (`GET /documents/download?d=...`).

    Args:
        client: An authenticated MorningClient (injected).
        invoice_id: Morning document id.
        lang: Which link to prefer — "he" (Hebrew) or "origin" (default/English).
            Falls back to whichever is present if the preferred one is missing.

    Returns:
        A Hebrew confirmation string containing the PDF download URL.

    Raises:
        ValueError: if no download URL is present on the document at all.
    """
    original = client.get_invoice(invoice_id)
    urls = original.get("url") or {}
    pdf_url = urls.get(lang) or urls.get("origin") or urls.get("he")

    if not pdf_url:
        raise ValueError(f"No PDF download URL available for invoice {invoice_id!r}.")

    invoice_number = original.get("number", invoice_id)
    return f"קישור להורדת חשבונית מספר {invoice_number}:\n{pdf_url}"
