"""
Unit tests for AgreementsManager (Feature 089, T007-T009): the Agreements DB, the component
state machine, the agreement-close cascade, revisions, and the ledger events each write
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

    def test_no_op_save_creates_no_revision_and_no_event(self, mgr):
        agreement, _ = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        revisions, events = len(mgr.revisions(aid)), len(_events(mgr))
        _, ids = mgr.edit_component(aid, key, {"amount": 5000}, "webapp")
        assert ids == [] and len(mgr.revisions(aid)) == revisions and len(_events(mgr)) == events

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


class TestRevisionsAndLedger:
    def test_every_mutation_writes_one_revision_with_actor_and_event_ids(self, mgr):
        agreement, create_ids = _create(mgr)
        aid = agreement["agreement_id"]
        key = _by_label(agreement, "ריטיינר")["component_key"]
        _, edit_ids = mgr.edit_component(aid, key, {"amount": 6000}, "whatsapp")
        revisions = mgr.revisions(aid)
        assert [r["action"] for r in revisions] == ["create_agreement", "edit_component"]
        assert [r["actor"] for r in revisions] == ["webapp", "whatsapp"]
        assert revisions[0]["ledger_event_ids"] == create_ids
        assert revisions[1]["ledger_event_ids"] == edit_ids
        assert revisions[1]["changed"] == {"amount": [5000, 6000]}
        assert revisions[1]["snapshot"]["amount"] == 6000
        assert revisions[0]["created_at"] <= revisions[1]["created_at"]

    def test_revisions_survive_component_delete(self, mgr):
        agreement, _ = _create(mgr)
        key = _by_label(agreement, "ריטיינר")["component_key"]
        mgr.delete_component(agreement["agreement_id"], key, "webapp")
        assert mgr.revisions(agreement["agreement_id"])[-1]["action"] == "delete_component"

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
        revisions = mgr.revisions(aid)
        last = [r for r in revisions if r["action"] == "edit_component"][-1]
        assert _by_label(mgr.get_agreement(aid), "ריטיינר")["amount"] == last["snapshot"]["amount"]


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
        revisions, events = len(mgr.revisions(aid)), len(_events(mgr))
        with pytest.raises(LedgerCapacityError) as exc:
            mgr.set_agreement_status(aid, "complete", "webapp", **at(0))   # same minute: 6 + 6 > 10
        assert exc.value.code == "ledger_busy"
        assert mgr.get_agreement(aid)["status"] == "Active"
        assert len(mgr.revisions(aid)) == revisions and len(_events(mgr)) == events
        mgr.set_agreement_status(aid, "complete", "webapp", **at(1))        # next minute: fine
        assert mgr.get_agreement(aid)["status"] == "Completed"
