"""Integration tests for the auth endpoints + route guard (Story 1A).

Real Starlette app via TestClient, real temp password-hash file, no mocking.
"""
import logging

import pytest

pytestmark = pytest.mark.integration


def test_health_is_unauthenticated(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert body["version"]  # from apps/webapp/VERSION


def test_login_wrong_password_401(client):
    resp = client.post("/api/auth/login", json={"password": "not-it"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_password"


def test_login_right_password_returns_token(client, known_password):
    resp = client.post("/api/auth/login", json={"password": known_password})
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_protected_route_requires_token(client):
    assert client.get("/api/events").status_code == 401
    assert client.get(
        "/api/events", headers={"Authorization": "Bearer garbage"}
    ).status_code == 401


def test_login_then_use_token_then_logout_invalidates_it(client, known_password):
    token = client.post("/api/auth/login", json={"password": known_password}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/events", headers=auth).status_code == 200

    assert client.post("/api/auth/logout", headers=auth).status_code == 204

    # same token no longer works — the route guard trusts server state, not the client
    assert client.get("/api/events", headers=auth).status_code == 401


def test_concurrent_sessions_do_not_interfere(client, known_password):
    a = client.post("/api/auth/login", json={"password": known_password}).json()["token"]
    b = client.post("/api/auth/login", json={"password": known_password}).json()["token"]
    assert a != b
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {a}"})
    assert client.get("/api/events", headers={"Authorization": f"Bearer {a}"}).status_code == 401
    assert client.get("/api/events", headers={"Authorization": f"Bearer {b}"}).status_code == 200


def test_every_login_attempt_is_audit_logged_without_secrets(client, known_password, caplog):
    with caplog.at_level(logging.INFO, logger="webapp_backend"):
        client.post("/api/auth/login", json={"password": "wrong"})
        client.post("/api/auth/login", json={"password": known_password})

    login_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("LOGIN ")]
    assert login_lines == ["LOGIN failure", "LOGIN success"]
    joined = "\n".join(login_lines)
    assert known_password not in joined
    assert "wrong" not in joined


def test_missing_password_file_starts_app_but_all_logins_fail(tmp_path, known_password):
    from starlette.testclient import TestClient

    from webapp_backend.config import AppConfig
    from webapp_backend.server import build_app

    cfg = AppConfig(
        environment="test",
        password_hash_file=str(tmp_path / "nope" / "password.hash"),
        denidin_data_root=str(tmp_path),
        password_salt="denidin-pw",
    )
    with TestClient(build_app(cfg)) as c:
        assert c.get("/health").status_code == 200
        assert c.post("/api/auth/login", json={"password": known_password}).status_code == 401
