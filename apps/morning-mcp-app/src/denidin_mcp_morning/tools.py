"""MCP tool implementations wrapping MorningClient for invoice management.

Each function here corresponds 1:1 to an MCP tool registered in server.py
(see contracts/<tool>.json and user-stories.md for the tool contract and
acceptance criteria). Tools receive a MorningClient by dependency injection
(no globals, no monkey-patching per CONSTITUTION.md §XVII) and return a
human-readable, Hebrew-formatted string.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import tiktoken
from email_validator import EmailNotValidError, validate_email
from pydantic import ValidationError

from .audit import log_mutation, log_refusal
from .formatters import (
    format_ambiguous_clients_message,
    format_client_details,
    format_client_list,
    format_client_not_found,
    format_financial_summary,
    format_invoice_confirmation,
    format_invoice_details,
    format_invoice_list,
    format_original_not_linked_to_client,
    format_too_many_clients_message,
    format_too_many_invoices_message,
)
from .models import _MORNING_STATUS_CODES, Client, FinancialSummary, Invoice
from .morning_client import MorningClient
from .utils.logger import get_logger
from .utils.time_utils import now_local

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

# Feature 038: max raw items list_invoices will fetch pages for (mirrors
# _LIST_CLIENTS_MAX_ITEMS's role for list_clients, below) — beyond this,
# report the real total and ask to narrow rather than fetching further
# pages/dumping an unusably long WhatsApp reply.
_LIST_INVOICES_MAX_ITEMS = 100

# Python-level default matching MorningMCPConfig.list_invoices_token_budget's
# default (config.py) — server.py always passes the real config value
# explicitly; this default only matters for direct calls (tests, ad hoc
# scripts) that don't thread a config object through. Real, unmodified
# practical MCP tool-call output limit (research.md Decision 7) — not a
# self-imposed margin below it.
_LIST_INVOICES_TOKEN_BUDGET = 2500

# Reserved out of the token budget for the count line and any truncation
# note, so the *item-block* budget is budget-minus-reserve, not the full
# amount (research.md Decision 6/7: any value in this range gives the same
# outcome for the fixtures this feature's tests use).
_LIST_INVOICES_TOKEN_BUDGET_RESERVE = 120

_TOKEN_ENCODING = tiktoken.get_encoding("o200k_base")

_STATUS_ALIASES = {
    "unpaid": {"unpaid", "open"},
    "paid": {"paid", "closed"},
    "overdue": {"overdue"},
    "cancelled": {"cancelled"},
}


def _build_create_invoice_payload(
    client_id: str,
    amount: float,
    description: str,
    due_date: Optional[str] = None,
    vat_included: bool = True,
    currency: str = "ILS",
) -> dict:
    """Map friendly create_invoice inputs onto a real Morning /documents payload.

    Feature 027: `client_id` is a real, resolved Morning client_id (never a
    bare name) — confirmed live (research.md Decision 1) that Morning
    attaches the document to that real client record, populating
    name/email/etc. server-side. Callers (create_invoice) MUST resolve the
    client via `_resolve_client_for_document_creation` before calling this.

    Mirrors the shape the sandbox is known to accept (see the passing
    tests/integration/test_morning_sandbox_invoices_crud.py fixture): a single
    income line and a single payment line — the sandbox requires at least one
    payment line (תקבולים) to accept a document.
    """
    today = now_local().date().isoformat()
    vat_type = 1 if vat_included else 0

    payload = {
        "type": _TAX_INVOICE_DOCUMENT_TYPE,
        "date": today,
        "lang": "he",
        "vatType": vat_type,
        "currency": currency,
        "rounding": False,
        "signed": True,
        "description": description,
        "client": {
            "self": False,
            "id": client_id,
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


# bugfix-028 A3b - Morning's real payment-method codes, enumerated live against
# the sandbox on 2026-08-09 (types 6-9 and 12 do not exist). Which fields a
# payment line may carry depends entirely on its type: bank details persist ONLY
# on type 4, and a reference number ONLY on type 5/10. Type 1 (מזומן) silently
# drops everything except date/price, which is how four production deposits lost
# their bank details without a single error.
_PAYMENT_TYPE_CASH = 1
_PAYMENT_TYPE_CHEQUE = 2
_PAYMENT_TYPE_CREDIT_CARD = 3
_PAYMENT_TYPE_BANK_TRANSFER = 4
_PAYMENT_TYPE_PAYPAL = 5
_PAYMENT_TYPE_APP = 10

_PAYMENT_APP_TYPES = {"bit": 1, "pay": 2, "paybox": 3, "colu": 4, "google pay": 5, "apple pay": 6}

# The default is a BANK TRANSFER, not cash (user decision, 2026-08-09, reversing
# the earlier triage call that "all payments are intentionally booked as cash" -
# made under a wrong impression). Payments must reflect how the money actually
# arrived.
_DEFAULT_PAYMENT_METHOD = "bank_transfer"

_PAYMENT_METHOD_TYPES = {
    "bank_transfer": _PAYMENT_TYPE_BANK_TRANSFER,
    "cash": _PAYMENT_TYPE_CASH,
    "cheque": _PAYMENT_TYPE_CHEQUE,
    "credit_card": _PAYMENT_TYPE_CREDIT_CARD,
    "paypal": _PAYMENT_TYPE_PAYPAL,
}


def _validate_payment_date(payment_date: Optional[str]) -> str:
    """Validate a real transaction date for a payment line (bugfix-028 A3).

    A payment-backed document records money that has ALREADY moved, so its
    payment date is a fact to be carried, never a value to be guessed. Silently
    substituting "today" is exactly what dated four production documents 09/08
    for deposits value-dated 04/08-06/08.

    Raises ValueError - never falls back - when the date is missing, unparseable,
    or in the future (money cannot have arrived tomorrow; a future date means the
    extraction failed and the user must be asked).
    """
    if not payment_date:
        raise ValueError(
            "A payment-backed document needs the real date the money moved, and none "
            "was supplied. Ask the user for the transaction date rather than assuming today."
        )
    # Accepts ISO (YYYY-MM-DD) and this project's own persisted DD/MM/YYYY form.
    # The ledger event that supplies this date stores it as DD/MM/YYYY - by design,
    # matching `event_date` (REQ-DATA-005/007) - and Israeli bank confirmations
    # print it that way too, so ISO-only meant our own captured date could not be
    # handed to our own tool without a conversion nobody performed. DD/MM is not
    # ambiguous here: nothing in this system emits MM/DD.
    parsed = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(payment_date, fmt).date()
            break
        except (ValueError, TypeError):
            continue
    if parsed is None:
        raise ValueError(
            f"Transaction date {payment_date!r} is not a usable date "
            f"(expected YYYY-MM-DD or DD/MM/YYYY). Ask the user to confirm the date "
            f"rather than guessing at its format."
        )
    if parsed > now_local().date():
        raise ValueError(
            f"Transaction date {payment_date!r} is in the future - money cannot already "
            f"have arrived. Ask the user to confirm the real transaction date."
        )
    # Always hand Morning the ISO form, whichever form came in - the API takes
    # YYYY-MM-DD, and returning the caller's string verbatim would send a
    # DD/MM/YYYY date straight through.
    return parsed.isoformat()


def _build_payment_line(
    amount: float,
    payment_date: str,
    payment_method: str = _DEFAULT_PAYMENT_METHOD,
    bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None,
    bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None,
    currency: str = "ILS",
) -> dict:
    """Build one Morning payment line carrying how, and when, the money arrived.

    Field support is per-type and live-verified (2026-08-09): `bankName`/
    `bankBranch`/`bankAccount` persist only on type 4, and `transactionId` only
    on types 5 and 10. Anything sent on a type that doesn't support it is
    dropped by Morning without an error, so this maps deliberately rather than
    sending everything and hoping.
    """
    method = (payment_method or _DEFAULT_PAYMENT_METHOD).strip().casefold()
    line: Dict[str, Any] = {
        "price": amount,
        "date": _validate_payment_date(payment_date),
        "currency": currency,
        "currencyRate": 1,
    }

    if method in _PAYMENT_APP_TYPES:
        line["type"] = _PAYMENT_TYPE_APP
        line["appType"] = _PAYMENT_APP_TYPES[method]
        if transaction_reference:
            line["transactionId"] = transaction_reference
        return line

    if method not in _PAYMENT_METHOD_TYPES:
        raise ValueError(
            f"Unknown payment method {payment_method!r}. Supported: "
            f"{sorted(list(_PAYMENT_METHOD_TYPES) + list(_PAYMENT_APP_TYPES))}"
        )

    line["type"] = _PAYMENT_METHOD_TYPES[method]
    if line["type"] == _PAYMENT_TYPE_BANK_TRANSFER:
        # Morning renders these back as "בנק X / סניף Y / מס' חשבון Z" itself.
        if bank_number:
            line["bankName"] = bank_number
        if bank_branch:
            line["bankBranch"] = bank_branch
        if bank_account:
            line["bankAccount"] = bank_account
    elif line["type"] == _PAYMENT_TYPE_PAYPAL and transaction_reference:
        line["transactionId"] = transaction_reference
    return line


def _read_back_stored_total(client: MorningClient, doc_id: str) -> Optional[float]:
    """Read what Morning ACTUALLY stored for a just-created document.

    bugfix-028 A4 failsafe. `POST /documents` returns no total and no amount at
    all (probed live 2026-08-09: the response carries only client/id/lang/number/
    signed/taxAuthority*/type/url/vatRate), so `response.get("total", amount)`
    always handed back the number we asked for. That is how a document Morning
    had stored at ₪2,784.80 was confirmed to the user as ₪2,360 for two days.

    Never raises: this runs after a document has already been created, and a
    failed read-back must not turn a successful creation into an error.
    """
    if not doc_id:
        return None
    try:
        stored = client.get_invoice(doc_id)
    except Exception as exc:  # noqa: BLE001 - failsafe: a read-back must never mask a real creation
        logger.warning(f"Could not read back document {doc_id} to verify its stored total: {exc}")
        return None
    total = stored.get("amount")
    return float(total) if isinstance(total, (int, float)) else None


def _amount_mismatch_warning(requested: float, stored: Optional[float]) -> str:
    """bugfix-028 A4: if what Morning stored differs from what the user approved,
    say so, show both numbers, and ask - never silently reconcile."""
    if stored is None or abs(stored - requested) < 0.01:
        return ""
    return (
        f"⚠️ שים לב: אישרת {requested:,.2f} ₪ אבל המסמך נוצר בפועל על סך "
        f"{stored:,.2f} ₪. מה תרצה שאעשה?\n\n"
    )


def _build_transaction_account_payload(
    client_id: str,
    amount: float,
    description: str,
    vat_included: bool,
    due_date: Optional[str] = None,
    currency: str = "ILS",
) -> dict:
    """Map create_transaction_account inputs onto a real Morning /documents
    payload for a type 300 ("חשבון עסקה") document.

    Feature 027: `client_id` is a real, resolved Morning client_id (never a
    bare name) - see _build_create_invoice_payload's docstring for the same
    note; callers (create_transaction_account) MUST resolve via
    `_resolve_client_for_document_creation` first.

    bugfix-028 A2 - `vat_included` is REQUIRED and has no default: an undecided
    VAT treatment may never reach Morning.

    This used to send no `vatType`/`vatRate` anywhere, on the bugfix-014 Flow 4
    premise that a type-300 "carries NO VAT obligation ... the field's mere
    presence implies a tax document". That premise was recorded from the
    customer's Morning UI and explicitly never reproduced against the API, and
    it is wrong: probed live 2026-08-09, omitting `vatType` is treated exactly
    as `vatType: 0` ("price EXCLUDES vat"), so Morning adds ~18% - a price of 11
    is stored as 12.98, and in production ₪2,360 was stored as ₪2,784.80.
    `vatType: 1` ("price INCLUDES vat") stores 11 as 11.
    """
    today = now_local().date().isoformat()
    vat_type = 1 if vat_included else 0

    payload = {
        "type": _TRANSACTION_ACCOUNT_DOCUMENT_TYPE,
        "date": today,
        "lang": "he",
        "vatType": vat_type,
        "currency": currency,
        "rounding": False,
        "signed": True,
        "description": description,
        "client": {
            "self": False,
            "id": client_id,
        },
        "income": [
            {
                "catalogNum": "",
                "description": description,
                "quantity": 1,
                "price": amount,
                "currency": currency,
                "currencyRate": 1,
                "vatType": vat_type,
            }
        ],
        "payment": [
            {
                "type": _PAYMENT_TYPE_CASH,
                "price": amount,
                "date": today,
            }
        ],
    }
    if due_date:
        payload["dueDate"] = due_date
    return payload


def create_transaction_account(
    client: MorningClient,
    client_name: str,
    amount: float,
    description: str,
    vat_included: bool,
    due_date: Optional[str] = None,
) -> str:
    """Create a non-tax transaction account ("חשבון עסקה", type 300) in
    Morning and return a Hebrew confirmation message.

    MCP tool: create_transaction_account (feature 021).

    Feature 027: client_name is resolved to a real Morning client record
    before anything is created (REQ-INV-001/002/003/005/011) - see
    create_invoice's docstring for the full found/not-found/ambiguous/
    non-exact-disclosure contract, reused identically here.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: Client name - resolved to a real client record, never
            passed through as a bare string.
        amount: Amount in NIS - carries no VAT (see _build_transaction_account_payload).
        description: Service/product description.
        due_date: Optional due date, ISO format YYYY-MM-DD.

    Returns:
        A Hebrew confirmation string with the document number and amount, or
        a friendly refusal message (no document created) if the client
        can't be resolved unambiguously.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolution = _resolve_client_for_document_creation(client, client_name)
    if resolution.refusal_message is not None:
        return resolution.refusal_message

    payload = _build_transaction_account_payload(
        resolution.client_id, amount, description, vat_included, due_date
    )
    response = client.create_invoice(payload)
    log_mutation(
        "create_transaction_account",
        payload=payload,
        response=response,
        client_id=resolution.client_id,
        client_name=resolution.disclosure_name or client_name,
    )

    doc_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    stored_total = _read_back_stored_total(client, doc_id)
    display_name = resolution.disclosure_name or client_name
    invoice = Invoice(
        id=doc_id,
        number=response.get("number"),
        client_name=display_name,
        amount=amount,
        total_amount=stored_total if stored_total is not None else amount,
        currency=response.get("currency", "ILS"),
        due_date=due_date,
        status=response.get("status"),
        type=_TRANSACTION_ACCOUNT_DOCUMENT_TYPE,
    )
    confirmation = _amount_mismatch_warning(amount, stored_total) + format_invoice_confirmation(invoice)
    if resolution.disclosure_name:
        return f"מצאתי והשתמשתי בלקוח הבא: {resolution.disclosure_name}\n{confirmation}"
    return confirmation


def _build_combo_document_payload(
    client_id: str,
    amount: float,
    description: str,
    vat_included: bool,
    payment_date: str,
    payment_method: str = _DEFAULT_PAYMENT_METHOD,
    bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None,
    bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None,
    currency: str = "ILS",
) -> dict:
    """Map create_combo_document inputs onto a real Morning /documents
    payload for a type 320 ("חשבונית מס/קבלה") combo invoice+receipt.

    Feature 027: `client_id` is a real, resolved Morning client_id (never a
    bare name) - see _build_create_invoice_payload's docstring for the same
    note; callers (create_combo_document) MUST resolve via
    `_resolve_client_for_document_creation` first.

    Per bugfix-014 Flow 1: this document is issued when payment has ALREADY been
    received - self-contained, always already "paid", no due date (unlike a type
    305 tax invoice, which is a request for later payment).

    bugfix-028 A3/A3b: because the money has already moved, this document
    records a real historical transaction - so `payment_date` is REQUIRED and
    validated (never defaulted to today), and the payment carries how the money
    arrived. The default method is a bank transfer, which is the only type
    Morning stores bank details on.

    Note the type-320 amount consistency rule (live-confirmed): Morning rejects
    the document outright with `errorCode 2422` if the income total and the
    payment total disagree - which is what a wrong `vatType` causes here. On a
    320 a VAT mistake fails loudly rather than inflating silently, unlike the
    type-300 case behind A2.
    """
    today = now_local().date().isoformat()
    vat_type = 1 if vat_included else 0

    return {
        "type": _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
        "date": today,
        "lang": "he",
        "vatType": vat_type,
        "currency": currency,
        "rounding": False,
        "signed": True,
        "description": description,
        "client": {
            "self": False,
            "id": client_id,
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
            _build_payment_line(
                amount=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                bank_number=bank_number,
                bank_branch=bank_branch,
                bank_account=bank_account,
                transaction_reference=transaction_reference,
                currency=currency,
            )
        ],
    }


def create_combo_document(
    client: MorningClient,
    client_name: str,
    amount: float,
    description: str,
    vat_included: bool,
    payment_date: str,
    payment_method: str = _DEFAULT_PAYMENT_METHOD,
    bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None,
    bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None,
) -> str:
    """Create an already-paid combo invoice+receipt ("חשבונית מס/קבלה",
    type 320) in Morning and return a Hebrew confirmation message.

    MCP tool: create_combo_document (feature 021).

    Feature 027: client_name is resolved to a real Morning client record
    before anything is created (REQ-INV-001/002/003/005/011) - see
    create_invoice's docstring for the full found/not-found/ambiguous/
    non-exact-disclosure contract, reused identically here.

    bugfix-028 (A2/A3/A3b): `vat_included` and `payment_date` are both REQUIRED.
    This document asserts that money has already arrived, so how much of it is
    VAT, and when it arrived, are facts about a real transaction - neither may be
    defaulted or guessed. Ask the user rather than assuming.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: Client name - resolved to a real client record, never
            passed through as a bare string.
        amount: Amount in NIS, already received.
        description: Service/product description.
        vat_included: Whether VAT is included in `amount`. Required - an
            undecided VAT treatment must never reach Morning (A2).
        payment_date: The real date the money moved, ISO YYYY-MM-DD. Required,
            must not be in the future, never defaulted to today (A3).
        payment_method: How the money arrived - "bank_transfer" (default),
            "cash", "cheque", "credit_card", "paypal", or a payment app
            ("bit", "pay", "paybox", "colu", "google pay", "apple pay").
        bank_number/bank_branch/bank_account: Bank details from the transfer
            confirmation. Stored only on a bank transfer (A3b).
        transaction_reference: The אסמכתה. Stored only on a payment app or
            PayPal payment - Morning has no field for it on a bank transfer.

    Returns:
        A Hebrew confirmation string with the document number and the amount
        Morning actually stored, or a friendly disambiguation message (no
        document created) if the client name matches more than one client.

    Raises:
        ClientNotFoundError: if the client name matches no client at all.
        ValueError: if payment_date is missing, unparseable, or in the future,
            or payment_method is unknown.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolution = _resolve_client_for_document_creation(client, client_name)
    if resolution.refusal_message is not None:
        return resolution.refusal_message

    payload = _build_combo_document_payload(
        resolution.client_id,
        amount,
        description,
        vat_included=vat_included,
        payment_date=payment_date,
        payment_method=payment_method,
        bank_number=bank_number,
        bank_branch=bank_branch,
        bank_account=bank_account,
        transaction_reference=transaction_reference,
    )
    response = client.create_invoice(payload)
    log_mutation(
        "create_combo_document",
        payload=payload,
        response=response,
        client_id=resolution.client_id,
        client_name=resolution.disclosure_name or client_name,
    )

    doc_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    stored_total = _read_back_stored_total(client, doc_id)
    display_name = resolution.disclosure_name or client_name
    invoice = Invoice(
        id=doc_id,
        number=response.get("number"),
        client_name=display_name,
        amount=amount,
        total_amount=stored_total if stored_total is not None else amount,
        currency=response.get("currency", "ILS"),
        status=response.get("status"),
        type=_INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
    )
    confirmation = _amount_mismatch_warning(amount, stored_total) + format_invoice_confirmation(invoice)
    if resolution.disclosure_name:
        return f"מצאתי והשתמשתי בלקוח הבא: {resolution.disclosure_name}\n{confirmation}"
    return confirmation


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

    Feature 027 (REQ-INV-001/002/003/005/011): client_name is resolved to a
    real Morning client record via `_resolve_client_for_document_creation`
    before anything is created - never passed through as a bare string:
    - Exactly one match (exact or non-exact/fuzzy) -> the document is
      attached to that real client's id; a non-exact match's real name is
      disclosed in the confirmation reply.
    - Zero matches -> no document is created; a friendly "client not found"
      message is returned instead.
    - More than one match -> no document is created; a disambiguation
      message listing the real candidates is returned instead.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: Client name - resolved to a real client record, never
            passed through as a bare string.
        amount: Invoice amount in NIS.
        description: Service/product description.
        due_date: Optional due date, ISO format YYYY-MM-DD.
        vat_included: Whether VAT is included in the amount (default True).

    Returns:
        A Hebrew confirmation string with the invoice number, amount, and
        status, or a friendly refusal message (no document created) if the
        client can't be resolved unambiguously.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolution = _resolve_client_for_document_creation(client, client_name)
    if resolution.refusal_message is not None:
        return resolution.refusal_message

    payload = _build_create_invoice_payload(resolution.client_id, amount, description, due_date, vat_included)
    response = client.create_invoice(payload)
    log_mutation(
        "create_invoice",
        payload=payload,
        response=response,
        client_id=resolution.client_id,
        client_name=resolution.disclosure_name or client_name,
    )

    invoice_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    display_name = resolution.disclosure_name or client_name
    invoice = Invoice(
        id=invoice_id,
        number=response.get("number"),
        client_name=display_name,
        amount=amount,
        total_amount=response.get("total", amount),
        currency=response.get("currency", "ILS"),
        due_date=due_date,
        status=response.get("status"),
    )
    confirmation = format_invoice_confirmation(invoice)
    if resolution.disclosure_name:
        return f"מצאתי והשתמשתי בלקוח הבא: {resolution.disclosure_name}\n{confirmation}"
    return confirmation


def _map_list_invoices_filters(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
    number: Optional[str] = None,
) -> Dict[str, Any]:
    """Map friendly list_invoices filters onto Morning's real /documents/search params.

    Key names (fromDate/toDate/clientName) are proven against the sandbox by
    tests/integration/test_morning_sandbox_invoices_crud.py. `status` is
    deliberately NOT sent server-side — see _matches_status.

    `number` (bugfix, 2026-08-07): Morning's real /documents/search endpoint
    has always accepted a `number` filter (confirmed via the checked-in
    Postman collection's own "Search Documents" example - a bare int, e.g.
    `"number": 12001`) - this was never wired up here, so any reference to
    an invoice by its human-visible number alone (no client name/date) had
    no real way to resolve short of an unfiltered list_invoices call, which
    fails outright once the sandbox holds more documents than the fetch cap
    (_LIST_INVOICES_MAX_ITEMS). `number` is accepted here as a string (the
    natural shape a model/user provides, e.g. "51365") and converted to the
    int Morning's API actually expects; a non-numeric value is dropped
    rather than sent (Morning would reject it, and silently sending a
    string risks matching nothing with no clear error).
    """
    params: Dict[str, Any] = {}
    if from_date:
        params["fromDate"] = from_date
    if to_date:
        params["toDate"] = to_date
    if client_name:
        params["clientName"] = client_name
    if number:
        try:
            params["number"] = int(number)
        except (TypeError, ValueError):
            logger.warning("Ignoring non-numeric invoice number filter: %r", number)
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


def _truncate_invoices_to_token_budget(
    invoices: List[Invoice], token_budget: int
) -> List[Invoice]:
    """Return the largest prefix of `invoices` whose formatted blocks fit
    within `token_budget` (reserving headroom for the count line/closing
    note - REQ-INVOICE-008, research.md Decision 6/7)."""
    item_budget = token_budget - _LIST_INVOICES_TOKEN_BUDGET_RESERVE
    shown: List[Invoice] = []
    cumulative_tokens = 0
    for invoice in invoices:
        block_tokens = len(_TOKEN_ENCODING.encode(format_invoice_confirmation(invoice)))
        if cumulative_tokens + block_tokens > item_budget:
            break
        cumulative_tokens += block_tokens
        shown.append(invoice)
    return shown


def list_invoices(
    client: MorningClient,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
    number: Optional[str] = None,
    token_budget: int = _LIST_INVOICES_TOKEN_BUDGET,
) -> str:
    """List/search invoices and return a Hebrew, human-readable result.

    MCP tool: list_invoices (contracts/list_invoices.json, user-stories.md
    US1/US2/US3). Real-pagination fetch cap ported from list_clients
    (Feature 026, research.md Decision 1) - reads the real total from
    Morning's first page and decides what to do before fetching anything
    further:
    - `total > _LIST_INVOICES_MAX_ITEMS`: fetch nothing further - report
      the real total and ask for a narrower search instead of silently
      truncating or dumping an unusable wall of text (REQ-INVOICE-003).
    - `total <= _LIST_INVOICES_MAX_ITEMS`: fetch every remaining page
      internally, apply the local status filter, and - if the complete
      formatted reply would exceed `token_budget` - include only the
      largest prefix that fits, with an honest "showing X of Y" message
      (REQ-INVOICE-008/009).

    Args:
        client: An authenticated MorningClient (injected).
        status: Optional filter — "paid", "unpaid", "overdue", "cancelled", or "all".
        from_date: Optional start date, ISO format YYYY-MM-DD.
        to_date: Optional end date, ISO format YYYY-MM-DD.
        client_name: Optional client-name filter.
        number: Optional exact document-number filter (e.g. "51365") - the
            real Morning API's own `number` search field (bugfix, 2026-08-07),
            previously never wired up here. Non-numeric values are ignored.
        token_budget: Max estimated tiktoken size of the formatted reply
            before truncation (REQ-INVOICE-010: config-driven in
            production via MorningMCPConfig.list_invoices_token_budget,
            passed in by server.py - this default is only used by direct
            calls that don't thread a config value through).

    Returns:
        A Hebrew string listing matching invoices (a token-budget-limited
        prefix if the complete set doesn't fit), a friendly "no results"
        message if none match, or a "too many, narrow your search" message
        if the real total exceeds the fetch cap.
    """
    params = _map_list_invoices_filters(from_date, to_date, client_name, number)
    first_page = client.list_invoices(params=params)
    raw_items = _extract_items(first_page)
    page_info = first_page if isinstance(first_page, dict) else {}
    total = page_info.get("total", len(raw_items)) or 0

    if total > _LIST_INVOICES_MAX_ITEMS:
        return format_too_many_invoices_message(total)

    items = list(raw_items)
    page_num = page_info.get("page", 1) or 1
    total_pages = page_info.get("pages", 1) or 1
    while len(items) < total and page_num < total_pages:
        page_num += 1
        next_page = client.list_invoices(params={**params, "page": page_num})
        items.extend(_extract_items(next_page))

    matching_items = [item for item in items if _matches_status(item, status)]

    invoices: List[Invoice] = []
    for item in matching_items:
        try:
            invoices.append(Invoice.model_validate(item))
        except ValidationError as exc:
            logger.warning("Skipping unparseable invoice in list_invoices result: %s", exc)

    shown_invoices = _truncate_invoices_to_token_budget(invoices, token_budget)

    return format_invoice_list(shown_invoices, total_matched=len(invoices))


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


def _build_cancellation_payload(
    original: dict,
    amount: Optional[float] = None,
    description: Optional[str] = None,
) -> dict:
    """Build a Morning credit-invoice (type 330) payload that cancels/credits
    `original`, either in full (defaults) or partially (`amount` override).

    Israeli law does not allow deleting/voiding an issued tax invoice — the
    correct mechanism (confirmed live via GET /documents/types: 330 =
    "חשבונית זיכוי") is to issue a linked credit invoice that offsets it.
    Mirrors the original's client and line items rather than guessing, since
    this produces a real financial document. `amount`/`description` let a
    caller override the mirrored defaults (feature 021: standalone,
    partial credit notes are a real Morning capability, not just a full
    cancellation side effect of update_invoice_status).

    Feature 027 (REQ-INV-012): reuses `original`'s real client_id instead of
    rebuilding a bare-name client object - callers (create_credit_note) MUST
    check `_extract_linked_client_id(original)` and refuse before calling
    this if it's None (a pre-feature, bare-name-only original).
    """
    today = now_local().date().isoformat()
    income_items = original.get("income") or []
    original_id = str(original.get("id") or original.get("documentId") or "")
    original_number = original.get("number")
    total_amount = original.get("total")
    if total_amount is None:
        total_amount = sum(
            float(item.get("price", 0)) * float(item.get("quantity", 1)) for item in income_items
        )
    credit_amount = amount if amount is not None else total_amount
    credit_description = description or f"ביטול חשבונית מספר {original_number or original_id}"

    return {
        "type": _CREDIT_INVOICE_DOCUMENT_TYPE,
        "date": today,
        "lang": original.get("lang", "he"),
        "vatType": original.get("vatType", 1),
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": True,
        "description": credit_description,
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {
            "self": False,
            "id": _extract_linked_client_id(original),
        },
        "income": [
            {
                "catalogNum": "",
                "description": credit_description,
                "quantity": 1,
                "price": credit_amount,
                "currency": original.get("currency", "ILS"),
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": original.get("vatType", 1),
            }
        ],
        "payment": [{"type": 1, "price": credit_amount, "date": today}],
    }


def create_credit_note(
    client: MorningClient,
    original_invoice_id: str,
    amount: Optional[float] = None,
    description: Optional[str] = None,
) -> str:
    """Create a standalone credit note ("חשבונית זיכוי", type 330) linked to
    an existing document, and return a Hebrew confirmation.

    MCP tool: create_credit_note (feature 021). Directly user-invocable and
    supports partial credit notes via `amount`. Feature 023 removed the
    separate update_invoice_status tool and its internal _cancel_invoice
    helper (which this function already fully subsumed for the full-amount
    case) - "cancel" phrasing now dispatches straight here, decided by the
    model, not a status-word-matching code path.

    Args:
        client: An authenticated MorningClient (injected).
        original_invoice_id: Morning document id of the invoice being credited.
        amount: Optional override — defaults to the original's full total.
        description: Optional override — defaults to a generated cancellation note.

    Returns:
        A Hebrew confirmation string with the new credit note's number, or a
        friendly refusal message (no document created, REQ-INV-013) if the
        original isn't linked to a real client record.

    Raises:
        Any exception raised by `client.get_invoice` if `original_invoice_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    original = client.get_invoice(original_invoice_id)
    if _extract_linked_client_id(original) is None:
        log_refusal(
            "create_credit_note",
            "original_not_linked_to_client",
            original_invoice_id=original_invoice_id,
        )
        return format_original_not_linked_to_client()

    payload = _build_cancellation_payload(original, amount=amount, description=description)
    credit_response = client.create_invoice(payload)
    log_mutation(
        "create_credit_note",
        payload=payload,
        response=credit_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    original_number = original.get("number", original_invoice_id)
    credit_number = credit_response.get("number", credit_response.get("id", ""))

    return (
        f"הופקה חשבונית זיכוי מספר {credit_number} עבור חשבונית מספר {original_number}."
    )


_CLOSED_STATUS_CODES = {1, 2}  # closed (via payment) / manually closed — see models._MORNING_STATUS_CODES


def _build_payment_receipt_payload(original: dict, amount: Optional[float] = None) -> dict:
    """Build a Morning receipt (type 400) payload that marks `original` paid
    (fully by default, or partially via `amount`).

    Real mechanism (confirmed live): POST /documents/{id}/close returns 400
    (errorCode 3000) for tax invoices — close/open only apply to documents
    that were manually closed via that same endpoint (its own error message:
    "לא ניתן לפתוח מסמך שאינו סגור ידנית", i.e. "cannot open a document that
    wasn't manually closed"). A tax invoice is instead marked paid by issuing
    a linked Receipt (type 400) referencing it via linkedDocumentIds; Morning
    then flips the original's status automatically (verified live: None -> 1).
    `amount` lets a caller issue a partial-payment receipt (feature 021:
    standalone create_receipt) instead of always closing the full amount.

    Feature 027 (REQ-INV-012): reuses `original`'s real client_id instead of
    rebuilding a bare-name client object - callers (create_receipt) MUST
    check `_extract_linked_client_id(original)` and refuse before calling
    this if it's None (a pre-feature, bare-name-only original).
    """
    today = now_local().date().isoformat()
    original_id = str(original.get("id") or original.get("documentId") or "")
    original_number = original.get("number")
    total_amount = original.get("total")
    if total_amount is None:
        total_amount = original.get("amount")
    receipt_amount = amount if amount is not None else total_amount

    return {
        "type": 400,
        "date": today,
        "lang": original.get("lang", "he"),
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": True,
        "description": f"תשלום עבור חשבונית מספר {original_number or original_id}",
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {"self": False, "id": _extract_linked_client_id(original)},
        "payment": [{"type": 1, "price": receipt_amount, "date": today}],
    }


def _build_combo_closing_payload(
    original: dict,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    vat_included: bool = True,
) -> dict:
    """Build a Morning invoice/receipt combo (type 320) payload that closes a
    type-300 ("חשבון עסקה") `original` as paid, either in full (defaults) or
    partially (`amount` override).

    Per bugfix-014's Flow 4 finding: a type-300 document is closed by a
    type-320 combo document, not the type-400 receipt used for type-305.
    A 320 document is self-contained and invoice-shaped (carries its own
    line items/VAT), unlike a bare receipt.

    `vat_included` controls the new document's own top-level `vatType`
    (1/0) - it must NOT be inferred from the original's own `vatType`
    (confirmed live, feature 023): a real type-300 document created via
    create_transaction_account carries no VAT concept and Morning reports it
    back as `vatType: 0`.

    Always builds a single clean income line from the resolved close amount
    (never mirrors the original's raw `income` items - confirmed live,
    feature 023: those items carry `vatRate`/`vatType` computed under the
    ORIGINAL's own vatType context, e.g. a no-vatRate item still gets
    Morning's default ~18% applied despite the account's exempt vatType;
    resubmitting them verbatim under this document's own, possibly
    different, `vat_included` creates an internally inconsistent payload -
    Morning then correctly refuses to reconcile income against payment, or
    reconciles them at a different total than intended and never flips the
    original's status). The resolved amount instead comes from Morning's own
    authoritative computed total (`total`, falling back to `amount`) rather
    than re-summing raw item prices, since that sum would miss any VAT
    Morning silently applied - confirmed live: a 40.0 item with no vatRate
    became a real 47.2 "amount" owed; closing for 40.0 instead of 47.2 left
    the original genuinely underpaid and its status correctly never flipped.

    Feature 027 (REQ-INV-012): reuses `original`'s real client_id instead of
    rebuilding a bare-name client object - callers (close_transaction_account)
    MUST check `_extract_linked_client_id(original)` and refuse before
    calling this if it's None (a pre-feature, bare-name-only original).
    """
    today = now_local().date().isoformat()
    original_id = str(original.get("id") or original.get("documentId") or "")
    original_number = original.get("number")
    total_amount = original.get("total")
    if total_amount is None:
        total_amount = original.get("amount")
    if total_amount is None:
        income_items = original.get("income") or []
        total_amount = sum(
            float(item.get("price", 0)) * float(item.get("quantity", 1)) for item in income_items
        )

    vat_type = 1 if vat_included else 0
    close_amount = amount if amount is not None else total_amount
    close_description = description or f"תשלום עבור חשבון עסקה מספר {original_number or original_id}"

    return {
        "type": _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
        "date": today,
        "lang": original.get("lang", "he"),
        "vatType": vat_type,
        "currency": original.get("currency", "ILS"),
        "rounding": False,
        "signed": True,
        "description": close_description,
        "linkedDocumentIds": [original_id] if original_id else [],
        "client": {
            "self": False,
            "id": _extract_linked_client_id(original),
        },
        "income": [
            {
                "catalogNum": "",
                "description": close_description,
                "quantity": 1,
                "price": close_amount,
                "currency": original.get("currency", "ILS"),
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": vat_type,
            }
        ],
        "payment": [{"type": 1, "price": close_amount, "date": today}],
    }


def close_transaction_account(
    client: MorningClient,
    original_invoice_id: str,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    vat_included: bool = True,
) -> str:
    """Create a standalone combo document ("חשבונית מס/קבלה", type 320) that
    closes an existing transaction account ("חשבון עסקה", type 300), linked
    via `linkedDocumentIds`, and return a Hebrew confirmation.

    MCP tool: close_transaction_account (feature 023). Mirrors
    create_credit_note/create_receipt's existing standalone-with-reference
    pattern (021), extended to the type-300->320 closing flow (bugfix-014
    Flow 4, originally 020). Feature 023 removed the separate
    update_invoice_status tool - "mark as paid" phrasing for a type-300
    original now dispatches straight here, decided by the model, not a
    status-word-matching code path.

    Idempotency (feature 023): unlike Morning itself, which does NOT reject a
    duplicate closing document (confirmed live), a full-amount call
    (`amount=None`) against an already-closed original is a no-op returning
    the current state, so repeated "mark as paid"-style requests can't create
    duplicate combo documents. An explicit partial `amount` always creates a
    new document regardless of current status - partial closes are a
    deliberate, repeatable real Morning capability.

    Args:
        client: An authenticated MorningClient (injected).
        original_invoice_id: Morning document id of the transaction account
            being closed.
        amount: Optional override — defaults to the original's full total.
        description: Optional override — defaults to a generated closing note.
        vat_included: Whether the new combo document should include VAT
            (default True). Must be decided explicitly by the caller - never
            inferred from the type-300 original's own (VAT-less) shape;
            asking the user when unstated is the model's responsibility
            (runtime_constitution.md), not this function's.

    Returns:
        A Hebrew confirmation string with the new combo document's number,
        or a friendly refusal message (no document created, REQ-INV-013) if
        the original isn't linked to a real client record.

    Raises:
        ValueError: If the original document's type is not 300 (transaction
            account) — the combo-closing flow only applies to type-300
            originals; other types are not guessed at.
        Any exception raised by `client.get_invoice` if `original_invoice_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    original = client.get_invoice(original_invoice_id)
    original_type = original.get("type")
    if original_type != _TRANSACTION_ACCOUNT_DOCUMENT_TYPE:
        raise ValueError(
            f"Cannot close as a transaction account: unsupported document type {original_type} "
            f"(only {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} is supported)"
        )

    if amount is None and original.get("status") in _CLOSED_STATUS_CODES:
        # Already closed — idempotent no-op, avoid creating a duplicate closing document.
        return format_invoice_confirmation(Invoice.model_validate(original))

    if _extract_linked_client_id(original) is None:
        # Pre-feature, bare-name-only original - refuse rather than fall
        # back to rebuilding a bare-name client object (REQ-INV-013).
        log_refusal(
            "close_transaction_account",
            "original_not_linked_to_client",
            original_invoice_id=original_invoice_id,
        )
        return format_original_not_linked_to_client()

    payload = _build_combo_closing_payload(
        original, amount=amount, description=description, vat_included=vat_included
    )
    combo_response = client.create_invoice(payload)
    log_mutation(
        "close_transaction_account",
        payload=payload,
        response=combo_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    original_number = original.get("number", original_invoice_id)
    combo_number = combo_response.get("number", combo_response.get("id", ""))

    return (
        f"הופקה חשבונית מס/קבלה מספר {combo_number} לסגירת חשבון עסקה מספר {original_number}."
    )


def create_receipt(
    client: MorningClient,
    original_invoice_id: str,
    amount: Optional[float] = None,
    payment_date: Optional[str] = None,
) -> str:
    """Create a standalone receipt ("קבלה", type 400) linked to an existing
    document, and return a Hebrew confirmation.

    MCP tool: create_receipt (feature 021). Directly user-invocable and
    supports partial-amount receipts. Feature 023 removed the separate
    update_invoice_status tool - "mark as paid" phrasing for a type-305
    original now dispatches straight here, decided by the model (which must
    resolve the original's real type itself via get_invoice_details first),
    not a status-word-matching code path.

    Only accepts a type-305 original (feature 023) - any other type (300,
    a transaction account closed by close_transaction_account instead; 320,
    already self-closed; 330/400, not themselves payable) is rejected. This
    is a deterministic backstop for when the caller picked the wrong tool,
    not the primary defense (the model is expected to resolve the type
    correctly before calling any create_*/close_* tool).

    Idempotency (feature 023): unlike Morning itself, which does NOT reject a
    duplicate receipt (confirmed live - two full receipts were both created
    against the same already-paid invoice with no rejection), a full-amount
    call (`amount=None`) against an already-closed original is a no-op
    returning the current state. An explicit partial `amount` always creates
    a new receipt regardless of current status - partial payments are a
    deliberate, repeatable real Morning capability.

    Args:
        client: An authenticated MorningClient (injected).
        original_invoice_id: Morning document id of the invoice being paid.
        amount: Optional override — defaults to the original's full total.
        payment_date: Currently unused — payload uses today's date; reserved
            for backdating support.

    Returns:
        A Hebrew confirmation string with the new receipt's number, or a
        friendly refusal message (no document created, REQ-INV-013) if the
        original isn't linked to a real client record.

    Raises:
        ValueError: If the original document's type is not 305 (tax
            invoice) — e.g. 300 (transaction account, use
            close_transaction_account instead), 320 (combo, already
            self-closed), 330/400 (a credit note/receipt is not itself
            something to pay). Strict positive check (only 305 allowed),
            matching close_transaction_account's own guard and the
            unsupported-type rejection the removed update_invoice_status
            used to provide for any non-300/305 original.
        Any exception raised by `client.get_invoice` if `original_invoice_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    original = client.get_invoice(original_invoice_id)
    original_type = original.get("type")
    if original_type != _TAX_INVOICE_DOCUMENT_TYPE:
        raise ValueError(
            f"Cannot create a receipt for document type {original_type} "
            f"(only {_TAX_INVOICE_DOCUMENT_TYPE} is supported - use close_transaction_account "
            f"for a {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} original)"
        )

    if amount is None and original.get("status") in _CLOSED_STATUS_CODES:
        # Already paid — idempotent no-op, avoid creating a duplicate receipt.
        return format_invoice_confirmation(Invoice.model_validate(original))

    if _extract_linked_client_id(original) is None:
        # Pre-feature, bare-name-only original - refuse rather than fall
        # back to rebuilding a bare-name client object (REQ-INV-013).
        log_refusal(
            "create_receipt",
            "original_not_linked_to_client",
            original_invoice_id=original_invoice_id,
        )
        return format_original_not_linked_to_client()

    payload = _build_payment_receipt_payload(original, amount=amount)
    receipt_response = client.create_invoice(payload)
    log_mutation(
        "create_receipt",
        payload=payload,
        response=receipt_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    original_number = original.get("number", original_invoice_id)
    receipt_number = receipt_response.get("number", receipt_response.get("id", ""))

    return f"הופקה קבלה מספר {receipt_number} עבור חשבונית מספר {original_number}."


_ISRAELI_PHONE_MOBILE_LENGTH = 10  # 0 + 3-digit prefix + 7 digits, e.g. 050-1234567
_ISRAELI_PHONE_LANDLINE_LENGTH = 9  # 0 + 1-digit area code + 7 digits, e.g. 02-1234567


# Bugfix (2026-08-07, found while verifying Feature 027): the model does not
# consistently type a Hebrew consonant-modifier apostrophe the same way
# across turns - e.g. add_client sees a plain ASCII apostrophe ("סידורוביץ'")
# but a later turn's create_invoke call reconstructs the same name using the
# correct Hebrew geresh punctuation mark ("סידורוביץ׳", U+05F3) instead, or
# vice versa. Since Morning's real client search is sensitive to this exact
# character (confirmed live: a full-name query with the "wrong" variant
# returned zero matches even though the client existed and a shorter,
# punctuation-free query found it fine), that silent inconsistency caused a
# real, existing client to be reported as "not found". Every client name is
# now normalized to the single correct Hebrew form (geresh, never a plain or
# typographic apostrophe) at every write and lookup boundary, so resolution
# is robust to whichever variant was actually typed.
_HEBREW_GERESH = "׳"  # ׳
_APOSTROPHE_VARIANTS = ("'", "’")  # ASCII ' and typographic '


def _normalize_hebrew_geresh(name: str) -> str:
    """Replace any apostrophe-like character with the correct Hebrew geresh."""
    for variant in _APOSTROPHE_VARIANTS:
        name = name.replace(variant, _HEBREW_GERESH)
    return name


def _resolve_client_by_name(client: MorningClient, name: str) -> Tuple[Optional[Client], List[Client]]:
    """Resolve a client by name via Search Clients (REQ-CLIENT-003/007).

    Returns (resolved_client, all_candidates):
    - 0 matches: (None, [])
    - 1 match: (client, [client])
    - >1 matches: (None, [client1, client2, ...]) - caller must disambiguate, never guess.
    """
    response = client.search_clients({"name": _normalize_hebrew_geresh(name)})
    items = response.get("items") or []
    candidates = [Client.model_validate(item) for item in items]
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _is_exact_name_match(resolved_name: str, queried_name: str) -> bool:
    """Whether a resolved client's stored name is identical (case-
    insensitive, whitespace-trimmed, apostrophe/geresh-normalized) to what
    was searched for. Morning's real search is a token-prefix match
    (confirmed live, research.md Decision 12) - a single non-ambiguous match
    can still be a partial/prefix reference, not the literal stored name, so
    callers must distinguish the two before deciding whether to explicitly
    disclose which client was found. Normalizing both sides here (not just
    at the search boundary) keeps this comparison correct even against an
    older client record stored before this normalization existed."""
    return _normalize_hebrew_geresh(resolved_name.strip().casefold()) == _normalize_hebrew_geresh(
        queried_name.strip().casefold()
    )


class ClientResolution(NamedTuple):
    """Result of resolving a Group A document-creation tool's free-text
    client_name to a real Morning client (feature 027, REQ-INV-001/002/003/
    005/011).

    Exactly one of (client_id, refusal_message) is set:
    - Resolved (0 or 1... well, exactly 1 match): client_id is set;
      disclosure_name is set only when the match was non-exact (fuzzy/
      substring), signalling the caller must disclose it before/with the
      confirmation reply; refusal_message is None.
    - Not found (0 matches) or ambiguous (>1 matches): client_id is None,
      refusal_message holds the friendly Hebrew text to return as-is (no
      document creation call should be made), disclosure_name is None.
    """

    client_id: Optional[str]
    disclosure_name: Optional[str]
    refusal_message: Optional[str]


class ClientNotFoundError(ValueError):
    """No client matched the name a document was asked to be created for.

    bugfix-028 B4(c): this used to be returned as ordinary tool output with
    `error=None`, indistinguishable from success at every layer above. In
    production that let one ₪40,000 document be approved eight times, created
    zero times, with the user never told the previous attempt had failed. The
    tool was asked to create a document and did not create one - that is a
    failure, and it has to be typed as one.
    """


# bugfix-028 B4(a): a name may be NARROWED but never DECORATED. Morning's client
# search is a word-aligned prefix match of the whole stored name (probed live
# 2026-08-09), so `הסתדרות כללית חדשה` matches, `הסתדרות` matches, and
# `הסתדרות כללית חדשה (ח.פ 589103852)` matches NOTHING. `list_clients` renders
# exactly that parenthesised form as a display label, the model reasonably fed
# it back as the client's identity, and this app then failed to find its own
# client. A tool's own output must be valid input to its sibling tool.
_CLIENT_NAME_DECORATION = re.compile(r"\s*\([^()]*\)\s*$")


def _strip_client_name_decoration(client_name: str) -> str:
    """Drop a trailing parenthesised qualifier - `(ח.פ …)`, `(טלפון …)`, or both -
    from a client name. Only ever strips a TRAILING parenthetical, so a client
    genuinely named e.g. `חברה (2019) בע"מ` mid-string is untouched."""
    stripped = _CLIENT_NAME_DECORATION.sub("", client_name).strip()
    return stripped or client_name


def _resolve_client_for_document_creation(client: MorningClient, client_name: str) -> ClientResolution:
    """Resolve a Group A document-creation tool's client_name to a real
    client_id, or a friendly refusal message (feature 027).

    Reuses Feature 026's `_resolve_client_by_name`/`_is_exact_name_match`
    unchanged - this is a thin combination of the two into the single
    branch document-creation tools need, never a new Morning API call.

    bugfix-028 B4: on a miss, retries once with any trailing parenthesised
    decoration removed (see _strip_client_name_decoration), and raises
    ClientNotFoundError rather than returning a friendly string when nothing
    matches at all. An AMBIGUOUS match still returns its refusal message - that
    is a question for the user ("which of these did you mean?"), not a failure.
    """
    resolved, candidates = _resolve_client_by_name(client, client_name)

    if resolved is None and not candidates:
        undecorated = _strip_client_name_decoration(client_name)
        if undecorated != client_name:
            logger.info(
                f"No client matched {client_name!r}; retrying without its trailing "
                f"qualifier as {undecorated!r} (bugfix-028 B4)"
            )
            resolved, candidates = _resolve_client_by_name(client, undecorated)
            client_name = undecorated

    if resolved is not None:
        disclosure_name = None if _is_exact_name_match(resolved.name, client_name) else resolved.name
        return ClientResolution(client_id=resolved.id, disclosure_name=disclosure_name, refusal_message=None)
    # bugfix-036: a refusal is a decision this server made about a document, but
    # it is not an exception, so nothing used to record it - the three failed
    # create_transaction_account attempts for הסתדרות כללית חדשה (7-9 Aug 2026)
    # left no trace at all. Logged here rather than in each caller so every
    # document-creation tool, present and future, is covered by construction;
    # the tool name is on the boundary's TOOL CALL line under the same corr id.
    if candidates:
        log_refusal(
            "document_creation",
            "ambiguous_client",
            client_name=client_name,
            candidates=[(candidate.id, candidate.name) for candidate in candidates],
        )
        return ClientResolution(
            client_id=None, disclosure_name=None, refusal_message=format_ambiguous_clients_message(candidates)
        )
    log_refusal("document_creation", "client_not_found", client_name=client_name)
    raise ClientNotFoundError(f"{format_client_not_found()} ({client_name})")


def _extract_linked_client_id(original: dict) -> Optional[str]:
    """Read a real client_id off an already-fetched linked original
    document, if present (feature 027, REQ-INV-012/013).

    Used by Group B tools (create_credit_note/create_receipt/
    close_transaction_account), which derive their client from the
    original document they're linked to rather than searching by name.
    Returns None when the original's client sub-object has no id at all
    (a pre-feature, bare-name-only attachment) - callers must refuse
    rather than fall back to rebuilding a bare-name object.
    """
    client_info = original.get("client") or {}
    return client_info.get("id")


def _validate_email(email: str) -> str:
    """Validate email format client-side (REQ-CLIENT-015), mirroring Morning's
    own documented server-side rule (errorCode 1102/1120). Uses email-validator
    (already a project dependency, already the pattern used by models.Client)."""
    try:
        result = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(f"Invalid email address: {email!r}") from exc
    return result.normalized


def _normalize_israeli_phone(phone: str) -> str:
    """Normalize a phone number to Israeli local dashed format (REQ-CLIENT-016).

    No Morning-side format rule exists to mirror (confirmed via the full
    error-code catalog) - this is an app-level policy choice. Accepts
    +972/972-prefixed, local, dashed, or undashed input; rejects anything
    that doesn't resolve to a plausible Israeli number (9 or 10 digits
    starting with 0).
    """
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    if not digits.startswith("0") or len(digits) not in (
        _ISRAELI_PHONE_LANDLINE_LENGTH,
        _ISRAELI_PHONE_MOBILE_LENGTH,
    ):
        raise ValueError(f"Phone number does not resolve to a plausible Israeli number: {phone!r}")
    if len(digits) == _ISRAELI_PHONE_MOBILE_LENGTH:
        return f"{digits[:3]}-{digits[3:]}"
    return f"{digits[:2]}-{digits[2:]}"


_LIST_CLIENTS_MAX_ITEMS = 30  # beyond this, report the real total and ask to
                              # narrow rather than fetch further pages/dump
                              # an unusably long WhatsApp reply.


def list_clients(client: MorningClient, name: Optional[str] = None) -> str:
    """List existing Morning clients and return a Hebrew, human-readable list.

    MCP tool: list_clients (contracts/list_clients.json, user-stories.md US1).
    Read-only - no approval wait (REQ-CLIENT-008).

    Production accounts can have hundreds of clients (confirmed live: 278 in
    this app's own real sandbox, research.md Decision 11/12) - Morning's
    search is genuinely paginated (`total`/`pages` in every response), so
    this reads the real total from page 1 first and decides what to do
    before fetching anything further:
    - `total <= _LIST_CLIENTS_MAX_ITEMS`: fetch every remaining page
      internally and return the complete, accurate list - "pagination" is
      purely an internal mechanism here, never something the user pages
      through themselves.
    - `total > _LIST_CLIENTS_MAX_ITEMS`: fetch nothing further - report the
      real total and ask for a narrower search (e.g. by name) instead of
      silently truncating or dumping an unusable wall of text.

    Args:
        client: An authenticated MorningClient (injected).
        name: Optional name filter (apostrophe/geresh-normalized - see
            `_normalize_hebrew_geresh`), passed to Morning's real search
            (token-prefix match) to narrow results server-side.

    Returns:
        A Hebrew string listing matching clients, a friendly "no clients"
        message if none, or a "too many, narrow your search" message with
        the real total if the count exceeds the display cap.
    """
    payload: Dict[str, Any] = {"name": _normalize_hebrew_geresh(name)} if name else {}
    first_page = client.search_clients(payload)
    total = first_page.get("total", 0) or 0

    if total > _LIST_CLIENTS_MAX_ITEMS:
        return format_too_many_clients_message(total)

    items = list(first_page.get("items") or [])
    page_num = first_page.get("page", 1) or 1
    total_pages = first_page.get("pages", 1) or 1
    while len(items) < total and page_num < total_pages:
        page_num += 1
        next_page = client.search_clients({**payload, "page": page_num})
        items.extend(next_page.get("items") or [])

    clients = [Client.model_validate(item) for item in items]
    return format_client_list(clients)


def get_client_details(client: MorningClient, name: str) -> str:
    """Retrieve a single client's full detail record by name.

    MCP tool: get_client_details (contracts/get_client_details.json,
    user-stories.md US2). Read-only - no approval wait (REQ-CLIENT-008).
    Name-only lookup (REQ-CLIENT-002, analysis 2026-07-29: tax-ID lookup was
    considered and dropped). Never guesses on ambiguous matches
    (REQ-CLIENT-003/007) and never includes the internal client_id
    (REQ-CLIENT-018). When resolved via a non-exact (partial/prefix) match,
    explicitly discloses which client was found rather than silently
    presenting details as if the reference were certain.
    """
    resolved, candidates = _resolve_client_by_name(client, name)
    if resolved is not None:
        return format_client_details(resolved, is_exact_match=_is_exact_name_match(resolved.name, name))
    if candidates:
        return format_ambiguous_clients_message(candidates)
    return format_client_not_found()


def _build_add_client_payload(
    name: str,
    email: str,
    phone: str,
    tax_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Map friendly add_client inputs onto the real Morning /clients payload.

    Real field names (confirmed via the Postman collection's "Add Client"
    example): `emails` is a list, `taxId` is camelCase, `phone` is its own
    top-level field (confirmed via the Search Clients example, distinct from
    `mobile` — REQ-CLIENT-014). name/email/phone are all required
    (REQ-CLIENT-012); email/phone are validated and normalized by the caller
    before this is built.
    """
    payload: Dict[str, Any] = {"name": name, "emails": [email], "phone": phone}
    if tax_id:
        payload["taxId"] = tax_id
    return payload


def add_client(
    client: MorningClient,
    name: str,
    email: str,
    phone: str,
    tax_id: Optional[str] = None,
) -> str:
    """Add a new client to Morning and return a Hebrew confirmation.

    MCP tool: add_client (contracts/add_client.json, user-stories.md US3).
    Reworked by Feature 026: name/email/phone are all required (no default -
    omitting one is a Python-level TypeError, REQ-CLIENT-012); no `address`
    parameter (REQ-CLIENT-013, out of scope); email is validated and phone
    normalized to Israeli local dashed format before any network call
    (REQ-CLIENT-015/016). Approval-gated at the denidin-app layer
    (ai_handler.APPROVAL_REQUIRED_MCP_TOOLS).

    Args:
        client: An authenticated MorningClient (injected).
        name: Client/company name (required, apostrophe/geresh-normalized -
            see `_normalize_hebrew_geresh` - so the stored record always uses
            the correct Hebrew form regardless of which variant was typed).
        email: Client email (required, validated).
        phone: Client phone number (required, normalized to Israeli format).
        tax_id: Optional Israeli business tax ID (ע"מ).

    Returns:
        A Hebrew confirmation string with the created client's name. Never
        includes the internal Morning client_id (REQ-CLIENT-018).

    Raises:
        ValueError: if email or phone fails validation/normalization.
    """
    normalized_name = _normalize_hebrew_geresh(name)
    validated_email = _validate_email(email)
    normalized_phone = _normalize_israeli_phone(phone)
    payload = _build_add_client_payload(normalized_name, validated_email, normalized_phone, tax_id)
    response = client.add_client(payload)
    # bugfix-036: the response was previously discarded outright, so the id
    # Morning assigned the new client existed nowhere in this app. It still
    # never reaches the caller (REQ-CLIENT-018) - only the log.
    log_mutation(
        "add_client",
        payload=payload,
        response=response,
        client_id=(response or {}).get("id") if isinstance(response, dict) else None,
        client_name=normalized_name,
    )
    return f"נוצר לקוח חדש: {normalized_name}"


def _build_update_client_payload(
    new_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    tax_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a partial Morning /clients/{id} PUT payload containing only the
    fields actually being changed (research.md Decision 3 - confirmed
    empirically via test_update_client_partial_payload_preserves_other_fields:
    a partial PUT does not clobber untouched fields)."""
    payload: Dict[str, Any] = {}
    if new_name:
        payload["name"] = new_name
    if email:
        payload["emails"] = [email]
    if phone:
        payload["phone"] = phone
    if tax_id:
        payload["taxId"] = tax_id
    return payload


def update_client(
    client: MorningClient,
    name: str,
    new_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    tax_id: Optional[str] = None,
) -> str:
    """Update an existing client's fields and return a Hebrew confirmation.

    MCP tool: update_client (contracts/update_client.json, user-stories.md
    US4). `name` identifies WHICH client to update (resolved via
    `_resolve_client_by_name` - never guesses on an ambiguous match,
    REQ-CLIENT-003/007); `new_name`/`email`/`phone`/`tax_id` are the optional
    fields being changed - at least one is required. Approval-gated at the
    denidin-app layer (ai_handler.APPROVAL_REQUIRED_MCP_TOOLS).

    Args:
        client: An authenticated MorningClient (injected).
        name: Current name of the client to update (required, resolves the
            target - apostrophe/geresh-normalized before resolution, see
            `_normalize_hebrew_geresh`).
        new_name: Optional new name value (apostrophe/geresh-normalized).
        email: Optional new email (validated).
        phone: Optional new phone (normalized to Israeli format).
        tax_id: Optional new Israeli business tax ID (ע"מ).

    Returns:
        A Hebrew confirmation string. Never includes the internal Morning
        client_id (REQ-CLIENT-018).

    Raises:
        ValueError: if none of new_name/email/phone/tax_id is given, or if
            email/phone fails validation/normalization.
    """
    if not any([new_name, email, phone, tax_id]):
        raise ValueError("update_client requires at least one of new_name/email/phone/tax_id to change.")

    resolved, candidates = _resolve_client_by_name(client, name)
    if resolved is None:
        if candidates:
            log_refusal(
                "update_client",
                "ambiguous_client",
                client_name=name,
                candidates=[(candidate.id, candidate.name) for candidate in candidates],
            )
            return format_ambiguous_clients_message(candidates)
        log_refusal("update_client", "client_not_found", client_name=name)
        return format_client_not_found()

    is_exact_match = _is_exact_name_match(resolved.name, name)
    normalized_new_name = _normalize_hebrew_geresh(new_name) if new_name else None
    validated_email = _validate_email(email) if email else None
    normalized_phone = _normalize_israeli_phone(phone) if phone else None
    payload = _build_update_client_payload(normalized_new_name, validated_email, normalized_phone, tax_id)
    response = client.update_client(resolved.id, payload)
    log_mutation(
        "update_client",
        payload=payload,
        response=response,
        client_id=resolved.id,
        client_name=normalized_new_name or resolved.name,
    )

    display_name = normalized_new_name or resolved.name
    if is_exact_match:
        return f"עודכנו פרטי הלקוח: {display_name}"
    return f"מצאתי ועדכנתי את הלקוח הבא: {resolved.name}\nהפרטים שעודכנו: {display_name}"


def _resolve_period_dates(
    period: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> tuple:
    """Resolve a friendly period name to a concrete (from_date, to_date) range."""
    today = now_local().date()

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
    invoice (see create_credit_note) issues a linked
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
