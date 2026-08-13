"""Unit tests for bugfix-038: Group B document approvals (create_receipt/
create_credit_note/create_combo_document_as_reference) must show the referenced
document's own real data (client name, document date, amount at minimum),
never a blank/placeholder Part 1.

Design confirmed live with the user 2026-08-13: Group B MCP tool signatures
stay thin (no new display-only params). Instead, `_build_pending_approval_
details` correlates the pending call's `original_internal_morning_id` against a
`get_invoice_details` call already executed earlier in the SAME turn
(passed in as `mcp_calls`) and renders that call's real output as Part 1,
minus its internal-id line (never shown to users).

Pure functions, no I/O - no mocking concerns (CONSTITUTION §I/§V only
restricts mocking internal components, not testing a pure helper directly).
See tests/billed/test_group_b_reference_approval_billed.py for the paid,
real-API companion coverage of this same behavior end-to-end.
"""
import json

import pytest

from src.handlers.ai_handler import (
    _build_pending_approval_details,
    _find_referenced_document_details,
    _strip_internal_morning_id_line,
)

_INVOICE_ID = "ac538347-7cc8-4221-b070-8d70ff348710"
_OTHER_INVOICE_ID = "11111111-2222-3333-4444-555555555555"

# A realistic get_invoice_details real output shape (mirrors
# morning-mcp-app's format_invoice_details/format_invoice_confirmation).
_REAL_INVOICE_DETAILS_OUTPUT = (
    "חשבונית #52077\n"
    'לקוח: "צפניה עוז"\n'
    "סכום: ₪19.00\n"
    "סוג מסמך: חשבונית מס\n"
    "סטטוס: לא שולם\n"
    "תאריך הפקה: 13/08/2026\n"
    f"מזהה פנימי (internal_morning_id): {_INVOICE_ID}"
)


def _get_invoice_details_call(internal_morning_id: str, output: str = _REAL_INVOICE_DETAILS_OUTPUT) -> dict:
    return {
        "name": "get_invoice_details",
        "error": None,
        "arguments": json.dumps({"internal_morning_id": internal_morning_id}),
        "output": output,
    }


# ---------------------------------------------------------------------------
# _strip_internal_morning_id_line
# ---------------------------------------------------------------------------

def test_strip_internal_morning_id_line_removes_only_that_line():
    result = _strip_internal_morning_id_line(_REAL_INVOICE_DETAILS_OUTPUT)

    assert _INVOICE_ID not in result
    assert "מזהה פנימי" not in result
    assert 'לקוח: "צפניה עוז"' in result
    assert "סכום: ₪19.00" in result
    assert "תאריך הפקה: 13/08/2026" in result


def test_strip_internal_morning_id_line_handles_text_without_the_line():
    text = 'לקוח: "צפניה עוז"\nסכום: ₪19.00'
    assert _strip_internal_morning_id_line(text) == text


# ---------------------------------------------------------------------------
# _find_referenced_document_details
# ---------------------------------------------------------------------------

def test_find_referenced_document_details_matches_on_internal_morning_id():
    mcp_calls = [_get_invoice_details_call(_INVOICE_ID)]

    result = _find_referenced_document_details(_INVOICE_ID, mcp_calls)

    assert result == _REAL_INVOICE_DETAILS_OUTPUT


def test_find_referenced_document_details_ignores_mismatched_internal_morning_id():
    mcp_calls = [_get_invoice_details_call(_OTHER_INVOICE_ID)]

    assert _find_referenced_document_details(_INVOICE_ID, mcp_calls) is None


def test_find_referenced_document_details_ignores_other_tool_calls():
    mcp_calls = [
        {"name": "list_invoices", "error": None, "arguments": "{}", "output": "some list"},
        {"name": "create_receipt", "error": None,
         "arguments": json.dumps({"original_internal_morning_id": _INVOICE_ID}), "output": "created"},
    ]

    assert _find_referenced_document_details(_INVOICE_ID, mcp_calls) is None


def test_find_referenced_document_details_returns_none_for_empty_calls():
    assert _find_referenced_document_details(_INVOICE_ID, []) is None


def test_find_referenced_document_details_returns_none_for_no_internal_morning_id():
    mcp_calls = [_get_invoice_details_call(_INVOICE_ID)]
    assert _find_referenced_document_details(None, mcp_calls) is None
    assert _find_referenced_document_details("", mcp_calls) is None


def test_find_referenced_document_details_never_raises_on_malformed_arguments():
    mcp_calls = [{
        "name": "get_invoice_details", "error": None,
        "arguments": "{not valid json", "output": _REAL_INVOICE_DETAILS_OUTPUT,
    }]

    assert _find_referenced_document_details(_INVOICE_ID, mcp_calls) is None


def test_find_referenced_document_details_returns_none_when_output_missing():
    """A get_invoice_details call that errored (output empty/None) must never
    be treated as a usable reference, even if its arguments match."""
    mcp_calls = [{
        "name": "get_invoice_details", "error": "not found",
        "arguments": json.dumps({"internal_morning_id": _INVOICE_ID}), "output": None,
    }]

    assert _find_referenced_document_details(_INVOICE_ID, mcp_calls) is None


def test_find_referenced_document_details_picks_the_matching_call_among_several():
    mcp_calls = [
        _get_invoice_details_call(_OTHER_INVOICE_ID, output="wrong document"),
        _get_invoice_details_call(_INVOICE_ID, output=_REAL_INVOICE_DETAILS_OUTPUT),
    ]

    assert _find_referenced_document_details(_INVOICE_ID, mcp_calls) == _REAL_INVOICE_DETAILS_OUTPUT


# ---------------------------------------------------------------------------
# _build_pending_approval_details - the bugfix-038 core behavior
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name,extra_args", [
    ("create_receipt", {"payment_date": "2026-08-13"}),
    ("create_credit_note", {}),
    ("create_combo_document_as_reference", {"vat_included": True}),
])
def test_group_b_tools_render_reference_block_when_lookup_present(tool_name, extra_args):
    """The core bugfix-038 assertion, for all three Group B tools: given a
    same-turn get_invoice_details call matching original_internal_morning_id, the
    approval's Part 1 must carry the reference document's real client name,
    date, and amount - the user's own bare-minimum list (2026-08-13)."""
    args = json.dumps({"original_internal_morning_id": _INVOICE_ID, **extra_args})
    mcp_calls = [_get_invoice_details_call(_INVOICE_ID)]

    result = _build_pending_approval_details(tool_name, args, mcp_calls)

    assert "📄 המסמך המקושר:" in result
    assert "צפניה עוז" in result
    assert "19.00" in result
    assert "13/08/2026" in result
    assert _INVOICE_ID not in result, "the internal Morning id must never reach the user"
    assert result.endswith("אישור — כן/לא?")


@pytest.mark.parametrize("tool_name", ["create_receipt", "create_credit_note", "create_combo_document_as_reference"])
def test_group_b_tools_omit_reference_block_when_no_lookup_found(tool_name):
    """Accepted risk (user, 2026-08-13): if the model didn't look up the
    original in this same turn, there is nothing to correlate against - the
    approval falls back to today's behavior (no reference block, no crash),
    never a fabricated or stale value."""
    args = json.dumps({"original_internal_morning_id": _INVOICE_ID})

    result = _build_pending_approval_details(tool_name, args, mcp_calls=None)

    assert "📄 המסמך המקושר:" not in result
    assert "(מהמסמך המקושר)" in result  # existing Part-2 placeholder, unchanged


@pytest.mark.parametrize("tool_name", ["create_receipt", "create_credit_note", "create_combo_document_as_reference"])
def test_group_b_tools_omit_reference_block_on_mismatched_lookup(tool_name):
    args = json.dumps({"original_internal_morning_id": _INVOICE_ID})
    mcp_calls = [_get_invoice_details_call(_OTHER_INVOICE_ID)]

    result = _build_pending_approval_details(tool_name, args, mcp_calls)

    assert "📄 המסמך המקושר:" not in result


def test_group_a_tools_are_unaffected_by_mcp_calls():
    """Regression guard: create_invoice/create_transaction_account/
    create_combo_document never reference an existing document, so passing
    mcp_calls must be a strict no-op for them - identical output with or
    without it."""
    args = json.dumps({"client_name": "דנה כהן", "amount": 500, "description": "ייעוץ"})
    mcp_calls = [_get_invoice_details_call(_INVOICE_ID)]

    with_calls = _build_pending_approval_details("create_invoice", args, mcp_calls)
    without_calls = _build_pending_approval_details("create_invoice", args, mcp_calls=None)

    assert with_calls == without_calls
    assert "📄 המסמך המקושר:" not in with_calls


def test_reference_block_precedes_the_request_details_block():
    """Part 1 (reference data) must come before Part 2 (the request being
    approved) - user's own ordering (2026-08-13: "part 1 the ref data ...
    and part 2 what we are doing")."""
    args = json.dumps({"original_internal_morning_id": _INVOICE_ID, "payment_date": "2026-08-13"})
    mcp_calls = [_get_invoice_details_call(_INVOICE_ID)]

    result = _build_pending_approval_details("create_receipt", args, mcp_calls)

    assert result.index("📄 המסמך המקושר:") < result.index("📋 לאישור:")


def test_default_mcp_calls_parameter_is_optional_backward_compatible():
    """Every existing call site that doesn't yet pass mcp_calls (if any)
    must keep working exactly as before this bugfix."""
    args = json.dumps({"original_internal_morning_id": _INVOICE_ID})
    result = _build_pending_approval_details("create_receipt", args)
    assert "📄 המסמך המקושר:" not in result
