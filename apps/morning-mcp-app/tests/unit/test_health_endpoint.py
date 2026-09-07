"""Tests for the /health and /is_alive route handlers (bugfix-043).

Real Starlette app + real Starlette TestClient (same pattern as
test_auth_middleware.py), built directly from the handler factories rather
than the full FastMCP server - no application code under test is faked.
"""
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from denidin_mcp_morning.server import (
    BearerTokenMiddleware,
    HEALTH_PATH,
    IS_ALIVE_PATH,
    _make_health_handler,
    _make_is_alive_handler,
)


class _FakeAuth:
    def __init__(self, should_succeed: bool):
        self._should_succeed = should_succeed

    def get_token(self):
        if self._should_succeed:
            return "fake-token"
        raise ConnectionError("simulated auth failure")


class _FakeClient:
    def __init__(self, should_succeed: bool):
        self.auth = _FakeAuth(should_succeed)


def _build_app(morning_client=None, log_path=None, auth_token=None):
    app = Starlette(
        routes=[
            Route(HEALTH_PATH, _make_health_handler("test", "1.0.0", morning_client=morning_client, log_path=log_path), methods=["GET"]),
            Route(IS_ALIVE_PATH, _make_is_alive_handler(), methods=["GET"]),
        ]
    )
    if auth_token:
        app.add_middleware(BearerTokenMiddleware, token=auth_token)
    return app


def test_health_returns_200_when_no_deep_checks_configured():
    """Backward-compatible shape - callers that don't pass
    morning_client/log_path (e.g. watchdog.py's existing simple check) still
    get a plain 200 with no deep checks reported as failed."""
    client = TestClient(_build_app())

    response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_up"] == "success"
    assert "morning_connectivity" not in body
    assert "logs_writing" not in body


def test_health_returns_200_when_all_deep_checks_succeed(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("recent\n")

    client = TestClient(_build_app(morning_client=_FakeClient(should_succeed=True), log_path=log_path))

    response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["morning_connectivity"] == "success"
    assert body["logs_writing"] == "success"


def test_health_returns_503_when_morning_connectivity_fails(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("recent\n")

    client = TestClient(_build_app(morning_client=_FakeClient(should_succeed=False), log_path=log_path))

    response = client.get(HEALTH_PATH)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "fail"
    assert body["morning_connectivity"] == "fail"
    assert body["logs_writing"] == "success"


def test_health_returns_503_when_logs_are_stale(tmp_path):
    import os
    import time

    log_path = tmp_path / "app.log"
    log_path.write_text("old\n")
    old_time = time.time() - 3600
    os.utime(log_path, (old_time, old_time))

    client = TestClient(_build_app(morning_client=_FakeClient(should_succeed=True), log_path=log_path))

    response = client.get(HEALTH_PATH)

    assert response.status_code == 503
    assert response.json()["logs_writing"] == "fail"


def test_is_alive_returns_200_with_no_real_checks():
    client = TestClient(_build_app())

    response = client.get(IS_ALIVE_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_is_alive_exempt_from_bearer_auth_same_as_health():
    """is_alive must be reachable unauthenticated - it's called from
    denidin-app across the tunnel specifically to test raw reachability,
    which a 401 would defeat the purpose of."""
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get(IS_ALIVE_PATH)

    assert response.status_code == 200


def test_health_still_exempt_from_bearer_auth_with_is_alive_present():
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get(HEALTH_PATH)

    assert response.status_code == 200
