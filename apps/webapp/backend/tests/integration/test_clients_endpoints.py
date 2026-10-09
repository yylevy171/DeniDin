"""Feature 092 - Clients-tab write endpoints, end to end through the real Starlette app
(``build_app`` + ``TestClient``), real files on disk. The official Morning client list is
supplied via ``build_app``'s injected ``official_clients_fn`` (dependency injection - no
Morning call, no mock)."""
import json
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.clients_helpers import MIGRATION_KEY, OLD, agreement, payment, read_json, write_json

pytestmark = pytest.mark.integration

DEBT = "לקוח חוב"  # 10,000 / 2,000
PAID = "לקוח משלם"  # 3,000 / 3,000
PAST = "לקוח עבר"
OFFICIAL = [DEBT, PAID, PAST]


@pytest.fixture
def clients_dir(tmp_path) -> Path:
    return tmp_path / "webapp_data" / "clients"


@pytest.fixture
def api(tmp_path, password_hash_file, known_password, clients_dir):
    from starlette.testclient import TestClient

    from webapp_backend.config import AppConfig
    from webapp_backend.server import build_app

    data_root = tmp_path / "data"
    events_dir = data_root / "events"
    events_dir.mkdir(parents=True)
    for e in [
        agreement("A1", DEBT, 10000), payment("C1", DEBT, 2000),
        agreement("A2", PAID, 3000), payment("C2", PAID, 3000),
        agreement("A3", PAST, 4000, when=OLD),
    ]:
        (events_dir / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    write_json(clients_dir / "migrations.json", {MIGRATION_KEY: "2026-10-01T00:00:00+03:00"})

    config = AppConfig(
        environment="test",
        password_hash_file=str(password_hash_file),
        denidin_data_root=str(data_root),
        webapp_data_root=str(tmp_path / "webapp_data"),
    )
    # Feature 089: the agreed total now comes from the Agreements DB; the totals are injected
    # here (dependency injection, like the official client list) - the fixture's ledger
    # `הסכם` events only mirror them and are no longer summed.
    totals = {DEBT: 10000.0, PAID: 3000.0, PAST: 4000.0}
    with TestClient(build_app(config, official_clients_fn=lambda: list(OFFICIAL),
                              agreements_totals_fn=lambda: dict(totals))) as c:
        token = c.post("/api/auth/login", json={"password": known_password}).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def _status(api, client, action):
    return api.post(f"/api/clients/{quote(client)}/status", json={"action": action})


def _row(api, client):
    body = api.get("/api/clients").json()
    return next(r for r in body["clients"] if r["official_name"] == client)


class TestSetLineStatus:
    @pytest.mark.parametrize("action,stored,section", [
        ("close", "closed", "settled"),
        ("check", "check", "check"),
        ("active", "active", "active"),
    ])
    def test_action_persists_and_reroutes(self, api, clients_dir, action, stored, section):
        resp = _status(api, DEBT, action)
        assert resp.status_code == 200
        assert resp.json() == {"client_id": DEBT, "line_status": stored}
        assert read_json(clients_dir / "client_status.json") == {DEBT: stored}
        r = _row(api, DEBT)
        assert r["status"] == section
        assert r["line_status"] == stored
        assert (r["display_agreed"], r["display_paid"]) == (10000, 2000)

    def test_reopen_closed_debt_line_returns_to_debt(self, api, clients_dir):
        _status(api, DEBT, "close")
        resp = _status(api, DEBT, "reopen")
        assert resp.status_code == 200
        assert resp.json() == {"client_id": DEBT, "line_status": None}
        assert DEBT not in read_json(clients_dir / "client_status.json", {})
        assert _row(api, DEBT)["status"] == "debt"

    def test_reopen_closed_fully_paid_line_goes_active(self, api):
        _status(api, PAID, "close")
        resp = _status(api, PAID, "reopen")
        assert resp.json()["line_status"] == "active"
        assert _row(api, PAID)["status"] == "active"

    def test_reopen_computed_green_line_goes_active(self, api):
        assert _row(api, PAID)["status"] == "settled"
        resp = _status(api, PAID, "reopen")
        assert resp.status_code == 200
        assert resp.json()["line_status"] == "active"
        assert _row(api, PAID)["status"] == "active"

    def test_repeating_an_action_is_idempotent(self, api):
        assert _status(api, DEBT, "check").status_code == 200
        assert _status(api, DEBT, "check").status_code == 200
        assert _row(api, DEBT)["status"] == "check"


class TestSetLineStatusErrors:
    def test_unknown_action_is_400(self, api):
        resp = _status(api, DEBT, "explode")
        assert resp.status_code == 400
        assert resp.json()["error"] == "bad_request"

    def test_missing_action_is_400(self, api):
        resp = api.post(f"/api/clients/{quote(DEBT)}/status", json={})
        assert resp.status_code == 400

    def test_unknown_client_is_404(self, api):
        resp = _status(api, "אין כזה לקוח", "close")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_past_line_is_409_and_unchanged(self, api, clients_dir):
        resp = _status(api, PAST, "close")
        assert resp.status_code == 409
        assert resp.json()["error"] == "not_allowed"
        assert PAST not in read_json(clients_dir / "client_status.json", {})
        assert _row(api, PAST)["status"] == "past"

    def test_requires_auth(self, api):
        api.headers.pop("Authorization")
        assert _status(api, DEBT, "close").status_code == 401


@pytest.fixture
def api_with_aliases(api, clients_dir, tmp_path):
    """Adds an unresolved bank name and an explicit mapping on top of ``api``'s ledger."""
    events_dir = tmp_path / "data" / "events"
    for e in [payment("C9", "Yisrael I", 500), payment("C8", "שם לא מוכר", 50)]:
        (events_dir / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    write_json(clients_dir / "client_mapping.json", {"Yisrael I": DEBT})
    write_json(clients_dir / "mapping_notes.json", {"Yisrael I": "הערה"})
    api.get("/api/events?refresh=1")  # the ledger reload (clients ?refresh=1 doesn't re-read events)
    return api


def _unmatched_names(api, refresh=False):
    body = api.get("/api/clients?refresh=1" if refresh else "/api/clients").json()
    return {u["raw_name"]: u for u in body["unmatched"]}


class TestUnlinkMapping:
    """T019"""

    def test_unlink_returns_name_to_resolve_list(self, api_with_aliases, clients_dir):
        api = api_with_aliases
        assert _row(api, DEBT)["mapped_aliases"] == ["Yisrael I"]
        assert _row(api, DEBT)["display_paid"] == 2500

        resp = api.post("/api/clients/mapping/unlink", json={"raw_name": "Yisrael I"})
        assert resp.status_code == 200
        assert resp.json() == {"raw_name": "Yisrael I", "unlinked_from": DEBT}
        assert read_json(clients_dir / "client_mapping.json") == {}

        assert _row(api, DEBT)["display_paid"] == 2000
        assert _row(api, DEBT)["mapped_aliases"] == []
        assert _unmatched_names(api)["Yisrael I"]["note"] == "הערה"

    def test_unlink_unknown_name_is_404(self, api_with_aliases):
        resp = api_with_aliases.post("/api/clients/mapping/unlink", json={"raw_name": "אין"})
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_unlink_missing_raw_name_is_400(self, api_with_aliases):
        assert api_with_aliases.post("/api/clients/mapping/unlink", json={}).status_code == 400

    def test_unlink_requires_auth(self, api_with_aliases):
        api_with_aliases.headers.pop("Authorization")
        resp = api_with_aliases.post("/api/clients/mapping/unlink", json={"raw_name": "Yisrael I"})
        assert resp.status_code == 401


class TestHideUnmatched:
    """T028"""

    def test_hide_is_persisted_idempotent_and_survives_refresh(self, api_with_aliases, clients_dir):
        api = api_with_aliases
        assert "שם לא מוכר" in _unmatched_names(api)
        for _ in range(2):
            resp = api.post("/api/clients/unmatched/hide", json={"raw_name": "שם לא מוכר"})
            assert resp.status_code == 200
            assert resp.json() == {"raw_name": "שם לא מוכר", "hidden": True}
        assert read_json(clients_dir / "hidden_unmatched.json") == ["שם לא מוכר"]
        assert "שם לא מוכר" not in _unmatched_names(api, refresh=True)

    def test_hide_missing_raw_name_is_400(self, api_with_aliases):
        assert api_with_aliases.post("/api/clients/unmatched/hide", json={}).status_code == 400

    def test_hide_requires_auth(self, api_with_aliases):
        api_with_aliases.headers.pop("Authorization")
        resp = api_with_aliases.post("/api/clients/unmatched/hide", json={"raw_name": "x"})
        assert resp.status_code == 401
