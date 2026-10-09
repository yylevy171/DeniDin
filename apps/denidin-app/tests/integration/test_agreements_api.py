"""Agreements API (Feature 089): real Starlette app over a real AgreementsManager and
LedgerEventManager on a throwaway data root - requests go through the real ASGI stack
(auth, JSON parsing, error mapping), never straight into the manager."""
import json

import pytest
from starlette.testclient import TestClient

from src.services.agreements_api import build_app
from src.utils.time_utils import now_local
from tests.denidin_test_support import make_agreements_manager

TOKEN = "test-token-089"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def manager(tmp_path):
    return make_agreements_manager(tmp_path)


@pytest.fixture
def client(manager):
    return TestClient(build_app(manager, TOKEN))


def _new_agreement(client, title="ערעור", components=None):
    body = {
        "actor": "webapp", "client_name": "ישראל ישראלי", "title": title, "partner_name": "עו״ד כהן",
        "partner_percent": 25,
        "components": components or [
            {"label": "ריטיינר", "amount": 5000, "vat_status": "לא כולל מע״מ"},
            {"label": "הצלחה", "percent": 12, "trigger_condition": "זכייה"},
        ],
    }
    response = client.post("/agreements", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    return response.json()


class TestAuth:
    def test_is_alive_needs_no_token(self, client):
        assert client.get("/is_alive").status_code == 200

    def test_missing_token_is_rejected(self, client):
        response = client.get("/agreements/totals")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"

    def test_wrong_token_is_rejected(self, client):
        assert client.get("/agreements/totals", headers={"Authorization": "Bearer nope"}).status_code == 401

    def test_empty_configured_token_rejects_everything(self, manager):
        locked = TestClient(build_app(manager, ""))
        assert locked.get("/agreements/totals", headers={"Authorization": "Bearer "}).status_code == 401


class TestCreateAndRead:
    def test_create_returns_agreement_components_and_ledger_events(self, client):
        data = _new_agreement(client)
        agreement = data["agreement"]
        assert agreement["status"] == "Active"
        assert {c["label"]: c["status"] for c in agreement["components"]} == {"ריטיינר": "Active", "הצלחה": "Pending"}
        assert len(data["ledger_event_ids"]) == 2
        assert all(c["locked"] is False for c in agreement["components"])

    def test_list_by_client_and_get_one(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        listed = client.get("/agreements", params={"client_name": "ישראל ישראלי"}, headers=AUTH).json()
        assert [a["agreement_id"] for a in listed["agreements"]] == [agreement_id]
        one = client.get(f"/agreements/{agreement_id}", headers=AUTH).json()
        assert one["agreement"]["client_name"] == "ישראל ישראלי"

    def test_list_without_client_name_is_a_validation_error(self, client):
        response = client.get("/agreements", headers=AUTH)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation"

    def test_totals_sum_non_cancelled_components(self, client):
        _new_agreement(client)
        assert client.get("/agreements/totals", headers=AUTH).json()["totals"] == {"ישראל ישראלי": 5000}

    def test_unknown_agreement_is_404(self, client):
        response = client.get("/agreements/does-not-exist", headers=AUTH)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_create_without_components_is_422_with_fields(self, client):
        response = client.post("/agreements", headers=AUTH, json={
            "actor": "webapp", "client_name": "ישראל ישראלי", "title": "x", "components": []})
        assert response.status_code == 422
        assert "components" in response.json()["error"]["fields"]

    def test_non_json_body_is_422(self, client):
        response = client.post("/agreements", headers=AUTH, content=b"not json")
        assert response.status_code == 422


class TestWritesAndErrors:
    def test_wrong_actor_is_rejected(self, client):
        response = client.post("/agreements", headers=AUTH, json={
            "actor": "someone", "client_name": "א", "title": "ב", "components": [{"label": "ג", "amount": 1}]})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_actor"

    def test_edit_agreement_fields_and_reject_unknown_field(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        ok = client.patch(f"/agreements/{agreement_id}", headers=AUTH, json={"actor": "webapp", "payer_name": "חברה בע״מ"})
        assert ok.status_code == 200
        assert ok.json()["agreement"]["payer_name"] == "חברה בע״מ"
        bad = client.patch(f"/agreements/{agreement_id}", headers=AUTH, json={"actor": "webapp", "status": "Completed"})
        assert bad.status_code == 422

    def test_no_op_save_returns_state_and_no_events(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        response = client.patch(f"/agreements/{agreement_id}", headers=AUTH, json={"actor": "webapp", "partner_percent": 25})
        assert response.status_code == 200
        assert response.json()["ledger_event_ids"] == []

    def test_edit_component_then_complete_it_locks_it(self, client):
        agreement = _new_agreement(client)["agreement"]
        agreement_id = agreement["agreement_id"]
        key = next(c["component_key"] for c in agreement["components"] if c["label"] == "ריטיינר")
        edited = client.patch(f"/agreements/{agreement_id}/components/{key}", headers=AUTH,
                              json={"actor": "webapp", "amount": 6000})
        assert edited.status_code == 200
        done = client.post(f"/agreements/{agreement_id}/components/{key}/status", headers=AUTH,
                           json={"actor": "webapp", "action": "complete"})
        assert done.status_code == 200
        locked = client.patch(f"/agreements/{agreement_id}/components/{key}", headers=AUTH,
                              json={"actor": "webapp", "amount": 7000})
        assert locked.status_code == 409
        assert locked.json()["error"]["code"] == "locked"

    def test_illegal_transition_is_409(self, client):
        agreement = _new_agreement(client)["agreement"]
        key = next(c["component_key"] for c in agreement["components"] if c["label"] == "ריטיינר")
        response = client.post(f"/agreements/{agreement['agreement_id']}/components/{key}/status",
                               headers=AUTH, json={"actor": "webapp", "action": "activate"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "illegal_transition"

    def test_duplicate_label_is_422(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        response = client.post(f"/agreements/{agreement_id}/components", headers=AUTH,
                               json={"actor": "webapp", "label": "ריטיינר", "amount": 1})
        assert response.status_code == 422

    def test_add_component_and_delete_it(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        added = client.post(f"/agreements/{agreement_id}/components", headers=AUTH,
                            json={"actor": "webapp", "label": "בונוס", "amount": 900})
        assert added.status_code == 200
        key = next(c["component_key"] for c in added.json()["agreement"]["components"] if c["label"] == "בונוס")
        deleted = client.delete(f"/agreements/{agreement_id}/components/{key}", headers=AUTH, params={"actor": "webapp"})
        assert deleted.status_code == 200
        assert "בונוס" not in [c["label"] for c in deleted.json()["agreement"]["components"]]
        assert len(deleted.json()["ledger_event_ids"]) == 1

    def test_cancel_agreement_cascades_and_locks(self, client):
        agreement = _new_agreement(client)["agreement"]
        response = client.post(f"/agreements/{agreement['agreement_id']}/status", headers=AUTH,
                               json={"actor": "webapp", "action": "cancel"})
        assert response.status_code == 200
        data = response.json()["agreement"]
        assert data["status"] == "Cancelled"
        assert {c["status"] for c in data["components"]} == {"Cancelled"}
        assert all(c["locked"] for c in data["components"])

    def test_revisions_are_chronological_and_changed_marks_edits(self, client):
        agreement_id = _new_agreement(client)["agreement"]["agreement_id"]
        client.patch(f"/agreements/{agreement_id}", headers=AUTH, json={"actor": "webapp", "payer_name": "חברה"})
        revisions = client.get(f"/agreements/{agreement_id}/revisions", headers=AUTH).json()["revisions"]
        assert [r["action"] for r in revisions][:1] == ["create_agreement"]
        assert revisions[-1]["action"] == "edit_agreement"
        assert json.dumps(revisions[-1]["changed"], ensure_ascii=False)

    def test_ledger_busy_is_503_and_writes_nothing(self, client, manager):
        """Fill this minute's ten `הסכם` event-id slots; a write needing one more is refused
        whole (human decision 2026-10-09), and nothing lands in the DB."""
        ledger = manager.denidin.ledger_event_manager
        minute = now_local().strftime("%H%M")
        for index in range(10):
            ledger.add_ledger_events_from_call(
                session_id=None, message_id=None, message_timestamp=None,
                call_arguments={"source_type": "הסכם", "client_name": f"לקוח{index}", "description": "d",
                                "components": [{"amount": "1", "component_label": "x"}], "component_count": 1})
        response = client.post("/agreements", headers=AUTH, json={
            "actor": "webapp", "client_name": "לקוח חדש", "title": "t", "components": [{"label": "a", "amount": 1}]})
        if now_local().strftime("%H%M") != minute:
            pytest.skip("the minute rolled over mid-test")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ledger_busy"
        assert client.get("/agreements", params={"client_name": "לקוח חדש"}, headers=AUTH).json()["agreements"] == []
