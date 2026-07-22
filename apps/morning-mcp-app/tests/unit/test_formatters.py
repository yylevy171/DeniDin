"""Tests for denidin_mcp_morning.formatters — Hebrew/₪/VAT/date formatting.

Real objects, no mocking. Covers T005 from
specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
"""
from datetime import date

import pytest

from denidin_mcp_morning.formatters import (
    format_currency_ils,
    format_date_il,
    format_invoice_confirmation,
    format_invoice_details,
    translate_document_type,
    translate_payment_type,
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


# ============================================================================
# bugfix-014: document type / payment type translation, linked documents
# ============================================================================

# Live-confirmed, 2026-07-21/22, via GET /documents/types on the real sandbox
# (see bugfix-014's Investigation Findings) - the authoritative source, not a
# guess.
@pytest.mark.parametrize(
    "type_code,expected_he",
    [
        (300, "חשבון עסקה"),
        (305, "חשבונית מס"),
        (320, "חשבונית מס / קבלה"),
        (330, "חשבונית זיכוי"),
        (400, "קבלה"),
    ],
)
def test_translate_document_type_known_codes(type_code, expected_he):
    assert translate_document_type(type_code) == expected_he


def test_translate_document_type_unknown_code_falls_back_to_the_code():
    assert translate_document_type(999) == "999"


def test_translate_document_type_none_falls_back_gracefully():
    assert translate_document_type(None) == ""


# Live-confirmed, 2026-07-22, via GET /payments/types on the real sandbox.
@pytest.mark.parametrize(
    "payment_type_code,expected_he",
    [
        (0, "ניכוי במקור"),
        (1, "מזומן"),
        (2, "צ'ק"),
        (3, "כרטיס אשראי"),
        (4, "העברה בנקאית"),
        (5, "פייפאל"),
        (10, "אפליקציית תשלום"),
        (11, "אחר"),
    ],
)
def test_translate_payment_type_known_codes(payment_type_code, expected_he):
    assert translate_payment_type(payment_type_code) == expected_he


def test_translate_payment_type_unknown_code_falls_back_to_the_code():
    assert translate_payment_type(999) == "999"


def test_format_invoice_confirmation_includes_translated_document_type():
    invoice = Invoice.model_validate(dict(REAL_DOCUMENT_RESPONSE_SAMPLE, type=305))

    message = format_invoice_confirmation(invoice)

    assert "חשבונית מס" in message


def test_format_invoice_details_includes_linked_documents_section():
    """Regression for bugfix-014's double-counting bug: a receipt/credit
    linked to this invoice must be visible in get_invoice_details' output so
    the model can net paid/owed itself, per the runtime constitution's flow
    guidance - not appear as an unrelated separate charge."""
    with_link = dict(
        REAL_DOCUMENT_RESPONSE_SAMPLE,
        type=305,
        linkedDocuments=[
            {
                "id": "dda4d655-4018-4461-a472-506198876f2a",
                "type": 400,
                "number": 80109,
                "documentDate": "2026-07-21",
                "amount": 88,
                "currency": "ILS",
            }
        ],
    )
    invoice = Invoice.model_validate(with_link)

    message = format_invoice_details(invoice)

    assert "מסמכים מקושרים" in message
    assert "80109" in message
    assert "קבלה" in message
    assert "₪88.00" in message


def test_format_invoice_details_omits_linked_documents_section_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    message = format_invoice_details(invoice)

    assert "מסמכים מקושרים" not in message
