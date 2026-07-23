"""Tests for feature 021 (flexible Morning document creation): new
type-specific creation tools (create_transaction_account, create_combo_document,
create_credit_note, create_receipt) and the payload-builder refactor that
lets 330/400 be created standalone, not only as update_invoice_status side
effects.

Uses a fake MorningClient (dependency-injected, matching the real
create_invoice/get_invoice contracts) — this mocks a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
from denidin_mcp_morning import tools


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary."""

    def __init__(self, get_invoice_response=None, create_invoice_response=None):
        self._get_invoice_response = get_invoice_response
        self._create_invoice_response = create_invoice_response or {"id": "new-doc-1", "number": "1001"}
        self.create_invoice_calls = []
        self.get_invoice_calls = []

    def get_invoice(self, invoice_id):
        self.get_invoice_calls.append(invoice_id)
        if self._get_invoice_response is None:
            raise LookupError(f"no such invoice: {invoice_id}")
        return self._get_invoice_response

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return self._create_invoice_response


def _original_invoice(doc_id="orig-1", number="500", amount=1000.0, client_name="לקוח בדיקה"):
    return {
        "id": doc_id,
        "number": number,
        "type": 305,
        "client": {"name": client_name},
        "amount": amount,
        "total": amount,
        "currency": "ILS",
        "lang": "he",
        "vatType": 1,
        "status": None,
        "income": [
            {
                "catalogNum": "",
                "description": "שירות",
                "quantity": 1,
                "price": amount,
                "currency": "ILS",
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": 1,
            }
        ],
    }


# --- _build_transaction_account_payload (type 300) ---


def test_build_transaction_account_payload_has_no_vat_fields():
    payload = tools._build_transaction_account_payload(
        client_name="לקוח בדיקה", amount=500.0, description="שירות ייעוץ"
    )

    assert payload["type"] == 300
    assert "vatType" not in payload
    for income_item in payload["income"]:
        assert "vatType" not in income_item
        assert "vatRate" not in income_item


def test_build_transaction_account_payload_includes_due_date_when_given():
    with_due_date = tools._build_transaction_account_payload(
        client_name="לקוח בדיקה", amount=500.0, description="שירות", due_date="2026-08-01"
    )
    without_due_date = tools._build_transaction_account_payload(
        client_name="לקוח בדיקה", amount=500.0, description="שירות"
    )

    assert with_due_date["dueDate"] == "2026-08-01"
    assert "dueDate" not in without_due_date


# --- _build_combo_document_payload (type 320) ---


def test_build_combo_document_payload_type_and_shape():
    payload = tools._build_combo_document_payload(
        client_name="לקוח בדיקה", amount=750.0, description="מכירה מיידית"
    )

    assert payload["type"] == 320
    assert payload["vatType"] == 1
    assert "dueDate" not in payload


def test_build_combo_document_payload_vat_excluded_when_requested():
    payload = tools._build_combo_document_payload(
        client_name="לקוח בדיקה", amount=750.0, description="מכירה מיידית", vat_included=False
    )

    assert payload["vatType"] == 0


# --- _build_cancellation_payload (type 330) — refactored for overrides ---


def test_build_credit_note_payload_defaults_mirror_original():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original)

    assert payload["type"] == 330
    assert payload["linkedDocumentIds"] == ["orig-1"]
    assert payload["income"][0]["price"] == 1000.0


def test_build_credit_note_payload_amount_override():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original, amount=250.0)

    assert payload["income"][0]["price"] == 250.0
    assert payload["payment"][0]["price"] == 250.0


def test_build_credit_note_payload_description_override():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original, description="זיכוי חלקי לפי בקשת הלקוח")

    assert payload["description"] == "זיכוי חלקי לפי בקשת הלקוח"


# --- _build_payment_receipt_payload (type 400) — refactored for overrides ---


def test_build_receipt_payload_defaults_and_override():
    original = _original_invoice()

    default_payload = tools._build_payment_receipt_payload(original)
    assert default_payload["type"] == 400
    assert default_payload["linkedDocumentIds"] == ["orig-1"]
    assert default_payload["payment"][0]["price"] == 1000.0

    override_payload = tools._build_payment_receipt_payload(original, amount=400.0)
    assert override_payload["payment"][0]["price"] == 400.0


# --- Regression guards: existing internal call sites still work post-refactor ---


def test_cancel_invoice_still_works_after_refactor():
    original = _original_invoice(doc_id="orig-2", number="600")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "credit-1", "number": "700"},
    )

    result = tools._cancel_invoice(client, "orig-2")

    assert "600" in result
    assert "700" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 330
    assert sent_payload["linkedDocumentIds"] == ["orig-2"]


def test_mark_invoice_paid_still_works_after_refactor():
    original = _original_invoice(doc_id="orig-3", number="601")
    original["status"] = None  # not yet paid
    updated = dict(original)
    updated["status"] = 1  # closed/paid after the receipt is issued

    client = _FakeMorningClient(get_invoice_response=original)
    # get_invoice is called twice by _mark_invoice_paid: once for the
    # original, once to re-fetch after issuing the receipt.
    responses = iter([original, updated])
    client.get_invoice = lambda invoice_id: next(responses)

    result = tools._mark_invoice_paid(client, "orig-3")

    assert "601" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-3"]


# --- New standalone tool functions ---


def test_create_transaction_account_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "ta-1", "number": "800", "status": None})

    result = tools.create_transaction_account(client, "לקוח בדיקה", 500.0, "שירות ייעוץ")

    assert "800" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 300
    assert "vatType" not in sent_payload


def test_create_combo_document_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "combo-1", "number": "801", "status": 1})

    result = tools.create_combo_document(client, "לקוח בדיקה", 750.0, "מכירה מיידית")

    assert "801" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320


def test_create_credit_note_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.create_credit_note(client, "nonexistent-id")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_create_credit_note_happy_path_uses_original_and_allows_override():
    original = _original_invoice(doc_id="orig-4", number="602")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "credit-2", "number": "701"},
    )

    result = tools.create_credit_note(client, "orig-4", amount=300.0)

    assert "701" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 330
    assert sent_payload["linkedDocumentIds"] == ["orig-4"]
    assert sent_payload["income"][0]["price"] == 300.0


def test_create_receipt_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.create_receipt(client, "nonexistent-id")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_create_receipt_happy_path_uses_original_and_allows_override():
    original = _original_invoice(doc_id="orig-5", number="603")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "receipt-2", "number": "702"},
    )

    result = tools.create_receipt(client, "orig-5", amount=600.0)

    assert "702" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-5"]
    assert sent_payload["payment"][0]["price"] == 600.0
