"""Tests for feature 021 (flexible Morning document creation): new
type-specific creation tools (create_transaction_account, create_combo_document,
create_credit_note, create_receipt) and the payload-builder refactor that
lets 330/400 be created standalone, not only as update_invoice_status side
effects.

Also covers feature 023 (reference-linked combo document creation):
create_combo_document_as_reference, and the _build_combo_closing_payload override
support it needs.

Uses a fake MorningClient (dependency-injected, matching the real
create_invoice/get_invoice contracts) — this mocks a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
import pytest

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

    def get_invoice(self, internal_morning_id):
        self.get_invoice_calls.append(internal_morning_id)
        if self._get_invoice_response is None:
            raise LookupError(f"no such invoice: {internal_morning_id}")
        return self._get_invoice_response

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return self._create_invoice_response

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        return self._search_clients_response


def _client_record(client_id="client-1", name="לקוח בדיקה"):
    """A raw Morning /clients/search item - just enough shape for
    `_require_resolved_client` (Group A resolution)."""
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


def test_build_transaction_account_payload_states_its_vat_treatment():
    """bugfix-028 A2 - INVERTED 2026-08-09. This test previously asserted the
    payload had NO vatType/vatRate anywhere, encoding bugfix-014 Flow 4's premise
    that a type-300 "carries no VAT obligation ... the field's mere presence
    implies a tax document". That premise was recorded from the customer's
    Morning UI and explicitly never reproduced against the API, and it is wrong:
    probed live, omitting `vatType` is treated exactly as `vatType: 0` (price
    EXCLUDES VAT) and Morning adds ~18%. It is what stored ₪2,360 as ₪2,784.80 in
    production. The old assertion was pinning the bug in place.
    """
    payload = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות ייעוץ", vat_included=True
    )

    assert payload["type"] == 300
    assert payload["client"] == {"self": False, "id": "client-1"}
    assert payload["vatType"] == 1, "a VAT-inclusive amount must say so explicitly"
    for income_item in payload["income"]:
        assert income_item["vatType"] == 1

    exclusive = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות ייעוץ", vat_included=False
    )
    assert exclusive["vatType"] == 0


def test_build_transaction_account_payload_includes_due_date_when_given():
    with_due_date = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות", vat_included=True,
        due_date="2026-08-01"
    )
    without_due_date = tools._build_transaction_account_payload(
        client_id="client-1", amount=45.0, description="שירות", vat_included=True
    )

    assert with_due_date["dueDate"] == "2026-08-01"
    assert "dueDate" not in without_due_date


# --- _build_combo_document_payload (type 320) ---


def test_build_combo_document_payload_type_and_shape():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית",
        vat_included=True, payment_date="2026-07-12"
    )

    assert payload["type"] == 320
    assert payload["client"] == {"self": False, "id": "client-1"}
    assert payload["vatType"] == 1
    assert "dueDate" not in payload


def test_build_combo_document_payload_vat_excluded_when_requested():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית",
        vat_included=False, payment_date="2026-07-12"
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

    default_payload = tools._build_payment_receipt_payload(original, payment_date="2026-07-12")
    assert default_payload["type"] == 400
    assert default_payload["linkedDocumentIds"] == ["orig-1"]
    assert default_payload["payment"][0]["price"] == 90.0
    assert default_payload["payment"][0]["date"] == "2026-07-12"

    override_payload = tools._build_payment_receipt_payload(original, payment_date="2026-07-12", amount=35.0)
    assert override_payload["payment"][0]["price"] == 35.0


def test_build_standalone_receipt_payload_shape():
    """Feature 056 (REQ-INV-017): a standalone receipt has no prior document
    to reference - it records a pure cash movement (deposit, loan repayment,
    or advance payment), so unlike every other document type this app
    creates, it must carry no VAT/income line at all, and no
    linkedDocumentIds (there's nothing to link to). Client attachment uses
    an already-resolved client_id directly (the caller is responsible for
    resolving it via resolve_client_name first, same as create_invoice)."""
    payload = tools._build_standalone_receipt_payload(
        client_id="client-9",
        amount=250.0,
        description="פיקדון מלקוח",
        payment_date="2026-08-01",
    )

    assert payload["type"] == 400
    assert "income" not in payload
    assert "vatType" not in payload
    assert "linkedDocumentIds" not in payload or payload["linkedDocumentIds"] == []
    assert payload["client"] == {"self": False, "id": "client-9"}
    assert payload["payment"] == [{"type": 1, "price": 250.0, "date": "2026-08-01"}]


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

    result = tools.create_receipt(client, "orig-3", payment_date="2026-07-12")

    assert "601" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-3"]


# --- create_invoice (feature 022; previously had no dedicated unit test at
# all - only indirect coverage via the shared resolution-helper test and
# billed/E2E tests - gap found and closed 2026-08-12 during the client-name-
# resolution architecture fix) ---


def test_create_invoice_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "inv-1", "number": "900", "status": None})

    result = tools.create_invoice(client, "לקוח בדיקה", 120.0, "ייעוץ", name_resolved=True)

    assert "900" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["client"] == {"self": False, "id": "client-1"}


def test_create_invoice_refuses_when_client_not_found():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNotFoundError):
        tools.create_invoice(client, "לקוח שלא קיים", 120.0, "ייעוץ", name_resolved=True)

    assert client.create_invoice_calls == []


def test_create_invoice_not_resolved_refuses_without_any_lookup():
    """Architecture fix (2026-08-12, user decision): create_invoice no
    longer does its own fuzzy/word-growth matching - it requires
    name_resolved=True and refuses immediately, with zero Morning calls,
    otherwise. Follow-up (2026-08-12): this is now a real raise, not
    ordinary refusal text - two outcomes only, succeed or raise."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.create_invoice(client, "לקוח בדיקה", 120.0, "ייעוץ")

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.create_invoice_calls == []


# --- New standalone tool functions ---


def test_create_transaction_account_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "ta-1", "number": "800", "status": None})

    result = tools.create_transaction_account(
        client, "לקוח בדיקה", 45.0, "שירות ייעוץ", vat_included=True, name_resolved=True
    )

    assert "800" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 300
    assert sent_payload["client"] == {"self": False, "id": "client-1"}
    # bugfix-028 A2 (inverted): omitting vatType is NOT "no VAT" to Morning - it
    # is "price excludes VAT", and it silently adds ~18%.
    assert sent_payload["vatType"] == 1


def test_create_transaction_account_refuses_when_client_not_found():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    # bugfix-028 B4(c) (changed): a client that cannot be found is a FAILURE, not
    # a friendly string returned as ordinary output with error=None - that is what
    # let one production document be approved 8 times and created 0 times.
    # Requires name_resolved=True (architecture fix, 2026-08-12) - the caller
    # must have already gone through resolve_client_name.
    with pytest.raises(tools.ClientNotFoundError):
        tools.create_transaction_account(
            client, "לקוח שלא קיים", 45.0, "שירות ייעוץ", vat_included=True, name_resolved=True
        )

    assert client.create_invoice_calls == []


def test_create_transaction_account_not_resolved_refuses_without_any_lookup():
    """Architecture fix (2026-08-12, user decision): create_transaction_account
    no longer does its own fuzzy/word-growth matching - it requires
    name_resolved=True and refuses immediately, with zero Morning calls,
    otherwise. Follow-up (2026-08-12): this is now a real raise, not
    ordinary refusal text - two outcomes only, succeed or raise."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.create_transaction_account(client, "לקוח בדיקה", 45.0, "שירות ייעוץ", vat_included=True)

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.create_invoice_calls == []


def test_create_combo_document_not_resolved_refuses_without_any_lookup():
    """Architecture fix (2026-08-12, user decision): create_combo_document
    no longer does its own fuzzy/word-growth matching - it requires
    name_resolved=True and refuses immediately, with zero Morning calls,
    otherwise. Real raise, not ordinary refusal text - two outcomes only,
    succeed or raise. (Added 2026-08-12 alongside the other five gated
    tools' equivalent test - this one was missing.)"""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.create_combo_document(
            client, "לקוח בדיקה", 65.0, "מכירה מיידית", vat_included=True, payment_date="2026-07-12"
        )

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.create_invoice_calls == []


def test_create_combo_document_returns_hebrew_confirmation():
    client = _FakeMorningClient(create_invoice_response={"id": "combo-1", "number": "801", "status": 1})

    result = tools.create_combo_document(
        client, "לקוח בדיקה", 65.0, "מכירה מיידית",
        vat_included=True, payment_date="2026-07-12", name_resolved=True,
    )

    assert "801" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["client"] == {"self": False, "id": "client-1"}


def test_create_combo_document_ambiguous_with_name_resolved_raises_not_found():
    """Architecture fix (2026-08-12): create_combo_document no longer
    discloses ambiguous candidates itself - that's resolve_client_name's job
    now (see test_tools_resolve_client_name.py). Asserting name_resolved=True
    against a name that's still ambiguous is a contract violation, and
    collapses to the same ClientNotFoundError as any other non-exact result
    under exact-only mode - a real behavior change from the old
    disambiguation-message shape."""
    client = _FakeMorningClient(
        search_clients_response={
            "items": [_client_record(client_id="c-1", name="לקוח א"), _client_record(client_id="c-2", name="לקוח ב")],
            "total": 2,
        }
    )

    with pytest.raises(tools.ClientNotFoundError):
        tools.create_combo_document(
            client, "לקוח", 65.0, "מכירה מיידית",
            vat_included=True, payment_date="2026-07-12", name_resolved=True,
        )

    assert client.create_invoice_calls == []


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
        tools.create_receipt(client, "nonexistent-id", payment_date="2026-07-12")
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

    result = tools.create_receipt(client, "orig-5b", payment_date="2026-07-12")

    assert client.create_invoice_calls == []
    assert result == format_original_not_linked_to_client()


def test_create_receipt_happy_path_uses_original_and_allows_override():
    original = _original_invoice(doc_id="orig-5", number="603")
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "receipt-2", "number": "702"},
    )

    result = tools.create_receipt(client, "orig-5", payment_date="2026-07-12", amount=55.0)

    assert "702" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert sent_payload["linkedDocumentIds"] == ["orig-5"]
    assert sent_payload["payment"][0]["price"] == 55.0


# --- create_receipt's standalone branch (feature 056, REQ-INV-014/015/016/024) ---


def test_create_receipt_standalone_branch_no_original_given(caplog):
    """(1) original_internal_morning_id=None, name_resolved=True, a resolved
    client -> builds the standalone shape (no income/vatType key, no
    linkedDocumentIds) rather than the linked-original shape, and never
    calls client.get_invoice at all (there is no original to fetch)."""
    client = _FakeMorningClient(create_invoice_response={"id": "receipt-3", "number": "800"})

    with caplog.at_level("INFO", logger="denidin_mcp_morning.audit"):
        result = tools.create_receipt(
            client,
            client_name="לקוח בדיקה",
            amount=250.0,
            description="פיקדון מלקוח",
            payment_date="2026-08-01",
            name_resolved=True,
        )

    assert "800" in result
    assert client.get_invoice_calls == [], "no original to fetch - get_invoice must never be called"
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 400
    assert "income" not in sent_payload
    assert "vatType" not in sent_payload
    assert "linkedDocumentIds" not in sent_payload or sent_payload["linkedDocumentIds"] == []
    assert sent_payload["client"] == {"self": False, "id": "client-1"}

    # (4) log_mutation is called with the resolved client's id/name - REQ-INV-024.
    audit_records = [r for r in caplog.records if "AUDIT create_receipt OK" in r.message]
    assert len(audit_records) == 1, f"expected exactly one audit log line, got: {caplog.records!r}"
    assert "client_id=client-1" in audit_records[0].message
    assert "client_name='לקוח בדיקה'" in audit_records[0].message


def test_create_receipt_standalone_branch_refuses_without_name_resolved():
    """(2) original_internal_morning_id=None, name_resolved=False (default)
    -> refuses immediately via the same _require_resolved_client contract
    violation create_invoice already uses, no Morning call attempted at
    all."""
    client = _FakeMorningClient()

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.create_receipt(
            client,
            client_name="לקוח בדיקה",
            amount=250.0,
            description="פיקדון מלקוח",
            payment_date="2026-08-01",
        )

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.get_invoice_calls == []
    assert client.create_invoice_calls == []


# --- Feature 023: _build_combo_closing_payload override support ---


def test_build_combo_closing_payload_defaults_use_a_clean_single_income_line():
    """Full close (no overrides): a single clean income line built from the
    resolved total, never the original's raw income items - confirmed live
    (feature 023) that mirroring them verbatim creates an internally
    inconsistent payload, since those items carry vatRate/vatType computed
    under the ORIGINAL's own (possibly different) vatType context."""
    original = _original_invoice(doc_id="orig-300", number="900", amount=85.0, doc_type=300)

    payload = tools._build_combo_closing_payload(original, payment_date="2026-07-12")

    assert payload["type"] == 320
    assert payload["linkedDocumentIds"] == ["orig-300"]
    assert payload["description"] == "תשלום עבור חשבון עסקה מספר 900"
    assert len(payload["income"]) == 1
    assert payload["income"][0]["price"] == 85.0
    assert payload["income"][0]["vatRate"] == 0
    assert payload["payment"][0]["price"] == 85.0
    # bugfix-038: payment_date is now real (validated), never hardcoded to today.
    assert payload["payment"][0]["date"] == "2026-07-12"


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

    payload = tools._build_combo_closing_payload(original, payment_date="2026-07-12")

    assert payload["payment"][0]["price"] == 85.0, (
        "Must use original['amount'] (85.0), not sum raw income item prices (60.0)"
    )


def test_build_combo_closing_payload_amount_override():
    original = _original_invoice(doc_id="orig-301", number="901", amount=85.0, doc_type=300)

    payload = tools._build_combo_closing_payload(original, payment_date="2026-07-12", amount=28.0)

    assert payload["payment"][0]["price"] == 28.0
    assert len(payload["income"]) == 1
    assert payload["income"][0]["price"] == 28.0


def test_build_combo_closing_payload_description_override():
    original = _original_invoice(doc_id="orig-302", number="902", doc_type=300)

    payload = tools._build_combo_closing_payload(
        original, payment_date="2026-07-12", description="סגירה חלקית לפי בקשת הלקוח"
    )

    assert payload["description"] == "סגירה חלקית לפי בקשת הלקוח"
    assert payload["income"][0]["description"] == "סגירה חלקית לפי בקשת הלקוח"


# --- Feature 023: create_combo_document_as_reference (new standalone tool) ---


def test_create_combo_document_as_reference_requires_existing_document():
    client = _FakeMorningClient(get_invoice_response=None)

    try:
        tools.create_combo_document_as_reference(client, "nonexistent-id", payment_date="2026-07-12")
        assert False, "expected an exception when original document doesn't exist"
    except LookupError:
        pass

    assert client.create_invoice_calls == [], "must not create a document when the original lookup fails"


def test_create_combo_document_as_reference_refuses_when_original_has_no_client_id():
    """Feature 027 (REQ-INV-013): a pre-feature, bare-name-only original
    must not silently get a bare-name closing document either - refuse
    instead."""
    original = _original_invoice(doc_id="orig-6b", number="604b", doc_type=300, client_id=None)
    original["status"] = None  # not yet closed - would otherwise hit the idempotent no-op path first
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.create_combo_document_as_reference(client, "orig-6b", payment_date="2026-07-12")

    assert client.create_invoice_calls == []
    assert result == format_original_not_linked_to_client()


def test_create_combo_document_as_reference_happy_path_full_amount():
    """US1: close an existing type-300 document with a full-amount combo document."""
    original = _original_invoice(doc_id="orig-6", number="604", amount=145.0, doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-2", "number": "703"},
    )

    result = tools.create_combo_document_as_reference(client, "orig-6", payment_date="2026-07-12")

    assert "703" in result
    assert "604" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["linkedDocumentIds"] == ["orig-6"]
    assert sent_payload["payment"][0]["price"] == 145.0
    # bugfix-038: payment_date is now real (validated), never hardcoded to today.
    assert sent_payload["payment"][0]["date"] == "2026-07-12"


def test_create_combo_document_as_reference_happy_path_partial_amount():
    """US2: close an existing type-300 document with a partial-amount combo document."""
    original = _original_invoice(doc_id="orig-7", number="605", amount=145.0, doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-3", "number": "704"},
    )

    result = tools.create_combo_document_as_reference(client, "orig-7", payment_date="2026-07-12", amount=45.0)

    assert "704" in result
    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["type"] == 320
    assert sent_payload["payment"][0]["price"] == 45.0


def test_create_combo_document_as_reference_rejects_non_transaction_account_original():
    """US3: referencing a non-type-300 document must be rejected, not silently miscreated."""
    original = _original_invoice(doc_id="orig-8", number="606", doc_type=305)
    client = _FakeMorningClient(get_invoice_response=original)

    try:
        tools.create_combo_document_as_reference(client, "orig-8", payment_date="2026-07-12")
        assert False, "expected ValueError for a non-type-300 original"
    except ValueError as exc:
        assert "305" in str(exc)

    assert client.create_invoice_calls == [], "must not create a document for an unsupported original type"


def test_create_combo_document_as_reference_description_override():
    original = _original_invoice(doc_id="orig-9", number="607", doc_type=300)
    client = _FakeMorningClient(
        get_invoice_response=original,
        create_invoice_response={"id": "combo-4", "number": "705"},
    )

    tools.create_combo_document_as_reference(
        client, "orig-9", payment_date="2026-07-12", description="סגירה לפי הסכמה בעל פה"
    )

    sent_payload = client.create_invoice_calls[0]
    assert sent_payload["description"] == "סגירה לפי הסכמה בעל פה"


# --- Feature 023: regression guard for the transaction-account closing flow ---


def test_create_combo_document_as_reference_still_works_after_vat_included_param_added():
    """Regression guard: the type-300->320 closing flow (originally 020's
    update_invoice_status branching, now create_combo_document_as_reference directly,
    per feature 023) must remain correct after _build_combo_closing_payload
    gained the vat_included parameter (replacing the buggy
    original.get("vatType", 1) inference - see feature 023's spec.md)."""
    original = _original_invoice(doc_id="orig-10", number="608", amount=60.0, doc_type=300)
    original["status"] = None  # not yet paid
    client = _FakeMorningClient(get_invoice_response=original)

    result = tools.create_combo_document_as_reference(client, "orig-10", payment_date="2026-07-12")

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
        client_id="client-1", amount=45.0, description="שירות ייעוץ", vat_included=True
    )
    assert payload["signed"] is True


def test_build_combo_document_payload_is_signed():
    payload = tools._build_combo_document_payload(
        client_id="client-1", amount=65.0, description="מכירה מיידית",
        vat_included=True, payment_date="2026-07-12"
    )
    assert payload["signed"] is True


def test_build_cancellation_payload_is_signed():
    original = _original_invoice()
    payload = tools._build_cancellation_payload(original)
    assert payload["signed"] is True


def test_build_payment_receipt_payload_is_signed():
    original = _original_invoice()
    payload = tools._build_payment_receipt_payload(original, payment_date="2026-07-12")
    assert payload["signed"] is True


def test_build_combo_closing_payload_is_signed():
    original = _original_invoice(doc_type=300)
    payload = tools._build_combo_closing_payload(original, payment_date="2026-07-12")
    assert payload["signed"] is True
