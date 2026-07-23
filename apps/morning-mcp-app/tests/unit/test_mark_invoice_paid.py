"""Tests for spec 020: _mark_invoice_paid must issue the correct closing
document type based on the original document's own `type` — a type-320
combo document for type-300 originals ("חשבון עסקה"), the existing type-400
receipt for type-305 originals ("חשבונית מס"), and a clear error for any
other type rather than guessing an unverified mapping.

Root cause this fixes: bugfix-014's Flow 4 finding that the prior code
unconditionally built a type-400 receipt regardless of the original's type,
which would create the WRONG document for a type-300 original.

Uses a fake MorningClient (dependency-injected, matching the real
get_invoice/create_invoice contract) - this is mocking a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
from denidin_mcp_morning.tools import _mark_invoice_paid


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
    mapping - status as an int code, per models._MORNING_STATUS_CODES)."""
    return {
        "id": doc_id,
        "number": number or doc_id,
        "type": doc_type,
        "client": {"name": "לקוח בדיקה"},
        "amount": total,
        "total": total,
        "status": status_code,  # 0 = unpaid, 1 = closed/paid
        "documentDate": "2026-07-10",
        "dueDate": "2026-07-31",
    }


def test_type_305_still_issues_a_type_400_receipt():
    """Regression: existing tax-invoice behavior must stay unchanged."""
    original = _raw_invoice("inv-305", doc_type=305, status_code=0)
    client = _FakeMorningClient(original)

    _mark_invoice_paid(client, "inv-305")

    assert len(client.create_invoice_calls) == 1
    payload = client.create_invoice_calls[0]
    assert payload["type"] == 400
    assert payload["linkedDocumentIds"] == ["inv-305"]


def test_type_300_issues_a_type_320_combo_document_not_a_receipt():
    """The bugfix-014 Flow 4 fix: a type-300 original must be closed by a
    type-320 combo document, never the type-400 receipt used for type-305."""
    original = _raw_invoice("inv-300", doc_type=300, status_code=0)
    client = _FakeMorningClient(original)

    _mark_invoice_paid(client, "inv-300")

    assert len(client.create_invoice_calls) == 1
    payload = client.create_invoice_calls[0]
    assert payload["type"] == 320, f"Expected a type-320 combo document, got: {payload!r}"
    assert payload["linkedDocumentIds"] == ["inv-300"]


def test_unsupported_original_type_raises_instead_of_guessing():
    """Per spec 020's clarification: only 300/305 are supported as original
    types; anything else must raise rather than silently defaulting to the
    (possibly wrong) type-400 receipt path."""
    original = _raw_invoice("inv-330", doc_type=330, status_code=0)
    client = _FakeMorningClient(original)

    try:
        _mark_invoice_paid(client, "inv-330")
        assert False, "Expected ValueError for unsupported original document type"
    except ValueError as exc:
        assert "330" in str(exc)
    assert client.create_invoice_calls == [], "No document should be created for an unsupported type"


def test_already_closed_type_300_is_idempotent_no_op():
    """The idempotency check (_CLOSED_STATUS_CODES) must short-circuit before
    the type-based branch fires, for type-300 same as type-305."""
    original = _raw_invoice("inv-300-paid", doc_type=300, status_code=1)
    client = _FakeMorningClient(original)

    _mark_invoice_paid(client, "inv-300-paid")

    assert client.create_invoice_calls == [], "Already-closed invoice must not trigger a new closing document"


def test_already_closed_type_305_is_idempotent_no_op():
    original = _raw_invoice("inv-305-paid", doc_type=305, status_code=2)
    client = _FakeMorningClient(original)

    _mark_invoice_paid(client, "inv-305-paid")

    assert client.create_invoice_calls == [], "Already-closed invoice must not trigger a new closing document"
