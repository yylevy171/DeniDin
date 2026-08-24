"""Tests for denidin_mcp_morning.models — Pydantic models over the real Morning shape.

Real objects, no mocking. Covers T004 from
specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
Sample shapes are drawn from the real Morning /documents payload used by the
existing passing sandbox test (tests/integration/test_morning_sandbox_invoices_crud.py).
"""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from denidin_mcp_morning.models import Client, FinancialSummary, Invoice, LinkedDocument, Payment

REAL_DOCUMENT_RESPONSE_SAMPLE = {
    "id": "5f2c1a2b-0000-4c11-9a1a-abcdef123456",
    "number": "INV-2026-001",
    "type": 320,
    "documentType": 320,
    "client": {
        "id": "client-123",
        "name": "Tech Corp",
        "emails": ["billing@techcorp.example"],
        "phone": "+972541234567",
    },
    "date": "2026-07-08",
    "dueDate": "2026-08-08",
    "currency": "ILS",
    "vatType": 1,
    "income": [
        {"description": "Consulting services", "quantity": 1, "price": 5000.0, "vatType": 1}
    ],
    "amount": 5000.0,
    "total": 5850.0,
    "vatAmount": 850.0,
}


def test_invoice_model_parses_real_document_response():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.id == "5f2c1a2b-0000-4c11-9a1a-abcdef123456"
    assert invoice.client_name == "Tech Corp"
    assert invoice.amount == 5000.0
    assert invoice.total_amount == 5850.0
    assert invoice.currency == "ILS"
    assert invoice.issue_date == date(2026, 7, 8)
    assert invoice.due_date == date(2026, 8, 8)


def test_invoice_model_rejects_negative_amount():
    bad = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, amount=-100.0)

    with pytest.raises(ValidationError):
        Invoice.model_validate(bad)


def test_invoice_model_defaults_currency_to_ils_when_omitted():
    no_currency = {k: v for k, v in REAL_DOCUMENT_RESPONSE_SAMPLE.items() if k != "currency"}

    invoice = Invoice.model_validate(no_currency)

    assert invoice.currency == "ILS"


def test_invoice_model_coerces_integer_document_number_to_string():
    """Regression: the real Morning /documents response returns `number` as an
    int (discovered via the real sandbox in test_morning_sandbox_create_invoice_tool.py),
    not the string this model originally assumed."""
    int_number = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, number=50002)

    invoice = Invoice.model_validate(int_number)

    assert invoice.number == "50002"


@pytest.mark.parametrize(
    "morning_status_code,expected_status",
    [(0, "unpaid"), (1, "paid"), (2, "paid"), (3, "cancelled"), (4, "cancelled")],
)
def test_invoice_model_maps_morning_numeric_status_codes(morning_status_code, expected_status):
    """Regression: /documents(/search) returns `status` as an int (discovered
    via the real sandbox in test_morning_sandbox_list_invoices_tool.py), whose
    meaning was confirmed live against GET /documents/statuses."""
    with_status = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, status=morning_status_code)

    invoice = Invoice.model_validate(with_status)

    assert invoice.status == expected_status


def test_invoice_model_preserves_already_string_status():
    with_status = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, status="unpaid")

    invoice = Invoice.model_validate(with_status)

    assert invoice.status == "unpaid"


def test_client_model_requires_name():
    with pytest.raises(ValidationError):
        Client.model_validate({"email": "a@b.com"})


def test_client_model_validates_email_format():
    with pytest.raises(ValidationError):
        Client.model_validate({"name": "Tech Corp", "email": "not-an-email"})


def test_client_model_accepts_minimal_valid_payload():
    client = Client.model_validate({"name": "Tech Corp"})

    assert client.name == "Tech Corp"
    assert client.email is None


def test_payment_model_round_trip():
    payment = Payment.model_validate(
        {
            "id": "pay-1",
            "invoice_id": "5f2c1a2b-0000-4c11-9a1a-abcdef123456",
            "amount": 5850.0,
            "currency": "ILS",
            "payment_date": "2026-07-10",
            "method": "card",
        }
    )

    assert payment.amount == 5850.0
    assert payment.payment_date == date(2026, 7, 10)


def test_financial_summary_model_computes_no_math_itself_just_validates():
    summary = FinancialSummary.model_validate(
        {
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "total_invoiced": 125000.0,
            "total_paid": 105000.0,
            "total_unpaid": 20000.0,
            "invoice_count": 24,
            "paid_invoice_count": 20,
            "unpaid_invoice_count": 4,
            "average_invoice_amount": 5208.33,
        }
    )

    assert summary.invoice_count == summary.paid_invoice_count + summary.unpaid_invoice_count


def test_models_use_utc_for_any_generated_timestamps():
    """If a model stamps created_at itself, it must be UTC (CONSTITUTION §II)."""
    client = Client.model_validate({"name": "Tech Corp"})

    if client.created_at is not None:
        assert client.created_at.tzinfo == timezone.utc


# ============================================================================
# bugfix-014: linkedDocuments exposure (receipts/credits linked to invoices)
# ============================================================================

REAL_LINKED_RECEIPT_SAMPLE = {
    "id": "800e89f0-342f-401b-ad03-62b4baf450eb",
    "type": 305,
    "number": 50500,
    "documentDate": "2026-07-15",
    "amount": 88,
    "currency": "ILS",
    "currencyRate": 1,
    "reverseCharge": False,
}


def test_linked_document_model_parses_real_shape():
    """Real shape confirmed live, 2026-07-21/22, via GET /documents/{id} on a
    receipt linked to an invoice (see bugfix-014's Investigation Findings) -
    this is the field that never appears on /documents/search (list_invoices'
    endpoint), only on the single-document GET."""
    linked = LinkedDocument.model_validate(REAL_LINKED_RECEIPT_SAMPLE)

    assert linked.id == "800e89f0-342f-401b-ad03-62b4baf450eb"
    assert linked.type == 305
    assert linked.number == "50500"
    assert linked.document_date == date(2026, 7, 15)
    assert linked.amount == 88
    assert linked.currency == "ILS"


def test_linked_document_model_coerces_integer_number_to_string():
    linked = LinkedDocument.model_validate(dict(REAL_LINKED_RECEIPT_SAMPLE, number=80109))

    assert linked.number == "80109"


def test_invoice_model_maps_linked_documents_from_real_response():
    """Regression for bugfix-014: without this, an invoice/receipt/credit's
    linkedDocuments (the real, structured, bidirectional link Morning provides)
    was silently dropped - the model had no way to tell a receipt/credit apart
    from an independent invoice, causing double-counted totals."""
    with_links = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, linkedDocuments=[REAL_LINKED_RECEIPT_SAMPLE])

    invoice = Invoice.model_validate(with_links)

    assert len(invoice.linked_documents) == 1
    assert invoice.linked_documents[0].number == "50500"
    assert invoice.linked_documents[0].amount == 88


def test_invoice_model_defaults_linked_documents_to_empty_list():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.linked_documents == []


def test_invoice_model_maps_creation_timestamp_from_real_response():
    """Feature 025 (denidin-app, Morning-Sourced Ledger Events), T003a: real
    Green Invoice /documents(/search) responses carry a `creationDate` field
    - a genuine Unix epoch integer with full second-level precision (live-
    confirmed 2026-08-21 against the real dev sandbox: e.g. 1787241168 ->
    2026-08-20 18:52:48 Israel local) - completely separate from
    `documentDate`/issue_date (date-only). Until this field existed, that
    full-precision creation time was silently unavailable to any MCP tool
    caller, even though the real API always sends it."""
    with_creation = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, creationDate=1787241168)

    invoice = Invoice.model_validate(with_creation)

    assert invoice.creation_timestamp == datetime.fromtimestamp(1787241168, tz=timezone.utc)


def test_invoice_model_creation_timestamp_defaults_to_none_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.creation_timestamp is None


def test_invoice_model_maps_top_level_description_from_real_response():
    """denidin-app's Feature 025: real /documents(/search) responses carry a
    top-level `description` (live-confirmed 2026-08-21: e.g. "תחזוקה") that
    this model dropped entirely - it was never mapped, so no MCP tool could
    ever surface it, which is exactly why the reconciliation sweep's captured
    ledger events all had description=null. Distinct from income[].description
    (a per-line-item field)."""
    with_description = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, description="תחזוקה")

    invoice = Invoice.model_validate(with_description)

    assert invoice.description == "תחזוקה"


def test_invoice_model_description_defaults_to_none_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.description is None


# Real payment shapes, captured live from the dev sandbox 2026-08-23 (see
# specs/.../025-morning-sourced-ledger-events/artifacts/). Note the raw key is
# `payment` (singular) while the model field is `payments` (plural).
REAL_BANK_TRANSFER_PAYMENT = {
    "id": "c4c52171-36d0-4b0a-9ed4-aff529de96f3", "date": "2026-07-12", "type": 4,
    "status": 1, "price": 1500, "currency": "ILS", "currencyRate": 1, "paymentStatus": 0,
    "ref": [], "cancellable": False, "bankName": "31", "bankBranch": "109",
    "bankAccount": "105542585", "name": "העברה בנקאית",
    "description": "בנק 31 / סניף 109 / מס' חשבון 105542585", "amount": 1500,
}
REAL_CASH_PAYMENT = {
    "id": "57100ebc-6a75-4aeb-855a-1361fca7f010", "date": "2026-08-20", "type": 1,
    "status": 0, "price": 500, "currency": "ILS", "currencyRate": 1, "paymentStatus": 0,
    "ref": [305], "cancellable": True, "name": "מזומן", "description": "", "amount": 500,
}


def test_invoice_payments_maps_from_the_raw_singular_payment_key():
    """Pre-existing bug (found 2026-08-22, fixed 2026-08-23): the raw API key is
    `payment` but the model field is `payments`, with NO mapping between them -
    so Invoice.payments was ALWAYS [] for every caller, which is why
    get_invoice_details' 'תשלומים:' block was dead code that had never rendered
    for anyone, and why the reconciliation sweep could never see bank details."""
    raw = dict(REAL_DOCUMENT_RESPONSE_SAMPLE, payment=[REAL_BANK_TRANSFER_PAYMENT])

    invoice = Invoice.model_validate(raw)

    assert len(invoice.payments) == 1


def test_payment_model_does_not_require_invoice_id():
    """The raw payment object carries no invoice_id at all, so requiring it
    meant Payment would have failed validation even once the mapping existed."""
    payment = Payment.model_validate(REAL_CASH_PAYMENT)

    assert payment.invoice_id is None
    assert payment.amount == 500


def test_payment_model_maps_structured_bank_fields():
    """These exist ONLY on get_invoice_details' response - /documents/search
    carries the same information merely concatenated into a Hebrew string."""
    payment = Payment.model_validate(REAL_BANK_TRANSFER_PAYMENT)

    assert payment.bank_name == "31"
    assert payment.bank_branch == "109"
    assert payment.bank_account == "105542585"


def test_payment_model_maps_method_name_date_and_type():
    payment = Payment.model_validate(REAL_BANK_TRANSFER_PAYMENT)

    assert payment.method == "העברה בנקאית"     # raw `name`
    assert payment.payment_type == 4             # raw `type` (4 = העברה בנקאית)
    assert payment.payment_date == date(2026, 7, 12)


def test_payment_model_leaves_bank_fields_none_for_a_cash_payment():
    payment = Payment.model_validate(REAL_CASH_PAYMENT)

    assert payment.bank_name is None
    assert payment.method == "מזומן"


def test_invoice_payments_defaults_to_empty_list_when_absent():
    invoice = Invoice.model_validate(REAL_DOCUMENT_RESPONSE_SAMPLE)

    assert invoice.payments == []


def test_invoice_maps_morning_literal_status_label_alongside_canonical():
    """Feature 025 Phase 9: Morning's status vocabulary is open/closed, NOT
    paid/unpaid - we map `1 מסמך סגור` -> "paid", but for a proforma "closed"
    plausibly means "converted to an invoice". Keep Morning's own literal label
    so the ledger never loses the real value (confirmed live against
    GET /documents/statuses)."""
    invoice = Invoice.model_validate(dict(REAL_DOCUMENT_RESPONSE_SAMPLE, status=1))

    assert invoice.status == "paid"                    # canonical, unchanged
    assert invoice.status_label == "מסמך סגור"          # Morning's own words
    assert invoice.status_code == 1                     # raw int


def test_invoice_status_label_for_every_real_morning_status_code():
    """All five confirmed live via GET /documents/statuses (2026-08-23)."""
    expected = {
        0: "מסמך פתוח", 1: "מסמך סגור", 2: "מסמך סומן ידנית כסגור",
        3: "מסמך מבטל", 4: "מסמך שבוטל",
    }
    for code, label in expected.items():
        invoice = Invoice.model_validate(dict(REAL_DOCUMENT_RESPONSE_SAMPLE, status=code))
        assert invoice.status_label == label, f"status {code}"
