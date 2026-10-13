"""Feature 066 - the backfill carries how a receipt was paid: a cheque keeps its number and bank
details, and a Morning "app" payment is named Bit or PayBox. (The backfill only ever writes
source_type חשבונית events, so the הפקדה flip has nothing to change here.)"""
import json

import pytest

import transform


def _raw_document(doc_id, display_number, creation_iso, amount):
    return {
        "id": doc_id, "number": display_number, "type": 400,
        "client": {"id": f"client-{doc_id}", "name": "Test Client Ltd."},
        "status": 2, "amount": amount, "total": amount, "vat": 0.0,
        "documentDate": creation_iso[:10], "creationDate": creation_iso,
        "income": [{"description": "Consulting", "quantity": 1, "price": amount, "amountTotal": amount}],
    }


def _run(tmp_path, payment):
    input_dir, output_dir = tmp_path / "input", tmp_path / "output"
    input_dir.mkdir()
    doc = _raw_document("doc-a", 50001, "2026-10-01T09:30:00", amount=1500.0)
    doc["payment"] = [payment]
    (input_dir / "doc-a.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert transform.main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)]) == 0
    (path,) = (output_dir / "events").glob("*.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_a_cheque_receipt_keeps_its_number_and_bank_details(tmp_path):
    event = _run(tmp_path, {"name": "צ'ק", "type": 2, "date": "2026-10-01", "amount": 1500.0,
                            "chequeNum": "80000062", "bankName": "11", "bankBranch": "117", "bankAccount": "121022"})
    assert (event["source_type"], event["check_number"]) == ("חשבונית", "80000062")
    assert (event["bank_number"], event["bank_branch"], event["bank_account"]) == ("11", "117", "121022")


@pytest.mark.parametrize("app_type,label", [(1, "ביט"), (3, "פייבוקס")])
def test_an_app_receipt_is_named_bit_or_paybox(tmp_path, app_type, label):
    event = _run(tmp_path, {"name": "אפליקציית תשלום", "type": 10, "appType": app_type,
                            "date": "2026-10-01", "amount": 1500.0})
    assert event["accounting_document_payment_method"] == label and event["check_number"] is None
