"""Tests for denidin_mcp_morning.auth — MorningAuth's OAuth2 client_credentials
flow against Morning's real, current token endpoint (feature 053; migrated
from the deprecated `/account/token` JWT exchange - see
https://www.greeninvoice.co.il/help-center/api-updates-26/ and auth.py's own
docstring for the full, source-verified contract).

`requests.post` is monkeypatched here - this mocks the third-party network
call itself (CONSTITUTION §I/§V permits mocking external services in tests;
it's mocking internal application components that's forbidden), never an
internal component. See tests/integration/test_morning_sandbox_auth_oauth2.py
for the real, unmocked round-trip against the actual sandbox.
"""
import json

import pytest
import requests

from denidin_mcp_morning.auth import MorningAuth

_AUTH_URL = "https://api.sandbox.morning.dev"
_CLIENT_ID = "test-client-id"
_CLIENT_SECRET = "test-client-secret"


class _FakeResponse:
    """Stands in for `requests.Response` - the real third-party network
    boundary being mocked here, not an internal component."""

    def __init__(self, status_code: int, body: dict, content: bool = True):
        self.status_code = status_code
        self._body = body
        self.content = content
        self.text = json.dumps(body)
        self.headers = {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if 400 <= self.status_code:
            http_error = requests.exceptions.HTTPError(f"{self.status_code} error")
            http_error.response = self
            raise http_error


def _success_response(access_token="real-jwt-token", expires_at=9999999999):
    return _FakeResponse(200, {"accessToken": access_token, "tokenType": "Bearer", "expiresAt": expires_at})


def _oauth2_error_response(status_code, error_code):
    return _FakeResponse(status_code, {"error": error_code, "error_description": "details"})


def _make_auth(refresh_before_seconds=300):
    return MorningAuth(
        api_key_id=_CLIENT_ID,
        api_key_secret=_CLIENT_SECRET,
        auth_url=_AUTH_URL,
        refresh_before_seconds=refresh_before_seconds,
    )


# --------------------------------------------------------------------- request shape

def test_request_token_posts_to_the_real_oauth2_endpoint(monkeypatch):
    """Confirmed contract (Morning's real, current OpenAPI spec, not assumed):
    POST {auth_url}/idp/v1/oauth/token - a DIFFERENT host than the main API."""
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _success_response()

    monkeypatch.setattr(requests, "post", fake_post)
    auth = _make_auth()

    auth.get_token()

    assert captured["url"] == "https://api.sandbox.morning.dev/idp/v1/oauth/token"


def test_request_token_body_has_grant_type_client_id_client_secret(monkeypatch):
    """Confirmed contract: TokenRequest schema requires exactly these three
    fields - `id`/`secret` (the old shape) is no longer accepted."""
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _success_response()

    monkeypatch.setattr(requests, "post", fake_post)
    auth = _make_auth()

    auth.get_token()

    assert captured["json"] == {
        "grant_type": "client_credentials",
        "client_id": _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
    }


def test_auth_url_is_independent_of_base_url(monkeypatch):
    """The token endpoint's host must never be derived from base_url/api_url -
    MorningAuth doesn't even accept a base_url anymore, only auth_url."""
    assert not hasattr(_make_auth(), "base_url")


# --------------------------------------------------------------------- response parsing

def test_get_token_returns_the_real_access_token(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _success_response(access_token="abc123"))
    auth = _make_auth()

    assert auth.get_token() == "abc123"


def test_get_token_raises_clear_error_when_access_token_missing(monkeypatch):
    """Never silently return an empty/None token - fail loudly and clearly."""
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **k: _FakeResponse(200, {"tokenType": "Bearer", "expiresAt": 9999999999}),
    )
    auth = _make_auth()

    with pytest.raises(RuntimeError, match="accessToken"):
        auth.get_token()


def test_get_token_raises_clear_error_when_expires_at_missing(monkeypatch):
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **k: _FakeResponse(200, {"accessToken": "abc123", "tokenType": "Bearer"}),
    )
    auth = _make_auth()

    with pytest.raises(RuntimeError, match="expiresAt"):
        auth.get_token()


# --------------------------------------------------------------------- caching / expiry

def test_get_token_caches_and_does_not_refetch_within_expiry(monkeypatch):
    call_count = {"n": 0}

    def fake_post(*a, **k):
        call_count["n"] += 1
        return _success_response(expires_at=9999999999)  # far future

    monkeypatch.setattr(requests, "post", fake_post)
    auth = _make_auth()

    first = auth.get_token()
    second = auth.get_token()

    assert first == second
    assert call_count["n"] == 1


def test_get_token_uses_the_real_expires_at_not_an_assumed_ttl(monkeypatch):
    """Core feature-053 behavior: cache expiry is the REAL timestamp Morning
    returned, not `now + some_config_default` (the old, removed
    token_ttl_seconds behavior)."""
    import time

    real_expires_at = time.time() + 2  # 2 seconds from now
    monkeypatch.setattr(requests, "post", lambda *a, **k: _success_response(expires_at=real_expires_at))
    auth = _make_auth(refresh_before_seconds=0)

    assert auth._token_expiry == 0.0  # nothing fetched yet
    auth.get_token()
    assert auth._token_expiry == real_expires_at


def test_get_token_refreshes_once_past_real_expiry_minus_refresh_margin(monkeypatch):
    import time

    call_count = {"n": 0}
    now = time.time()

    def fake_post(*a, **k):
        call_count["n"] += 1
        # First call: expires in 100s. Second call (after we fast-forward the
        # clock past expiry - refresh_before_seconds): expires far in the future.
        expires_at = now + 100 if call_count["n"] == 1 else now + 999999
        return _success_response(expires_at=expires_at)

    monkeypatch.setattr(requests, "post", fake_post)
    auth = _make_auth(refresh_before_seconds=300)  # refresh anytime within 300s of expiry

    auth.get_token()
    assert call_count["n"] == 1  # first fetch

    # expires_at (now+100) - refresh_before_seconds (300) is already in the
    # past relative to `now`, so the very next get_token() must refetch.
    auth.get_token()
    assert call_count["n"] == 2


# --------------------------------------------------------------------- OAuth2 error cases (US2)

@pytest.mark.parametrize("status_code,error_code", [
    (400, "invalid_request"),
    (400, "unsupported_grant_type"),
    (400, "invalid_grant"),
    (400, "unauthorized_client"),
    (401, "invalid_client"),
])
def test_each_documented_oauth2_error_raises_http_error(monkeypatch, status_code, error_code):
    """Every documented Morning OAuth2 error case (RFC 6749 format) must
    surface as a requests.exceptions.HTTPError - never crash uncaught, never
    silently return an empty/fake token. The MCP boundary
    (errors.friendly_error_message) maps this onward to a friendly message -
    covered separately; this test only proves auth.py itself fails correctly."""
    monkeypatch.setattr(requests, "post", lambda *a, **k: _oauth2_error_response(status_code, error_code))
    auth = _make_auth()

    with pytest.raises(requests.exceptions.HTTPError):
        auth.get_token()


def test_oauth2_error_response_status_code_is_preserved_on_the_exception(monkeypatch):
    """errors.friendly_error_message's mapping (401->auth-failed, 400->
    request-rejected) depends on exc.response.status_code being real and
    correct."""
    monkeypatch.setattr(requests, "post", lambda *a, **k: _oauth2_error_response(401, "invalid_client"))
    auth = _make_auth()

    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        auth.get_token()

    assert exc_info.value.response.status_code == 401
