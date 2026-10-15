"""
Unit tests for AgreementsManager (Feature 089, T007-T009): the Agreements DB, the component
state machine, the agreement-close cascade, and the ledger events each write
produces. Runs on a real LedgerEventManager over a throwaway data root (no mocks).

Deliberately never asserts on the ledger's schema_version value (CLAUDE.md).
"""
import json
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.managers.agreements_manager import (
    IllegalTransitionError, InvalidActorError, LockedError, NotFoundError, ValidationError,
)
from tests.denidin_test_support import make_agreements_manager

RETAINER = {"label": "ריטיינר", "description": "ריטיינר חודשי", "amount": 5000, "vat_status": "לא כולל"}
SUCCESS = {"label": "שכר הצלחה", "description": "אחוז מהזכייה", "percent": 20,
           "percent_base": "סכום הזכייה", "trigger_condition": "אם נזכה בתיק"}


@pytest.fixture
def mgr(tmp_path):
    return make_agreements_manager(tmp_path)


def _create(mgr, components=None, **overrides):
    args: Dict[str, Any] = dict(client_name="ישראל ישראלי", title="ערעור לארצי",
                                components=components or [dict(RETAINER), dict(SUCCESS)], actor="webapp")
    args.update(overrides)
    return mgr.create_agreement(**args)


def _events(mgr) -> List[Dict[str, Any]]:
    root = Path(mgr.denidin.config.data_root) / "events"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.json"))]


def _by_label(agreement, label):
    return next(c for c in agreement["components"] if c["label"] == label)


class TestCreateAndDefaults:
    def test_db_lives_under_data_root(self, mgr, tmp_path):
        assert (tmp_path / "agreements" / "agreements.db").exists()

    def test_create_agreement_with_components(self, mgr):
        agreement, event_ids = _create(mgr)
        assert agreement["client_name"] == "ישראל ישראלי"
        assert agreement["status"] == "Active"
        assert [c["label"] for c in agreement["components"]] == ["ריטיינר", "שכר הצלחה"]
        assert len(event_ids) == 2
        assert agreement["agreement_id"].endswith("-ישראל_ישראלי-ערעור_לארצי")

    def test_uat_3_1_smart_defaulting(self, mgr):
        agreement, _ = _create(mgr)
        assert _by_label(agreement, "ריטיינר")["status"] == "Active"      # no trigger
        assert _by_label(agreement, "שכר הצלחה")["status"] == "Pending"   # has a trigger

    def test_requires_client_title_and_a_component(self, mgr):
        with pytest.raises(ValidationError) as exc:
            mgr.create_agreement(client_name="", title="", components=[], actor="webapp")
        assert set(exc.value.fields) == {"client_name", "title", "components"}

    def test_component_needs_amount_or_percent(self, mgr):
        with pytest.raises(ValidationError) as exc:
            _create(mgr, components=[{"label": "בלי ערך"}])
        assert "amount" in exc.value.fields

    def test_duplicate_label_within_agreement_rejected(self, mgr):
        with pytest.raises(ValidationError) as exc:
            _create(mgr, components=[dict(RETAINER), dict(RETAINER)])
        assert "label" in exc.value.fields

    def test_unknown_actor_rejected(self, mgr):
        with pytest.raises(InvalidActorError):
            _create(mgr, actor="somebody")

    def test_amount_strings_are_normalized(self, mgr):
        agreement, _ = _create(mgr, components=[{"label": "א", "amount": "5,000₪"}])
        assert agreement["components"][0]["amount"] == 5000


class TestReads:
    def test_find_and_get(self, mgr):
        agreement, _ = _create(mgr)
        assert mgr.get_agreement(agreement["agreement_id"])["title"] == "ערעור לארצי"
        assert [a["agreement_id"] for a in mgr.find_agreements("ישראל ישראלי")] == [agreement["agreement_id"]]
        assert mgr.find_agreements("מישהו אחר") == []

    def test_get_unknown_agreement(self, mgr):
        with pytest.raises(NotFoundError):
            mgr.get_agreement("nope")

    def test_totals_exclude_cancelled_and_percent_only(self, mgr):
        agreement, _ = _create(mgr, components=[
            {"label": "א", "amount": 5000}, {"label": "ב", "amount": 3000}, {"label": "ג", "percent": 10}])
        aid = agreement["agreement_id"]
        assert mgr.totals() == {"ישראל ישראלי": 8000}
        key_b = _by_label(agreement, "ב")["component_key"]
        mgr.set_component_status(aid, key_b, "cancel", "webapp")
        assert mgr.totals() == {"ישראל ישראלי": 5000}


class TestEditing:
    def test_edit_component_only_changes_that_component(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        before = _by_label(agreement, "שכר הצלחה")
        key = _by_label(agreement, "ריטיינר")["component_key"]
        updated, ids = mgr.edit_component(aid, key, {"amount": 6000}, "webapp")
        assert _by_label(updated, "ריטיינר")["amount"] == 6000
        assert _by_label(updated, "שכר הצלחה") == before
        assert len(ids) == 1

    def test_wording_only_edit_writes_a_ledger_event(self, mgr):
        agreement, _ = _create(mgr)
        key = _by_label(agreement, "ריטיינר")["component_key"]
        before = len(_events(mgr))
        _, ids = mgr.edit_component(agreement["agreement_id"], key, {"description": "נוסח חדש"}, "webapp")
        assert len(ids) == 1 and len(_events(mgr)) == before + 1
        assert _events(mgr)[-1]["description"] == "נוסח חדש"

    def test_no_op_save_creates_no_event(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        events = len(_events(mgr))
        _, ids = mgr.edit_component(aid, key, {"amount": 5000}, "webapp")
        assert ids == [] and len(_events(mgr)) == events

    def test_rename_label_updates_component_id_and_rejects_duplicates(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        updated, _ = mgr.edit_component(aid, key, {"label": "ריטיינר חדש"}, "webapp")
        renamed = _by_label(updated, "ריטיינר חדש")
        assert renamed["component_key"] == key and renamed["component_id"].endswith("ריטיינר_חדש")
        with pytest.raises(ValidationError):
            mgr.edit_component(aid, key, {"label": "שכר הצלחה"}, "webapp")

    def test_component_cannot_lose_both_amount_and_percent(self, mgr):
        agreement, _ = _create(mgr)
        key = _by_label(agreement, "ריטיינר")["component_key"]
        with pytest.raises(ValidationError):
            mgr.edit_component(agreement["agreement_id"], key, {"amount": None}, "webapp")

    def test_unknown_field_rejected(self, mgr):
        agreement, _ = _create(mgr)
        key = _by_label(agreement, "ריטיינר")["component_key"]
        with pytest.raises(ValidationError):
            mgr.edit_component(agreement["agreement_id"], key, {"status": "Completed"}, "webapp")

    def test_edit_agreement_writes_one_event_per_component(self, mgr):
        agreement, _ = _create(mgr)
        events_before = len(_events(mgr))
        updated, ids = mgr.edit_agreement(agreement["agreement_id"],
                                          {"payer_name": "ההסתדרות", "partner_name": "עו״ד כהן",
                                           "partner_percent": 25}, "webapp")
        assert (updated["payer_name"], updated["partner_name"], updated["partner_percent"]) == \
            ("ההסתדרות", "עו״ד כהן", 25)
        assert len(ids) == 2 and len(_events(mgr)) == events_before + 2
        last_two = _events(mgr)[-2:]
        assert all(e["payer_name"] == "ההסתדרות" and e["split_partner"] == "עו״ד כהן"
                   and e["split_percent"] == 25 for e in last_two)

    def test_edit_agreement_rejects_other_fields(self, mgr):
        agreement, _ = _create(mgr)
        with pytest.raises(ValidationError):
            mgr.edit_agreement(agreement["agreement_id"], {"status": "Cancelled"}, "webapp")

    def test_title_and_description_are_db_only_edits_and_the_id_is_not_editable(self, mgr):
        agreement, _ = _create(mgr)
        events_before = len(_events(mgr))
        updated, ids = mgr.edit_agreement(agreement["agreement_id"],
                                          {"title": "שם חדש", "agreement_description": "תיאור חופשי להסכם"}, "webapp")
        assert updated["title"] == "שם חדש" and updated["agreement_description"] == "תיאור חופשי להסכם"
        assert updated["agreement_id"] == agreement["agreement_id"]
        assert ids == [] and len(_events(mgr)) == events_before
        with pytest.raises(ValidationError):
            mgr.edit_agreement(agreement["agreement_id"], {"agreement_id": "other"}, "webapp")

    def test_edit_blank_title_is_rejected(self, mgr):
        agreement, _ = _create(mgr)
        with pytest.raises(ValidationError):
            mgr.edit_agreement(agreement["agreement_id"], {"title": "  "}, "webapp")

    def test_updated_at_moves_on_any_real_write_including_components(self, mgr):
        agreement, _ = _create(mgr, agreement_description="תיאור ראשוני")
        assert agreement["agreement_description"] == "תיאור ראשוני"
        key = _by_label(agreement, "ריטיינר")["component_key"]
        updated, _ = mgr.edit_component(agreement["agreement_id"], key, {"amount": 6000}, "webapp")
        assert updated["created_at"] == agreement["created_at"]
        assert updated["updated_at"] > agreement["updated_at"]

    def test_add_component_default_status_and_event(self, mgr):
        agreement, _ = _create(mgr, components=[dict(RETAINER)])
        updated, ids = mgr.add_component(agreement["agreement_id"], dict(SUCCESS), "webapp")
        assert _by_label(updated, "שכר הצלחה")["status"] == "Pending" and len(ids) == 1

    def test_delete_component_pushes_cancellation_event_referencing_origin(self, mgr):
        agreement, ids = _create(mgr)
        aid = agreement["agreement_id"]
        comp = _by_label(agreement, "ריטיינר")
        assert comp["origin_event_id"] == ids[0]
        updated, delete_ids = mgr.delete_component(aid, comp["component_key"], "webapp")
        assert [c["label"] for c in updated["components"]] == ["שכר הצלחה"]
        event = next(e for e in _events(mgr) if e["event_id"] == delete_ids[0])
        assert event["event_subtype"] == "ביטול" and event["reference"] == ids[0]

    def test_unknown_component(self, mgr):
        agreement, _ = _create(mgr)
        with pytest.raises(NotFoundError):
            mgr.edit_component(agreement["agreement_id"], "nope", {"amount": 1}, "webapp")


class TestComponentLifecycle:
    @pytest.mark.parametrize("start,action,expected", [
        ("Pending", "activate", "Active"),
        ("Active", "complete", "Completed"),
        ("Pending", "cancel", "Cancelled"),
        ("Active", "cancel", "Cancelled"),
    ])
    def test_legal_transitions_write_an_event_carrying_the_status(self, mgr, start, action, expected):
        components = [dict(SUCCESS)] if start == "Pending" else [dict(RETAINER)]
        agreement, _ = _create(mgr, components=components)
        comp = agreement["components"][0]
        assert comp["status"] == start
        updated, ids = mgr.set_component_status(agreement["agreement_id"], comp["component_key"], action, "webapp")
        assert updated["components"][0]["status"] == expected
        assert len(ids) == 1
        assert next(e for e in _events(mgr) if e["event_id"] == ids[0])["component_status"] == expected

    def test_illegal_transitions(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        active = _by_label(agreement, "ריטיינר")["component_key"]
        pending = _by_label(agreement, "שכר הצלחה")["component_key"]
        with pytest.raises(IllegalTransitionError):
            mgr.set_component_status(aid, active, "activate", "webapp")
        with pytest.raises(IllegalTransitionError):
            mgr.set_component_status(aid, pending, "complete", "webapp")
        with pytest.raises(IllegalTransitionError):
            mgr.set_component_status(aid, active, "reopen", "webapp")

    def test_completed_and_cancelled_components_are_locked_until_reopened(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        done, _ = mgr.set_component_status(aid, key, "complete", "webapp")
        assert _by_label(done, "ריטיינר")["locked"] is True
        with pytest.raises(LockedError):
            mgr.edit_component(aid, key, {"amount": 1}, "webapp")
        with pytest.raises(LockedError):
            mgr.delete_component(aid, key, "webapp")
        with pytest.raises(LockedError):
            mgr.set_component_status(aid, key, "cancel", "webapp")
        reopened, _ = mgr.set_component_status(aid, key, "reopen", "webapp")
        assert _by_label(reopened, "ריטיינר")["status"] == "Active"
        assert _by_label(reopened, "ריטיינר")["locked"] is False


BASE_TS = 1_790_000_000  # a fixed instant; tests step it a minute at a time (10 events max per minute)


def at(minutes: int) -> Dict[str, int]:
    return {"message_timestamp": BASE_TS + 60 * minutes}


class TestAgreementCloseCascade:
    def _three(self, mgr):
        agreement, _ = _create(mgr, components=[
            {"label": "פעיל", "amount": 1000},
            {"label": "ממתין", "amount": 2000, "trigger_condition": "אם"},
            {"label": "שולם", "amount": 3000},
            {"label": "בוטל", "amount": 4000},
        ], message_timestamp=BASE_TS)
        aid = agreement["agreement_id"]
        mgr.set_component_status(aid, _by_label(agreement, "שולם")["component_key"], "complete", "webapp", **at(1))
        mgr.set_component_status(aid, _by_label(agreement, "בוטל")["component_key"], "cancel", "webapp", **at(1))
        return aid

    def test_mark_completed_cascade(self, mgr):
        aid = self._three(mgr)
        before = len(_events(mgr))
        closed, ids = mgr.set_agreement_status(aid, "complete", "webapp", **at(2))
        assert closed["status"] == "Completed"
        statuses = {c["label"]: c["status"] for c in closed["components"]}
        assert statuses == {"פעיל": "Completed", "ממתין": "Cancelled", "שולם": "Completed", "בוטל": "Cancelled"}
        assert all(c["locked"] for c in closed["components"])
        assert len(ids) == 4 and len(_events(mgr)) == before + 4  # one per component, even unchanged
        assert {e["agreement_status"] for e in _events(mgr)[-4:]} == {"Completed"}

    def test_cancel_cascade(self, mgr):
        aid = self._three(mgr)
        closed, _ = mgr.set_agreement_status(aid, "cancel", "webapp", **at(2))
        statuses = {c["label"]: c["status"] for c in closed["components"]}
        assert closed["status"] == "Cancelled"
        assert statuses == {"פעיל": "Cancelled", "ממתין": "Cancelled", "שולם": "Completed", "בוטל": "Cancelled"}

    def test_reopen_agreement_leaves_components_alone(self, mgr):
        aid = self._three(mgr)
        mgr.set_agreement_status(aid, "complete", "webapp", **at(2))
        events_before = len(_events(mgr))
        reopened, ids = mgr.set_agreement_status(aid, "reopen", "webapp", **at(3))
        statuses = {c["label"]: c["status"] for c in reopened["components"]}
        assert reopened["status"] == "Active"
        assert statuses == {"פעיל": "Completed", "ממתין": "Cancelled", "שולם": "Completed", "בוטל": "Cancelled"}
        assert len(ids) == 4 and len(_events(mgr)) == events_before + 4
        assert {e["agreement_status"] for e in _events(mgr)[-4:]} == {"Active"}

    def test_closed_agreement_blocks_component_writes(self, mgr):
        aid = self._three(mgr)
        closed, _ = mgr.set_agreement_status(aid, "complete", "webapp", **at(2))
        key = _by_label(closed, "פעיל")["component_key"]
        with pytest.raises(LockedError):
            mgr.set_component_status(aid, key, "reopen", "webapp")
        with pytest.raises(LockedError):
            mgr.add_component(aid, {"label": "חדש", "amount": 1}, "webapp")

    def test_agreement_transitions_validated(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        with pytest.raises(IllegalTransitionError):
            mgr.set_agreement_status(aid, "reopen", "webapp")
        mgr.set_agreement_status(aid, "complete", "webapp")
        with pytest.raises(IllegalTransitionError):
            mgr.set_agreement_status(aid, "cancel", "webapp")


class TestLedger:
    def test_create_event_carries_full_component_and_agreement_state(self, mgr):
        _create(mgr, payer_name="ההסתדרות", partner_name="עו״ד כהן", partner_percent=25)
        event = next(e for e in _events(mgr) if e["component_label"] == "שכר הצלחה")
        assert event["source_type"] == "הסכם" and event["event_subtype"] == "יצירה"
        assert event["client_name"] == "ישראל ישראלי" and event["payer_name"] == "ההסתדרות"
        assert event["percent"] == 20 and event["percent_base"] == "סכום הזכייה"
        assert event["trigger_condition"] == "אם נזכה בתיק"
        assert event["component_status"] == "Pending" and event["agreement_status"] == "Active"
        assert event["split_partner"] == "עו״ד כהן" and event["split_percent"] == 25
        assert event["hours"] is None and event["original_client_name"] is None

    def test_a_six_component_close_yields_six_distinct_event_ids(self, mgr):
        agreement, _ = _create(mgr, components=[{"label": f"רכיב {i}", "amount": 100 * (i + 1)} for i in range(6)],
                               message_timestamp=BASE_TS)
        _, ids = mgr.set_agreement_status(agreement["agreement_id"], "complete", "webapp", **at(1))
        assert len(ids) == 6 and len(set(ids)) == 6

    def test_concurrent_writes_serialize_last_write_wins(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        errors: List[BaseException] = []

        def worker(amount: int) -> None:
            try:
                mgr.edit_component(aid, key, {"amount": amount}, "webapp")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(1000 + i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        # last write wins: the amount is one of the values written, never a torn/lost state
        assert _by_label(mgr.get_agreement(aid), "ריטיינר")["amount"] in {1000 + i for i in range(8)}


class TestCreateFromCapture:
    CAPTURE = {
        "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "ישראל ישראלי",
        "description": "ערעור לארצי", "payer_name": None, "vat_status": "לא כולל",
        "agreement_id": "1026-ישראל_ישראלי-ערעור_לארצי",
        "components": [
            {"component_label": "ריטיינר", "description": "ריטיינר", "amount": "5,000", "percent": None,
             "percent_base": None, "hours": None, "hourly_rate": None, "txn_date": None,
             "trigger_condition": None},
            {"component_label": "שכר הצלחה", "description": "אחוז", "amount": None, "percent": "20%",
             "percent_base": "הזכייה", "hours": None, "hourly_rate": None, "txn_date": None,
             "trigger_condition": "אם נזכה"},
        ],
    }

    def test_capture_creates_agreement_in_db_and_events(self, mgr):
        ids = mgr.create_from_capture(dict(self.CAPTURE), "sess-1", "msg-1", 1790000000)
        agreement = mgr.get_agreement(self.CAPTURE["agreement_id"])
        assert [c["status"] for c in agreement["components"]] == ["Active", "Pending"]
        assert len(ids) == 2
        assert {e["session_id"] for e in _events(mgr)} == {"sess-1"}

    def test_hours_worked_lines_stay_ledger_only(self, mgr):
        capture = json.loads(json.dumps(self.CAPTURE))
        capture["components"].append({"component_label": "שעות", "description": "עבודה", "amount": "800",
                                      "hours": "2", "hourly_rate": "400", "txn_date": "2026-10-01"})
        ids = mgr.create_from_capture(capture, "sess-1", "msg-1", 1790000000)
        agreement = mgr.get_agreement(self.CAPTURE["agreement_id"])
        assert [c["label"] for c in agreement["components"]] == ["ריטיינר", "שכר הצלחה"]
        assert len(ids) == 3
        assert any(e["hours"] == 2 for e in _events(mgr))

    def test_capture_the_db_refuses_falls_back_to_the_ledger(self, mgr):
        capture = json.loads(json.dumps(self.CAPTURE))
        capture["client_name"] = None
        ids = mgr.create_from_capture(capture, "sess-1", "msg-1", 1790000000)
        assert len(ids) == 2 and mgr.list_agreements() == []

    def test_second_capture_for_same_agreement_amends_in_place(self, mgr):
        mgr.create_from_capture(dict(self.CAPTURE), "sess-1", "msg-1", 1790000000)
        amended = json.loads(json.dumps(self.CAPTURE))
        amended["components"][0]["amount"] = "6,000"
        mgr.create_from_capture(amended, "sess-1", "msg-2", 1790000100)
        agreement = mgr.get_agreement(self.CAPTURE["agreement_id"])
        assert len(agreement["components"]) == 2
        assert _by_label(agreement, "ריטיינר")["amount"] == 6000


class TestLedgerCapacity:
    """Human decision 2026-10-09: a minute holds 10 `הסכם` ledger events; a write needing more
    is refused whole, up front - nothing written, nothing silently dropped."""

    def test_write_needing_more_slots_than_free_is_refused_and_writes_nothing(self, mgr):
        from src.managers.agreements_manager import LedgerCapacityError
        agreement, _ = _create(mgr, components=[{"label": f"רכיב {i}", "amount": 100} for i in range(6)],
                               message_timestamp=BASE_TS)
        aid = agreement["agreement_id"]
        events = len(_events(mgr))
        with pytest.raises(LedgerCapacityError) as exc:
            mgr.set_agreement_status(aid, "complete", "webapp", **at(0))   # same minute: 6 + 6 > 10
        assert exc.value.code == "ledger_busy"
        assert mgr.get_agreement(aid)["status"] == "Active"
        assert len(_events(mgr)) == events
        mgr.set_agreement_status(aid, "complete", "webapp", **at(1))        # next minute: fine
        assert mgr.get_agreement(aid)["status"] == "Completed"


class TestSoftDelete:
    """Nothing is ever really deleted: rows get is_active = 0 and every query filters on it."""

    @staticmethod
    def _rows(mgr, table, where="1=1", args=()):
        import sqlite3
        conn = sqlite3.connect(str(mgr.db_path))
        try:
            return conn.execute(f"SELECT is_active FROM {table} WHERE {where}", args).fetchall()  # noqa: S608
        finally:
            conn.close()

    def test_deleted_agreement_disappears_from_every_read(self, mgr):
        agreement, _ = _create(mgr)
        agreement_id = agreement["agreement_id"]
        mgr.delete_agreement(agreement_id, "webapp")
        with pytest.raises(NotFoundError):
            mgr.get_agreement(agreement_id)
        assert mgr.find_agreements("ישראל ישראלי") == []
        assert mgr.list_agreements() == []
        assert mgr.totals() == {}

    def test_rows_are_kept_and_flagged_inactive(self, mgr):
        agreement, _ = _create(mgr)
        agreement_id = agreement["agreement_id"]
        mgr.delete_agreement(agreement_id, "webapp")
        assert self._rows(mgr, "agreements", "agreement_id = ?", (agreement_id,)) == [(0,)]
        assert self._rows(mgr, "components", "agreement_id = ?", (agreement_id,)) == [(0,), (0,)]

    def test_delete_writes_no_ledger_events(self, mgr):
        agreement, _ = _create(mgr)
        before = len(_events(mgr))
        mgr.delete_agreement(agreement["agreement_id"], "webapp")
        assert len(_events(mgr)) == before

    def test_deleting_twice_or_an_unknown_id_is_not_found(self, mgr):
        agreement, _ = _create(mgr)
        mgr.delete_agreement(agreement["agreement_id"], "webapp")
        with pytest.raises(NotFoundError):
            mgr.delete_agreement(agreement["agreement_id"], "webapp")
        with pytest.raises(NotFoundError):
            mgr.delete_agreement("nope", "webapp")

    def test_wrong_actor_is_rejected_and_nothing_changes(self, mgr):
        agreement, _ = _create(mgr)
        with pytest.raises(InvalidActorError):
            mgr.delete_agreement(agreement["agreement_id"], "someone")
        assert mgr.get_agreement(agreement["agreement_id"])["status"] == "Active"

    def test_other_agreements_are_untouched(self, mgr):
        keep, _ = _create(mgr)
        gone, _ = _create(mgr, client_name="אחר", title="תיק אחר")
        mgr.delete_agreement(gone["agreement_id"], "webapp")
        assert [a["agreement_id"] for a in mgr.list_agreements()] == [keep["agreement_id"]]
        assert mgr.totals() == {"ישראל ישראלי": 5000}

    def test_deleted_component_is_soft_deleted_and_its_label_is_reusable(self, mgr):
        agreement, _ = _create(mgr)
        key = _by_label(agreement, "ריטיינר")["component_key"]
        mgr.delete_component(agreement["agreement_id"], key, "webapp")
        assert self._rows(mgr, "components", "component_key = ?", (key,)) == [(0,)]
        after = mgr.get_agreement(agreement["agreement_id"])
        assert [c["label"] for c in after["components"]] == ["שכר הצלחה"]
        again, _ = mgr.add_component(agreement["agreement_id"], dict(RETAINER), "webapp")
        assert "ריטיינר" in [c["label"] for c in again["components"]]

    def test_same_agreement_id_can_be_created_again_after_a_delete(self, mgr):
        first, _ = _create(mgr)
        agreement_id = first["agreement_id"]
        mgr.delete_agreement(agreement_id, "webapp")
        second, _ = _create(mgr)                      # same client + title -> same agreement_id
        assert second["agreement_id"] == agreement_id
        assert [c["label"] for c in second["components"]] == ["ריטיינר", "שכר הצלחה"]
        assert len(self._rows(mgr, "agreements", "agreement_id = ?", (agreement_id,))) == 2
        assert sorted(r[0] for r in self._rows(mgr, "agreements", "agreement_id = ?", (agreement_id,))) == [0, 1]
        # edits hit only the live agreement
        mgr.edit_agreement(agreement_id, {"payer_name": "חברה"}, "webapp")
        assert mgr.get_agreement(agreement_id)["payer_name"] == "חברה"

    def test_two_live_agreements_cannot_share_an_id(self, mgr):
        _create(mgr)
        with pytest.raises(ValidationError):
            _create(mgr)

    def test_database_created_before_the_flag_existed_is_upgraded_in_place(self, tmp_path):
        import sqlite3
        db = tmp_path / "agreements" / "agreements.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(str(db))
        conn.executescript("""
            CREATE TABLE agreements (agreement_id TEXT PRIMARY KEY, title TEXT NOT NULL, client_name TEXT NOT NULL,
                payer_name TEXT, partner_name TEXT, partner_percent REAL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE components (component_key TEXT PRIMARY KEY, component_id TEXT NOT NULL, agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id),
                label TEXT NOT NULL, description TEXT, amount INTEGER, percent REAL, percent_base TEXT,
                trigger_condition TEXT, vat_status TEXT, txn_date TEXT, status TEXT NOT NULL, origin_event_id TEXT,
                sort_order INTEGER NOT NULL);
            CREATE TABLE revisions (revision_id INTEGER PRIMARY KEY AUTOINCREMENT, agreement_id TEXT NOT NULL,
                component_key TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                changed_json TEXT NOT NULL, ledger_event_ids_json TEXT NOT NULL, created_at TEXT NOT NULL);
            INSERT INTO agreements VALUES ('old-1','כותרת','לקוח ישן',NULL,NULL,NULL,'Active','2026-01-01','2026-01-01');
            INSERT INTO components VALUES ('k1','old-1-רכיב','old-1','רכיב',NULL,900,NULL,NULL,NULL,NULL,NULL,'Active',NULL,0);
        """)
        conn.commit()
        conn.close()
        upgraded = make_agreements_manager(tmp_path)
        assert [a["agreement_id"] for a in upgraded.find_agreements("לקוח ישן")] == ["old-1"]
        assert upgraded.totals() == {"לקוח ישן": 900}


class TestStatusDropdownPath:
    """2026-10-13: a status dropdown picks a target status; any component status -> any other while the agreement is Active."""

    def test_component_can_go_back_to_pending_and_to_any_other_status(self, mgr):
        agreement, _ = _create(mgr, components=[dict(RETAINER)])
        aid, key = agreement["agreement_id"], agreement["components"][0]["component_key"]
        for target in ("Pending", "Completed", "Pending", "Cancelled", "Active"):
            updated, ids = mgr.set_component_status_to(aid, key, target, "webapp")
            assert updated["components"][0]["status"] == target and len(ids) == 1
        assert _events(mgr)[-1]["component_status"] == "Active"

    def test_same_status_is_a_noop_and_closed_agreement_locks_components(self, mgr):
        agreement, _ = _create(mgr, components=[dict(RETAINER)])
        aid, key = agreement["agreement_id"], agreement["components"][0]["component_key"]
        events = len(_events(mgr))
        _, ids = mgr.set_component_status_to(aid, key, "Active", "webapp")
        assert ids == [] and len(_events(mgr)) == events
        mgr.set_agreement_status_to(aid, "Completed", "webapp")
        with pytest.raises(LockedError):
            mgr.set_component_status_to(aid, key, "Pending", "webapp")
        with pytest.raises(ValidationError):
            mgr.set_component_status_to(aid, key, "Bogus", "webapp")

    def test_agreement_target_status_cascades_like_complete_and_cancel(self, mgr):
        agreement, _ = _create(mgr)  # retainer Active, success Pending
        aid = agreement["agreement_id"]
        closed, _ = mgr.set_agreement_status_to(aid, "Cancelled", "webapp")
        assert closed["status"] == "Cancelled"
        assert {c["label"]: c["status"] for c in closed["components"]} == {"ריטיינר": "Cancelled", "שכר הצלחה": "Cancelled"}
        reopened, _ = mgr.set_agreement_status_to(aid, "Active", "webapp")
        assert reopened["status"] == "Active"  # components unchanged by a reopen
        assert all(c["status"] == "Cancelled" for c in reopened["components"])
        done, _ = mgr.set_agreement_status_to(aid, "Completed", "webapp")
        assert done["status"] == "Completed"
        with pytest.raises(ValidationError):
            mgr.set_agreement_status_to(aid, "Pending", "webapp")


class TestAgreedTotalAndLineReopen:
    """2026-10-14: the agreed total counts Active and Completed components only; the client line's
    reopen turns the agreement's Completed components back to Active."""

    def test_totals_count_only_active_and_completed(self, mgr):
        agreement, _ = _create(mgr, components=[
            {"label": "פעיל", "amount": 1000},
            {"label": "ממתין", "amount": 2000, "trigger_condition": "בהצלחה"},
            {"label": "סגור", "amount": 4000},
            {"label": "מבוטל", "amount": 8000}])
        aid = agreement["agreement_id"]
        assert _by_label(agreement, "ממתין")["status"] == "Pending"
        mgr.set_component_status_to(aid, _by_label(agreement, "סגור")["component_key"], "Completed", "webapp")
        mgr.set_component_status_to(aid, _by_label(agreement, "מבוטל")["component_key"], "Cancelled", "webapp")
        assert mgr.totals() == {"ישראל ישראלי": 5000}
        mgr.set_component_status_to(aid, _by_label(agreement, "ממתין")["component_key"], "Active", "webapp")
        assert mgr.totals() == {"ישראל ישראלי": 7000}

    def test_reopen_components_turns_completed_back_to_active_only_when_asked(self, mgr):
        agreement, _ = _create(mgr)  # retainer Active, success Pending
        aid = agreement["agreement_id"]
        mgr.set_agreement_status_to(aid, "Completed", "webapp")  # Active->Completed, Pending->Cancelled
        plain, _ = mgr.set_agreement_status_to(aid, "Active", "webapp")
        assert sorted(c["status"] for c in plain["components"]) == ["Cancelled", "Completed"]
        mgr.set_agreement_status_to(aid, "Completed", "webapp")
        reopened, ids = mgr.set_agreement_status_to(aid, "Active", "webapp", reopen_components=True)
        assert reopened["status"] == "Active"
        assert sorted(c["status"] for c in reopened["components"]) == ["Active", "Cancelled"]
        assert len(ids) == len(reopened["components"])


class TestAgreementDate:
    def test_agreement_date_sets_created_at_while_updated_at_is_the_write_time(self, mgr):
        agreement, _ = mgr.create_agreement(
            client_name="לקוח", title="הסכם ישן", components=[{"label": "שכר טרחה", "amount": 1000}],
            actor="migration", agreement_date="2024-10-15")
        assert agreement["created_at"].startswith("2024-10-15T00:00:00")
        assert not agreement["updated_at"].startswith("2024-10-15")

    def test_without_agreement_date_created_at_is_now(self, mgr):
        agreement, _ = _create(mgr)
        assert agreement["created_at"][:10] == agreement["updated_at"][:10]

    def test_bad_agreement_date_is_rejected(self, mgr):
        with pytest.raises(ValidationError):
            mgr.create_agreement(client_name="לקוח", title="הסכם", components=[{"label": "א", "amount": 1}],
                                 actor="migration", agreement_date="15/10/24")
