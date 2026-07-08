"""Tests for denidin_mcp_morning.models — Pydantic models over the real Morning shape.

Real objects, no mocking. Covers T004 from
specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
Sample shapes are drawn from the real Morning /documents payload used by the
existing passing sandbox test (tests/integration/test_morning_sandbox_invoices_crud.py).
"""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from denidin_mcp_morning.models import Client, FinancialSummary, Invoice, Payment

REAL_DOCUMENT_RESPONSE_SAMPLE = {
    "id": "5f2c1a2b-0000-4c11-9a1a-abcdef123456",
    "number": "INV-2026-001",
    "type": 320,
    "documentType": 320,
    "client": {
        "id": "client-123",
        "name": "Tech Corp",
        "emails": ["billing@techcorp.example"],
        "phone": "+972541234567",
    },
    "date": "2026-07-08",
    "dueDate": "2026-08-08",
    "currency": "ILS",
    "vatType": 1,
    "income": [
        {"description": "Consulting services", "quantity": 1, "price": 5000.0, "vatType": 1}
    ],
    "amount": 5000.0,
    "total": 5850.0,
    "vatAmount": 850.0,
}


def test_invoice_model_parses_real_document_response():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.id == "5f2c1a2b-0000-4c11-9a1a-abcdef123456"
    assert invoice.client_name == "Tech Corp"
    assert invoice.amount == 5000.0
    assert invoice.total_amount == 5850.0
    assert invoice.currency == "ILS"
    assert invoice.issue_date == date(2026, 7, 8)
    assert invoice.due_date == date(2026, 8, 8)


def test_invoice_model_rejects_negative_amount():
    bad = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, amount=-100.0)

    with pytest.raises(ValidationError):
        Invoice.model_validate(bad)


def test_invoice_model_defaults_currency_to_ils_when_omitted():
    no_currency = {k: v for k, v in REAL_DOCUMENT_RESPONSE_SAMPLE.items() if k != "currency"}

    invoice = Invoice.model_validate(no_currency)

    assert invoice.currency == "ILS"


def test_client_model_requires_name():
    with pytest.raises(ValidationError):
        Client.model_validate({"email": "a@b.com"})


def test_client_model_validates_email_format():
    with pytest.raises(ValidationError):
        Client.model_validate({"name": "Tech Corp", "email": "not-an-email"})


def test_client_model_accepts_minimal_valid_payload():
    client = Client.model_validate({"name": "Tech Corp"})

    assert client.name == "Tech Corp"
    assert client.email is None


def test_payment_model_round_trip():
    payment = Payment.model_validate(
        {
            "id": "pay-1",
            "invoice_id": "5f2c1a2b-0000-4c11-9a1a-abcdef123456",
            "amount": 5850.0,
            "currency": "ILS",
            "payment_date": "2026-07-10",
            "method": "card",
        }
    )

    assert payment.amount == 5850.0
    assert payment.payment_date == date(2026, 7, 10)


def test_financial_summary_model_computes_no_math_itself_just_validates():
    summary = FinancialSummary.model_validate(
        {
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "total_invoiced": 125000.0,
            "total_paid": 105000.0,
            "total_unpaid": 20000.0,
            "invoice_count": 24,
            "paid_invoice_count": 20,
            "unpaid_invoice_count": 4,
            "average_invoice_amount": 5208.33,
        }
    )

    assert summary.invoice_count == summary.paid_invoice_count + summary.unpaid_invoice_count


def test_models_use_utc_for_any_generated_timestamps():
    """If a model stamps created_at itself, it must be UTC (CONSTITUTION §II)."""
    client = Client.model_validate({"name": "Tech Corp"})

    if client.created_at is not None:
        assert client.created_at.tzinfo == timezone.utc
