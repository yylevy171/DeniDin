"""
Feature 069 (mechanism move) — Task A / T006a.

Pins the three ledger-capture lifecycle log lines emitted by the ledgerer
(`LedgerEventManager.persist_recognized_event`) — `contracts/recognition-and-logging.md`
C6 (logging), `data-model.md` §4, FR-069-035.

INFO level, `[069]` prefix, one `now_local()` `time=` field per line (offset-aware).
`type` maps `בנק`→`deposit`, `הסכם`→`agreement`, `חשבונית`→`invoice`.

    [069] ledger capture recognized: type=<...> session=<id> chat=<id> time=<iso>
    [069] ledger event written: type=<...> event_id=<id> session=<id> chat=<id> time=<iso>
    [069] ledger capture declined by operator: type=<...> name=<repr> session=<id> reason=declined_by_operator time=<iso>

`none` → no INFO line at all (DEBUG only). No mocks — no external service on this path.
"""
import json
import logging
import re
from pathlib import Path

import pytest

from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.session_manager import SessionManager

CHAT_ID = "group-crumbs@g.us"
TRIGGER_TS = "2026-07-15T09:30:00+03:00"

_TIME_OFFSET = re.compile(r"time=\S*[+-]\d{2}:\d{2}")


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
        "bank_number": None, "bank_branch": None, "bank_account": None,
        "accounting_document_display_number": None, "reference": None, "reference_hint": None,
    }}


def _lines_069(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("[069]")]


# --------------------------------------------------------------------------- #

def test_recognized_and_written_lines_for_a_bank_capture(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    (event_id,) = lem.persist_recognized_event(_bank_verdict(trigger_id), session, completing_id)

    lines = _lines_069(caplog)
    recognized = [l for l in lines if l.startswith("[069] ledger capture recognized:")]
    written = [l for l in lines if l.startswith("[069] ledger event written:")]
    assert len(recognized) == 1
    assert len(written) == 1

    assert "type=deposit" in recognized[0]
    assert f"session={session.session_id}" in recognized[0]
    assert f"chat={session.whatsapp_chat}" in recognized[0]
    assert _TIME_OFFSET.search(recognized[0])

    assert "type=deposit" in written[0]
    assert f"event_id={event_id}" in written[0]
    assert f"session={session.session_id}" in written[0]
    assert f"chat={session.whatsapp_chat}" in written[0]
    assert _TIME_OFFSET.search(written[0])


def test_type_token_maps_agreement(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    verdict = {"verdict": "complete", "trigger_message_id": trigger_id, "event": {
        "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "דנה כהן",
        "description": "הסכם", "vat_status": None, "payer_name": None,
        "amount": None, "txn_date": None,
        "components": [{"amount": "4000", "description": "ריטיינר"}], "component_count": 1,
        "bank_number": None, "bank_branch": None, "bank_account": None,
        "accounting_document_display_number": None, "reference": None, "reference_hint": None,
    }}
    lem.persist_recognized_event(verdict, session, completing_id)

    lines = _lines_069(caplog)
    assert any(l.startswith("[069] ledger capture recognized:") and "type=agreement" in l
               for l in lines)
    assert any(l.startswith("[069] ledger event written:") and "type=agreement" in l
               for l in lines)
    assert not any("type=deposit" in l or "type=invoice" in l for l in lines)


def test_declined_line_format(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    verdict = {"verdict": "declined", "source_type": "בנק",
               "client_name_stated": "יוסי מהחנייה", "reason": "declined_by_operator"}
    lem.persist_recognized_event(verdict, session, completing_id)

    lines = _lines_069(caplog)
    declined = [l for l in lines if l.startswith("[069] ledger capture declined by operator:")]
    assert len(declined) == 1
    assert "type=deposit" in declined[0]
    assert "name='יוסי מהחנייה'" in declined[0]           # <client_name_stated!r>
    assert f"session={session.session_id}" in declined[0]
    assert "reason=declined_by_operator" in declined[0]
    assert _TIME_OFFSET.search(declined[0])
    assert not any(l.startswith("[069] ledger event written:") for l in lines)


def test_none_verdict_emits_no_info_line(lem, sm, caplog):
    session, trigger_id, completing_id = _build_session(sm)
    caplog.set_level(logging.INFO)

    lem.persist_recognized_event({"verdict": "none"}, session, completing_id)

    assert _lines_069(caplog) == []
