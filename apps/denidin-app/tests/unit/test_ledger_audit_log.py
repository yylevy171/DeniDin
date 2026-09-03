"""
Feature 069 — ledger-event audit log.

Every `LedgerEvent` that is actually persisted to disk emits exactly one
INFO-level `[AUDIT-LEDGER]` line carrying the event's COMPLETE JSON record.
The single call site is `LedgerEventManager.add_ledger_event` (the chokepoint
every persistence path funnels through), so both the Feature 069 post-turn
ledgerer and the Feature 025 reconciliation sweep are covered.

No mocks — no external service on this path.
"""
import json
import logging
import re
from pathlib import Path

import pytest

from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.session_manager import SessionManager

CHAT_ID = "group-audit@g.us"
TRIGGER_TS = "2026-07-15T09:30:00+03:00"

_AUDIT_JSON = re.compile(r"\[AUDIT-LEDGER\].*\bjson=(\{.*\})\s*$")


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


@pytest.fixture
def lem(tmp_path, sm):
    manager = LedgerEventManager(storage_dir=str(tmp_path / "events"))
    manager.session_manager = sm
    return manager


def _build_session(sm):
    trigger_id = sm.add_message(chat_id=CHAT_ID, role="user", content="הפקדה מהלקוחה דנה כהן",
                                user_role="godfather", sender="972500000002",
                                sender_name="בעל הבית")
    completing_id = sm.add_message(chat_id=CHAT_ID, role="assistant", content="רשמתי.",
                                   user_role="godfather")
    session = sm.get_session(CHAT_ID)
    path = Path(sm.storage_dir) / session.session_id / "messages" / f"{trigger_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["timestamp"] = TRIGGER_TS
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return session, trigger_id, completing_id


def _bank_verdict(trigger_id):
    return {"verdict": "complete", "trigger_message_id": trigger_id, "event": {
        "source_type": "בנק", "event_subtype": "הפקדה", "client_name": "דנה כהן",
        "description": "הפקדה בנקאית", "amount": "5000", "txn_date": "2026-07-15",
        "vat_status": None, "payer_name": None, "components": [], "component_count": 0,
        "bank_number": "12", "bank_branch": "345", "bank_account": "678901",
        "accounting_document_display_number": None, "reference": None, "reference_hint": None,
    }}


def _agreement_verdict(trigger_id):
    return {"verdict": "complete", "trigger_message_id": trigger_id, "event": {
        "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "דנה כהן",
        "description": "הסכם שכר טרחה", "vat_status": None, "payer_name": "איגוד העובדים",
        "amount": None, "txn_date": None,
        "components": [
            {"amount": "4000", "description": "ריטיינר חודשי"},
            {"amount": None, "percent": "12", "description": "בונוס הצלחה"},
        ],
        "component_count": 2,
        "bank_number": None, "bank_branch": None, "bank_account": None,
        "accounting_document_display_number": None, "reference": None, "reference_hint": None,
    }}


def _audit_payloads(caplog):
    out = []
    for rec in caplog.records:
        m = _AUDIT_JSON.search(rec.getMessage())
        if m:
            out.append(json.loads(m.group(1)))
    return out


def _events_on_disk(lem):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(Path(lem.storage_dir).glob("*.json"))]


# --------------------------------------------------------------------------- #

def test_one_audit_line_per_persisted_event_with_full_json(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    (event_id,) = lem.persist_recognized_event(_bank_verdict(trigger_id), session, completing_id)

    payloads = _audit_payloads(caplog)
    assert len(payloads) == 1
    (disk_record,) = _events_on_disk(lem)
    # the audit payload IS the persisted record, byte-for-byte
    assert payloads[0] == disk_record
    assert payloads[0]["event_id"] == event_id
    assert payloads[0]["bank_account"] == "678901"
    assert payloads[0]["amount"] == 5000


def test_multi_component_agreement_audits_every_file(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    created = lem.persist_recognized_event(_agreement_verdict(trigger_id), session, completing_id)

    assert len(created) == 2
    payloads = _audit_payloads(caplog)
    assert len(payloads) == 2
    assert sorted(p["event_id"] for p in payloads) == sorted(created)
    assert {p["source_type"] for p in payloads} == {"הסכם"}
    by_id = {p["event_id"]: p for p in payloads}
    for disk_record in _events_on_disk(lem):
        assert by_id[disk_record["event_id"]] == disk_record


def test_declined_and_none_emit_no_audit_line(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    lem.persist_recognized_event(
        {"verdict": "declined", "source_type": "בנק",
         "client_name_stated": "יוסי", "reason": "declined_by_operator"},
        session, completing_id)
    lem.persist_recognized_event({"verdict": "none"}, session, completing_id)

    assert _audit_payloads(caplog) == []
