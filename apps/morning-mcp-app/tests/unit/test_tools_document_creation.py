"""Tests for feature 021 (flexible Morning document creation): new
type-specific creation tools (create_transaction_account, create_combo_document,
create_credit_note, create_receipt) and the payload-builder refactor that
lets 330/400 be created standalone, not only as update_invoice_status side
effects.

Also covers feature 023 (reference-linked combo document creation):
close_transaction_account, and the _build_combo_closing_payload override
support it needs.

Uses a fake MorningClient (dependency-injected, matching the real
create_invoice/get_invoice contracts) — this mocks a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
from denidin_mcp_morning import tools
from denidin_mcp_morning.formatters import format_original_not_linked_to_client


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary.

    Feature 027: Group A tools (create_transaction_account/
    create_combo_document) now resolve their client_name via
    `search_clients` before creating anything - `search_clients_response`
    lets tests control that resolution (default: a single match on
    "לקוח בדיקה", client_id "client-1", so existing happy-path tests keep
    passing unchanged in spirit)."""

    def __init__(self, get_invoice_response=None, create_invoice_response=None, search_clients_response=None):
        self._get_invoice_response = get_invoice_response
        self._create_invoice_response = create_invoice_response or {"id": "new-doc-1", "number": "1001"}
        self._search_clients_response = search_clients_response or {
            "items": [_client_record()],
            "total": 1,
        }
        self.create_invoice_calls = []
        self.get_invoice_calls = []
        self.search_clients_calls = []

    def get_invoice(self, invoice_id):
        self.get_invoice_calls.append(invoice_id)
        if self._get_invoice_response is None:
            raise LookupError(f"no such invoice: {invoice_id}")
        return self._get_invoice_response

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return self._create_invoice_response

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        return self._search_clients_response


def _client_record(client_id="client-1", name="לקוח בדיקה"):
    """A raw Morning /clients/search item - just enough shape for
    `_resolve_client_for_document_creation` (Group A resolution)."""
    return {"id": client_id, "name": name, "active": True, "phone": "", "emails": []}


def _original_invoice(
    doc_id="orig-1", number="500", amount=90.0, client_name="לקוח בדיקה", client_id="client-1", doc_type=305
):
    """A raw Morning /documents/{id} response, used as a Group B tool's
    linked original. Feature 027 (REQ-INV-012/013): `client_id` defaults to
    a real-looking id (the "preserve" path, matching any document created
    on/after this feature) - pass `client_id=None` to simulate a pre-feature,
    bare-name-only original (the "refuse" path)."""
    client_ref = {"name": client_name}
    if client_id is not None:
        client_ref["id"] = client_id
    return {
        "id": doc_id,
        "number": number,
        "type": doc_type,
        "client": client_ref,
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
        client_id="client-1", amount=45.0, description="שירות ייעוץ"
    )

    assert payload["type"] == 300
    assert payload["client"] == {"self": False, "id": "client-1"}
    assert "vatType" not in payload
    for income_item in payload["income"]:
        assert "vatType" not in income_item
        assert "vatRate" not in income_item


def test_build_transaction_account_payload_includes_due_date_when_given():
    with_due_date = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות", due_date="2026-08-01"
    )
    without_due_date = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות"
    )

    assert with_due_date["dueDate"] == "2026-08-01"
    assert "dueDate" not in without_due_date


# --- _build_combo_document_payload (type 320) ---


def test_build_combo_document_payload_type_and_shape():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית"
    )

    assert payload["type"] == 320
    assert payload["client"] == {"self": False, "id": "client-1"}
    assert payload["vatType"] == 1
    assert "dueDate" not in payload


def test_build_combo_document_payload_vat_excluded_when_requested():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית", vat_included=False
    )

    assert payload["vatType"] == 0


# --- _build_cancellation_payload (type 330) — refactored for overrides ---


def test_build_credit_note_payload_defaults_mirror_original():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original)

    assert payload["type"] == 330
    assert payload["linkedDocumentIds"] == ["orig-1"]
    assert payload["income"][0]["price"] == 90.0


def test_build_credit_note_payload_amount_override():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original, amount=25.0)

    assert payload["income"][0]["price"] == 25.0
    assert payload["payment"][0]["price"] == 25.0


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
    assert default_payload["payment"][0]["price"] == 90.0

    override_payload = tools._build_payment_receipt_payload(original, amount=35.0)
    assert override_payload["payment"][0]["price"] == 35.0


# --- Regression guards: functionality formerly reached via the removed
# _cancel_invoice/_mark_invoice_paid (behind update_invoice_status, feature
# 023 removed both) still works, now reached via the direct tools that
# replace them ---


def test_full_cancellation_still_works_via_create_credit_note():
    """Formerly _cancel_invoice's own scenario (full-amount cancellation) -
    create_credit_note already fully subsumes it; this guards that the
    behavior _cancel_invoice used to provide is not lost."""
    original = _original_invoice(doc_id="orig-2", number="600")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "credit-1", "number": "700"},
    )

    result = tools.create_credit_note(client, "orig-2")

    assert "600" in result
    assert "700" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 330
    assert sent_payload["linkedDocumentIds"] == ["orig-2"]


def test_full_payment_still_works_via_create_receipt():
    """Formerly _mark_invoice_paid's own type-305 scenario - create_receipt
    already fully subsumes it (with an added idempotency guard, see
    test_mark_invoice_paid.py); this guards the basic full-payment behavior
    is not lost."""
    original = _original_invoice(doc_id="orig-3", number="601")
    original["status"] = None  # not yet paid
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.create_receipt(client, "orig-3")

    assert "601" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-3"]


# --- New standalone tool functions ---


def test_create_transaction_account_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "ta-1", "number": "800", "status": None})

    result = tools.create_transaction_account(client, "לקוח בדיקה", 45.0, "שירות ייעוץ")

    assert "800" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 300
    assert sent_payload["client"] == {"self": False, "id": "client-1"}
    assert "vatType" not in sent_payload


def test_create_transaction_account_refuses_when_client_not_found():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    result = tools.create_transaction_account(client, "לקוח שלא קיים", 45.0, "שירות ייעוץ")

    assert client.create_invoice_calls == []
    assert "לא נמצא" in result or "אין" in result


def test_create_combo_document_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "combo-1", "number": "801", "status": 1})

    result = tools.create_combo_document(client, "לקוח בדיקה", 65.0, "מכירה מיידית")

    assert "801" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["client"] == {"self": False, "id": "client-1"}


def test_create_combo_document_refuses_when_client_ambiguous():
    client = _FakeMorningClient(
        search_clients_response={
            "items": [_client_record(client_id="c-1", name="לקוח א"), _client_record(client_id="c-2", name="לקוח ב")],
            "total": 2,
        }
    )

    result = tools.create_combo_document(client, "לקוח", 65.0, "מכירה מיידית")

    assert client.create_invoice_calls == []
    assert "לקוח א" in result
    assert "לקוח ב" in result


def test_create_credit_note_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.create_credit_note(client, "nonexistent-id")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_create_credit_note_refuses_when_original_has_no_client_id():
    """Feature 027 (REQ-INV-013): a pre-feature, bare-name-only original
    must not silently get a bare-name credit note either - refuse instead."""
    original = _original_invoice(doc_id="orig-4b", number="602b", client_id=None)
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.create_credit_note(client, "orig-4b")

    assert client.create_invoice_calls == []
    assert result == format_original_not_linked_to_client()


def test_create_credit_note_happy_path_uses_original_and_allows_override():
    original = _original_invoice(doc_id="orig-4", number="602")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "credit-2", "number": "701"},
    )

    result = tools.create_credit_note(client, "orig-4", amount=28.0)

    assert "701" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 330
    assert sent_payload["linkedDocumentIds"] == ["orig-4"]
    assert sent_payload["income"][0]["price"] == 28.0


def test_create_receipt_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.create_receipt(client, "nonexistent-id")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_create_receipt_refuses_when_original_has_no_client_id():
    """Feature 027 (REQ-INV-013): a pre-feature, bare-name-only original
    must not silently get a bare-name receipt either - refuse instead."""
    original = _original_invoice(doc_id="orig-5b", number="603b", client_id=None)
    original["status"] = None  # not yet paid - would otherwise hit the idempotent no-op path first
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.create_receipt(client, "orig-5b")

    assert client.create_invoice_calls == []
    assert result == format_original_not_linked_to_client()


def test_create_receipt_happy_path_uses_original_and_allows_override():
    original = _original_invoice(doc_id="orig-5", number="603")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "receipt-2", "number": "702"},
    )

    result = tools.create_receipt(client, "orig-5", amount=55.0)

    assert "702" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-5"]
    assert sent_payload["payment"][0]["price"] == 55.0


# --- Feature 023: _build_combo_closing_payload override support ---


def test_build_combo_closing_payload_defaults_use_a_clean_single_income_line():
    """Full close (no overrides): a single clean income line built from the
    resolved total, never the original's raw income items - confirmed live
    (feature 023) that mirroring them verbatim creates an internally
    inconsistent payload, since those items carry vatRate/vatType computed
    under the ORIGINAL's own (possibly different) vatType context."""
    original = _original_invoice(doc_id="orig-300", number="900", amount=85.0, doc_type=300)

    payload = tools._build_combo_closing_payload(original)

    assert payload["type"] == 320
    assert payload["linkedDocumentIds"] == ["orig-300"]
    assert payload["description"] == "תשלום עבור חשבון עסקה מספר 900"
    assert len(payload["income"]) == 1
    assert payload["income"][0]["price"] == 85.0
    assert payload["income"][0]["vatRate"] == 0
    assert payload["payment"][0]["price"] == 85.0


def test_build_combo_closing_payload_prefers_amount_field_over_summing_income_items():
    """Root-cause regression guard (feature 023): when 'total' is absent
    (the real shape Morning returns for a document created via
    create_transaction_account), the resolved close amount must come from
    the original's own 'amount' field - which already reflects any VAT
    Morning silently applied - not from summing raw income item prices,
    which would miss that VAT and understate the amount."""
    original = _original_invoice(doc_id="orig-300b", number="900b", amount=85.0, doc_type=300)
    original["total"] = None  # the real shape: "total" is absent, only "amount" is authoritative
    original["income"][0]["price"] = 60.0  # raw item price, deliberately less than "amount" (VAT was added)

    payload = tools._build_combo_closing_payload(original)

    assert payload["payment"][0]["price"] == 85.0, (
        "Must use original['amount'] (85.0), not sum raw income item prices (60.0)"
    )


def test_build_combo_closing_payload_amount_override():
    original = _original_invoice(doc_id="orig-301", number="901", amount=85.0, doc_type=300)

    payload = tools._build_combo_closing_payload(original, amount=28.0)

    assert payload["payment"][0]["price"] == 28.0
    assert len(payload["income"]) == 1
    assert payload["income"][0]["price"] == 28.0


def test_build_combo_closing_payload_description_override():
    original = _original_invoice(doc_id="orig-302", number="902", doc_type=300)

    payload = tools._build_combo_closing_payload(original, description="סגירה חלקית לפי בקשת הלקוח")

    assert payload["description"] == "סגירה חלקית לפי בקשת הלקוח"
    assert payload["income"][0]["description"] == "סגירה חלקית לפי בקשת הלקוח"


# --- Feature 023: close_transaction_account (new standalone tool) ---


def test_close_transaction_account_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.close_transaction_account(client, "nonexistent-id")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_close_transaction_account_refuses_when_original_has_no_client_id():
    """Feature 027 (REQ-INV-013): a pre-feature, bare-name-only original
    must not silently get a bare-name closing document either - refuse
    instead."""
    original = _original_invoice(doc_id="orig-6b", number="604b", doc_type=300, client_id=None)
    original["status"] = None  # not yet closed - would otherwise hit the idempotent no-op path first
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.close_transaction_account(client, "orig-6b")

    assert client.create_invoice_calls == []
    assert result == format_original_not_linked_to_client()


def test_close_transaction_account_happy_path_full_amount():
    """US1: close an existing type-300 document with a full-amount combo document."""
    original = _original_invoice(doc_id="orig-6", number="604", amount=145.0, doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-2", "number": "703"},
    )

    result = tools.close_transaction_account(client, "orig-6")

    assert "703" in result
    assert "604" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["linkedDocumentIds"] == ["orig-6"]
    assert sent_payload["payment"][0]["price"] == 145.0


def test_close_transaction_account_happy_path_partial_amount():
    """US2: close an existing type-300 document with a partial-amount combo document."""
    original = _original_invoice(doc_id="orig-7", number="605", amount=145.0, doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-3", "number": "704"},
    )

    result = tools.close_transaction_account(client, "orig-7", amount=45.0)

    assert "704" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["payment"][0]["price"] == 45.0


def test_close_transaction_account_rejects_non_transaction_account_original():
    """US3: referencing a non-type-300 document must be rejected, not silently miscreated."""
    original = _original_invoice(doc_id="orig-8", number="606", doc_type=305)
    client = _FakeMorningClient(get_invoice_response=original)

    try:
        tools.close_transaction_account(client, "orig-8")
        assert False, "expected ValueError for a non-type-300 original"
    except ValueError as exc:
        assert "305" in str(exc)

    assert client.create_invoice_calls == [], "must not create a document for an unsupported original type"


def test_close_transaction_account_description_override():
    original = _original_invoice(doc_id="orig-9", number="607", doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-4", "number": "705"},
    )

    tools.close_transaction_account(client, "orig-9", description="סגירה לפי הסכמה בעל פה")

    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["description"] == "סגירה לפי הסכמה בעל פה"


# --- Feature 023: regression guard for the transaction-account closing flow ---


def test_close_transaction_account_still_works_after_vat_included_param_added():
    """Regression guard: the type-300->320 closing flow (originally 020's
    update_invoice_status branching, now close_transaction_account directly,
    per feature 023) must remain correct after _build_combo_closing_payload
    gained the vat_included parameter (replacing the buggy
    original.get("vatType", 1) inference - see feature 023's spec.md)."""
    original = _original_invoice(doc_id="orig-10", number="608", amount=60.0, doc_type=300)
    original["status"] = None  # not yet paid
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.close_transaction_account(client, "orig-10")

    assert "608" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["linkedDocumentIds"] == ["orig-10"]
    assert sent_payload["payment"][0]["price"] == 60.0
    assert sent_payload["vatType"] == 1  # vat_included defaults to True


# --- bugfix-026: every document payload must be created signed, or Morning
# refuses to let it be shared by email (blocked in prod - see
# specs/bugfixes/bugfix-026-morning-documents-created-unsigned.md) ---


def test_build_create_invoice_payload_is_signed():
    payload = tools._build_create_invoice_payload(
        client_id="client-1", amount=100.0, description="שירות ייעוץ"
    )
    assert payload["signed"] is True


def test_build_transaction_account_payload_is_signed():
    payload = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות ייעוץ"
    )
    assert payload["signed"] is True


def test_build_combo_document_payload_is_signed():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית"
    )
    assert payload["signed"] is True


def test_build_cancellation_payload_is_signed():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original)
    assert payload["signed"] is True


def test_build_payment_receipt_payload_is_signed():
    original = _original_invoice()
    payload = tools._build_payment_receipt_payload(original)
    assert payload["signed"] is True


def test_build_combo_closing_payload_is_signed():
    original = _original_invoice(doc_type=300)
    payload = tools._build_combo_closing_payload(original)
    assert payload["signed"] is True
