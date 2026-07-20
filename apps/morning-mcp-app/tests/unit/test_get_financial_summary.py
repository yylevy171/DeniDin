"""Regression test for bugfix-012: get_financial_summary silently drops real
invoices whose Morning `type` isn't in the tool's own primary-invoice
allowlist ({305, 320}), while list_invoices (no such filter) shows them fine.

Confirmed live in production (2026-07-20): a real unpaid invoice (issued
10/07/2026) was correctly returned by list_invoices(status="unpaid") but
absent from get_financial_summary's totals for the identical date range -
user manually confirmed via the Morning dashboard that the invoice is
genuinely still unpaid, ruling out a timing/data-change explanation.

Uses a fake MorningClient (dependency-injected, matching the real
list_invoices(params) -> list[dict] contract) - this is mocking a third-party
API boundary, not an internal component (CONSTITUTION.md SSI/SSV).
"""
from denidin_mcp_morning.tools import get_financial_summary


class _FakeMorningClient:
    """Stands in for MorningClient.list_invoices - the real network boundary."""

    def __init__(self, items):
        self._items = items

    def list_invoices(self, params=None):
        return self._items


def _raw_invoice(doc_id, doc_type, status_code, amount, client_name="לקוח בדיקה"):
    """A Morning /documents/search-shaped raw item (see models.py's Invoice
    mapping - documentDate/dueDate/client{} nesting, status as an int code)."""
    return {
        "id": doc_id,
        "number": doc_id,
        "type": doc_type,
        "client": {"name": client_name},
        "amount": amount,
        "total": amount,
        "status": status_code,  # 0 = unpaid, 1 = closed/paid (models._MORNING_STATUS_CODES)
        "documentDate": "2026-07-10",
        "dueDate": "2026-07-31",
    }


def test_unpaid_invoice_with_non_allowlisted_type_is_still_counted():
    """The real bug: an unpaid invoice of type 300 (a real Morning document
    type, just not 305/320) must still appear in the totals - the same way
    it already does in list_invoices, which applies no type filter at all."""
    client = _FakeMorningClient([
        _raw_invoice("paid-1", doc_type=305, status_code=1, amount=1000),
        _raw_invoice("unpaid-other-type", doc_type=300, status_code=0, amount=10620),
    ])

    result = get_financial_summary(client, period="custom", from_date="2026-07-01", to_date="2026-07-31")

    assert "מספר חשבוניות: 2 " in result, f"Expected both invoices counted, got: {result!r}"
    assert "10,620.00" in result, f"Unpaid invoice's amount missing from totals: {result!r}"
    assert "לא שולם: ₪10,620.00" in result, f"Unpaid total wrong/missing: {result!r}"


def test_credit_invoice_is_still_excluded_from_total_invoiced():
    """The one document type that SHOULD be excluded from total_invoiced -
    credit invoices (330) - must remain excluded after the fix (this is not
    the bug; only the over-broad allowlist for everything else is)."""
    client = _FakeMorningClient([
        _raw_invoice("paid-1", doc_type=305, status_code=1, amount=1000),
        _raw_invoice("credit-1", doc_type=330, status_code=1, amount=200),
    ])

    result = get_financial_summary(client, period="custom", from_date="2026-07-01", to_date="2026-07-31")

    assert "סה\"כ הופק: ₪800.00" in result, (
        f"Credit invoice amount should net out of total_invoiced (1000 - 200 = 800): {result!r}"
    )


def test_receipt_type_is_excluded_from_totals():
    """Non-billable document types (e.g. 400 = receipt) must stay excluded
    from the totals even after the allowlist is widened to a 300-399 billable
    range - a receipt documents money already received against another
    document, so counting it too would double-count that same money as two
    separate financial events. This guards against a future fix over-widening
    the range (or deleting the check outright, as the original bugfix-012
    draft briefly did) rather than confirming any bug present today."""
    client = _FakeMorningClient([
        _raw_invoice("paid-1", doc_type=305, status_code=1, amount=1000),
        _raw_invoice("receipt-1", doc_type=400, status_code=1, amount=1000),
    ])

    result = get_financial_summary(client, period="custom", from_date="2026-07-01", to_date="2026-07-31")

    assert "מספר חשבוניות: 1 " in result, f"Receipt must not be counted as its own invoice: {result!r}"
    assert "סה\"כ הופק: ₪1,000.00" in result, f"Receipt amount must not inflate total_invoiced: {result!r}"
