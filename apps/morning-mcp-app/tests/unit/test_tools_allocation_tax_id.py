"""Feature 098: mandatory client ID above the allocation threshold.

A tax invoice (305) or tax invoice/receipt (320) whose pre-VAT amount EXCEEDS
the threshold (5,000) must never be sent to Morning for a client without a
9-digit ID. Everything else behaves exactly as before.

Pure helpers are tested directly. The tools are driven with a fake
MorningClient - a stand-in for the third-party Morning API boundary, injected
by dependency injection (same pattern as test_tools_document_creation.py;
CONSTITUTION §I/§V) - so each test can assert that nothing was sent to Morning.
"""
import pytest

from denidin_mcp_morning import tools
from denidin_mcp_morning.tools import (
    DEFAULT_INVOICING_RULES,
    ClientTaxIdRequiredError,
    InvoicingRules,
    _enforce_allocation_tax_id,
    _exceeds_allocation_threshold,
    _has_valid_tax_id,
    _pre_vat_amount,
)

VALID_TAX_ID = "308253681"
CLIENT_NAME = "לקוח בדיקה"
CREATED_ID = "new-doc-1"


def _created_document(doc_type=320, amount=12000.0):
    """A minimal real-shaped GET /documents/{id} response for the re-fetch
    every create_* tool does after creating (bugfix-028 A4)."""
    return {
        "id": CREATED_ID,
        "number": "70001",
        "type": doc_type,
        "documentType": doc_type,
        "client": {"id": "client-1", "name": CLIENT_NAME},
        "date": "2026-10-05",
        "currency": "ILS",
        "vatType": 1,
        "income": [{"description": "x", "quantity": 1, "price": amount, "vatType": 1}],
        "amount": amount,
        "total": amount,
    }


class _FakeMorningClient:
    """Records calls; returns pre-set responses. `tax_id` controls the one
    client every lookup returns (search and GET by id alike)."""

    def __init__(self, tax_id=None, original=None, created_type=320):
        record = {"id": "client-1", "name": CLIENT_NAME, "active": True, "phone": "", "emails": []}
        if tax_id is not None:
            record["taxId"] = tax_id
        self._client_record = record
        self._original = original
        self._created = _created_document(created_type)
        self.create_invoice_calls = []
        self.get_client_calls = []

    def search_clients(self, payload):
        return {"items": [dict(self._client_record)], "total": 1}

    def get_client(self, client_id):
        self.get_client_calls.append(client_id)
        return dict(self._client_record)

    def get_invoice(self, internal_morning_id):
        if internal_morning_id == CREATED_ID:
            return self._created
        if self._original is not None and internal_morning_id == self._original["id"]:
            return self._original
        raise LookupError(f"no such invoice: {internal_morning_id}")

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return {"id": CREATED_ID, "number": "70001"}


def _transaction_account(total=10000.0, status=0):
    return {
        "id": "ta-1",
        "number": "40001",
        "type": 300,
        "status": status,
        "client": {"id": "client-1", "name": CLIENT_NAME},
        "currency": "ILS",
        "lang": "he",
        "total": total,
    }


# ---------------------------------------------------------------------------
# _has_valid_tax_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tax_id", ["308253681", " 308253681 ", "000000018"])
def test_nine_digits_is_a_valid_tax_id(tax_id):
    assert _has_valid_tax_id(tax_id) is True


@pytest.mark.parametrize("tax_id", [None, "", "12345678", "1234567890", "30825368a", "308-253-681", "   "])
def test_anything_but_nine_digits_is_not_a_valid_tax_id(tax_id):
    assert _has_valid_tax_id(tax_id) is False


# ---------------------------------------------------------------------------
# _pre_vat_amount / _exceeds_allocation_threshold
# ---------------------------------------------------------------------------


def _payload(doc_type, price, vat_type, quantity=1, extra_lines=()):
    """Same shape as the real builders: `vat_type` on the document and on each line."""
    income = [{"price": price, "quantity": quantity}] + list(extra_lines)
    income = [{"vatType": vat_type, **line} for line in income]
    return {"type": doc_type, "vatType": vat_type, "income": income}


def test_pre_vat_amount_strips_vat_when_prices_include_it():
    """5,900 including 18% VAT is exactly 5,000 before VAT (UAT 3.2)."""
    assert _pre_vat_amount(_payload(320, 5900, 1), 0.18) == 5000.00


def test_pre_vat_amount_is_the_price_when_vat_is_not_included():
    assert _pre_vat_amount(_payload(305, 5001, 0), 0.18) == 5001.00


def test_pre_vat_amount_reads_the_line_not_the_document_vat_type():
    """bugfix-071's corrected shape: document `vatType: 0` (regular), line
    `vatType: 1` (price includes VAT). 5,900 including VAT is 5,000 before it."""
    payload = {"type": 320, "vatType": 0,
               "income": [{"description": "x", "quantity": 1, "price": 5900, "vatType": 1}]}
    assert _pre_vat_amount(payload, 0.18) == 5000.00
    assert not _exceeds_allocation_threshold(payload, DEFAULT_INVOICING_RULES)


def test_pre_vat_amount_sums_price_times_quantity_over_all_lines():
    payload = _payload(305, 1000, 0, quantity=3, extra_lines=[{"price": 2500, "quantity": 1}])
    assert _pre_vat_amount(payload, 0.18) == 5500.00


def test_exactly_the_threshold_does_not_exceed_it():
    """The rule is "עולה על" - strictly greater."""
    assert _exceeds_allocation_threshold(_payload(320, 5900, 1), DEFAULT_INVOICING_RULES) is False
    assert _exceeds_allocation_threshold(_payload(305, 5000, 0), DEFAULT_INVOICING_RULES) is False


def test_just_above_the_threshold_exceeds_it():
    assert _exceeds_allocation_threshold(_payload(305, 5001, 0), DEFAULT_INVOICING_RULES) is True


@pytest.mark.parametrize("doc_type", [300, 330, 400])
def test_out_of_scope_document_types_never_exceed(doc_type):
    assert _exceeds_allocation_threshold(_payload(doc_type, 50000, 0), DEFAULT_INVOICING_RULES) is False


# ---------------------------------------------------------------------------
# _enforce_allocation_tax_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_type", [305, 320])
def test_enforce_refuses_above_threshold_without_an_id(doc_type):
    with pytest.raises(ClientTaxIdRequiredError) as excinfo:
        _enforce_allocation_tax_id("t", _payload(doc_type, 8000, 0), None, CLIENT_NAME, DEFAULT_INVOICING_RULES)
    message = str(excinfo.value)
    assert CLIENT_NAME in message
    assert "5,000" in message
    assert "מספר הקצאה" in message


def test_enforce_allows_above_threshold_with_an_id():
    _enforce_allocation_tax_id("t", _payload(320, 12000, 1), VALID_TAX_ID, CLIENT_NAME, DEFAULT_INVOICING_RULES)


def test_enforce_treats_a_malformed_stored_id_as_missing():
    with pytest.raises(ClientTaxIdRequiredError):
        _enforce_allocation_tax_id("t", _payload(320, 12000, 1), "12345678", CLIENT_NAME, DEFAULT_INVOICING_RULES)


def test_enforce_allows_at_or_below_threshold_without_an_id():
    _enforce_allocation_tax_id("t", _payload(320, 4500, 1), None, CLIENT_NAME, DEFAULT_INVOICING_RULES)
    _enforce_allocation_tax_id("t", _payload(320, 5900, 1), None, CLIENT_NAME, DEFAULT_INVOICING_RULES)


@pytest.mark.parametrize("doc_type", [300, 330, 400])
def test_enforce_never_refuses_out_of_scope_types(doc_type):
    _enforce_allocation_tax_id("t", _payload(doc_type, 50000, 0), None, CLIENT_NAME, DEFAULT_INVOICING_RULES)


def test_enforce_uses_the_configured_threshold_in_its_check_and_message():
    rules = InvoicingRules(allocation_threshold_nis=10000.0, vat_rate=0.18)
    _enforce_allocation_tax_id("t", _payload(305, 7000, 0), None, CLIENT_NAME, rules)
    with pytest.raises(ClientTaxIdRequiredError) as excinfo:
        _enforce_allocation_tax_id("t", _payload(305, 10001, 0), None, CLIENT_NAME, rules)
    assert "10,000" in str(excinfo.value)


def test_refusal_is_audit_logged(caplog):
    with pytest.raises(ClientTaxIdRequiredError):
        _enforce_allocation_tax_id("create_invoice", _payload(305, 8000, 0), None, CLIENT_NAME, DEFAULT_INVOICING_RULES)
    assert any("REFUSED" in r.getMessage() and "client_tax_id_required" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# The three tools
# ---------------------------------------------------------------------------


def test_create_invoice_above_threshold_without_id_sends_nothing():
    client = _FakeMorningClient(tax_id=None, created_type=305)
    with pytest.raises(ClientTaxIdRequiredError):
        tools.create_invoice(client, CLIENT_NAME, 8000.0, "שירות", vat_included=False, name_resolved=True)
    assert client.create_invoice_calls == []


def test_create_invoice_above_threshold_with_id_is_created():
    client = _FakeMorningClient(tax_id=VALID_TAX_ID, created_type=305)
    tools.create_invoice(client, CLIENT_NAME, 8000.0, "שירות", vat_included=False, name_resolved=True)
    assert len(client.create_invoice_calls) == 1


def test_create_combo_document_above_threshold_without_id_sends_nothing():
    client = _FakeMorningClient(tax_id=None)
    with pytest.raises(ClientTaxIdRequiredError):
        tools.create_combo_document(
            client, CLIENT_NAME, 12000.0, "שירות", vat_included=True,
            payment_date="2026-10-01", name_resolved=True,
        )
    assert client.create_invoice_calls == []


def test_create_combo_document_above_threshold_with_id_is_created():
    client = _FakeMorningClient(tax_id=VALID_TAX_ID)
    tools.create_combo_document(
        client, CLIENT_NAME, 12000.0, "שירות", vat_included=True,
        payment_date="2026-10-01", name_resolved=True,
    )
    assert len(client.create_invoice_calls) == 1


def test_create_combo_document_below_threshold_without_id_is_created():
    client = _FakeMorningClient(tax_id=None)
    tools.create_combo_document(
        client, CLIENT_NAME, 4500.0, "שירות", vat_included=True,
        payment_date="2026-10-01", name_resolved=True,
    )
    assert len(client.create_invoice_calls) == 1


def test_create_combo_document_respects_a_custom_threshold():
    client = _FakeMorningClient(tax_id=None)
    rules = InvoicingRules(allocation_threshold_nis=10000.0, vat_rate=0.18)
    tools.create_combo_document(
        # 8,260 including VAT = 7,000 before VAT: above the default 5,000, below 10,000.
        # (A 320 always includes VAT - bugfix-071.)
        client, CLIENT_NAME, 8260.0, "שירות", vat_included=True,
        payment_date="2026-10-01", name_resolved=True, rules=rules,
    )
    assert len(client.create_invoice_calls) == 1


def test_create_transaction_account_is_never_checked():
    client = _FakeMorningClient(tax_id=None, created_type=300)
    tools.create_transaction_account(client, CLIENT_NAME, 12000.0, "שירות", vat_included=True, name_resolved=True)
    assert len(client.create_invoice_calls) == 1


def test_closing_a_transaction_account_above_threshold_without_id_sends_nothing():
    client = _FakeMorningClient(tax_id=None, original=_transaction_account(10000.0))
    with pytest.raises(ClientTaxIdRequiredError):
        tools.create_combo_document_as_reference(client, "ta-1", payment_date="2026-10-01")
    assert client.create_invoice_calls == []
    assert client.get_client_calls == ["client-1"]


def test_closing_a_transaction_account_reads_the_clients_current_id():
    """The original's client snapshot has no ID; the client's current record
    does (added after the 300 was created, UAT 2.1) - so it's created."""
    client = _FakeMorningClient(tax_id=VALID_TAX_ID, original=_transaction_account(10000.0))
    tools.create_combo_document_as_reference(client, "ta-1", payment_date="2026-10-01")
    assert len(client.create_invoice_calls) == 1


def test_closing_a_transaction_account_below_threshold_makes_no_client_lookup():
    client = _FakeMorningClient(tax_id=None, original=_transaction_account(3000.0))
    tools.create_combo_document_as_reference(client, "ta-1", payment_date="2026-10-01")
    assert len(client.create_invoice_calls) == 1
    assert client.get_client_calls == []
