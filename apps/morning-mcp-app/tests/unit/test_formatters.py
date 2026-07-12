"""Tests for denidin_mcp_morning.formatters — Hebrew/₪/VAT/date formatting.

Real objects, no mocking. Covers T005 from
specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
"""
from datetime import date

from denidin_mcp_morning.formatters import (
    format_currency_ils,
    format_date_il,
    format_invoice_confirmation,
    translate_status,
)
from denidin_mcp_morning.models import Invoice

REAL_DOCUMENT_RESPONSE_SAMPLE = {
    "id": "5f2c1a2b-0000-4c11-9a1a-abcdef123456",
    "number": "INV-2026-001",
    "type": 320,
    "client": {"id": "client-123", "name": "Tech Corp"},
    "date": "2026-07-08",
    "dueDate": "2026-08-08",
    "currency": "ILS",
    "amount": 5000.0,
    "total": 5850.0,
    "vatAmount": 850.0,
    "status": "unpaid",
}


def test_format_currency_ils_adds_symbol_and_thousands_separator():
    assert format_currency_ils(5000) == "₪5,000.00"


def test_format_currency_ils_rounds_to_two_decimals():
    assert format_currency_ils(5850.5) == "₪5,850.50"


def test_format_date_il_uses_dd_mm_yyyy():
    assert format_date_il(date(2026, 7, 8)) == "08/07/2026"


def test_translate_status_paid():
    assert translate_status("paid") == "שולם"


def test_translate_status_unpaid():
    assert translate_status("unpaid") == "לא שולם"


def test_translate_status_overdue():
    assert translate_status("overdue") == "פג תוקף"


def test_translate_status_cancelled():
    assert translate_status("cancelled") == "בוטל"


def test_translate_status_unknown_falls_back_to_original():
    assert translate_status("some_other_status") == "some_other_status"


def test_format_invoice_confirmation_is_in_hebrew_and_includes_key_fields():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    message = format_invoice_confirmation(invoice)

    assert invoice.number in message
    assert "₪5,850.00" in message
    assert "לא שולם" in message  # translated status (unpaid)
