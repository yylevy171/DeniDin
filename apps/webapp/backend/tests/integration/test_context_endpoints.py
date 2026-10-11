"""Integration tests for /events/{id}/context and /media/{token} (Story 3A)."""
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx_client(app_config, known_password):
    from starlette.testclient import TestClient

    from webapp_backend.server import build_app

    root = Path(app_config.denidin_data_root)
    (root / "events").mkdir(parents=True)
    (root / "media").mkdir()
    (root / "media" / "shot.jpg").write_bytes(b"\xff\xd8\xffDATA")
    (root / "events" / "E1.json").write_text(json.dumps({
        "event_id": "E1", "source_type": "בנק", "event_subtype": "הפקדה",
        "client_name": "פלוני", "amount": 1000, "description": "d",
        "event_datetime": "03/08/2026 19:20", "txn_date": None,
        "session_id": "s1", "message_id": "m2",
    }, ensure_ascii=False), encoding="utf-8")
    (root / "events" / "E2.json").write_text(json.dumps({
        "event_id": "E2", "source_type": "הסכם", "event_subtype": "יצירה",
        "client_name": "x", "amount": 1, "description": "d",
        "event_datetime": "03/08/2026 19:20", "txn_date": None,
        "session_id": "ghost-session", "message_id": "m9",
    }, ensure_ascii=False), encoding="utf-8")

    sdir = root / "sessions" / "s1" / "messages"
    sdir.mkdir(parents=True)
    (root / "sessions" / "s1" / "session.json").write_text('{"session_id": "s1"}', encoding="utf-8")
    (sdir / "m1.json").write_text(json.dumps({
        "message_id": "m1", "role": "user", "content": "here is the deposit",
        "timestamp": "2026-08-03T19:15:00+00:00", "image_path": "media/shot.jpg",
    }), encoding="utf-8")
    (sdir / "m2.json").write_text(json.dumps({
        "message_id": "m2", "role": "assistant", "content": "logged it",
        "timestamp": "2026-08-03T19:20:00+00:00",
    }), encoding="utf-8")

    with TestClient(build_app(app_config)) as c:
        c._token = c.post("/api/auth/login", json={"password": known_password}).json()["token"]
        yield c


def _auth(c):
    return {"Authorization": f"Bearer {c._token}"}


def test_context_happy_path_with_media(ctx_client):
    body = ctx_client.get("/api/events/E1/context", headers=_auth(ctx_client)).json()
    assert [m["message_id"] for m in body["messages"]] == ["m1", "m2"]
    assert body["messages"][0]["side"] == "right"
    assert body["messages"][1]["side"] == "left"
    media_url = body["messages"][0]["media_url"]

    media = ctx_client.get(media_url, headers=_auth(ctx_client))
    assert media.status_code == 200
    assert media.content == b"\xff\xd8\xffDATA"
    assert media.headers["content-type"].startswith("image/")


def test_context_unavailable_for_missing_session(ctx_client):
    body = ctx_client.get("/api/events/E2/context", headers=_auth(ctx_client)).json()
    assert body["error"] == "context_unavailable"


def test_context_404_for_unknown_event(ctx_client):
    resp = ctx_client.get("/api/events/NOPE/context", headers=_auth(ctx_client))
    assert resp.status_code == 404


def test_media_unknown_token_404(ctx_client):
    assert ctx_client.get("/api/media/garbage", headers=_auth(ctx_client)).status_code == 404


def test_context_and_media_require_auth(ctx_client):
    assert ctx_client.get("/api/events/E1/context").status_code == 401
    assert ctx_client.get("/api/media/whatever").status_code == 401


def test_lookback_minutes_clamped(ctx_client):
    body = ctx_client.get(
        "/api/events/E1/context?lookback_minutes=9999", headers=_auth(ctx_client)
    ).json()
    assert body["lookback_minutes_used"] == 60
