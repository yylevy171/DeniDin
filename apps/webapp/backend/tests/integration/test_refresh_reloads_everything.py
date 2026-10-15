"""bugfix-074 - any refresh reloads everything: the ledger event files, the cached conversations, the
Morning client list and the computed clients report. Real Starlette app (``build_app`` + ``TestClient``),
real files on disk; the official client list is injected (no Morning call)."""
import json

import pytest

from tests.clients_helpers import agreement, payment
from tests.integration.test_agreements_endpoints import TOKEN as AGREEMENTS_TOKEN, denidin_api  # noqa: F401

pytestmark = pytest.mark.integration

OLD_CLIENT = "לקוח ותיק"
NEW_CLIENT = "לקוח חדש"


@pytest.fixture
def world(tmp_path, password_hash_file, known_password, denidin_api):  # noqa: F811
    """(api, write_event, official) - ``official`` is the live Morning list the app reads from."""
    from starlette.testclient import TestClient

    from webapp_backend.config import AppConfig
    from webapp_backend.server import build_app

    data_root = tmp_path / "data"
    events_dir = data_root / "events"
    events_dir.mkdir(parents=True)

    def write_event(e):
        (events_dir / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")

    write_event(agreement("A1", OLD_CLIENT, 1000))
    official = [OLD_CLIENT]
    config = AppConfig(
        environment="test", password_hash_file=str(password_hash_file), denidin_data_root=str(data_root),
        webapp_data_root=str(tmp_path / "webapp_data"),
        denidin_agreements_url=denidin_api, denidin_agreements_token=AGREEMENTS_TOKEN,
    )
    totals = {OLD_CLIENT: 1000.0, NEW_CLIENT: 8000.0}
    with TestClient(build_app(config, official_clients_fn=lambda: list(official),
                              agreements_totals_fn=lambda: dict(totals))) as api:
        token = api.post("/api/auth/login", json={"password": known_password}).json()["token"]
        api.headers.update({"Authorization": f"Bearer {token}"})
        api.get("/api/clients")  # fill the caches, as the first page load does
        yield api, write_event, official


def _section(api, name):
    rows = {r["official_name"]: r for r in api.get("/api/clients").json()["clients"]}
    return rows[name]["status"] if name in rows else None


def _event_ids(api):
    return {e["event_id"] for e in api.get("/api/events").json()["events"]}


def _add_new_client_with_agreement(write_event, official):
    """What happens in WhatsApp: the client is created in Morning and an agreement event is written."""
    official.append(NEW_CLIENT)
    write_event(agreement("A9", NEW_CLIENT, 8000))


class TestClientsRefreshReloadsTheLedger:
    def test_new_client_is_not_stuck_in_past(self, world):
        api, write_event, official = world
        _add_new_client_with_agreement(write_event, official)

        api.get("/api/clients?refresh=1")

        assert _section(api, NEW_CLIENT) == "debt"  # not "past"

    def test_events_list_shows_the_new_event(self, world):
        api, write_event, official = world
        _add_new_client_with_agreement(write_event, official)
        assert "A9" not in _event_ids(api)

        api.get("/api/clients?refresh=1")

        assert "A9" in _event_ids(api)


class TestEventsRefreshReloadsTheClients:
    def test_new_morning_client_appears(self, world):
        api, write_event, official = world
        _add_new_client_with_agreement(write_event, official)
        assert _section(api, NEW_CLIENT) is None

        api.get("/api/events?refresh=1")

        assert _section(api, NEW_CLIENT) == "debt"


class TestRefreshEndpoint:
    def test_reloads_both(self, world):
        api, write_event, official = world
        _add_new_client_with_agreement(write_event, official)

        resp = api.post("/api/refresh")

        assert resp.status_code == 204
        assert "A9" in _event_ids(api)
        assert _section(api, NEW_CLIENT) == "debt"

    def test_requires_auth(self, world):
        api, _, _ = world
        api.headers.pop("Authorization")
        assert api.post("/api/refresh").status_code == 401
