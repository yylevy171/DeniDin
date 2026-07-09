"""Tests for the MCP server's optional bearer-token auth (Phase 5, T021-auth).

Real Starlette app + real Starlette TestClient (ASGI in-process, not
mocking) — no application code under test is faked. This server has one
expected main consumer (denidin-app) plus ad hoc manual tests, so a single
shared secret is the appropriate model, not multi-tenant OAuth.
"""
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from denidin_mcp_morning.server import BearerTokenMiddleware


def _build_app(auth_token):
    async def homepage(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(BearerTokenMiddleware, token=auth_token)
    return app


def test_no_token_configured_allows_any_request():
    """No auth_token set -> the middleware is a no-op (pure local/dev use)."""
    client = TestClient(_build_app(auth_token=None))

    response = client.get("/")

    assert response.status_code == 200
    assert response.text == "ok"


def test_missing_authorization_header_rejected_when_token_configured():
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get("/")

    assert response.status_code == 401


def test_wrong_token_rejected():
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get("/", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401


def test_correct_token_allowed():
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get("/", headers={"Authorization": "Bearer super-secret"})

    assert response.status_code == 200
    assert response.text == "ok"


def test_malformed_authorization_header_rejected():
    """A header present but not in the 'Bearer <token>' shape must not be
    accidentally accepted (e.g. Basic auth, or just the raw token)."""
    client = TestClient(_build_app(auth_token="super-secret"))

    response = client.get("/", headers={"Authorization": "super-secret"})

    assert response.status_code == 401
