"""
Feature 069 (mechanism move) — Task A / T005a.

Pins the **ledgerer** — `LedgerEventManager.persist_recognized_event(verdict,
session, completing_message_id)` — the mechanical, ZERO-AI consumer of the
recognition call's tri-state verdict
(`contracts/recognition-and-logging.md` C6, `data-model.md` §3).

What the ledgerer does (and only this):
  - mints `event_id` / `event_datetime` / `captured_at` (+ `agreement_id` /
    `component_id` for `הסכם`),
  - explodes `הסכם` `components` → one immutable JSON file per component,
  - dedups + persists,
  - back-links the new `event_id`(s) onto the **completing** message's
    `Message.ledger_event_ids` (NOT the trigger message),
  - makes NO OpenAI call, NO client resolution, NO Morning lookup, NO ledger query.

`event_datetime` is the **hard pointer** (option A, 2026-09-02): the trigger
message's own persisted `Message.timestamp` (an Asia/Jerusalem ISO string),
parsed and formatted `%d/%m/%Y %H:%M` — never `now_local()`, never the
recognition-call clock, never `local_from_timestamp` off a Green API epoch that
isn't persisted anywhere.

Real `LedgerEventManager` + real `SessionManager`. No mocks — there is no
external service on this path.

Scope note: Phase 2 covers `הסכם` + `בנק`. The `חשבונית` synchronous-persistence
path (which needs the `accounting_document_json` blob shape from a real Morning
`create_*` response) is Phase 5 (US2), not here.
"""
import json
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.session_manager import SessionManager
from src.utils.time_utils import now_local

CHAT_ID = "group-ledgerer@g.us"
TRIGGER_TS = "2026-07-15T09:30:12.500000+03:00"
EXPECTED_EVENT_DATETIME = "15/07/2026 09:30"


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


@pytest.fixture
def lem(tmp_path, sm):
    manager = LedgerEventManager(storage_dir=str(tmp_path / "events"))
    manager.session_manager = sm          # injected the same way AIHandler will wire it
    return manager


def _message_path(sm, session, message_id):
    return Path(sm.storage_dir) / session.session_id / "messages" / f"{message_id}.json"


def _rewrite_timestamp(sm, session, message_id, iso):
    path = _message_path(sm, session, message_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["timestamp"] = iso
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_message(sm, session, message_id):
    return json.loads(_message_path(sm, session, message_id).read_text(encoding="utf-8"))


def _build_session(sm, trigger_content="חתמנו הסכם שכר טרחה עם דנה כהן"):
    trigger_id = sm.add_message(
        chat_id=CHAT_ID, role="user", content=trigger_content,
        user_role="godfather", sender="972500000002", sender_name="בעל הבית")
    completing_id = sm.add_message(
        chat_id=CHAT_ID, role="assistant", content="רשמתי.", user_role="godfather")
    session = sm.get_session(CHAT_ID)
    _rewrite_timestamp(sm, session, trigger_id, TRIGGER_TS)
    return session, trigger_id, completing_id


def _agreement_verdict(trigger_id, **event_overrides):
    event = {
        "source_type": "הסכם",
        "event_subtype": "יצירה",
        "client_name": "דנה כהן",
        "description": "הסכם שכר טרחה",
        "vat_status": None,
        "payer_name": "איגוד העובדים",
        "amount": None,
        "txn_date": None,
        "components": [
            {"amount": "4000", "percent": None, "percent_base": None,
             "trigger_condition": None, "hours": None, "hourly_rate": None,
             "description": "ריטיינר חודשי"},
            {"amount": None, "percent": "12", "percent_base": "פיצוי",
             "trigger_condition": "עם קבלת פיצוי", "hours": None, "hourly_rate": None,
             "description": "בונוס הצלחה"},
        ],
        "component_count": 2,
        "bank_number": None, "bank_branch": None, "bank_account": None,
        "accounting_document_display_number": None,
        "reference": None, "reference_hint": None,
    }
    event.update(event_overrides)
    return {"verdict": "complete", "trigger_message_id": trigger_id, "event": event}


def _bank_verdict(trigger_id, **event_overrides):
    event = {
        "source_type": "בנק",
        "event_subtype": "הפקדה",
        "client_name": "דנה כהן",
        "description": "הפקדה בנקאית מהלקוח",
        "amount": "5000",
        "txn_date": "2026-07-15",
        "vat_status": None,
        "payer_name": None,
        "components": [],
        "component_count": 0,
        "bank_number": "12", "bank_branch": "345", "bank_account": "678901",
        "accounting_document_display_number": None,
        "reference": None, "reference_hint": None,
    }
    event.update(event_overrides)
    return {"verdict": "complete", "trigger_message_id": trigger_id, "event": event}


def _events_on_disk(lem):
    return sorted(Path(lem.storage_dir).glob("*.json"))


def _load_events(lem):
    return [json.loads(p.read_text(encoding="utf-8")) for p in _events_on_disk(lem)]


# --------------------------------------------------------------------------- #

class TestSignature:
    def test_method_exists(self):
        assert hasattr(LedgerEventManager, "persist_recognized_event")

    def test_positional_params(self):
        sig = inspect.signature(LedgerEventManager.persist_recognized_event)
        params = list(sig.parameters)
        assert params[:4] == ["self", "verdict", "session", "completing_message_id"]


class TestAgreementComplete:
    def test_one_file_per_component_sharing_agreement_id(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        created = lem.persist_recognized_event(
            _agreement_verdict(trigger_id), session, completing_id)

        assert len(created) == 2
        records = _load_events(lem)
        assert len(records) == 2
        agreement_ids = {r["agreement_id"] for r in records}
        assert len(agreement_ids) == 1 and None not in agreement_ids
        component_ids = {r["component_id"] for r in records}
        assert len(component_ids) == 2 and None not in component_ids
        assert all(r["source_type"] == "הסכם" for r in records)
        assert all(r["client_name"] == "דנה כהן" for r in records)
        assert all(r["event_id"].startswith("A") for r in records)

    def test_event_datetime_is_trigger_message_timestamp_not_now(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        lem.persist_recognized_event(
            _agreement_verdict(trigger_id), session, completing_id)

        records = _load_events(lem)
        assert {r["event_datetime"] for r in records} == {EXPECTED_EVENT_DATETIME}
        today = now_local().strftime("%d/%m/%Y")
        assert all(r["captured_at"].startswith(today) for r in records)
        assert all(not r["event_datetime"].startswith(today) for r in records)

    def test_optional_fields_reach_the_persisted_records(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        lem.persist_recognized_event(
            _agreement_verdict(trigger_id), session, completing_id)

        records = _load_events(lem)
        assert all(r["payer_name"] == "איגוד העובדים" for r in records)
        pct_record = next(r for r in records if r["percent"] is not None)
        assert str(pct_record["percent"]) == "12"
        assert pct_record["percent_base"] == "פיצוי"
        assert pct_record["trigger_condition"] == "עם קבלת פיצוי"
        amount_record = next(r for r in records if r["amount"] is not None)
        assert amount_record["amount"] == 4000

    def test_back_link_lands_on_completing_message_not_trigger(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        created = lem.persist_recognized_event(
            _agreement_verdict(trigger_id), session, completing_id)

        completing = _read_message(sm, session, completing_id)
        trigger = _read_message(sm, session, trigger_id)
        assert sorted(completing["ledger_event_ids"]) == sorted(created)
        assert trigger["ledger_event_ids"] == []

    def test_reference_id_decided_in_conversation_is_persisted(self, lem, sm):
        """`event.reference` already holds a real prior event_id (the conversation
        established the linkage via query_ledger_events) — the ledgerer persists it,
        it does not re-decide whether to link."""
        session, trigger_id, completing_id = _build_session(sm)
        # seed one prior event to point at
        seed = _bank_verdict(trigger_id, description="הפקדה קודמת")
        prior_ids = lem.persist_recognized_event(seed, session, completing_id)
        prior_id = prior_ids[0]

        session2, trigger2, completing2 = _build_session(sm)
        verdict = _agreement_verdict(trigger2, reference=prior_id)
        lem.persist_recognized_event(verdict, session2, completing2)

        newest = [r for r in _load_events(lem) if r["source_type"] == "הסכם"]
        assert all(r["reference"] == prior_id for r in newest)


class TestBankComplete:
    def test_single_file_vat_included_and_bank_triplet_retained(self, lem, sm):
        session, trigger_id, completing_id = _build_session(
            sm, trigger_content="הלקוחה דנה כהן העבירה 5000 להפקדה")

        created = lem.persist_recognized_event(
            _bank_verdict(trigger_id), session, completing_id)

        assert len(created) == 1
        (record,) = _load_events(lem)
        assert record["source_type"] == "בנק"
        assert record["event_id"].startswith("B")
        assert record["event_datetime"] == EXPECTED_EVENT_DATETIME
        assert record["vat_status"] == "כולל"          # code-forced for בנק
        assert record["amount"] == 5000
        assert record["client_name"] == "דנה כהן"
        assert (record["bank_number"], record["bank_branch"], record["bank_account"]) \
            == ("12", "345", "678901")
        assert record["agreement_id"] is None and record["component_id"] is None

    def test_back_link_on_completing_message(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        created = lem.persist_recognized_event(
            _bank_verdict(trigger_id), session, completing_id)

        completing = _read_message(sm, session, completing_id)
        assert completing["ledger_event_ids"] == created


class TestDeclinedAndNone:
    def test_declined_persists_nothing(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)
        verdict = {"verdict": "declined", "source_type": "בנק",
                   "client_name_stated": "יוסי מהחנייה",
                   "reason": "declined_by_operator"}

        created = lem.persist_recognized_event(verdict, session, completing_id)

        assert created == []
        assert _events_on_disk(lem) == []
        assert _read_message(sm, session, completing_id)["ledger_event_ids"] == []

    def test_none_persists_nothing(self, lem, sm):
        session, trigger_id, completing_id = _build_session(sm)

        created = lem.persist_recognized_event({"verdict": "none"}, session, completing_id)

        assert created == []
        assert _events_on_disk(lem) == []


class TestZeroAI:
    def test_no_ledger_query_during_persist(self, lem, sm, monkeypatch):
        session, trigger_id, completing_id = _build_session(sm)

        def _boom(*a, **k):
            raise AssertionError("ledgerer must not call query_events")

        monkeypatch.setattr(lem, "query_events", _boom)

        created = lem.persist_recognized_event(
            _agreement_verdict(trigger_id), session, completing_id)

        assert len(created) == 2

    def test_manager_has_no_openai_client(self, lem):
        assert not hasattr(lem, "client")
