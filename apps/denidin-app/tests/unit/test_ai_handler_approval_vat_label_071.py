"""bugfix-071 F9: the approval's VAT line follows the per-document-type VAT rule.

Only a 305/300 can be "not stated". A 320/standalone 400 records money already
paid (VAT inside it); a 400 against a 305, a 320 closing a 300 and a 330 take
their VAT from the original. An explicit "not included" is shown as-is.
"""
import json

import pytest

from src.handlers.ai_handler import _build_pending_approval_details

INCLUDED = "כולל מע״מ"
NOT_INCLUDED = "לא כולל מע״מ"
NOT_STATED = "(לא צוין — יש להבהיר לפני ההפקה)"
FROM_ORIGINAL = "לפי המסמך המקורי"
ORIGINAL = {"original_internal_morning_id": "abc-123"}


@pytest.mark.parametrize("tool_name, args, expected", [
    ("create_invoice", {}, NOT_STATED),
    ("create_invoice", {"vat_included": True}, INCLUDED),
    ("create_invoice", {"vat_included": False}, NOT_INCLUDED),
    ("create_transaction_account", {}, NOT_STATED),
    ("create_transaction_account", {"vat_included": True}, INCLUDED),
    ("create_transaction_account", {"vat_included": False}, NOT_INCLUDED),
    ("create_combo_document", {}, INCLUDED),
    ("create_combo_document", {"vat_included": True}, INCLUDED),
    ("create_combo_document", {"vat_included": False}, NOT_INCLUDED),
    ("create_receipt", {}, INCLUDED),
    ("create_receipt", {"vat_included": True}, INCLUDED),
    ("create_receipt", {"vat_included": False}, NOT_INCLUDED),
    ("create_receipt", dict(ORIGINAL), FROM_ORIGINAL),
    ("create_receipt", {**ORIGINAL, "vat_included": True}, FROM_ORIGINAL),
    ("create_receipt", {**ORIGINAL, "vat_included": False}, NOT_INCLUDED),
    ("create_combo_document_as_reference", dict(ORIGINAL), FROM_ORIGINAL),
    ("create_combo_document_as_reference", {**ORIGINAL, "vat_included": True}, FROM_ORIGINAL),
    ("create_combo_document_as_reference", {**ORIGINAL, "vat_included": False}, NOT_INCLUDED),
    ("create_credit_note", dict(ORIGINAL), FROM_ORIGINAL),
    ("create_credit_note", {**ORIGINAL, "vat_included": True}, FROM_ORIGINAL),
    ("create_credit_note", {**ORIGINAL, "vat_included": False}, NOT_INCLUDED),
])
def test_approval_vat_line_follows_the_document_type_rule(tool_name, args, expected):
    args = {"client_name": "לקוח", "amount": 100, "description": "ייעוץ", **args}
    details = _build_pending_approval_details(tool_name, json.dumps(args))
    vat_lines = [line for line in details.splitlines() if line.startswith("מע״מ:")]
    assert vat_lines == [f"מע״מ: {expected}"], details
