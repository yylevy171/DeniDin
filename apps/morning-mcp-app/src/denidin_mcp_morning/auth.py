import threading
import time
from typing import Optional
import requests

from .utils.logger import get_logger

logger = get_logger(__name__)


def _redact_token_body(body: dict) -> dict:
    """Copy of the /account/token request body safe to log - `secret`/`apiKey` are
    real credentials and must never reach a log line (same rule as morning_client.py's
    `_redact_headers`, user request 2026-08-12: log EVERYTHING sent to/from Morning,
    minus actual secrets)."""
    redacted = dict(body)
    for key in ("secret", "apiKey"):
        if key in redacted:
            redacted[key] = "<redacted>"
    return redacted


def _redact_token(token: Optional[str]) -> str:
    """A live bearer token is itself a real credential (valid for the full TTL) -
    log only enough of it to correlate log lines, never the usable value."""
    if not token:
        return "<none>"
    return f"{token[:8]}...<redacted>"


def _redact_token_response_body(body):
    """Same idea as `_redact_token_body`, for the /account/token RESPONSE - Morning
    can return the live token directly in the JSON body (`token`/`access_token`),
    not just the X-Authorization-Bearer header, so both need masking."""
    if not isinstance(body, dict):
        return body
    redacted = dict(body)
    for key in ("token", "access_token"):
        if key in redacted:
            redacted[key] = _redact_token(redacted[key])
    return redacted


class MorningAuth:
    """Manage JWT tokens obtained from Morning /account/token using an API key.

    - Caches token and expiration
    - Supports either a single API key string or an API key id + secret pair
    """

    def __init__(self, api_key: str = None, api_key_id: str = None, api_key_secret: str = None, base_url: str = None, token_ttl_seconds: int = 3600, refresh_before_seconds: int = 300):
        self.api_key = api_key
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self.base_url = base_url.rstrip("/")
        self.token_ttl_seconds = token_ttl_seconds
        self.refresh_before_seconds = refresh_before_seconds
        self._token_lock = threading.Lock()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _now(self) -> float:
        return time.time()

    def _request_token(self) -> str:
        url = f"{self.base_url}/account/token"
        # Morning's docs and Postman collection use JSON keys {"id": ..., "secret": ...}
        # Support three forms for compatibility/tests:
        #  - id + secret: {"id": "...", "secret": "..."}
        #  - apiKeyId + apiKeySecret: {"apiKeyId": "...", "apiKeySecret": "..."}
        #  - single API key: {"apiKey": "..."}
        body = None
        if self.api_key_id and self.api_key_secret:
            # Prefer the Postman/collection format
            body = {"id": self.api_key_id, "secret": self.api_key_secret}
        elif self.api_key:
            body = {"apiKey": self.api_key}
        else:
            raise RuntimeError("No API key provided to MorningAuth")

        # DEBUG deliberately - see morning_client.py's _request docstring for why this
        # requires server.py's main() to have called reconfigure_package_log_level().
        logger.debug("Morning API request: POST %s json=%s", url, _redact_token_body(body))
        resp = requests.post(url, json=body, timeout=10)
        try:
            resp_body = resp.json() if resp.content else None
        except ValueError:
            resp_body = resp.text
        logger.debug(
            "Morning API response: status=%s body=%s x-authorization-bearer=%s",
            resp.status_code, _redact_token_response_body(resp_body),
            _redact_token(resp.headers.get("X-Authorization-Bearer")),
        )
        resp.raise_for_status()
        data = resp.json()
        # Token may be returned in header X-Authorization-Bearer or in JSON token field
        token = resp.headers.get("X-Authorization-Bearer") or data.get("token") or data.get("access_token")
        if not token:
            raise RuntimeError("Token not found in /account/token response")
        return token

    def get_token(self) -> str:
        """Return a valid token, refreshing if necessary."""
        with self._token_lock:
            now = self._now()
            if self._token and now < self._token_expiry - self.refresh_before_seconds:
                return self._token
            # need to refresh
            token = self._request_token()
            self._token = token
            self._token_expiry = now + self.token_ttl_seconds
            return token
