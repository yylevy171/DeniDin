import threading
import time
from typing import Optional
import requests

from .utils.logger import get_logger

logger = get_logger(__name__)

_TOKEN_PATH = "/idp/v1/oauth/token"


def _redact_token_body(body: dict) -> dict:
    """Copy of the token request body safe to log - `client_secret` is a real
    credential and must never reach a log line (same rule as morning_client.py's
    `_redact_headers`, user request 2026-08-12: log EVERYTHING sent to/from Morning,
    minus actual secrets)."""
    redacted = dict(body)
    if "client_secret" in redacted:
        redacted["client_secret"] = "<redacted>"
    return redacted


def _redact_token(token: Optional[str]) -> str:
    """A live bearer token is itself a real credential (valid for the full TTL) -
    log only enough of it to correlate log lines, never the usable value."""
    if not token:
        return "<none>"
    return f"{token[:8]}...<redacted>"


def _redact_token_response_body(body):
    """Same idea as `_redact_token_body`, for the token RESPONSE - the JSON body
    carries the live access token directly (`accessToken`), which must be masked."""
    if not isinstance(body, dict):
        return body
    redacted = dict(body)
    if "accessToken" in redacted:
        redacted["accessToken"] = _redact_token(redacted["accessToken"])
    return redacted


class MorningAuth:
    """Manage OAuth2 access tokens obtained from Morning's `/idp/v1/oauth/token`
    endpoint (feature 053 - migrated from the old `/account/token` JWT exchange,
    which Morning deprecated: see
    https://www.greeninvoice.co.il/help-center/api-updates-26/ - old address/
    structure supported "until June 2026", after which old paths are blocked).

    Real, verified contract (fetched directly from Morning's own current OpenAPI
    spec, https://developers.morning.co - not assumed from documentation prose):
    - Request: POST {auth_url}/idp/v1/oauth/token,
      body {"grant_type": "client_credentials", "client_id": ..., "client_secret": ...}
    - Response: {"accessToken": ..., "tokenType": "Bearer", "expiresAt": <unix ts>}
    - `auth_url` is a DIFFERENT HOST than the rest of the Morning API (main API:
      api.greeninvoice.co.il; token endpoint: api.morning.co prod /
      api.sandbox.morning.dev sandbox) - this path has its own `servers` override
      in the real spec, distinct from every other endpoint's default host. It
      cannot be derived from `base_url` and must be configured explicitly
      (CONSTITUTION §I: no inference).
    - Errors follow the OAuth2/RFC 6749 error format: 400 invalid_request
      (missing grant_type), 400 unsupported_grant_type, 400 invalid_grant (API
      key expired/revoked/pending), 400 unauthorized_client (no active
      subscription/API access), 401 invalid_client (bad client_id/client_secret,
      or account blocked) - `resp.raise_for_status()` turns any of these into a
      `requests.exceptions.HTTPError`, mapped to a friendly message by
      `errors.friendly_error_message` at the MCP boundary (401->auth-failed,
      400->request-rejected - see that module).

    Caches the token using the REAL `expiresAt` timestamp the response carries,
    never an assumed fixed TTL (the old `/account/token` flow had no authoritative
    expiry, so `token_ttl_seconds` config existed to approximate one - removed
    entirely now that a real value is always available).
    """

    def __init__(
        self,
        api_key_id: str,
        api_key_secret: str,
        auth_url: str,
        refresh_before_seconds: int = 300,
    ):
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self.auth_url = auth_url.rstrip("/")
        self.refresh_before_seconds = refresh_before_seconds
        self._token_lock = threading.Lock()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _now(self) -> float:
        return time.time()

    def _request_token(self) -> tuple:
        """Returns (access_token, expires_at) - both taken directly from
        Morning's real response, never assumed."""
        url = f"{self.auth_url}{_TOKEN_PATH}"
        body = {
            "grant_type": "client_credentials",
            "client_id": self.api_key_id,
            "client_secret": self.api_key_secret,
        }

        # DEBUG deliberately - see morning_client.py's _request docstring for why this
        # requires server.py's main() to have called reconfigure_package_log_level().
        logger.debug("Morning API request: POST %s json=%s", url, _redact_token_body(body))
        resp = requests.post(url, json=body, timeout=10)
        try:
            resp_body = resp.json() if resp.content else None
        except ValueError:
            resp_body = resp.text
        logger.debug(
            "Morning API response: status=%s body=%s",
            resp.status_code, _redact_token_response_body(resp_body),
        )
        resp.raise_for_status()
        data = resp.json()

        access_token = data.get("accessToken")
        expires_at = data.get("expiresAt")
        if not access_token:
            raise RuntimeError("accessToken not found in /idp/v1/oauth/token response")
        if expires_at is None:
            raise RuntimeError("expiresAt not found in /idp/v1/oauth/token response")

        return access_token, float(expires_at)

    def get_token(self) -> str:
        """Return a valid token, refreshing if necessary."""
        with self._token_lock:
            now = self._now()
            if self._token and now < self._token_expiry - self.refresh_before_seconds:
                return self._token
            # need to refresh
            token, expires_at = self._request_token()
            self._token = token
            self._token_expiry = expires_at
            return token
