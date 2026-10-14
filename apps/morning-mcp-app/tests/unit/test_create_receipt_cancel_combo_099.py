"""Feature 099 - create_receipt cancels a 320 with a negative receipt.

Mechanism verified against the real Morning sandbox (2026-10-09, see the
feature's research.md): a type-400 with linkedDocumentIds=[<320 id>] and a
negative payment price is accepted. Uses a fake MorningClient at the network
boundary only (CONSTITUTION §I/§V), like test_mark_invoice_paid.py."""
import json

import pytest

from denidin_mcp_morning.tools import create_receipt
from denidin_mcp_morning.utils.time_utils import now_local


class _FakeMorningClient:
    def __init__(self, original):
        self._original = original
        self.create_invoice_calls = []

    def get_invoice(self, internal_morning_id):
        if internal_morning_id == self._original["id"]:
            return self._original
        return {**self._original, "id": internal_morning_id, "type": 400, "number": 9001, "amount": -self._original["amount"],
                "status": 1, "payment": [], "linkedDocuments": []}

    def create_invoice(self, payload):
        self.create_invoice_calls.append(payload)
        return {"id": "cancel-400", "number": 9001}


def _combo(payment=None, linked=None, client=True, total=1000):
    doc = {
        "id": "doc-320", "number": 60720, "type": 320, "amount": total, "total": total,
        "currency": "ILS", "lang": "he", "status": 1,
        "payment": [payment or {"type": 4, "price": total, "bankName": "12", "bankBranch": "345",
                                "bankAccount": "678901", "name": "העברה בנקאית"}],
        "linkedDocuments": linked or [],
    }
    if client:
        doc["client"] = {"id": "client-1", "name": "לקוח בדיקה"}
    return doc


def test_cancelling_receipt_payload_is_a_negative_linked_400_with_the_first_payments_details():
    client = _FakeMorningClient(_combo())

    create_receipt(client, "doc-320")

    assert len(client.create_invoice_calls) == 1
    payload = client.create_invoice_calls[0]
    assert payload["type"] == 400
    assert payload["linkedDocumentIds"] == ["doc-320"]
    assert payload["client"] == {"self": False, "id": "client-1"}
    assert payload["description"] == "ביטול חשבונית מס קבלה 60720"
    assert len(payload["payment"]) == 1
    line = payload["payment"][0]
    assert line["price"] == -1000
    assert line["date"] == now_local().date().isoformat()
    assert (line["type"], line["bankName"], line["bankBranch"], line["bankAccount"]) == (4, "12", "345", "678901")


def test_cheque_details_of_the_first_payment_are_copied():
    client = _FakeMorningClient(_combo(payment={
        "type": 2, "price": 1000, "chequeNum": "987654", "bankName": "12", "bankBranch": "345", "bankAccount": "678901"}))

    create_receipt(client, "doc-320")

    line = client.create_invoice_calls[0]["payment"][0]
    assert (line["type"], line["chequeNum"], line["bankName"]) == (2, "987654", "12")


def test_app_payment_type_of_the_first_payment_is_copied():
    client = _FakeMorningClient(_combo(payment={"type": 10, "price": 1000, "appType": 1, "transactionId": "BIT1"}))

    create_receipt(client, "doc-320")

    line = client.create_invoice_calls[0]["payment"][0]
    assert (line["type"], line["appType"], line["transactionId"]) == (10, 1, "BIT1")


def test_a_320_whose_cash_side_is_already_reversed_is_refused_and_nothing_is_created():
    client = _FakeMorningClient(_combo(linked=[{"type": 400, "number": 80868, "amount": -1000}]))

    result = json.loads(create_receipt(client, "doc-320"))

    assert result == {"status": "error", "reason": "original_already_cancelled"}
    assert client.create_invoice_calls == []


def test_a_320_that_only_has_its_330_still_gets_the_negative_400():
    """The 330 is created first; the 400 that follows it must not be refused (REQ-099-02/03)."""
    client = _FakeMorningClient(_combo(linked=[{"type": 330, "number": 70415, "amount": 1000}]))

    create_receipt(client, "doc-320")

    assert len(client.create_invoice_calls) == 1


def test_an_ordinary_positive_linked_document_does_not_count_as_a_cancellation():
    client = _FakeMorningClient(_combo(linked=[{"type": 400, "number": 1, "amount": 50}]))

    create_receipt(client, "doc-320")

    assert len(client.create_invoice_calls) == 1


def test_a_320_not_linked_to_a_client_is_refused():
    client = _FakeMorningClient(_combo(client=False))

    result = json.loads(create_receipt(client, "doc-320"))

    assert result == {"status": "error", "reason": "original_not_linked_to_client"}
    assert client.create_invoice_calls == []


def test_passing_an_amount_when_cancelling_a_320_is_an_error():
    client = _FakeMorningClient(_combo())

    with pytest.raises(ValueError):
        create_receipt(client, "doc-320", amount=200)

    assert client.create_invoice_calls == []


def test_document_json_lists_every_linked_document_with_type_and_amount():
    """Feature 099: the cancel flow tells 'already cancelled' from the document
    details, so ALL linked documents (not just the first) must be visible."""
    from denidin_mcp_morning.formatters import format_invoice_json
    from denidin_mcp_morning.models import Invoice

    doc = json.loads(format_invoice_json(Invoice.model_validate({
        "id": "doc-320", "number": 60720, "type": 320, "amount": 1000, "total": 1000, "status": 1,
        "client": {"id": "client-1", "name": "לקוח בדיקה"},
        "linkedDocuments": [
            {"id": "a", "type": 330, "number": 70415, "amount": 1000},
            {"id": "b", "type": 400, "number": 80868, "amount": -1000},
        ],
    })))

    assert [(d["type"], d["amount"]) for d in doc["linked_documents"]] == [(330, 1000), (400, -1000)]
    assert doc["linked_document"]["type"] == 330
