"""Tests for spec 020's original finding, now living directly on the tools
that replace `update_invoice_status` (removed, feature 023): the correct
closing document depends on the target's own `type` - a type-320 combo
document for type-300 originals ("חשבון עסקה"), the existing type-400
receipt for type-305 originals ("חשבונית מס") - and each tool defends its
own boundary (rejects the other's document type) rather than a central
dispatcher guessing from status-word phrasing.

Formerly these scenarios all ran through the single internal
`_mark_invoice_paid` helper behind `update_invoice_status(status="paid")`.
Feature 023 removed that indirection entirely: the model resolves the
target's real type itself (via get_invoice_details) and calls
`create_receipt` or `close_transaction_account` directly. This file still
covers the same root cause (bugfix-014's Flow 4: the prior code
unconditionally built a type-400 receipt regardless of the original's type)
and the same idempotency guarantee (no duplicate closing document on a
repeated "mark as paid"-style request) - just through the two direct tools
instead of the removed indirection.

Uses a fake MorningClient (dependency-injected, matching the real
get_invoice/create_invoice contract) - this is mocking a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
from datetime import timedelta

import pytest

from denidin_mcp_morning.tools import close_transaction_account, create_receipt
from denidin_mcp_morning.utils.time_utils import now_local


class _FakeMorningClient:
    """Stands in for MorningClient.get_invoice/create_invoice - the real
    network boundary."""

    def __init__(self, original, created_response=None):
        self._original = original
        self._created_response = created_response or {"id": "closing-doc-1", "number": "400-1"}
        self.create_invoice_calls = []

    def get_invoice(self, invoice_id):
        return self._original

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return self._created_response


def _raw_invoice(doc_id, doc_type, status_code, total=1000, number=None):
    """A Morning single-document-GET-shaped raw item (see models.py's Invoice
    mapping - status as an int code, per models._MORNING_STATUS_CODES).

    Feature 027 (REQ-INV-012): `client.id` is present, matching any document
    created on/after this feature (the "preserve" path) - this file isn't
    about client-attachment behavior at all, so it always uses the
    already-attached shape rather than exercising the refusal path (that's
    covered directly in test_tools_document_creation.py)."""
    return {
        "id": doc_id,
        "number": number or doc_id,
        "type": doc_type,
        "client": {"id": "client-1", "name": "לקוח בדיקה"},
        "amount": total,
        "total": total,
        "status": status_code,  # 0 = unpaid, 1 = closed/paid
        "documentDate": "2026-07-10",
        "dueDate": "2026-07-31",
    }


def test_type_305_still_issues_a_type_400_receipt():
    """Regression: existing tax-invoice behavior must stay unchanged, now
    reached via create_receipt directly instead of update_invoice_status."""
    original = _raw_invoice("inv-305", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)

    create_receipt(client, "inv-305", payment_date="2026-07-12")

    assert len(client.create_invoice_calls) == 1
    payload = client.create_invoice_calls[0]
    assert payload["type"] == 400
    assert payload["linkedDocumentIds"] == ["inv-305"]


def test_type_300_issues_a_type_320_combo_document_not_a_receipt():
    """The bugfix-014 Flow 4 fix: a type-300 original must be closed by a
    type-320 combo document, never the type-400 receipt used for type-305 -
    now reached via close_transaction_account directly."""
    original = _raw_invoice("inv-300", doc_type=300, status_code=0)
    client = _FakeMorningClient(original)

    close_transaction_account(client, "inv-300")

    assert len(client.create_invoice_calls) == 1
    payload = client.create_invoice_calls[0]
    assert payload["type"] == 320, f"Expected a type-320 combo document, got: {payload!r}"
    assert payload["linkedDocumentIds"] == ["inv-300"]


def test_create_receipt_rejects_a_transaction_account_original():
    """Per spec 020's original clarification (only 300/305 supported) and
    feature 023's per-tool guards: create_receipt must reject a type-300
    original rather than silently issuing the wrong document type - the
    caller should have used close_transaction_account instead."""
    original = _raw_invoice("inv-300b", doc_type=300, status_code=0)
    client = _FakeMorningClient(original)

    try:
        create_receipt(client, "inv-300b", payment_date="2026-07-12")
        assert False, "Expected ValueError for a type-300 original passed to create_receipt"
    except ValueError as exc:
        assert "300" in str(exc)
    assert client.create_invoice_calls == [], "No document should be created for a rejected original type"


def test_create_receipt_rejects_a_credit_note_original():
    """Broadened guard (feature 023): create_receipt only accepts a type-305
    original, matching the strict positive check the removed
    update_invoice_status used to provide for ANY unsupported original type
    (not just 300) - a type-330 credit note is itself a completed financial
    instrument, never something to issue a receipt against."""
    original = _raw_invoice("inv-330", doc_type=330, status_code=0)
    client = _FakeMorningClient(original)

    try:
        create_receipt(client, "inv-330", payment_date="2026-07-12")
        assert False, "Expected ValueError for a type-330 original passed to create_receipt"
    except ValueError as exc:
        assert "330" in str(exc)
    assert client.create_invoice_calls == [], "No document should be created for a rejected original type"


def test_close_transaction_account_rejects_a_tax_invoice_original():
    """Symmetric guard: close_transaction_account must reject a type-305
    original rather than guessing - the caller should have used
    create_receipt instead."""
    original = _raw_invoice("inv-305b", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)

    try:
        close_transaction_account(client, "inv-305b")
        assert False, "Expected ValueError for a type-305 original passed to close_transaction_account"
    except ValueError as exc:
        assert "305" in str(exc)
    assert client.create_invoice_calls == [], "No document should be created for a rejected original type"


def test_already_closed_type_300_is_idempotent_no_op():
    """The idempotency check must short-circuit before a new combo document
    is built, for a full-amount close_transaction_account call against an
    already-closed type-300 original - same guarantee update_invoice_status
    used to provide, now implemented directly in close_transaction_account
    since Morning itself does not reject a duplicate (verified live)."""
    original = _raw_invoice("inv-300-paid", doc_type=300, status_code=1)
    client = _FakeMorningClient(original)

    close_transaction_account(client, "inv-300-paid")

    assert client.create_invoice_calls == [], "Already-closed original must not trigger a new closing document"


def test_already_closed_type_305_is_idempotent_no_op():
    """Same idempotency guarantee for create_receipt against an
    already-closed type-305 original."""
    original = _raw_invoice("inv-305-paid", doc_type=305, status_code=2)
    client = _FakeMorningClient(original)

    create_receipt(client, "inv-305-paid", payment_date="2026-07-12")

    assert client.create_invoice_calls == [], "Already-closed original must not trigger a new receipt"


def test_partial_amount_close_transaction_account_ignores_idempotency_guard():
    """An explicit partial amount is a deliberate, repeatable action (e.g. a
    second partial payment) - it must NOT be silently no-op'd just because
    the original happens to already be marked closed from a prior payment."""
    original = _raw_invoice("inv-300-partial", doc_type=300, status_code=1)
    client = _FakeMorningClient(original)

    close_transaction_account(client, "inv-300-partial", amount=50.0)

    assert len(client.create_invoice_calls) == 1
    assert client.create_invoice_calls[0]["payment"][0]["price"] == 50.0


def test_partial_amount_create_receipt_ignores_idempotency_guard():
    """Same as above for create_receipt - a partial receipt request must
    always create a new receipt, regardless of current status."""
    original = _raw_invoice("inv-305-partial", doc_type=305, status_code=1)
    client = _FakeMorningClient(original)

    create_receipt(client, "inv-305-partial", payment_date="2026-07-12", amount=25.0)

    assert len(client.create_invoice_calls) == 1
    assert client.create_invoice_calls[0]["payment"][0]["price"] == 25.0


# -------------------------------------------------------------------- A3
# (2026-08-12): create_receipt's payment_date - mandatory, like
# create_combo_document/create_transaction_account's own A3 requirement, and
# validated by the same shared `_validate_payment_date` - never a silent
# "today". Unlike a bank-deposit screenshot, a verbal "mark as paid" request
# has no document to read a date from, so "today" is a genuinely likely real
# answer here - but only once the model has actually asked and the user
# confirmed it, never assumed.


@pytest.mark.parametrize(
    "bad_date",
    [None, "", "not-a-date", "2026-13-45"],
)
def test_create_receipt_refuses_a_missing_or_unusable_payment_date(bad_date):
    original = _raw_invoice("inv-305-nodate", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)

    with pytest.raises(ValueError):
        create_receipt(client, "inv-305-nodate", payment_date=bad_date)

    assert client.create_invoice_calls == [], "No receipt should be created without a real payment date"


def test_create_receipt_refuses_a_future_payment_date():
    original = _raw_invoice("inv-305-future", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)
    tomorrow = (now_local().date() + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError):
        create_receipt(client, "inv-305-future", payment_date=tomorrow)

    assert client.create_invoice_calls == [], "No receipt should be created for a future payment date"


def test_create_receipt_uses_the_given_payment_date_not_today():
    """The payment line must carry the REAL date given, not silently today -
    the document's own top-level issue date stays today regardless (a
    receipt can genuinely be issued today for a payment that arrived
    earlier), mirroring create_combo_document's same distinction."""
    original = _raw_invoice("inv-305-realdate", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)

    create_receipt(client, "inv-305-realdate", payment_date="2026-07-12")

    payload = client.create_invoice_calls[0]
    assert payload["payment"][0]["date"] == "2026-07-12"
    assert payload["date"] != "2026-07-12", "the document's own issue date should still be today"
