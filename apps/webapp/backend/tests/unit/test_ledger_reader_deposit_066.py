"""Feature 066 - the webapp shows every method of a הפקדה event like a bank deposit."""
import json
from pathlib import Path

import pytest

from webapp_backend.ledger_reader import LedgerReader


def _deposit(events_dir: Path, event_id: str, subtype: str, **fields) -> None:
    record = {"event_id": event_id, "source_type": "הפקדה", "event_subtype": subtype,
              "client_name": "דנה כהן", "amount": 500, "description": "d",
              "event_datetime": "01/10/2026 10:00", "txn_date": "01/10/2026",
              "vat_status": "כולל", "bank_number": None, "bank_branch": None,
              "bank_account": None, "check_number": None}
    record.update(fields)
    (events_dir / f"{event_id}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    (tmp_path / "events").mkdir()
    return tmp_path


def _keys(root, event_id):
    detail = LedgerReader(str(root)).get_event_detail(event_id)
    assert not detail.get("unsupported")
    return {f["key"]: f for f in detail["fields"]}


@pytest.mark.parametrize("subtype", ["בנק", "ביט", "פייבוקס", "צ׳ק", "מזומן"])
def test_every_method_is_listed_and_has_a_detail_view(root, subtype):
    _deposit(root / "events", "B1", subtype)
    detail = _keys(root, "B1")
    assert detail["source_type"]["value"] == "הפקדה" and detail["event_subtype"]["value"] == subtype
    assert detail["vat_status"]["value"] == "כולל"


def test_bank_and_cheque_show_the_bank_triplet_but_bit_does_not(root):
    for eid, sub in (("B1", "בנק"), ("B2", "צ׳ק")):
        _deposit(root / "events", eid, sub, bank_number="12", bank_branch="345", bank_account="678901")
    _deposit(root / "events", "B3", "ביט")  # the manager stores null bank fields for a Bit payment
    assert {"bank_number", "bank_branch", "bank_account"} <= set(_keys(root, "B1"))
    assert {"bank_number", "bank_branch", "bank_account"} <= set(_keys(root, "B2"))
    assert "bank_number" not in _keys(root, "B3")


def test_check_number_is_shown_for_a_cheque_only(root):
    _deposit(root / "events", "B1", "צ׳ק", check_number="987654")
    _deposit(root / "events", "B2", "בנק")  # the manager stores a null check_number for a bank transfer
    assert _keys(root, "B1")["check_number"]["value"] == "987654"
    assert "check_number" not in _keys(root, "B2")


def test_a_pre_066_bank_event_still_renders_until_it_is_migrated(root):
    _deposit(root / "events", "B1", "הפקדה", source_type="בנק", bank_number="12")
    detail = LedgerReader(str(root)).get_event_detail("B1")
    assert not detail.get("unsupported")


def _receipt(events_dir: Path, event_id: str, **fields) -> None:
    record = {"event_id": event_id, "source_type": "חשבונית", "event_subtype": "קבלה",
              "client_name": "דנה כהן", "amount": 500, "description": "d",
              "event_datetime": "01/10/2026 10:00", "txn_date": "01/10/2026", "vat_status": "כולל",
              "accounting_document_display_number": "50001", "accounting_document_status_label": "מסמך סגור",
              "accounting_document_payment_method": "צ'ק", "bank_number": "11", "bank_branch": "117",
              "bank_account": "121022", "check_number": "80000062"}
    record.update(fields)
    (events_dir / f"{event_id}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def test_a_receipt_paid_by_cheque_shows_the_cheque_number_and_bank_details(root):
    _receipt(root / "events", "C1")
    detail = _keys(root, "C1")
    assert detail["check_number"]["value"] == "80000062" and detail["bank_number"]["value"] == "11"


def test_a_receipt_paid_by_bit_shows_no_bank_or_cheque_fields(root):
    _receipt(root / "events", "C2", accounting_document_payment_method="ביט", bank_number=None,
             bank_branch=None, bank_account=None, check_number=None)
    detail = _keys(root, "C2")
    assert detail["accounting_document_payment_method"]["value"] == "ביט"
    assert not {"check_number", "bank_number"} & detail.keys()
