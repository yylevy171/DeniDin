"""Integration tests for the event-listing endpoints (Story 2A)."""
import json
from datetime import timedelta

import pytest

from utils.time_utils import now_local

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_client(app_config, known_password):
    from starlette.testclient import TestClient

    from webapp_backend.server import build_app

    events_dir = __import__("pathlib").Path(app_config.denidin_data_root) / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    recent = (now_local().date() - timedelta(days=1)).strftime("%d/%m/%Y")
    old = (now_local().date() - timedelta(days=40)).strftime("%d/%m/%Y")
    for eid, when, name in [("A1", recent, "Dana Cohen"), ("A2", recent, "Dan Levi"),
                            ("A3", old, "Old Client")]:
        (events_dir / f"{eid}.json").write_text(json.dumps({
            "event_id": eid, "source_type": "הסכם", "event_subtype": "יצירה",
            "client_name": name, "amount": 500, "description": "d",
            "event_datetime": f"{when} 10:00", "txn_date": None,
        }, ensure_ascii=False), encoding="utf-8")

    with TestClient(build_app(app_config)) as c:
        c._token = c.post("/api/auth/login", json={"password": known_password}).json()["token"]
        yield c


def _auth(c):
    return {"Authorization": f"Bearer {c._token}"}


def test_events_default_window(seeded_client):
    resp = seeded_client.get("/api/events", headers=_auth(seeded_client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["days_back"] == 7
    assert {r["event_id"] for r in body["events"]} == {"A1", "A2"}
    assert body["count"] == 2


def test_events_wider_window_includes_old(seeded_client):
    body = seeded_client.get("/api/events?days_back=60", headers=_auth(seeded_client)).json()
    assert {r["event_id"] for r in body["events"]} == {"A1", "A2", "A3"}


def test_events_bad_days_back_defaults(seeded_client):
    body = seeded_client.get("/api/events?days_back=abc", headers=_auth(seeded_client)).json()
    assert body["days_back"] == 7


def test_event_detail_found_and_404(seeded_client):
    ok = seeded_client.get("/api/events/A1", headers=_auth(seeded_client))
    assert ok.status_code == 200
    body = ok.json()
    assert body["event_id"] == "A1"
    client_field = next(f for f in body["fields"] if f["key"] == "client_name")
    assert client_field["value"] == "Dana Cohen"
    assert client_field["label"] == "שם לקוח"

    missing = seeded_client.get("/api/events/ZZ", headers=_auth(seeded_client))
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"


def test_clients_search_prefix(seeded_client):
    body = seeded_client.get("/api/clients/search?prefix=da", headers=_auth(seeded_client)).json()
    assert body["clients"] == ["Dan Levi", "Dana Cohen"]

    assert seeded_client.get(
        "/api/clients/search?prefix=d", headers=_auth(seeded_client)
    ).json()["clients"] == []


def test_event_endpoints_require_auth(seeded_client):
    assert seeded_client.get("/api/events").status_code == 401
    assert seeded_client.get("/api/events/A1").status_code == 401
    assert seeded_client.get("/api/clients/search?prefix=da").status_code == 401
