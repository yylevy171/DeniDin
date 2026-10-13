"""Feature 066 - a cheque payment line carries its own number plus the account it
is drawn on; Bit / PayBox / cash lines are unchanged."""
import pytest

from denidin_mcp_morning.tools import _build_payment_line, create_combo_document, create_receipt


def test_cheque_line_has_type_2_bank_fields_and_the_cheque_number():
    line = _build_payment_line(500, "2026-10-01", "cheque", "12", "345", "678901", cheque_number="987654")

    assert line["type"] == 2
    assert (line["bankName"], line["bankBranch"], line["bankAccount"], line["chequeNum"]) == ("12", "345", "678901", "987654")
    assert line["price"] == 500


def test_cheque_number_is_ignored_for_other_methods():
    assert "chequeNum" not in _build_payment_line(500, "2026-10-01", "bank_transfer", "12", "345", "678901", cheque_number="1")
    assert "chequeNum" not in _build_payment_line(500, "2026-10-01", "cash", cheque_number="1")


@pytest.mark.parametrize("method,app_type", [("bit", 1), ("paybox", 3)])
def test_app_lines_are_type_10_with_the_right_app(method, app_type):
    line = _build_payment_line(500, "2026-10-01", method)
    assert (line["type"], line["appType"]) == (10, app_type)
    assert "bankName" not in line


def test_cash_line_is_type_1_with_only_date_and_price():
    line = _build_payment_line(500, "2026-10-01", "cash", "12", "345", "678901")
    assert line["type"] == 1 and "bankName" not in line


class _Client:
    def __init__(self):
        self.created = []

    def create_invoice(self, payload):
        self.created.append(payload)
        return {"id": "d1", "number": 1}

    def get_invoice(self, _id):
        return {"id": "d1", "number": 1, "type": 400, "total": 500, "amount": 500, "status": 1,
                "client": {"id": "c1", "name": "x"}, "payment": [], "linkedDocuments": []}

    def search_clients(self, *a, **k):  # pragma: no cover - not reached when resolution is stubbed
        raise AssertionError


def test_create_receipt_standalone_forwards_the_cheque_number(monkeypatch):
    from denidin_mcp_morning import tools
    from types import SimpleNamespace
    monkeypatch.setattr(tools, "_require_resolved_client", lambda *a, **k: SimpleNamespace(id="c1", name="לקוח", tax_id="123456789"))
    client = _Client()

    create_receipt(client, client_name="x", amount=500, description="צ'ק", payment_date="2026-10-01",
                   name_resolved=True, payment_method="cheque", bank_number="12", bank_branch="345",
                   bank_account="678901", cheque_number="987654")

    line = client.created[0]["payment"][0]
    assert (line["type"], line["chequeNum"], line["bankName"]) == (2, "987654", "12")


def test_create_combo_document_forwards_the_cheque_number(monkeypatch):
    from denidin_mcp_morning import tools
    from types import SimpleNamespace
    monkeypatch.setattr(tools, "_require_resolved_client", lambda *a, **k: SimpleNamespace(id="c1", name="לקוח", tax_id="123456789"))
    client = _Client()

    create_combo_document(client, "x", 500, "d", "2026-10-01", None, "cheque", "12", "345", "678901",
                          None, True, "987654")

    line = client.created[0]["payment"][0]
    assert (line["type"], line["chequeNum"]) == (2, "987654")
