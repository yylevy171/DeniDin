"""Tests for denidin_mcp_morning.formatters — Hebrew/₪/VAT/date formatting.

Real objects, no mocking. Covers T005 from
specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
"""
import json
from datetime import date

import pytest

from denidin_mcp_morning.formatters import (
    format_client_name_resolved,
    format_currency_ils,
    format_date_il,
    format_invoice_confirmation,
    format_invoice_details,
    format_invoice_json,
    format_invoice_list,
    format_name_not_resolved,
    format_original_not_linked_to_client,
    format_too_many_invoices_message,
    format_transaction_account_cancelled,
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


def test_format_invoice_confirmation_includes_creation_timestamp():
    """denidin-app's Feature 025 (2026-08-22): the creation timestamp must be
    visible in the SHARED per-invoice block - which means list_invoices'
    output carries it too, not just get_invoice_details'. Root cause of the
    original failure: /documents/search already returns creationDate for
    every document, but the formatter dropped it, so the reconciliation
    sweep's model never saw a real creation time from list_invoices and had
    to be told to make N extra get_invoice_details calls to recover data the
    first call already had."""
    with_creation = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168)
    invoice = Invoice.model_validate(with_creation)

    message = format_invoice_confirmation(invoice)

    assert "נוצר ב" in message
    assert "20/08/2026" in message
    assert "18:52" in message


def test_format_invoice_confirmation_omits_creation_line_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert "נוצר ב" not in format_invoice_confirmation(invoice)


def test_format_invoice_confirmation_includes_description():
    """Same root cause as the creation timestamp: Morning returns a top-level
    description that was never mapped or rendered, so every reconciliation
    capture had description=null."""
    with_description = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, description="תחזוקה")
    invoice = Invoice.model_validate(with_description)

    message = format_invoice_confirmation(invoice)

    assert "תחזוקה" in message


def test_format_invoice_confirmation_omits_description_line_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert "תיאור" not in format_invoice_confirmation(invoice)


def test_format_invoice_list_items_carry_creation_timestamp_and_description():
    """The decisive one for Feature 025: a single list_invoices call must be
    sufficient on its own - every ledger field the reconciliation sweep needs
    (display number, type, status, real creation time, amount, description)
    present per item, so no get_invoice_details chaining is required at all."""
    raw = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168, description="תחזוקה")
    invoice = Invoice.model_validate(raw)

    message = format_invoice_list([invoice], total_matched=1)

    assert "INV-2026-001" in message      # display number
    assert "נוצר ב" in message and "18:52" in message  # real creation time
    assert "תחזוקה" in message            # description
    assert "₪5,850.00" in message         # amount


def test_format_invoice_details_does_not_duplicate_the_creation_line():
    """format_invoice_details embeds format_invoice_confirmation's block,
    which now carries the creation timestamp itself - it must not print a
    second one."""
    with_creation = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168)
    invoice = Invoice.model_validate(with_creation)

    message = format_invoice_details(invoice)

    assert message.count("נוצר ב") == 1


def test_format_invoice_details_includes_creation_timestamp_with_full_precision():
    """denidin-app's Feature 025 (Morning-Sourced Ledger Events), T004a: the
    real creationDate field carries full HH:MM precision (live-confirmed
    2026-08-21: 1787241168 -> 2026-08-20 18:52:48 Israel local) - the
    reconciliation sweep's OpenAI+MCP call needs this in get_invoice_details'
    own text output to populate accounting_document_creation_date accurately,
    since that's the only channel this tool exposes data through (a Hebrew
    formatted string, not structured JSON)."""
    with_creation = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168)
    invoice = Invoice.model_validate(with_creation)

    message = format_invoice_details(invoice)

    assert "20/08/2026" in message
    assert "18:52" in message


def test_format_invoice_details_omits_creation_timestamp_line_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    message = format_invoice_details(invoice)

    assert "נוצר" not in message


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


# --- format_client_name_resolved / format_name_not_resolved (client-name-resolution architecture fix) ---


def test_format_client_name_resolved_contains_the_exact_name_quoted():
    """The model must be able to copy this name verbatim into its next tool
    call together with name_resolved=True - quoted, matching the existing
    convention (format_invoice_confirmation's 'לקוח: "..."') so the name
    reads as one atomic, copyable token."""
    message = format_client_name_resolved("כרמלי דודי")

    assert '"כרמלי דודי"' in message


def test_format_client_name_resolved_never_mentions_a_client_id():
    """REQ-CLIENT-018 (feature 026): the internal Morning client_id must
    never reach the model, in any tool's return value."""
    message = format_client_name_resolved("כרמלי דודי")

    assert "client_id" not in message.lower()
    assert "id" not in message.lower().split()  # no bare "id" token


def test_format_name_not_resolved_names_the_resolution_tool():
    """A procedural instruction for the CALLING MODEL to act on immediately
    (call resolve_client_name, then retry) - not a domain question for the
    end user, so it must name the tool to call, not just say something
    vague like "try again"."""
    message = format_name_not_resolved()

    assert "resolve_client_name" in message
    assert "name_resolved" in message


# ============================================================================
# Feature 025 Phase 9: machine-readable JSON output (format="json")
#
# Rationale (see specs/.../proposal-full-document-capture.md): the Hebrew prose
# format is lossy and ambiguous for a machine consumer - "סכום: ₪51.92" hides
# whether VAT is included, "18:52" has dropped the seconds, and an absent field
# is simply not printed, so the model cannot tell "no VAT" from "VAT not shown"
# and guesses (this is what produced a fabricated 00:00 timestamp in a real
# live run). JSON carries native types and explicit nulls.
#
# The prose path is the DEFAULT and stays byte-for-byte unchanged - only the
# reconciliation sweep opts in.
# ============================================================================

REAL_BANK_TRANSFER_PAYMENT_FX = {
    "id": "c4c52171", "date": "2026-07-12", "type": 4, "price": 1500,
    "bankName": "31", "bankBranch": "109", "bankAccount": "105542585",
    "name": "העברה בנקאית", "description": "בנק 31 / סניף 109", "amount": 1500,
}


def _json_doc(**overrides):
    base = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168,
                description="תחזוקה", status=1)
    base.update(overrides)
    return json.loads(format_invoice_json(Invoice.model_validate(base)))


def test_json_carries_native_types_not_formatted_strings():
    """The core reason for this format: amount is a number, not '₪5,850.00'."""
    doc = _json_doc()

    assert isinstance(doc["amount"], (int, float))
    assert not isinstance(doc["amount"], str)


def test_json_carries_full_precision_creation_timestamp():
    """The prose format drops seconds; ISO-8601 keeps them."""
    doc = _json_doc()

    assert doc["creation_date"].startswith("2026-08-20T18:52:48")


def test_json_states_absent_fields_explicitly_as_null():
    """The decisive property vs prose: a missing field is VISIBLE as null,
    so the model never has to guess whether it was absent or just not shown."""
    doc = _json_doc()

    assert "payment" in doc
    assert doc["payment"] is None


def test_json_separates_vat_inclusive_and_exclusive_amounts():
    """'סכום: ₪51.92' alone is ambiguous about VAT; JSON is not."""
    doc = _json_doc(amount=51.92, amountExcludeVat=44, vat=7.92, vatRate=0.18)

    assert doc["amount_excl_vat"] == 44
    assert doc["vat_amount"] == 7.92
    assert doc["vat_rate"] == 0.18


def test_json_carries_both_canonical_status_and_morning_literal_label():
    doc = _json_doc(status=1)

    assert doc["status"] == "paid"              # our canonical interpretation
    assert doc["status_label"] == "מסמך סגור"    # Morning's own words
    assert doc["status_code"] == 1


def test_json_carries_display_number_and_internal_id_separately():
    doc = _json_doc()

    assert doc["display_number"] == "INV-2026-001"
    assert doc["internal_morning_id"] == "5f2c1a2b-0000-4c11-9a1a-abcdef123456"


def test_json_carries_translated_document_type_name():
    doc = _json_doc(type=305)

    assert doc["type"] == 305
    assert doc["type_name"] == "חשבונית מס"


def test_json_payment_block_carries_structured_bank_fields():
    doc = _json_doc(payment=[REAL_BANK_TRANSFER_PAYMENT_FX])

    assert doc["payment"]["method"] == "העברה בנקאית"
    assert doc["payment"]["date"] == "2026-07-12"
    assert doc["payment"]["bank_number"] == "31"
    assert doc["payment"]["bank_branch"] == "109"
    assert doc["payment"]["bank_account"] == "105542585"


def test_json_linked_document_carries_number_and_hebrew_type_name():
    """morning-mcp-app owns the type table, so it translates here - denidin-app
    never needs one (user decision, 2026-08-23)."""
    doc = _json_doc(linkedDocuments=[{
        "id": "442a5f51", "type": 305, "number": 52203,
        "documentDate": "2026-08-20", "amount": 58, "currency": "ILS",
    }])

    assert doc["linked_document"]["number"] == "52203"
    assert doc["linked_document"]["type"] == 305
    assert doc["linked_document"]["type_name"] == "חשבונית מס"


def test_json_linked_document_is_null_when_absent():
    assert _json_doc()["linked_document"] is None


def test_format_transaction_account_cancelled_never_says_paid():
    """Feature 056 (REQ-INV-026): get_invoice_details' existing formatter
    renders Morning's manually-closed status (2) as "שולם" (paid) -
    confirmed live (research.md) to be misleading for a cancellation where
    no money moved. This dedicated formatter must never say so, and must
    still name the account and client."""
    document = {
        "id": "txn-1",
        "number": 40371,
        "type": 300,
        "status": 2,
        "client": {"id": "client-1", "name": "לקוח בדיקה"},
    }

    message = format_transaction_account_cancelled(document)

    assert "שולם" not in message
    assert "תשלום" not in message
    assert "40371" in message
    assert "לקוח בדיקה" in message


def test_format_transaction_account_cancelled_omits_missing_client_name():
    """No client name in the document shouldn't crash or leave a stray
    label - same defensive shape as other formatters in this file."""
    document = {"id": "txn-2", "number": 40372, "type": 300, "status": 2}

    message = format_transaction_account_cancelled(document)

    assert "40372" in message
    assert "שולם" not in message
