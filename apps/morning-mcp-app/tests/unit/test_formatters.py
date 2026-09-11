"""Tests for denidin_mcp_morning.formatters — ₪/VAT/date value helpers and
the JSON response shapes every MCP tool returns (2026-09-04 JSON-only
contract - see the module's own docstring for the full rationale: every
tool now returns machine-readable JSON, unconditionally, with no more
`format`/`output_format` parameter and no more Hebrew-prose default).

Real objects, no mocking.
"""
import json
from datetime import date

import pytest

from denidin_mcp_morning.formatters import (
    format_ambiguous_clients_message,
    format_client_details,
    format_client_list,
    format_client_name_confirmation_question,
    format_client_name_resolved,
    format_client_not_found,
    format_currency_ils,
    format_date_il,
    format_invoice_json,
    format_invoice_list_json,
    format_name_not_resolved,
    format_original_not_linked_to_client,
    format_too_many_clients_message,
    format_too_many_invoices_message,
    format_transaction_account_cancelled,
    translate_document_type,
    translate_payment_type,
    translate_status,
)
from denidin_mcp_morning.models import Client, Invoice

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


# ============================================================================
# bugfix-014: document type / payment type translation
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


# ============================================================================
# format_invoice_json / format_invoice_list_json (Feature 025 Phase 9,
# unconditional as of the 2026-09-04 JSON-only contract)
#
# Rationale (see specs/.../proposal-full-document-capture.md): a Hebrew
# prose format is lossy and ambiguous for a machine consumer - "סכום:
# ₪51.92" hides whether VAT is included, "18:52" has dropped the seconds,
# and an absent field is simply not printed, so the model cannot tell "no
# VAT" from "VAT not shown" and guesses (this is what produced a fabricated
# 00:00 timestamp in a real live run). JSON carries native types and
# explicit nulls, and - as of 2026-09-04 - is the ONLY shape every tool
# returns; composing the Hebrew, bullet-style reply is entirely the calling
# model's job now.
# ============================================================================


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
    """A prose format would drop seconds; ISO-8601 keeps them."""
    doc = _json_doc()

    assert doc["creation_date"].startswith("2026-08-20T18:52:48")


def test_json_states_absent_fields_explicitly_as_null():
    """The decisive property vs prose: a missing field is VISIBLE as null,
    so the model never has to guess whether it was absent or just not shown."""
    doc = _json_doc()

    assert "payment" in doc
    assert doc["payment"] is None


def test_json_separates_vat_inclusive_and_exclusive_amounts():
    """'סכום: ₪51.92' alone would be ambiguous about VAT; JSON is not."""
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
    """The internal id is present so the calling model can use it in
    follow-up tool calls - but must NEVER be shown to the operator
    (runtime_constitution.md); display_number is the only human-visible
    label."""
    doc = _json_doc()

    assert doc["display_number"] == "INV-2026-001"
    assert doc["internal_morning_id"] == "5f2c1a2b-0000-4c11-9a1a-abcdef123456"


def test_json_carries_translated_document_type_name():
    doc = _json_doc(type=305)

    assert doc["type"] == 305
    assert doc["type_name"] == "חשבונית מס"


def test_json_carries_description_and_client_name():
    doc = _json_doc(description="תחזוקה")

    assert doc["description"] == "תחזוקה"
    assert doc["client_name"] == "Tech Corp"


def test_json_description_is_null_when_absent():
    doc = _json_doc(description=None)

    assert doc["description"] is None


def test_json_payment_block_carries_structured_bank_fields():
    payment = {
        "id": "c4c52171", "date": "2026-07-12", "type": 4, "price": 1500,
        "bankName": "31", "bankBranch": "109", "bankAccount": "105542585",
        "name": "העברה בנקאית", "description": "בנק 31 / סניף 109", "amount": 1500,
    }
    doc = _json_doc(payment=[payment])

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


def test_format_invoice_list_json_states_total_matched_and_shown():
    invoices = [Invoice.model_validate(dict(REAL_DOCUMENT_RESPONSE_SAMPLE, number=n))
                for n in ("A700", "A800", "A900")]

    payload = json.loads(format_invoice_list_json(invoices, total_matched=3))

    assert payload["total_matched"] == 3
    assert payload["shown"] == 3
    assert [d["display_number"] for d in payload["documents"]] == ["A700", "A800", "A900"]


def test_format_invoice_list_json_empty_list_is_valid():
    payload = json.loads(format_invoice_list_json([], total_matched=0))

    assert payload["total_matched"] == 0
    assert payload["documents"] == []


def test_format_too_many_invoices_message_is_json_with_real_total():
    payload = json.loads(format_too_many_invoices_message(103))

    assert payload["status"] == "too_many"
    assert payload["total"] == 103
    assert payload["kind"] == "invoices"


def test_format_too_many_clients_message_is_json_with_real_total():
    payload = json.loads(format_too_many_clients_message(50))

    assert payload["status"] == "too_many"
    assert payload["total"] == 50
    assert payload["kind"] == "clients"


# --- format_original_not_linked_to_client (feature 027, Group B refusal — REQ-INV-013) ---


def test_format_original_not_linked_to_client_is_error_json():
    payload = json.loads(format_original_not_linked_to_client())

    assert payload["status"] == "error"
    assert payload["reason"] == "original_not_linked_to_client"


# --- format_client_name_resolved / format_name_not_resolved (client-name-resolution architecture fix) ---


def test_format_client_name_resolved_carries_the_exact_name():
    """The model must be able to copy this name verbatim into its next tool
    call together with name_resolved=True."""
    payload = json.loads(format_client_name_resolved("כרמלי דודי"))

    assert payload["status"] == "resolved"
    assert payload["name"] == "כרמלי דודי"


def test_format_client_name_confirmation_question_carries_the_candidate_name():
    payload = json.loads(format_client_name_confirmation_question("כרמלי דודי"))

    assert payload["status"] == "needs_confirmation"
    assert payload["candidate_name"] == "כרמלי דודי"


def test_format_name_not_resolved_names_the_resolution_tool():
    """A procedural instruction for the CALLING MODEL to act on immediately
    (call resolve_client_name, then retry) - not a domain question for the
    end user, so it must name the tool to call, not just say something
    vague like "try again"."""
    payload = json.loads(format_name_not_resolved())

    assert payload["status"] == "error"
    assert "resolve_client_name" in payload["instruction"]
    assert "name_resolved" in payload["instruction"]


# --- client tools (REQ-CLIENT-018: internal client_id must never appear) ---


_SAMPLE_CLIENT = Client(name="כרמלי דודי", email="dudi@example.com", phone="0501234567", tax_id="123456789")


def test_client_dict_never_carries_client_id():
    payload = json.loads(format_client_details(_SAMPLE_CLIENT))

    assert "id" not in payload["client"]
    assert "client_id" not in json.dumps(payload).lower()


def test_format_client_list_states_count_and_clients():
    payload = json.loads(format_client_list([_SAMPLE_CLIENT]))

    assert payload["count"] == 1
    assert payload["clients"][0]["name"] == "כרמלי דודי"


def test_format_client_not_found_is_json():
    payload = json.loads(format_client_not_found())

    assert payload["found"] is False


def test_format_ambiguous_clients_message_lists_candidates_without_ids():
    payload = json.loads(format_ambiguous_clients_message([_SAMPLE_CLIENT]))

    assert payload["status"] == "ambiguous"
    assert payload["candidates"][0]["name"] == "כרמלי דודי"
    assert "id" not in payload["candidates"][0]


# --- format_transaction_account_cancelled (Feature 056, REQ-INV-026) ---


def test_format_transaction_account_cancelled_never_says_paid():
    """Feature 056 (REQ-INV-026): Morning's manually-closed status (2) would
    otherwise be misread as "paid" - confirmed live (research.md) to be
    misleading for a cancellation where no money moved. This dedicated
    formatter must never say so, and must still name the account and client."""
    document = {
        "id": "txn-1",
        "number": 40371,
        "type": 300,
        "status": 2,
        "client": {"id": "client-1", "name": "לקוח בדיקה"},
    }

    payload = json.loads(format_transaction_account_cancelled(document))

    assert payload["status"] == "cancelled"
    assert payload["display_number"] == 40371
    assert payload["client_name"] == "לקוח בדיקה"


def test_format_transaction_account_cancelled_omits_missing_client_name():
    """No client name in the document shouldn't crash or leave a stray
    value - same defensive shape as other formatters in this file."""
    document = {"id": "txn-2", "number": 40372, "type": 300, "status": 2}

    payload = json.loads(format_transaction_account_cancelled(document))

    assert payload["display_number"] == 40372
    assert payload["client_name"] is None
