"""MCP tool implementations wrapping MorningClient for invoice management.

Each function here corresponds 1:1 to an MCP tool registered in server.py
(see contracts/<tool>.json and user-stories.md for the tool contract and
acceptance criteria). Tools receive a MorningClient by dependency injection
(no globals, no monkey-patching per CONSTITUTION.md §XVII) and return a
human-readable, Hebrew-formatted string.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, NoReturn, Optional, Set, Tuple

import tiktoken
from email_validator import EmailNotValidError, validate_email
from pydantic import ValidationError

from .audit import log_mutation, log_refusal
from .formatters import (
    format_ambiguous_clients_message,
    format_client_details,
    format_client_list,
    format_client_name_confirmation_question,
    format_client_name_resolved,
    format_client_not_found,
    format_financial_summary,
    format_invoice_json,
    format_invoice_list_json,
    format_name_not_resolved,
    format_original_not_linked_to_client,
    format_too_many_clients_message,
    format_too_many_invoices_message,
    format_transaction_account_cancelled,
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
    client via `_require_resolved_client` before calling this.

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


def _amount_mismatch_info(requested: float, stored: Optional[float]) -> Optional[dict]:
    """bugfix-028 A4: if what Morning stored differs from what the operator
    approved, surface both numbers so the model can say so and ask - never
    silently reconcile. Returns a dict merged into the JSON document result
    (2026-09-04 JSON-only contract change - this used to be a prepended
    prose warning; a JSON tool result can't be prefixed with free text and
    stay valid JSON, so the mismatch is now a real field the model reads and
    turns into its own warning to the operator)."""
    if stored is None or abs(stored - requested) < 0.01:
        return None
    return {"requested_amount": requested, "actual_amount": stored}


def _with_amount_mismatch(invoice_json: str, requested: float, stored: Optional[float]) -> str:
    """Merge `_amount_mismatch_info` into an already-built `format_invoice_json`
    result, if a mismatch exists; returns `invoice_json` unchanged otherwise."""
    mismatch = _amount_mismatch_info(requested, stored)
    if mismatch is None:
        return invoice_json
    doc = json.loads(invoice_json)
    doc["amount_mismatch"] = mismatch
    return json.dumps(doc, ensure_ascii=False)


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
    `_require_resolved_client` first.

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
    name_resolved: bool = False,
) -> str:
    """Create a non-tax transaction account ("חשבון עסקה", type 300) in
    Morning and return a Hebrew confirmation message.

    MCP tool: create_transaction_account (feature 021).

    Client-name-resolution architecture fix (2026-08-12, user decision):
    this tool no longer does its own fuzzy/word-growth matching or
    disambiguation - that is entirely `resolve_client_name`'s job now. This
    tool requires `name_resolved=True` (the caller must have already
    resolved the name via `resolve_client_name`) and only ever accepts an
    exact, word-order-independent match - see `_require_resolved_client`'s
    docstring for the full contract.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: The client's exact, already-resolved name.
        amount: Amount in NIS - carries no VAT (see _build_transaction_account_payload).
        description: Service/product description.
        due_date: Optional due date, ISO format YYYY-MM-DD.
        name_resolved: Must be True (asserting `resolve_client_name` was
            already called with this name) or this refuses immediately,
            attempting no Morning lookup at all.

    Returns:
        A Hebrew confirmation string with the document number and amount on
        an exact match, or a plain procedural refusal string (name_resolved
        wasn't True - see `_require_resolved_client`).

    Raises:
        ClientNotFoundError: if name_resolved is True but the name doesn't
            match a real client exactly.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolved_client = _require_resolved_client(client, client_name, name_resolved, "create_transaction_account")

    payload = _build_transaction_account_payload(
        resolved_client.id, amount, description, vat_included, due_date
    )
    response = client.create_invoice(payload)
    log_mutation(
        "create_transaction_account",
        payload=payload,
        response=response,
        client_id=resolved_client.id,
        client_name=client_name,
    )

    doc_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    stored_total = _read_back_stored_total(client, doc_id)
    invoice = Invoice(
        id=doc_id,
        number=response.get("number"),
        client_name=client_name,
        amount=amount,
        total_amount=stored_total if stored_total is not None else amount,
        currency=response.get("currency", "ILS"),
        due_date=due_date,
        status=response.get("status"),
        type=_TRANSACTION_ACCOUNT_DOCUMENT_TYPE,
    )
    return _with_amount_mismatch(format_invoice_json(invoice), amount, stored_total)


def _build_combo_document_core_payload(
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
    lang: str = "he",
    linked_document_ids: Optional[List[str]] = None,
) -> dict:
    """bugfix-038: the SINGLE shared type-320 ("חשבונית מס/קבלה") payload
    shape, used by both `create_combo_document` (a fresh standalone
    document) and `create_combo_document_as_reference` (closing an existing
    type-300). Extracted after discovering these had drifted into two
    independent implementations (`_build_combo_document_payload` and
    `_build_combo_closing_payload`) - which is exactly why bugfix-028's A3/A3b
    payment-detail fix reached only one of them: nobody knew the second one
    existed. A fix here now reaches both by construction.

    Per bugfix-014 Flow 1: this document is issued when payment has ALREADY been
    received - self-contained, always already "paid", no due date (unlike a type
    305 tax invoice, which is a request for later payment).

    bugfix-028 A3/A3b: because the money has already moved, this document
    records a real historical transaction - so `payment_date` is REQUIRED and
    validated (never defaulted to today, via `_build_payment_line`'s own
    `_validate_payment_date` call), and the payment carries how the money
    arrived. The default method is a bank transfer, which is the only type
    Morning stores bank details on.

    Note the type-320 amount consistency rule (live-confirmed): Morning rejects
    the document outright with `errorCode 2422` if the income total and the
    payment total disagree - which is what a wrong `vatType` causes here. On a
    320 a VAT mistake fails loudly rather than inflating silently, unlike the
    type-300 case behind A2.

    `lang`/`linked_document_ids` exist only for the closing caller (mirrors
    the original type-300's own language, links back to it) - the fresh
    caller never passes them, preserving its exact prior payload shape (no
    `linkedDocumentIds` key at all when closing nothing).
    """
    today = now_local().date().isoformat()
    vat_type = 1 if vat_included else 0

    payload: Dict[str, Any] = {
        "type": _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
        "date": today,
        "lang": lang,
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
    if linked_document_ids is not None:
        payload["linkedDocumentIds"] = linked_document_ids
    return payload


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
    `_require_resolved_client` first.

    bugfix-038: thin wrapper over the shared `_build_combo_document_core_
    payload` - see that function's docstring for the full payload-shape
    rationale. Kept as its own named function so create_combo_document's
    call site (and every existing test targeting this name) is unaffected.
    """
    return _build_combo_document_core_payload(
        client_id=client_id,
        amount=amount,
        description=description,
        vat_included=vat_included,
        payment_date=payment_date,
        payment_method=payment_method,
        bank_number=bank_number,
        bank_branch=bank_branch,
        bank_account=bank_account,
        transaction_reference=transaction_reference,
        currency=currency,
    )


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
    name_resolved: bool = False,
) -> str:
    """Create an already-paid combo invoice+receipt ("חשבונית מס/קבלה",
    type 320) in Morning and return a Hebrew confirmation message.

    MCP tool: create_combo_document (feature 021).

    Client-name-resolution architecture fix (2026-08-12, user decision):
    this tool no longer does its own fuzzy/word-growth matching or
    disambiguation - that is entirely `resolve_client_name`'s job now. This
    tool requires `name_resolved=True` (the caller must have already
    resolved the name via `resolve_client_name`) and only ever accepts an
    exact, word-order-independent match - see `_require_resolved_client`'s
    docstring for the full contract.

    bugfix-028 (A2/A3/A3b): `vat_included` and `payment_date` are both REQUIRED.
    This document asserts that money has already arrived, so how much of it is
    VAT, and when it arrived, are facts about a real transaction - neither may be
    defaulted or guessed. Ask the user rather than assuming.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: The client's exact, already-resolved name.
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
        name_resolved: Must be True (asserting `resolve_client_name` was
            already called with this name) or this refuses immediately,
            attempting no Morning lookup at all.

    Returns:
        A Hebrew confirmation string with the document number and the amount
        Morning actually stored on an exact match, or a plain procedural
        refusal string (name_resolved wasn't True - see
        `_require_resolved_client`).

    Raises:
        ClientNotFoundError: if name_resolved is True but the name doesn't
            match a real client exactly.
        ValueError: if payment_date is missing, unparseable, or in the future,
            or payment_method is unknown.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolved_client = _require_resolved_client(client, client_name, name_resolved, "create_combo_document")

    payload = _build_combo_document_payload(
        resolved_client.id,
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
        client_id=resolved_client.id,
        client_name=client_name,
    )

    doc_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    stored_total = _read_back_stored_total(client, doc_id)
    invoice = Invoice(
        id=doc_id,
        number=response.get("number"),
        client_name=client_name,
        amount=amount,
        total_amount=stored_total if stored_total is not None else amount,
        currency=response.get("currency", "ILS"),
        status=response.get("status"),
        type=_INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
    )
    return _with_amount_mismatch(format_invoice_json(invoice), amount, stored_total)


def create_invoice(
    client: MorningClient,
    client_name: str,
    amount: float,
    description: str,
    due_date: Optional[str] = None,
    vat_included: bool = True,
    name_resolved: bool = False,
) -> str:
    """Create an invoice in Morning and return a Hebrew confirmation message.

    MCP tool: create_invoice (contracts/create_invoice.json, user-stories.md US1).

    Client-name-resolution architecture fix (2026-08-12, user decision):
    this tool no longer does its own fuzzy/word-growth matching or
    disambiguation - that is entirely `resolve_client_name`'s job now (the
    one, sole entry point for that). This tool requires `name_resolved=True`
    (the caller must have already resolved the name via `resolve_client_name`)
    and only ever accepts an exact, word-order-independent match:
    - Exactly one EXACT match -> the document is attached to that real
      client's id.
    - Anything else (non-exact, ambiguous, or zero matches) -> raises
      `ClientNotFoundError` - the caller was supposed to have already
      resolved this via `resolve_client_name`, so any non-exact result here
      is a contract violation, not a normal disambiguation moment.
    - `name_resolved` not `True` at all -> refuses immediately, attempting
      no Morning lookup, via a plain procedural string (never raised) - see
      `_require_resolved_client`'s docstring for the full contract.

    Args:
        client: An authenticated MorningClient (injected).
        client_name: The client's exact, already-resolved name.
        amount: Invoice amount in NIS.
        description: Service/product description.
        due_date: Optional due date, ISO format YYYY-MM-DD.
        vat_included: Whether VAT is included in the amount (default True).
        name_resolved: Must be True (asserting `resolve_client_name` was
            already called with this name) or this refuses immediately,
            attempting no Morning lookup at all.

    Returns:
        A Hebrew confirmation string with the invoice number, amount, and
        status on an exact match, or a plain procedural refusal string
        (name_resolved wasn't True).

    Raises:
        ClientNotFoundError: if name_resolved is True but the name doesn't
            match a real client exactly.
    """
    client_name = _normalize_hebrew_geresh(client_name)
    resolved_client = _require_resolved_client(client, client_name, name_resolved, "create_invoice")

    payload = _build_create_invoice_payload(resolved_client.id, amount, description, due_date, vat_included)
    response = client.create_invoice(payload)
    log_mutation(
        "create_invoice",
        payload=payload,
        response=response,
        client_id=resolved_client.id,
        client_name=client_name,
    )

    internal_morning_id = str(
        response.get("id")
        or response.get("documentId")
        or response.get("document_id")
        or (response.get("document") or {}).get("id")
        or ""
    )

    stored_total = _read_back_stored_total(client, internal_morning_id)
    invoice = Invoice(
        id=internal_morning_id,
        number=response.get("number"),
        client_name=client_name,
        amount=amount,
        total_amount=stored_total if stored_total is not None else amount,
        currency=response.get("currency", "ILS"),
        due_date=due_date,
        status=response.get("status"),
    )
    return _with_amount_mismatch(format_invoice_json(invoice), amount, stored_total)


def _map_list_invoices_filters(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
    document_display_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Map friendly list_invoices filters onto Morning's real /documents/search params.

    Key names (fromDate/toDate/clientName) are proven against the sandbox by
    tests/integration/test_morning_sandbox_invoices_crud.py. `status` is
    deliberately NOT sent server-side — see _matches_status.

    `document_display_number` (bugfix, 2026-08-07; renamed from `number` by
    bugfix-038 - see this file's module-level note on `internal_morning_id`
    vs `document_display_number`): Morning's real /documents/search endpoint
    has always accepted a `number` filter (confirmed via the checked-in
    Postman collection's own "Search Documents" example - a bare int, e.g.
    `"number": 12001`) - this was never wired up here, so any reference to
    an invoice by its human-visible number alone (no client name/date) had
    no real way to resolve short of an unfiltered list_invoices call, which
    fails outright once the sandbox holds more documents than the fetch cap
    (_LIST_INVOICES_MAX_ITEMS). Accepted here as a string (the natural shape
    a model/user provides, e.g. "51365") and converted to the int Morning's
    API actually expects (under its own wire key, `"number"` - unrelated to
    this parameter's name); a non-numeric value is dropped rather than sent
    (Morning would reject it, and silently sending a string risks matching
    nothing with no clear error).
    """
    params: Dict[str, Any] = {}
    if from_date:
        params["fromDate"] = from_date
    if to_date:
        params["toDate"] = to_date
    if client_name:
        params["clientName"] = client_name
    if document_display_number:
        try:
            params["number"] = int(document_display_number)
        except (TypeError, ValueError):
            logger.warning("Ignoring non-numeric document_display_number filter: %r", document_display_number)
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


# 2026-09-04 JSON-only contract change: list_invoices no longer truncates its
# result to a token budget (the JSON reply is always the complete match set,
# with total_matched stated explicitly) - _truncate_invoices_to_token_budget
# and the token-budget machinery it used were removed as dead code.


def list_invoices(
    client: MorningClient,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    client_name: Optional[str] = None,
    document_display_number: Optional[str] = None,
    name_resolved: bool = False,
    include_full_details: bool = False,
) -> str:
    """List/search invoices and return a JSON result.

    2026-09-04 JSON-only contract change: this tool used to also support an
    `output_format="text"` mode returning Hebrew prose, truncated to fit a
    token budget. That mode is abandoned entirely - the caller (DeniDin's
    model) is now responsible for reading this JSON and composing its own
    Hebrew, bullet-style reply. Since the JSON result is not token-budget-
    truncated (a reconciliation/automation consumer needs every match), the
    old `token_budget` parameter and its truncation helper are dead here too.

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
        document_display_number: Optional exact document-number filter (e.g.
            "51365" - the human-visible label, NEVER an internal_morning_id)
            - the real Morning API's own `number` search field (bugfix,
            2026-08-07), previously never wired up here. Non-numeric values
            are ignored.
    Returns:
        A JSON string (`format_invoice_list_json`) listing every matching
        invoice, with `total_matched` stated explicitly, a friendly
        "no results" JSON if a resolved/unfiltered/number/single-word
        search finds nothing, a "too many, narrow your search" JSON if the
        real total exceeds the fetch cap, or a plain procedural refusal if a
        multi-word `client_name` is given without `name_resolved=True`
        (architecture fix, 2026-08-12 - disambiguation/confirmation-
        question handling for a non-exact multi-word name now lives
        entirely in `resolve_client_name`, not here). An EXACT match
        (including word-order-independent, e.g. "Solutions Tech" against a
        client stored as "Tech Solutions") resolves and the search proceeds
        normally under the real stored name.

    Raises:
        ClientNotFoundError: if a multi-word `client_name` is given,
            `name_resolved=True`, and it doesn't match a real client
            exactly (unification, 2026-08-12). A single-word `client_name`
            is a substring filter, not a specific-client lookup, and never
            requires `name_resolved` or raises this way - see the comment
            at this method's first branch.
    """
    if client_name and len(client_name.split()) > 1:
        # Client-name-resolution architecture fix (2026-08-12, user
        # decision): this tool no longer does its own fuzzy/word-growth
        # matching or disambiguation for a multi-word client_name - that is
        # entirely resolve_client_name's job now. Single-word queries are
        # deliberately left untouched here (a genuine partial/substring
        # search, e.g. "Cohen", not a specific full-name lookup) - Feature
        # 031 already confirmed those work via Morning's own substring
        # matching, and resolving them through this gate risks a false
        # rejection against clients unrelated to the caller's intent (many
        # real clients can share one common word).
        resolved_client = _require_resolved_client(client, client_name, name_resolved, "list_invoices")
        client_name = resolved_client.name  # exact match - search under the real stored name
    params = _map_list_invoices_filters(from_date, to_date, client_name, document_display_number)
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

    # Feature 025 Phase 9 / 2026-09-04 JSON-only contract: `include_full_details`
    # gates the per-document fan-out. It is a CAPABILITY the caller opts into,
    # available in ANY context - a conversation that genuinely needs bank
    # details or linked documents should ask for it too (user, 2026-08-23: the
    # only cost is latency, and that is acceptable). It is simply not the
    # default, because most questions do not need it.
    if include_full_details:
        # Structured bank details (payment[].bankName/bankBranch/bankAccount) and
        # linkedDocuments exist ONLY on the single-document GET. Asking the MODEL
        # to chain those N calls proved unreliable in live trials (it stopped
        # after a couple of captures without ever calling get_invoice_details),
        # so the fan-out is deterministic code here instead. A failure on one
        # document falls back to its search entry rather than losing the sweep.
        detailed: List[Invoice] = []
        for inv in invoices:
            try:
                detailed.append(Invoice.model_validate(client.get_invoice(inv.id)))
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "list_invoices(include_full_details): detail fetch failed for %s (%s) - "
                    "falling back to the search entry, which has no bank/linked-document "
                    "data", inv.id, exc
                )
                detailed.append(inv)
        invoices = detailed

    # Machine-readable output, always. Not token-budget-truncated: the caller
    # (DeniDin's model) needs every match to compose an accurate reply, and
    # total_matched is stated explicitly so truncation is detectable rather
    # than silent.
    return format_invoice_list_json(invoices, total_matched=len(invoices))


def get_invoice_details(client: MorningClient, internal_morning_id: str) -> str:
    """Fetch full details for one invoice and return a JSON result.

    MCP tool: get_invoice_details (contracts/get_invoice_details.json,
    user-stories.md US3).

    Args:
        client: An authenticated MorningClient (injected).
        internal_morning_id: Morning document id.

    Returns:
        A JSON string (`format_invoice_json`) with status, dates, and any
        recorded payments. 2026-09-04 JSON-only contract change: this tool
        used to also support an `output_format="text"` Hebrew-prose mode -
        abandoned entirely, see module docstring.
    """
    response = client.get_invoice(internal_morning_id)
    invoice = Invoice.model_validate(response)
    return format_invoice_json(invoice)


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
    original_internal_morning_id: str,
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
        original_internal_morning_id: Morning document id of the invoice being credited.
        amount: Optional override — defaults to the original's full total.
        description: Optional override — defaults to a generated cancellation note.

    Returns:
        A Hebrew confirmation string with the new credit note's number, or a
        friendly refusal message (no document created, REQ-INV-013) if the
        original isn't linked to a real client record.

    Raises:
        Any exception raised by `client.get_invoice` if `original_internal_morning_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    original = client.get_invoice(original_internal_morning_id)
    if _extract_linked_client_id(original) is None:
        log_refusal(
            "create_credit_note",
            "original_not_linked_to_client",
            original_internal_morning_id=original_internal_morning_id,
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

    # bugfix-028 A4's lesson (see _read_back_stored_total): POST /documents
    # returns only a minimal echo (id/number/client/type/...), never amount/
    # total - format_invoice_json needs the full document, so re-fetch it
    # rather than validating the bare creation response.
    new_id = str(credit_response.get("id") or credit_response.get("documentId") or "")
    return format_invoice_json(Invoice.model_validate(client.get_invoice(new_id)))


_CLOSED_STATUS_CODES = {1, 2}  # closed (via payment) / manually closed — see models._MORNING_STATUS_CODES


def _build_payment_receipt_payload(original: dict, payment_date: str, amount: Optional[float] = None) -> dict:
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

    bugfix-028 A3 (2026-08-12): `payment_date` is REQUIRED and validated via
    `_validate_payment_date` (same shared validator as create_combo_document/
    create_transaction_account) - the money has already moved, so the date it
    moved is a fact the payment line must carry, never silently "today". The
    document's own top-level `date` (issue date, set below) stays today
    regardless - a receipt can genuinely be issued today for a payment that
    arrived on an earlier date.

    Feature 027 (REQ-INV-012): reuses `original`'s real client_id instead of
    rebuilding a bare-name client object - callers (create_receipt) MUST
    check `_extract_linked_client_id(original)` and refuse before calling
    this if it's None (a pre-feature, bare-name-only original).
    """
    validated_payment_date = _validate_payment_date(payment_date)
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
        "payment": [{"type": 1, "price": receipt_amount, "date": validated_payment_date}],
    }


def _build_standalone_receipt_payload(
    client_id: str,
    amount: float,
    description: str,
    payment_date: str,
) -> dict:
    """Build a Morning receipt (type 400) payload for a standalone receipt -
    one with no prior document to reference at all (feature 056).

    Unlike `_build_payment_receipt_payload` (which marks an existing type-305
    invoice paid), this records a pure cash movement that isn't business
    income - a deposit, a loan repayment, or an advance payment ahead of a
    transaction that hasn't completed (REQ-INV-014). It therefore carries no
    VAT/income line at all (REQ-INV-017 - consistent with how a type-300
    transaction account already has no VAT concept) and no
    `linkedDocumentIds` (REQ-INV-019 - there is nothing to link to, and a
    later real invoice for the same transaction is never required to
    reference this receipt back).

    `client_id` is a real, already-resolved Morning client_id (never a bare
    name) - callers (create_receipt's standalone branch) MUST resolve via
    `_require_resolved_client` first, same contract as every other create
    tool. `description` is caller-supplied free text (REQ-INV-018 - the
    model composes it, e.g. "פיקדון", "החזר הלוואה", "מקדמה על חשבון..."; no
    structured reason code exists).

    `payment_date` is REQUIRED and validated via `_validate_payment_date`
    (same shared validator as every other payment-carrying builder) - the
    money has already moved, so its real date is a fact to carry, never a
    silent "today". The document's own top-level `date` (issue date, set
    below) stays today regardless.
    """
    validated_payment_date = _validate_payment_date(payment_date)
    today = now_local().date().isoformat()

    return {
        "type": 400,
        "date": today,
        "lang": "he",
        "currency": "ILS",
        "rounding": False,
        "signed": True,
        "description": description,
        "client": {"self": False, "id": client_id},
        "payment": [{"type": 1, "price": amount, "date": validated_payment_date}],
    }


def _build_combo_closing_payload(
    original: dict,
    payment_date: str,
    payment_method: str = _DEFAULT_PAYMENT_METHOD,
    bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None,
    bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    vat_included: bool = True,
) -> dict:
    """Build a Morning invoice/receipt combo (type 320) payload that closes a
    type-300 ("חשבון עסקה") `original` as paid, either in full (defaults) or
    partially (`amount` override).

    bugfix-038: now a thin wrapper over the shared `_build_combo_document_
    core_payload` - previously an entirely independent reimplementation
    (`create_combo_document`'s own `_build_combo_document_payload` was the
    other one) that had silently hardcoded `payment: [{"type": 1, ...,
    "date": today}]` ever since, missing bugfix-028 A3/A3b's requirement
    that a payment-backed document record the REAL date/method/bank details
    the money moved with - because nobody fixing that bug knew this second
    implementation existed. `payment_date` is now REQUIRED and validated
    (via `_build_payment_line`'s `_validate_payment_date`, same as
    create_combo_document), never defaulted to today.

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
    rebuilding a bare-name client object - callers (create_combo_document_as_reference)
    MUST check `_extract_linked_client_id(original)` and refuse before
    calling this if it's None (a pre-feature, bare-name-only original).
    """
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

    close_amount = amount if amount is not None else total_amount
    close_description = description or f"תשלום עבור חשבון עסקה מספר {original_number or original_id}"

    return _build_combo_document_core_payload(
        client_id=_extract_linked_client_id(original),
        amount=close_amount,
        description=close_description,
        vat_included=vat_included,
        payment_date=payment_date,
        payment_method=payment_method,
        bank_number=bank_number,
        bank_branch=bank_branch,
        bank_account=bank_account,
        transaction_reference=transaction_reference,
        currency=original.get("currency", "ILS"),
        lang=original.get("lang", "he"),
        linked_document_ids=[original_id] if original_id else [],
    )


def create_combo_document_as_reference(
    client: MorningClient,
    original_internal_morning_id: str,
    payment_date: str,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    vat_included: bool = True,
    payment_method: str = _DEFAULT_PAYMENT_METHOD,
    bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None,
    bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None,
) -> str:
    """Create a standalone combo document ("חשבונית מס/קבלה", type 320) that
    closes an existing transaction account ("חשבון עסקה", type 300), linked
    via `linkedDocumentIds`, and return a Hebrew confirmation.

    MCP tool: create_combo_document_as_reference (feature 023, renamed from
    close_transaction_account by bugfix-038). Mirrors create_credit_note/
    create_receipt's existing standalone-with-reference pattern (021),
    extended to the type-300->320 closing flow (bugfix-014 Flow 4, originally
    020). Feature 023 removed the separate update_invoice_status tool -
    "mark as paid" phrasing for a type-300 original now dispatches straight
    here, decided by the model, not a status-word-matching code path.

    bugfix-038: `payment_date`/`payment_method`/bank details are now real
    parameters (previously this tool independently reimplemented type-320's
    payload via its own now-removed hardcoded `payment: [{"type": 1, ...,
    "date": today}]`, missing bugfix-028 A3/A3b's payment-detail requirement
    entirely because it was a second, undiscovered implementation of the same
    document shape create_combo_document already had this fixed for). Same
    treatment as create_combo_document exactly: required, validated, never
    defaulted to today.

    Idempotency (feature 023): unlike Morning itself, which does NOT reject a
    duplicate closing document (confirmed live), a full-amount call
    (`amount=None`) against an already-closed original is a no-op returning
    the current state, so repeated "mark as paid"-style requests can't create
    duplicate combo documents - this no-op path needs no `payment_date` at
    all, since no new document is created. An explicit partial `amount`
    always creates a new document regardless of current status - partial
    closes are a deliberate, repeatable real Morning capability.

    Args:
        client: An authenticated MorningClient (injected).
        original_internal_morning_id: Morning document id of the transaction account
            being closed.
        amount: Optional override — defaults to the original's full total.
        description: Optional override — defaults to a generated closing note.
        vat_included: Whether the new combo document should include VAT
            (default True). Must be decided explicitly by the caller - never
            inferred from the type-300 original's own (VAT-less) shape;
            asking the user when unstated is the model's responsibility
            (runtime_constitution.md), not this function's.
        payment_date: The real date the money moved, ISO YYYY-MM-DD or
            DD/MM/YYYY. Required whenever a document is actually created
            (validated by `_validate_payment_date` - never defaulted to
            today); not needed for the idempotent no-op path above.
        payment_method: How the money arrived - "bank_transfer" (default),
            "cash", "cheque", "credit_card", "paypal", or a payment app
            ("bit", "pay", "paybox", "colu", "google pay", "apple pay").
        bank_number/bank_branch/bank_account: Bank details from the transfer
            confirmation. Stored only on a bank transfer.
        transaction_reference: The אסמכתה. Stored only on a payment app or
            PayPal payment.

    Returns:
        A Hebrew confirmation string with the new combo document's number,
        or a friendly refusal message (no document created, REQ-INV-013) if
        the original isn't linked to a real client record.

    Raises:
        ValueError: If the original document's type is not 300 (transaction
            account) — the combo-closing flow only applies to type-300
            originals; other types are not guessed at. Also raised (via
            `_validate_payment_date`) if `payment_date` is missing,
            unparseable, or in the future, when a document is actually
            about to be created (not the idempotent no-op path).
        Any exception raised by `client.get_invoice` if `original_internal_morning_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    original = client.get_invoice(original_internal_morning_id)
    original_type = original.get("type")
    if original_type != _TRANSACTION_ACCOUNT_DOCUMENT_TYPE:
        raise ValueError(
            f"Cannot close as a transaction account: unsupported document type {original_type} "
            f"(only {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} is supported)"
        )

    if amount is None and original.get("status") in _CLOSED_STATUS_CODES:
        # Already closed — idempotent no-op, avoid creating a duplicate closing document.
        return format_invoice_json(Invoice.model_validate(original))

    if _extract_linked_client_id(original) is None:
        # Pre-feature, bare-name-only original - refuse rather than fall
        # back to rebuilding a bare-name client object (REQ-INV-013).
        log_refusal(
            "create_combo_document_as_reference",
            "original_not_linked_to_client",
            original_internal_morning_id=original_internal_morning_id,
        )
        return format_original_not_linked_to_client()

    payload = _build_combo_closing_payload(
        original,
        payment_date=payment_date,
        payment_method=payment_method,
        bank_number=bank_number,
        bank_branch=bank_branch,
        bank_account=bank_account,
        transaction_reference=transaction_reference,
        amount=amount,
        description=description,
        vat_included=vat_included,
    )
    combo_response = client.create_invoice(payload)
    log_mutation(
        "create_combo_document_as_reference",
        payload=payload,
        response=combo_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    # bugfix-028 A4's lesson (see _read_back_stored_total): POST /documents
    # returns only a minimal echo, never amount/total - re-fetch the full
    # document rather than validating the bare creation response.
    new_id = str(combo_response.get("id") or combo_response.get("documentId") or "")
    return format_invoice_json(Invoice.model_validate(client.get_invoice(new_id)))


def cancel_transaction_account(client: MorningClient, original_internal_morning_id: str) -> str:
    """Cancel an open transaction account ("חשבון עסקה", type 300) with
    ZERO documents created, and return a Hebrew confirmation (feature 056).

    Distinct from `create_combo_document_as_reference`, which deliberately
    creates a linked type-320 document to record fulfillment (the deal
    happened and was paid). This is the opposite case - the deal fell
    through, no money moved, nothing should be recorded as income
    (REQ-INV-020).

    Mechanism (research.md, live-confirmed 2026-08-18): the already-existing
    `MorningClient.close_invoice` (POST /documents/{id}/close) sets the
    account's status 0 -> 2 with no new document of any kind - confirmed
    live via `linkedDocuments` staying empty and the close response's own id
    matching the original. No new MorningClient method was needed.

    Idempotency (REQ-INV-021/025): unlike `create_receipt`/
    `create_combo_document_as_reference`, which lean on Morning's own
    non-rejection of a duplicate document, the raw Morning API DOES reject a
    redundant close with a 400 error ("לא ניתן לסגור מסמך שאינו פתוח" -
    cannot close a document that is not open) - confirmed live. This guard
    therefore lives entirely in application code: if the account is already
    closed for ANY reason (cancelled via this same path, status 2, or
    fulfilled via create_combo_document_as_reference, status 1),
    `close_invoice` is never called again - cancellation must never contradict
    a real payment document that already exists.

    Args:
        client: An authenticated MorningClient (injected).
        original_internal_morning_id: Morning document id of the transaction
            account being cancelled.

    Returns:
        A Hebrew confirmation string (REQ-INV-026 - never "שולם"/paid
        wording, unlike get_invoice_details' generic status formatter),
        identical in shape whether this call actually cancelled the account
        or found it already closed (idempotent no-op).

    Raises:
        ValueError: If the original document's type is not 300 (transaction
            account) — tax-invoice cancellation continues exclusively
            through create_credit_note's existing, document-producing flow
            (REQ-INV-022); this path is never a fallback for it.
        Any exception raised by `client.get_invoice` if
        `original_internal_morning_id` does not resolve to a real document
        (propagated, not swallowed).
    """
    original = client.get_invoice(original_internal_morning_id)
    original_type = original.get("type")
    if original_type != _TRANSACTION_ACCOUNT_DOCUMENT_TYPE:
        log_refusal(
            "cancel_transaction_account",
            "unsupported_document_type",
            original_internal_morning_id=original_internal_morning_id,
            document_type=original_type,
        )
        raise ValueError(
            f"Cannot cancel as a transaction account: unsupported document type {original_type} "
            f"(only {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} is supported - use create_credit_note "
            f"for a {_TAX_INVOICE_DOCUMENT_TYPE} original)"
        )

    if original.get("status") != 0:
        # Already closed - cancelled via this same path, or fulfilled via
        # create_combo_document_as_reference. Idempotent no-op: never call
        # close_invoice again (confirmed live, Morning's raw API rejects a
        # redundant close with a 400, it does not no-op itself).
        return format_transaction_account_cancelled(original)

    close_response = client.close_invoice(original_internal_morning_id)
    log_mutation(
        "cancel_transaction_account",
        payload={"action": "close", "internal_morning_id": original_internal_morning_id},
        response=close_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    return format_transaction_account_cancelled(close_response)


def create_receipt(
    client: MorningClient,
    original_internal_morning_id: Optional[str] = None,
    payment_date: Optional[str] = None,
    amount: Optional[float] = None,
    client_name: Optional[str] = None,
    description: Optional[str] = None,
    name_resolved: bool = False,
) -> str:
    """Create a receipt ("קבלה", type 400) and return a Hebrew confirmation -
    either linked to an existing document being paid, or standalone (feature
    056, no prior document at all).

    MCP tool: create_receipt (feature 021; relaxed by feature 056). Directly
    user-invocable and supports partial-amount receipts. Feature 023 removed
    the separate update_invoice_status tool - "mark as paid" phrasing for a
    type-305 original now dispatches straight here, decided by the model
    (which must resolve the original's real type itself via
    get_invoice_details first), not a status-word-matching code path.

    Feature 056 (REQ-INV-014): when `original_internal_morning_id` is None,
    this creates a STANDALONE receipt instead - for a deposit, loan
    repayment, or advance payment that has no invoice behind it at all
    (REQ-INV-015 through REQ-INV-019). That branch requires
    `client_name` + `name_resolved=True` (the same resolved-client contract
    `create_invoice` already uses - see `_require_resolved_client`),
    `amount`, `description`, and `payment_date`, and never touches
    `client.get_invoice` at all (there is no original to fetch). When
    `original_internal_morning_id` IS given, every existing behavior below
    is unchanged byte-for-byte (REQ-INV-016).

    Only accepts a type-305 original (feature 023) - any other type (300,
    a transaction account closed by create_combo_document_as_reference instead; 320,
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

    bugfix-028 A3 (2026-08-12): `payment_date` is REQUIRED - money already
    moved, so its real date is a fact to carry, never a silent "today"
    (same reasoning, same shared `_validate_payment_date` validator, as
    create_combo_document/create_transaction_account). The model may
    legitimately land on "today" as the answer (a verbal "mark as paid" often
    does mean today), but only after asking - never by skipping the question.

    Args:
        client: An authenticated MorningClient (injected).
        original_internal_morning_id: Morning document id of the invoice
            being paid. Omit for a standalone receipt (feature 056).
        payment_date: The real date the money moved, ISO YYYY-MM-DD (or
            DD/MM/YYYY). Required on both branches - raises if missing,
            unparseable, or in the future.
        amount: On the linked branch, an optional override (defaults to the
            original's full total). On the standalone branch, required.
        client_name: Standalone branch only - the client's exact,
            already-resolved name.
        description: Standalone branch only - free-text reason (e.g.
            "פיקדון", "החזר הלוואה", "מקדמה על חשבון...") - REQ-INV-018, no
            structured reason code.
        name_resolved: Standalone branch only - must be True (asserting
            `resolve_client_name` was already called with `client_name`) or
            this refuses immediately, attempting no Morning lookup at all.

    Returns:
        A Hebrew confirmation string with the new receipt's number, or (on
        the linked branch) a friendly refusal message (no document created,
        REQ-INV-013) if the original isn't linked to a real client record.

    Raises:
        ClientNotFoundError / ClientNameNotResolvedError: standalone branch
            only, via `_require_resolved_client` - see its own docstring.
        ValueError: linked branch only - if the original document's type is
            not 305 (tax invoice) — e.g. 300 (transaction account, use
            create_combo_document_as_reference instead), 320 (combo, already
            self-closed), 330/400 (a credit note/receipt is not itself
            something to pay). Strict positive check (only 305 allowed),
            matching create_combo_document_as_reference's own guard and the
            unsupported-type rejection the removed update_invoice_status
            used to provide for any non-300/305 original. Also raised (via
            `_validate_payment_date`) if `payment_date` is missing,
            unparseable, or in the future - except in the idempotent no-op
            case below, where it's never even inspected.
        Any exception raised by `client.get_invoice` if `original_internal_morning_id`
        does not resolve to a real document (propagated, not swallowed).
    """
    if original_internal_morning_id is None:
        # Feature 056: standalone receipt, no original to fetch at all.
        if client_name:
            client_name = _normalize_hebrew_geresh(client_name)
        resolved_client = _require_resolved_client(client, client_name, name_resolved, "create_receipt")

        payload = _build_standalone_receipt_payload(
            resolved_client.id, amount, description, payment_date
        )
        response = client.create_invoice(payload)
        log_mutation(
            "create_receipt",
            payload=payload,
            response=response,
            client_id=resolved_client.id,
            client_name=client_name,
        )
        # bugfix-028 A4's lesson (see _read_back_stored_total): POST
        # /documents returns only a minimal echo - re-fetch the full
        # document rather than validating the bare creation response.
        new_id = str(response.get("id") or response.get("documentId") or "")
        return format_invoice_json(Invoice.model_validate(client.get_invoice(new_id)))

    original = client.get_invoice(original_internal_morning_id)
    original_type = original.get("type")
    if original_type != _TAX_INVOICE_DOCUMENT_TYPE:
        raise ValueError(
            f"Cannot create a receipt for document type {original_type} "
            f"(only {_TAX_INVOICE_DOCUMENT_TYPE} is supported - use create_combo_document_as_reference "
            f"for a {_TRANSACTION_ACCOUNT_DOCUMENT_TYPE} original)"
        )

    if amount is None and original.get("status") in _CLOSED_STATUS_CODES:
        # Already paid — idempotent no-op, avoid creating a duplicate receipt.
        # payment_date is deliberately never inspected here - nothing is
        # actually being recorded on this path.
        return format_invoice_json(Invoice.model_validate(original))

    if _extract_linked_client_id(original) is None:
        # Pre-feature, bare-name-only original - refuse rather than fall
        # back to rebuilding a bare-name client object (REQ-INV-013).
        log_refusal(
            "create_receipt",
            "original_not_linked_to_client",
            original_internal_morning_id=original_internal_morning_id,
        )
        return format_original_not_linked_to_client()

    payload = _build_payment_receipt_payload(original, payment_date=payment_date, amount=amount)
    receipt_response = client.create_invoice(payload)
    log_mutation(
        "create_receipt",
        payload=payload,
        response=receipt_response,
        client_id=_extract_linked_client_id(original),
        client_name=(original.get("client") or {}).get("name"),
    )

    # bugfix-028 A4's lesson (see _read_back_stored_total): POST /documents
    # returns only a minimal echo - re-fetch the full document rather than
    # validating the bare creation response.
    new_id = str(receipt_response.get("id") or receipt_response.get("documentId") or "")
    return format_invoice_json(Invoice.model_validate(client.get_invoice(new_id)))


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


def _levenshtein(a: str, b: str) -> int:
    """Standard edit distance (insertions/deletions/substitutions, unit
    cost). No external dependency - this project has none for it."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current_row = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current_row.append(
                min(
                    previous_row[j] + 1,  # deletion
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j - 1] + cost,  # substitution
                )
            )
        previous_row = current_row
    return previous_row[-1]


def _bag_equal_words(query: str, candidate_name: str) -> bool:
    """Whether `query` and `candidate_name` are made of exactly the same
    words (case-insensitive, geresh-normalized), regardless of order -
    the real exactness criterion for the algorithm below (bugfix-039,
    round 3, 2026-08-11): the caller may not have typed the words in the
    same order Morning stored them, and that alone must never turn a
    genuinely exact name into a refusal."""

    def _bag(name: str) -> List[str]:
        return sorted(_normalize_hebrew_geresh(w.strip().casefold()) for w in name.split() if w)

    return _bag(query) == _bag(candidate_name)


def _search_word_prefix(client: MorningClient, prefix: str) -> Dict[str, Client]:
    """One real Morning /clients/search call for a single prefix string -
    the one search primitive the algorithm below is built from."""
    response = client.search_clients({"name": _normalize_hebrew_geresh(prefix)})
    items = response.get("items") or []
    candidates = [Client.model_validate(item) for item in items]
    return {c.id: c for c in candidates if c.id}


_COMMON_WORD_DISCOVERY_CAP = 10  # user decision, 2026-08-11 - see resolve_client_by_name's loop


def _grow_word(client: MorningClient, word: str, pool_ids: Optional[Set[str]]) -> Dict[str, Client]:
    """Grow `word`'s own prefix one letter at a time (intersected with
    `pool_ids` if given - None means unconstrained), stopping the moment
    the result narrows to exactly 1, or once the word's letters run out,
    or immediately on 0. Returns whatever {client_id: Client} state is at
    the point it stopped.

    This single mechanism naturally covers a query word with an extra
    trailing letter beyond a real, shorter stored word (e.g. "צורן" vs
    stored "צור") without any separate truncation step: it stops growing
    the instant "צור" (3 letters) already narrows to one candidate, and
    never reaches "צורו"/"צורן" where a longer-than-stored prefix would
    find nothing.

    Starts at 2 letters, not 1 (optimization, user decision 2026-08-11): a
    single letter always matches broadly (real sandbox observed: "D" alone
    -> 1479 total matches) - it can never usefully narrow anything, it's
    just a wasted call. `word` shorter than 2 letters returns {} outright
    (nothing to grow).

    Every step filters against the SAME original `pool_ids` throughout -
    never against a running/self-accumulated set from this word's own
    previous letter. This matters against the real API: Morning paginates
    (observed: 25 items/page even when the true total is in the
    thousands), so an earlier letter's own returned page is an arbitrary,
    non-representative sample of the TRUE match set - filtering a later,
    more specific letter's results against that arbitrary sample would
    silently discard real candidates that simply weren't on that earlier
    page (a real bug caught here, 2026-08-11, testing against the live
    sandbox: a freshly-seeded, genuinely-unique-marker client was dropped
    from its own discovery result entirely because an early single-letter
    page didn't happen to include it). Growing the prefix further is
    already inherently narrowing via Morning's own search semantics
    (anything matching a longer prefix necessarily also matches every
    shorter prefix of it) - no client-side re-intersection against a
    previous, possibly-incomplete page is needed or correct.
    """
    if len(word) < 2:
        return {}
    prefix = word[:2]
    results = _search_word_prefix(client, prefix)
    if pool_ids is not None:
        results = {cid: c for cid, c in results.items() if cid in pool_ids}
    if len(results) <= 1:
        return results  # 0 -> dead end; 1 -> unique, no benefit growing further
    for ch in word[2:]:
        prefix += ch
        results = _search_word_prefix(client, prefix)
        if pool_ids is not None:
            results = {cid: c for cid, c in results.items() if cid in pool_ids}
        if len(results) <= 1:
            return results
    return results  # word's own letters exhausted, still >1


def resolve_client_by_name(client: MorningClient, query: str) -> Tuple[Optional[Client], List[Client]]:
    """THE ONE client-name-resolution mechanism (bugfix-039, round 3, user
    decision 2026-08-11: "this AND ONLY this is the way to find clients in
    morning" - replaces the old _resolve_client_by_name_words/
    _search_word_with_truncation pair and every ad-hoc "try whole-string,
    then maybe fall back" pattern across every caller). Full algorithm
    writeup and the standalone prototype it was proven against first:
    specs/bugfixes/bugfix-039-list-invoices-skips-client-resolution.md.

    Returns (exact_client_or_None, ordered_candidates) - same shape as the
    old _resolve_client_by_name, but:
    - candidates are NEVER filtered by relevance (user decision,
      2026-08-11: independent per-word discovery surfacing an unrelated
      client that only shares one common word - e.g. a common patronymic/
      surname fragment - with the query is intentional, not a bug; a
      future refinement may special-case very common Hebrew name-part
      patterns, explicitly deferred, not part of this change)
    - candidates ARE always ordered by Levenshtein distance to the query
      (closest first), so a long list still shows the most plausible read
      on top.

    STEP 0 (cheap fast path, one call): the caller may have already given
    the exact right name (word-order-independent) - check the whole
    string at once before doing any of the real work below.

    If that doesn't resolve exactly and the query is multi-word, a single
    `for word in words:` pass (query order) does two things per word, in
    the same iteration:
    1. Grows an INTERSECTED pool (started unconstrained) via `_grow_word`
       - the only phase that can conclude an EXACT match (a unique
         candidate whose full stored words bag-equal every query word) or
         kill the chain (0 results) or carry an ambiguous pool to the next
         word.
    2. Independently of that pool, grows this SAME word alone via
       `_grow_word` again (unconstrained) - because a real candidate can
       be invisible to the intersected chain (e.g. a client sharing only
       the LAST of three query words with nothing in common on the first
       two is invisible to a chain that already narrowed on those first
       two) yet still worth surfacing as a "did you mean" option. Whatever
       this word alone narrows to is added to the running candidate set.
    The loop keeps going through every word regardless of whether the
    intersected chain already died, specifically so every word still gets
    its turn at independent discovery.

    STEP FINAL: once an exact match is concluded VIA THE LOOP (not Step 0
    - Step 0's own result is already a fresh, direct whole-string lookup,
    so re-running the identical query again would be pure waste), one
    more whole-string lookup on the resolved name re-confirms against
    fresh data - the loop's own confirmation came from piecemeal per-word/
    per-letter prefix searches, not one direct fetch of the full name.
    """
    query = _normalize_hebrew_geresh(query)
    words = [w for w in query.split() if w]
    if not words:
        return None, []

    # STEP 0 - already a fresh, direct lookup; no Step Final needed on top.
    resolved, _ = _resolve_client_by_name(client, query)
    if resolved is not None and _bag_equal_words(query, resolved.name):
        return resolved, []

    if len(words) < 2:
        # Single-word queries stay a broad partial search (existing app
        # policy elsewhere, e.g. list_invoices) - not this algorithm's
        # concern for exactness.
        candidates = list(_search_word_prefix(client, words[0]).values())
        return None, _sorted_by_distance(query, candidates)

    # SINGLE PASS over the words - exactness tracking and candidate
    # discovery both happen per word, in the same loop.
    pool_ids: Optional[Set[str]] = None
    chain_dead = False
    candidates: Dict[str, Client] = {}

    for word in words:
        if len(word) < 2:
            # A 1-letter word can never usefully narrow anything (see
            # _grow_word) - skip it entirely rather than spend a call on
            # it, for both discovery and the intersecting chain (user
            # decision, 2026-08-11).
            continue

        discovered = _grow_word(client, word, None)
        if len(discovered) <= _COMMON_WORD_DISCOVERY_CAP:
            candidates.update(discovered)
        # else: this word alone matched more than _COMMON_WORD_DISCOVERY_CAP
        # real clients even using its FULL length (never narrowed) - a
        # common Hebrew name-part (patronymic "בן", common surnames like
        # "כהן"/"לוי", common first names like "דוד") is exactly this
        # shape: real, but not a useful identifying signal on its own, so
        # none of its matches are added as candidates (user decision,
        # 2026-08-11 - a deterministic threshold, not relevance scoring).
        # Only applies to discovery; the intersecting chain below still
        # uses this same word normally, since a common word CAN still
        # correctly narrow to an exact match once combined with another
        # word (e.g. "בן" + "גוריון").

        if chain_dead:
            continue

        intersected = _grow_word(client, word, pool_ids)
        if len(intersected) == 0:
            chain_dead = True  # this word ordering can't reach an exact match
            continue
        if len(intersected) == 1:
            (candidate,) = intersected.values()
            if _bag_equal_words(query, candidate.name):
                return _resolve_client_final(client, candidate)  # EXACT MATCH, done
            chain_dead = True  # provably terminal (see _grow_word docstring), not exact
            continue
        pool_ids = set(intersected.keys())  # carry the ambiguous pool to the next word

    return None, _sorted_by_distance(query, list(candidates.values()))


def _sorted_by_distance(query: str, candidates: List[Client]) -> List[Client]:
    """Closest-to-the-query first (Levenshtein, normalized) - orders,
    never filters (see resolve_client_by_name's docstring)."""
    q = _normalize_hebrew_geresh(query.strip().casefold())
    return sorted(candidates, key=lambda c: _levenshtein(q, _normalize_hebrew_geresh(c.name.strip().casefold())))


def _resolve_client_final(client: MorningClient, resolved: Client) -> Tuple[Optional[Client], List[Client]]:
    """Fresh-data re-confirmation once exactness is concluded."""
    confirm, _ = _resolve_client_by_name(client, resolved.name)
    return (confirm or resolved), []


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


def resolve_client_name(client: MorningClient, name: str) -> str:
    """Resolve a free-text client name to Morning's real stored name and
    return a Hebrew resolution report (client-name-resolution architecture
    fix, bugfix-028 sub-piece, 2026-08-12, user decision). THE canonical,
    sole entry point for fuzzy/word-growth client-name resolution (built on
    `resolve_client_by_name`, bugfix-039 round 3) - supersedes calling that
    engine directly from any caller-facing tool.

    MCP tool: resolve_client_name. Read-only - no approval wait
    (REQ-CLIENT-008). The model MUST call this first, before any other tool
    that needs one specific client, whenever a user's request references a
    client by name - then pass the CONFIRMED, EXACT name back into the
    target tool together with `name_resolved=True`.

    Four outcomes, each a single Hebrew string:
    - Exactly one EXACT match -> discloses the stored name; use it verbatim.
    - Exactly one NON-exact match -> a closed yes/no confirmation question
      (format_client_name_confirmation_question) - same contract every
      other tool already used for this case.
    - More than one match -> an ambiguous-candidates listing
      (format_ambiguous_clients_message), Levenshtein-ordered.
    - Zero matches -> a friendly "not found" message (format_client_not_found).
      Unlike every tool that CONSUMES a resolved name, this does NOT raise
      ClientNotFoundError - it is the exploratory FIRST call, before any
      tool has been asked to act on a specific client, so a genuine
      zero-match here is an ordinary, expected outcome of exploring a name,
      not a failed mutation/lookup attempt (see `_raise_client_not_found`'s
      docstring for the contrasting case).

    Args:
        client: An authenticated MorningClient (injected).
        name: Free-text client name (apostrophe/geresh-normalized before
            resolution - see `_normalize_hebrew_geresh`).

    Returns:
        A Hebrew string: the resolved exact name (never the client_id -
        REQ-CLIENT-018), a confirmation question, an ambiguous-candidates
        list, or a "not found" message.
    """
    resolved, candidates = resolve_client_by_name(client, name)
    if resolved is not None:
        return format_client_name_resolved(resolved.name)
    if len(candidates) == 1:
        return format_client_name_confirmation_question(candidates[0].name)
    if candidates:
        return format_ambiguous_clients_message(candidates)
    return format_client_not_found()


def _resolve_exact_client_name(client: MorningClient, name: str) -> Optional[Client]:
    """Direct, exact (word-order-independent) lookup only - Step 0 of
    resolve_client_by_name, reused directly: one Search Clients call on the
    literal name, accepted only if it's a unique client whose stored name is
    a word-for-word (order-independent) match. Never grows letters, never
    picks a 'closest' candidate - that fuzzy work belongs to
    resolve_client_name alone now."""
    name = _normalize_hebrew_geresh(name)
    resolved, _ = _resolve_client_by_name(client, name)
    if resolved is not None and _bag_equal_words(name, resolved.name):
        return resolved
    return None


def _require_resolved_client(
    client: MorningClient, client_name: str, name_resolved: bool, tool_name: str
) -> Client:
    """The one gate every client-name-consuming tool shares (client-name-
    resolution architecture fix, bugfix-028 sub-piece, 2026-08-12, user
    decision: "these tools MUST GET a resolved name which matches").

    Every tool built on this gate has exactly two outcomes: it returns a
    real, resolved `Client`, or it raises (2026-08-12, user decision,
    tightened after the original 028 B4(c) fix stopped short of applying
    the same principle here: "the tool has no idea if resolve was called or
    not - it's stupid - it takes what it got and tries. if it succeeds -
    great. if it fails - it raises the exception according to what
    failed."). There is no third "ordinary refusal text" outcome anymore -
    that was the same shape of bug B4(c) already fixed for the
    zero-candidate case, just left unfixed here originally.

    Hard gate: name_resolved must be exactly True, or this raises
    IMMEDIATELY, without attempting any Morning lookup at all - forcing the
    model through resolve_client_name rather than letting a stale/guessed
    name get lucky against Morning by accident. Once True is asserted, this
    does ONLY an exact, word-order-independent lookup - no fuzzy/letter
    growth, no disambiguation dialogue (that already happened, or should
    have, in resolve_client_name). A multi-candidate OR zero-candidate
    result under this exact-only mode are treated identically -
    ClientNotFoundError - since the correct recovery for either is the
    same: call resolve_client_name and retry.
    """
    if not name_resolved:
        log_refusal(tool_name, "name_not_resolved", client_name=client_name)
        # This exception's message is surfaced verbatim by errors.py's
        # friendly_error_message - a real, plain-text procedural instruction,
        # NOT a tool-call return value, so it is deliberately NOT
        # format_name_not_resolved()'s JSON (2026-09-04 JSON-only contract
        # applies to tool results, not to exception messages read by
        # errors.py).
        raise ClientNameNotResolvedError(
            "יש לקרוא ל-resolve_client_name עם שם הלקוח קודם, להשתמש בשם המדויק "
            "שהוא מחזיר, ולנסות שוב עם name_resolved=true"
        )
    resolved = _resolve_exact_client_name(client, client_name)
    if resolved is None:
        _raise_client_not_found(tool_name, client_name)
    return resolved


class ClientNotFoundError(ValueError):
    """No client matched the name a document was asked to be created for.

    bugfix-028 B4(c): this used to be returned as ordinary tool output with
    `error=None`, indistinguishable from success at every layer above. In
    production that let one ₪40,000 document be approved eight times, created
    zero times, with the user never told the previous attempt had failed. The
    tool was asked to create a document and did not create one - that is a
    failure, and it has to be typed as one. Still raised here post-bugfix-039
    (user decision, 2026-08-12): only the true zero-real-candidate case raises
    - ambiguous and non-exact-single-match resolutions are genuine questions
    for the user, not failures, and still return an ordinary refusal message.
    """


class ClientNameNotResolvedError(ValueError):
    """The caller (the model) invoked a client-name-consuming tool without
    first calling `resolve_client_name` (name_resolved wasn't True).

    bugfix-028 B4(c) follow-up (2026-08-12, user decision): originally this
    was returned as ordinary tool output ("please call resolve_client_name
    first") with `error=None` - the exact same silent-failure shape B4(c)
    already fixed for the zero-candidate case, just reintroduced here. A
    distinct exception class from `ClientNotFoundError` on purpose (user:
    "you can have many exception classes for the different kinds of errors
    that can happen, if it's meaningful") - this is a caller-contract
    violation (skipped a required step), not "this client doesn't exist";
    logs/audits can tell the two apart even though both now surface as a
    real MCP-level failure (see server.py's `_call_with_error_boundary`).
    """


def _raise_client_not_found(tool_name: str, client_name: str) -> NoReturn:
    """The one place a genuine zero-candidate client-name resolution turns
    into a failure (unification, 2026-08-12, user decision: "I want 1 way
    and that every flow uses the same exact way" - previously
    `_resolve_client_for_document_creation`'s raise, `get_client_details`'s
    own `return format_client_not_found()`, and `list_invoices`'s silent
    fall-through to a generic "no results" message were three different
    mechanisms for the same underlying situation, with `list_invoices` not
    even signaling anything about the client specifically). Every tool
    that resolves one specific named client - whether to mutate it,
    describe it, or list documents for it - now raises this same
    exception, with the same message shape and the same audit-log entry,
    so `errors.py`'s `friendly_error_message` produces an identical
    user-facing message regardless of which tool was called.
    """
    log_refusal(tool_name, "client_not_found", client_name=client_name)
    # This exception's message is surfaced verbatim by errors.py's
    # friendly_error_message - real, plain-text Hebrew, NOT a tool-call
    # return value, so it is deliberately NOT format_client_not_found()'s
    # JSON (2026-09-04 JSON-only contract applies to tool results, not to
    # exception messages read by errors.py).
    raise ClientNotFoundError(f'לא נמצא לקוח בשם "{client_name}"')


def _extract_linked_client_id(original: dict) -> Optional[str]:
    """Read a real client_id off an already-fetched linked original
    document, if present (feature 027, REQ-INV-012/013).

    Used by Group B tools (create_credit_note/create_receipt/
    create_combo_document_as_reference), which derive their client from the
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


def get_client_details(client: MorningClient, name: str, name_resolved: bool = False) -> str:
    """Retrieve a single client's full detail record by name.

    MCP tool: get_client_details (contracts/get_client_details.json,
    user-stories.md US2). Read-only - no approval wait (REQ-CLIENT-008).
    Name-only lookup (REQ-CLIENT-002, analysis 2026-07-29: tax-ID lookup was
    considered and dropped). Never includes the internal client_id
    (REQ-CLIENT-018).

    Client-name-resolution architecture fix (2026-08-12, user decision):
    this tool no longer does its own fuzzy/word-growth matching or
    disambiguation - that is entirely `resolve_client_name`'s job now (the
    one, sole entry point for that). This tool requires `name_resolved=True`
    (the caller must have already resolved the name via `resolve_client_name`)
    and only ever accepts an exact, word-order-independent match - see
    `_require_resolved_client`'s docstring for the full contract.

    Args:
        client: An authenticated MorningClient (injected).
        name: The client's exact, already-resolved name.
        name_resolved: Must be True (asserting `resolve_client_name` was
            already called with this name) or this refuses immediately,
            attempting no Morning lookup at all.

    Returns:
        A Hebrew client-details string on an exact match, or a plain
        procedural refusal string (name_resolved wasn't True) - see
        `_require_resolved_client`.

    Raises:
        ClientNotFoundError: if name_resolved is True but the name doesn't
            match a real client exactly (unification, 2026-08-12 - this
            tool used to return a friendly string here, a different
            mechanism from every other client-resolving tool for the same
            situation; see `_raise_client_not_found`'s docstring).
    """
    resolved_client = _require_resolved_client(client, name, name_resolved, "get_client_details")
    return format_client_details(resolved_client, is_exact_match=True)


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
    return json.dumps(
        {
            "status": "created",
            "client": {
                "name": normalized_name, "email": validated_email,
                "phone": normalized_phone, "tax_id": tax_id,
            },
        },
        ensure_ascii=False,
    )


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
    name_resolved: bool = False,
) -> str:
    """Update an existing client's fields and return a Hebrew confirmation.

    MCP tool: update_client (contracts/update_client.json, user-stories.md
    US4). `new_name`/`email`/`phone`/`tax_id` are the optional fields being
    changed - at least one is required. Approval-gated at the denidin-app
    layer (ai_handler.APPROVAL_REQUIRED_MCP_TOOLS).

    Client-name-resolution architecture fix (2026-08-12, user decision):
    `name` identifies WHICH client to update, but this tool no longer does
    its own fuzzy/word-growth matching or disambiguation - that is entirely
    `resolve_client_name`'s job now. This tool requires `name_resolved=True`
    (the caller must have already resolved the name via `resolve_client_name`)
    and only ever accepts an exact, word-order-independent match - see
    `_require_resolved_client`'s docstring for the full contract.

    Args:
        client: An authenticated MorningClient (injected).
        name: The client's exact, already-resolved current name.
        new_name: Optional new name value (apostrophe/geresh-normalized).
        email: Optional new email (validated).
        phone: Optional new phone (normalized to Israeli format).
        tax_id: Optional new Israeli business tax ID (ע"מ).
        name_resolved: Must be True (asserting `resolve_client_name` was
            already called with this name) or this refuses immediately,
            attempting no Morning lookup at all.

    Returns:
        A Hebrew confirmation string on an exact match (client actually
        updated), or a plain procedural refusal string (name_resolved
        wasn't True - see `_require_resolved_client`). Never includes the
        internal Morning client_id (REQ-CLIENT-018).

    Raises:
        ClientNotFoundError: if name_resolved is True but the name doesn't
            match a real client exactly (bugfix-028 B4(c) - an update
            approved against a nonexistent client must not look
            indistinguishable from success).
        ValueError: if none of new_name/email/phone/tax_id is given, or if
            email/phone fails validation/normalization.
    """
    if not any([new_name, email, phone, tax_id]):
        raise ValueError("update_client requires at least one of new_name/email/phone/tax_id to change.")

    resolved_client = _require_resolved_client(client, name, name_resolved, "update_client")

    normalized_new_name = _normalize_hebrew_geresh(new_name) if new_name else None
    validated_email = _validate_email(email) if email else None
    normalized_phone = _normalize_israeli_phone(phone) if phone else None
    payload = _build_update_client_payload(normalized_new_name, validated_email, normalized_phone, tax_id)
    response = client.update_client(resolved_client.id, payload)
    log_mutation(
        "update_client",
        payload=payload,
        response=response,
        client_id=resolved_client.id,
        client_name=normalized_new_name or name,
    )

    display_name = normalized_new_name or name
    return json.dumps(
        {
            "status": "updated",
            "client": {
                "name": display_name, "email": validated_email,
                "phone": normalized_phone, "tax_id": tax_id,
            },
        },
        ensure_ascii=False,
    )


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


def download_invoice_pdf(client: MorningClient, internal_morning_id: str, lang: str = "he") -> str:
    """Return a PDF download link for an invoice, in a Hebrew confirmation string.

    MCP tool: download_invoice_pdf (contracts/download_invoice_pdf.json,
    user-stories.md US7).

    Real mechanism (confirmed live): no separate download endpoint call is
    needed — `GET /documents/{id}` (the existing `MorningClient.get_invoice`)
    already returns a `url: {he, origin}` object with ready-to-use, pre-signed
    PDF download links (`GET /documents/download?d=...`).

    Args:
        client: An authenticated MorningClient (injected).
        internal_morning_id: Morning document id.
        lang: Which link to prefer — "he" (Hebrew) or "origin" (default/English).
            Falls back to whichever is present if the preferred one is missing.

    Returns:
        A Hebrew confirmation string containing the PDF download URL.

    Raises:
        ValueError: if no download URL is present on the document at all.
    """
    original = client.get_invoice(internal_morning_id)
    urls = original.get("url") or {}
    pdf_url = urls.get(lang) or urls.get("origin") or urls.get("he")

    if not pdf_url:
        raise ValueError(f"No PDF download URL available for invoice {internal_morning_id!r}.")

    invoice_number = original.get("number", internal_morning_id)
    return json.dumps(
        {"display_number": invoice_number, "pdf_url": pdf_url}, ensure_ascii=False
    )
