"""Unit tests for _build_pending_approval_fallback_text (2026-07-30 finding):
when the model produces no narrating text alongside a pending MCP approval,
the fallback message must be built from the pending approval's own
arguments (already containing everything needed, e.g. a resolved client
name) rather than a fully generic "there's a pending action" string.

Pure function, no I/O - no mocking concerns (CONSTITUTION §I/§V only
restricts mocking internal components, not testing a pure helper directly).
"""
import json

from src.handlers.ai_handler import _build_pending_approval_fallback_text


def test_create_invoice_names_client_amount_and_description():
    args = json.dumps({"client_name": "דנה כהן", "amount": 500, "description": "ייעוץ"})

    result = _build_pending_approval_fallback_text("create_invoice", args)

    assert "דנה כהן" in result
    assert "500" in result
    assert "ייעוץ" in result
    assert result.endswith("לאשר?")


def test_create_transaction_account_names_client_and_amount():
    args = json.dumps({"client_name": "משה לוי", "amount": 250, "description": "עבודה"})

    result = _build_pending_approval_fallback_text("create_transaction_account", args)

    assert "משה לוי" in result
    assert "250" in result


def test_create_combo_document_names_client_and_amount():
    args = json.dumps({"client_name": "רותם", "amount": 80, "description": "מוצר"})

    result = _build_pending_approval_fallback_text("create_combo_document", args)

    assert "רותם" in result
    assert "80" in result


def test_add_client_names_the_new_client_details():
    args = json.dumps({"name": "אביתר כהן", "email": "avi@example.com", "phone": "050-1234567"})

    result = _build_pending_approval_fallback_text("add_client", args)

    assert "אביתר כהן" in result
    assert "avi@example.com" in result
    assert "050-1234567" in result


def test_update_client_names_the_resolved_client():
    args = json.dumps({"name": "מוניר קרילווביץ'", "phone": "052-9876543"})

    result = _build_pending_approval_fallback_text("update_client", args)

    assert "מוניר קרילווביץ'" in result


def test_update_client_prefers_new_name_when_renaming():
    args = json.dumps({"name": "שם ישן", "new_name": "שם חדש"})

    result = _build_pending_approval_fallback_text("update_client", args)

    assert "שם חדש" in result


def test_create_credit_note_never_includes_the_raw_internal_morning_id():
    """original_internal_morning_id is an internal UUID - constitution rule "never
    ask for or mention internal_morning_id" applies here too."""
    args = json.dumps({"original_internal_morning_id": "e206dc08-a492-4279-80cf-1f098a3cf607", "amount": 100})

    result = _build_pending_approval_fallback_text("create_credit_note", args)

    assert "e206dc08-a492-4279-80cf-1f098a3cf607" not in result
    assert "100" in result
    assert result.endswith("לאשר?")


def test_create_receipt_never_includes_the_raw_internal_morning_id():
    args = json.dumps({"original_internal_morning_id": "e206dc08-a492-4279-80cf-1f098a3cf607"})

    result = _build_pending_approval_fallback_text("create_receipt", args)

    assert "e206dc08-a492-4279-80cf-1f098a3cf607" not in result
    assert result.endswith("לאשר?")


def test_cancel_transaction_account_never_includes_the_raw_internal_morning_id():
    """Feature 056 (found via manual QA, 2026-08-20): cancel_transaction_account
    had no branch here at all, so it fell all the way through to the fully
    generic 'there's a pending action' text - not even naming the action,
    let alone the account. Must name the action specifically (never a blank
    generic), and never leak the raw internal id."""
    args = json.dumps({"original_internal_morning_id": "e206dc08-a492-4279-80cf-1f098a3cf607"})

    result = _build_pending_approval_fallback_text("cancel_transaction_account", args)

    assert "e206dc08-a492-4279-80cf-1f098a3cf607" not in result
    assert "יש פעולה הממתינה לאישורך" not in result, "must not fall back to the fully generic text"
    assert "לבטל" in result or "ביטול" in result, "must name the action as a cancellation"
    assert "עסקה" in result
    assert result.endswith("לאשר?")


def test_create_combo_document_as_reference_never_includes_the_raw_internal_morning_id():
    args = json.dumps({"original_internal_morning_id": "e206dc08-a492-4279-80cf-1f098a3cf607", "amount": 300})

    result = _build_pending_approval_fallback_text("create_combo_document_as_reference", args)

    assert "e206dc08-a492-4279-80cf-1f098a3cf607" not in result
    assert "300" in result


def test_unrecognized_tool_name_falls_back_to_generic_text():
    result = _build_pending_approval_fallback_text("some_future_tool", json.dumps({"foo": "bar"}))

    assert "יש פעולה הממתינה לאישורך" in result


def test_malformed_json_falls_back_to_generic_text():
    result = _build_pending_approval_fallback_text("update_client", "{not valid json")

    assert "יש פעולה הממתינה לאישורך" in result


def test_missing_expected_field_falls_back_to_generic_text():
    """create_invoice's message needs client_name/description - if either is
    missing, don't crash or produce a broken sentence, use the safe generic."""
    result = _build_pending_approval_fallback_text("create_invoice", json.dumps({"amount": 100}))

    assert "יש פעולה הממתינה לאישורך" in result


def test_non_dict_json_falls_back_to_generic_text():
    result = _build_pending_approval_fallback_text("update_client", json.dumps(["not", "a", "dict"]))

    assert "יש פעולה הממתינה לאישורך" in result


def test_empty_arguments_falls_back_to_generic_text():
    result = _build_pending_approval_fallback_text("update_client", "")

    assert "יש פעולה הממתינה לאישורך" in result
