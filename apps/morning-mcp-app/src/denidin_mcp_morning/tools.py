"""MCP tool implementations wrapping MorningClient for invoice management.

Each function here corresponds 1:1 to an MCP tool registered in server.py
(see contracts/<tool>.json and user-stories.md for the tool contract and
acceptance criteria). Tools receive a MorningClient by dependency injection
(no globals, no monkey-patching per CONSTITUTION.md §XVII) and return a
human-readable, Hebrew-formatted string.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .formatters import format_invoice_confirmation
from .models import Invoice
from .morning_client import MorningClient

_TAX_INVOICE_DOCUMENT_TYPE = 305


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
