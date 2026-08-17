"""Tests for the MCP server's optional bearer-token auth (Phase 5, T021-auth;
extended Feature 055 Phase 6/T023a for per-tenant token maps).

Real Starlette app + real Starlette TestClient (ASGI in-process, not
mocking) — no application code under test is faked. The original single-
shared-secret mode (`token=`) still has exactly this shape (one expected main
consumer, denidin-app, plus ad hoc manual tests - not multi-tenant OAuth);
Feature 055 adds a second, opt-in mode (`tokens=`, a per-tenant map) used only
once a config actually lists more than one tenant (REQ-PARITY-001: `token=`
alone is unchanged).
"""
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from denidin_mcp_morning.server import BearerTokenMiddleware
from denidin_mcp_morning.utils.tenant_context import current_tenant_id


def _build_app(auth_token=None, tenant_tokens=None):
    async def homepage(request):
        return PlainTextResponse("ok")

    async def whoami(request):
        return PlainTextResponse(str(current_tenant_id()))

    app = Starlette(routes=[Route("/", homepage), Route("/whoami", whoami)])
    if tenant_tokens is not None:
        app.add_middleware(BearerTokenMiddleware, tokens=tenant_tokens)
    else:
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


class TestPerTenantTokenMap:
    """Feature 055 Phase 6, T023a: each tenant's own token resolves to that
    tenant's tenant_id; an unrecognized token is rejected exactly as an
    invalid shared secret is today; two tenants sharing a token is a config-
    load error (tested at the config layer, test_config.py - not reachable
    here since the middleware itself is handed an already-built map)."""

    def _tenant_app(self):
        return _build_app(tenant_tokens={"token-a": "tenant-a", "token-b": "tenant-b"})

    def test_each_tenant_token_is_accepted(self):
        client = TestClient(self._tenant_app())

        response_a = client.get("/", headers={"Authorization": "Bearer token-a"})
        response_b = client.get("/", headers={"Authorization": "Bearer token-b"})

        assert response_a.status_code == 200
        assert response_b.status_code == 200

    def test_unrecognized_token_rejected_same_as_an_invalid_shared_secret(self):
        client = TestClient(self._tenant_app())

        response = client.get("/", headers={"Authorization": "Bearer not-a-real-token"})

        assert response.status_code == 401

    def test_missing_authorization_header_rejected(self):
        client = TestClient(self._tenant_app())

        response = client.get("/")

        assert response.status_code == 401

    def test_each_tokens_own_tenant_id_is_bound_for_the_request(self):
        """The resolved tenant_id is actually available downstream (via
        utils.tenant_context) for the duration of that request - not just
        "the request was allowed through"."""
        client = TestClient(self._tenant_app())

        response_a = client.get("/whoami", headers={"Authorization": "Bearer token-a"})
        response_b = client.get("/whoami", headers={"Authorization": "Bearer token-b"})

        assert response_a.text == "tenant-a"
        assert response_b.text == "tenant-b"

    def test_tenant_context_is_unset_outside_any_request(self):
        assert current_tenant_id() is None

    def test_health_path_still_bypasses_auth_in_tenant_mode(self):
        """Same existing exemption as single-secret mode - unauthenticated
        liveness probes must keep working regardless of auth mode."""
        async def health(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/health", health)])
        app.add_middleware(
            BearerTokenMiddleware, tokens={"token-a": "tenant-a"}
        )
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200

    def test_legacy_single_secret_mode_still_binds_no_tenant(self):
        """REQ-PARITY-001: the original token= mode is unaffected - it still
        grants access with no tenant concept at all (current_tenant_id() stays
        None), never accidentally resolving some default tenant."""
        client = TestClient(_build_app(auth_token="super-secret"))

        response = client.get("/whoami", headers={"Authorization": "Bearer super-secret"})

        assert response.text == "None"
