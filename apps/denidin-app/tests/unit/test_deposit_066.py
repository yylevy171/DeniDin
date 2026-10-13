"""Feature 066 - every incoming-funds event is source_type הפקדה; its subtype is the
METHOD (בנק / ביט / פייבוקס / צ׳ק / מזומן). Real ledgerer + real SessionManager (no
mocks), real extractor parsing, real tool schema."""
import json

import pytest

from src.handlers.extractors.image_extractor import (
    DEPOSIT_DOC_TYPES, DEPOSIT_SUBTYPE_BY_DOC_TYPE, REQUIRED_FIELDS, _parse_vision_json,
)
from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.ledger_event_recognizer import LEDGER_EVENT_TOOL, build_ledger_stash_text
from src.capabilities.media_analysis.handler import build_media_stash_text
from tests.unit.test_ledgerer import _bank_verdict, _build_session, _load_events, lem, sm  # noqa: F401 (fixtures)


# ---- extractor -------------------------------------------------------------------

@pytest.mark.parametrize("doc_type,subtype", [("bank", "בנק"), ("bit", "ביט"), ("paybox", "פייבוקס"), ("check", "צ׳ק")])
def test_each_deposit_doc_type_maps_to_its_method(doc_type, subtype):
    assert DEPOSIT_SUBTYPE_BY_DOC_TYPE[doc_type] == subtype
    assert doc_type in DEPOSIT_DOC_TYPES


def test_required_fields_per_deposit_doc_type():
    assert set(REQUIRED_FIELDS["bit"]) == {"payer_name", "amount", "txn_date"}
    assert set(REQUIRED_FIELDS["paybox"]) == {"payer_name", "amount", "txn_date"}
    assert set(REQUIRED_FIELDS["check"]) == {"payer_name", "amount", "check_number", "bank_number", "bank_branch", "bank_account"}
    assert "check_number" not in REQUIRED_FIELDS["bank"]


@pytest.mark.parametrize("doc_type", ["bit", "paybox", "check"])
def test_vision_json_with_a_new_doc_type_is_kept_not_downgraded_to_unknown(doc_type):
    parsed = _parse_vision_json(json.dumps({"doc_type": doc_type, "extracted_text": "x", "fields": {}}))
    assert parsed["doc_type"] == doc_type


def test_a_cheque_missing_its_number_reports_it_missing():
    fields = {"payer_name": "דנה", "amount": 500, "bank_number": "12", "bank_branch": "345", "bank_account": "6"}
    parsed = _parse_vision_json(json.dumps({"doc_type": "check", "extracted_text": "x", "fields": fields}))
    assert parsed["missing_required_fields"] == ["check_number"]


def test_a_bit_payment_needs_no_bank_details():
    fields = {"payer_name": "דנה", "amount": 500, "txn_date": "01/10/2026"}
    parsed = _parse_vision_json(json.dumps({"doc_type": "bit", "extracted_text": "x", "fields": fields}))
    assert parsed["missing_required_fields"] == []


# ---- stash -----------------------------------------------------------------------

def _stash(doc_type, fields):
    return build_media_stash_text({"doc_type": doc_type, "extracted_text": "הטקסט", "fields": fields}, "image")


def test_bit_stash_names_the_method_and_has_no_bank_lines():
    stash = _stash("bit", {"payer_name": "דנה", "amount": 500, "txn_date": "01/10/2026"})
    assert "אמצעי תשלום: ביט" in stash and "ביט" in stash.splitlines()[0]
    assert "מספר בנק" not in stash


def test_cheque_stash_carries_bank_triplet_and_the_cheque_number():
    stash = _stash("check", {"payer_name": "דנה", "amount": 500, "check_number": "987654",
                             "bank_number": "12", "bank_branch": "345", "bank_account": "678901"})
    assert "אמצעי תשלום: צ׳ק" in stash
    assert "מספר צ'ק: 987654" in stash and "מספר בנק: 12" in stash


def test_bank_stash_still_has_bank_triplet_and_no_cheque_number():
    stash = _stash("bank", {"payer_name": "דנה", "amount": 500, "txn_date": "01/10/2026",
                            "bank_number": "12", "bank_branch": "345", "bank_account": "678901"})
    assert "אמצעי תשלום: בנק" in stash and "מספר צ'ק" not in stash


# ---- recognizer tool schema ------------------------------------------------------

def _props():
    return LEDGER_EVENT_TOOL["parameters"]["properties"]


def test_source_type_enum_has_hafkada_and_not_bank():
    assert set(_props()["source_type"]["enum"]) == {"הסכם", "הפקדה", "חשבונית"}


def test_event_subtype_enum_carries_every_method():
    enum = set(_props()["event_subtype"]["enum"])
    assert {"בנק", "ביט", "פייבוקס", "צ׳ק", "מזומן"} <= enum and "הפקדה" not in enum


def test_check_number_is_a_required_nullable_property_of_the_strict_schema():
    assert "check_number" in _props()
    assert "check_number" in LEDGER_EVENT_TOOL["parameters"]["required"]


# ---- ledgerer / manager ----------------------------------------------------------

def test_cheque_event_persists_its_number_and_bank_triplet(lem, sm):
    session, trigger_id, completing_id = _build_session(sm)
    lem.persist_recognized_event(_bank_verdict(trigger_id, event_subtype="צ׳ק", check_number="987654"), session, completing_id)

    (record,) = _load_events(lem)
    assert (record["source_type"], record["event_subtype"], record["check_number"]) == ("הפקדה", "צ׳ק", "987654")
    assert record["bank_number"] == "12" and record["event_id"].startswith("B") and record["vat_status"] == "כולל"


def test_check_number_is_dropped_for_a_non_cheque_deposit(lem, sm):
    session, trigger_id, completing_id = _build_session(sm)
    lem.persist_recognized_event(_bank_verdict(trigger_id, check_number="999"), session, completing_id)

    (record,) = _load_events(lem)
    assert record["check_number"] is None


def test_bit_event_is_a_hafkada_with_subtype_bit(lem, sm):
    session, trigger_id, completing_id = _build_session(sm)
    lem.persist_recognized_event(
        _bank_verdict(trigger_id, event_subtype="ביט", bank_number=None, bank_branch=None, bank_account=None),
        session, completing_id)

    (record,) = _load_events(lem)
    assert (record["source_type"], record["event_subtype"], record["vat_status"]) == ("הפקדה", "ביט", "כולל")


def test_cash_without_a_date_is_still_a_complete_event():
    gaps = LedgerEventManager._mandatory_field_gaps("הפקדה", {
        "event_subtype": "מזומן", "client_name": "דנה", "amount": 500, "description": "מזומן", "txn_date": None})
    assert gaps == []


def test_other_methods_without_a_date_are_flagged_incomplete():
    gaps = LedgerEventManager._mandatory_field_gaps("הפקדה", {
        "event_subtype": "ביט", "client_name": "דנה", "amount": 500, "description": "ביט", "txn_date": None})
    assert gaps == ["תאריך עסקה"]


def test_same_content_same_day_is_a_duplicate_but_a_different_method_is_not(lem, sm):
    session, trigger_id, completing_id = _build_session(sm)
    lem.persist_recognized_event(_bank_verdict(trigger_id, event_subtype="ביט", bank_number=None,
                                               bank_branch=None, bank_account=None, txn_date=None), session, completing_id)
    session2, t2, c2 = _build_session(sm)
    again = lem.persist_recognized_event(_bank_verdict(t2, event_subtype="ביט", bank_number=None,
                                                       bank_branch=None, bank_account=None, txn_date=None), session2, c2)
    session3, t3, c3 = _build_session(sm)
    other = lem.persist_recognized_event(_bank_verdict(t3, event_subtype="פייבוקס", bank_number=None,
                                                       bank_branch=None, bank_account=None, txn_date=None), session3, c3)

    assert again == [] and len(other) == 1
    assert sorted(r["event_subtype"] for r in _load_events(lem)) == ["ביט", "פייבוקס"]


def test_a_dated_deposit_reported_twice_is_a_duplicate(lem, sm):
    """The verdict carries txn_date as ISO while the stored record holds DD/MM/YYYY
    (stored format unchanged) - the fingerprint must compare them in one form."""
    session, trigger_id, completing_id = _build_session(sm)
    first = lem.persist_recognized_event(_bank_verdict(trigger_id, txn_date="2026-07-15"), session, completing_id)
    session2, t2, c2 = _build_session(sm)
    second = lem.persist_recognized_event(_bank_verdict(t2, txn_date="2026-07-15"), session2, c2)

    assert len(first) == 1 and second == []
    (record,) = _load_events(lem)
    assert record["txn_date"] == "15/07/2026"


def test_a_different_transaction_date_is_not_a_duplicate(lem, sm):
    session, trigger_id, completing_id = _build_session(sm)
    lem.persist_recognized_event(_bank_verdict(trigger_id, txn_date="2026-07-15"), session, completing_id)
    session2, t2, c2 = _build_session(sm)
    second = lem.persist_recognized_event(_bank_verdict(t2, txn_date="2026-07-16"), session2, c2)

    assert len(second) == 1


# ---- Morning documents paid by cheque / Bit / PayBox (backfill + live reconciler) -------

def _receipt_event(payment):
    from tests.unit.test_ledger_event_manager import _accounting_event
    return _accounting_event(type=400, type_name="קבלה", display_number="50001", payment=payment)


def test_a_cheque_receipt_keeps_its_cheque_number_and_bank_details(lem):
    payment = {"method": "צ'ק", "type": 2, "date": "2026-10-01", "amount": 1500, "bank_number": "11",
               "bank_branch": "117", "bank_account": "121022", "app_type": None, "cheque_number": "80000062"}
    (event_id,) = lem.add_ledger_events_from_call(
        session_id="s", call_arguments=_receipt_event(payment), message_id="m", message_timestamp=None)
    record = next(r for r in _load_events(lem) if r["event_id"] == event_id)
    assert (record["check_number"], record["bank_number"], record["bank_account"]) == ("80000062", "11", "121022")


@pytest.mark.parametrize("app_type,label", [(1, "ביט"), (3, "פייבוקס")])
def test_an_app_payment_is_named_bit_or_paybox(lem, app_type, label):
    payment = {"method": "אפליקציית תשלום", "type": 10, "date": "2026-10-01", "amount": 2500, "bank_number": None,
               "bank_branch": None, "bank_account": None, "app_type": app_type, "cheque_number": None}
    (event_id,) = lem.add_ledger_events_from_call(
        session_id="s", call_arguments=_receipt_event(payment), message_id="m", message_timestamp=None)
    record = next(r for r in _load_events(lem) if r["event_id"] == event_id)
    assert record["accounting_document_payment_method"] == label and record["check_number"] is None
