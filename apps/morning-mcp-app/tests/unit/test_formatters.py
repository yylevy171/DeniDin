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
    format_invoice_list,
    format_original_not_linked_to_client,
    format_too_many_invoices_message,
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


# ============================================================================
# Feature 038: format_invoice_list count line + format_too_many_invoices_message
# ============================================================================


def _sample_invoice(number: str) -> Invoice:
    return Invoice.model_validate(dict(REAL_DOCUMENT_RESPONSE_SAMPLE, number=number))


def test_format_invoice_list_untruncated_states_exact_count_no_shown_of_total():
    # Invoice numbers deliberately avoid the digit "3" (the count under test)
    # so a false-positive digit match can't hide a missing/wrong count line.
    invoices = [_sample_invoice("A700"), _sample_invoice("A800"), _sample_invoice("A900")]

    message = format_invoice_list(invoices, total_matched=3)

    assert "נמצאו 3" in message  # designed count-line phrase, not a bare digit check
    assert message.count("חשבונית #") == 3
    assert "מתוך" not in message  # no "shown X of Y" language when nothing was omitted


def test_format_invoice_list_truncated_states_shown_of_total_and_narrow_note():
    # Invoice number deliberately avoids the digits "1"/"7" (shown/total
    # under test) so a false-positive digit match can't hide a missing/wrong
    # shown/total line.
    invoices = [_sample_invoice("A900")]

    message = format_invoice_list(invoices, total_matched=7)

    assert message.count("חשבונית #") == 1
    assert "מתוך 7" in message  # designed "shown X מתוך Y" phrase
    assert "1" in message.split("\n")[0]  # shown count (1) appears in the opening line
    assert "צמצם" in message or "לצמצם" in message  # asks to narrow the search


def test_format_invoice_list_empty_returns_unchanged_no_results_message():
    message = format_invoice_list([], total_matched=0)

    assert message == "לא נמצאו חשבוניות התואמות את החיפוש."


def test_format_invoice_list_no_longer_accepts_has_more_kwarg():
    with pytest.raises(TypeError):
        format_invoice_list([_sample_invoice("INV-001")], has_more=False)  # type: ignore[call-arg]


def test_format_too_many_invoices_message_states_total_and_asks_to_narrow():
    message = format_too_many_invoices_message(103)

    assert "נמצאו 103" in message
    assert "חשבונית #" not in message
    assert "צמצם" in message or "לצמצם" in message


# --- format_original_not_linked_to_client (feature 027, Group B refusal — REQ-INV-013) ---


def test_format_original_not_linked_to_client_is_a_friendly_non_empty_message():
    message = format_original_not_linked_to_client()

    assert isinstance(message, str)
    assert message  # non-empty


def test_format_original_not_linked_to_client_does_not_imply_a_fix_exists():
    """Constitution §X shape ('[what happened]. [what to do next].') - but
    this feature deliberately offers no remediation path (spec.md
    Clarifications 2026-08-06), so the message must not promise one."""
    message = format_original_not_linked_to_client()

    assert "נסה שוב" not in message  # "try again" - would falsely imply retrying helps
    assert "לקוח" in message  # mentions the actual problem (client linkage), not a generic error
