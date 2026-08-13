from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import MorningAuth
from .utils.logger import get_logger

logger = get_logger(__name__)


def _redact_headers(headers: dict) -> dict:
    """Copy of `headers` safe to log - the bearer token is a real secret and must
    never reach a log line (user request, 2026-08-12: log EVERYTHING sent to/from
    Morning - this is the one exception, for the same reason API keys are never
    logged elsewhere in this app)."""
    redacted = dict(headers)
    if "Authorization" in redacted:
        redacted["Authorization"] = "Bearer <redacted>"
    return redacted


def _build_session(retries: int = 3, backoff_factor: float = 0.5):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class MorningClient:
    """Client for Morning Green Receipt API with token management and retries.

    Feature 053: `auth_url` is REQUIRED - the token endpoint lives on a
    different host than `base_url` (see auth.py's docstring), so it can never
    be defaulted/derived, only configured explicitly (CONSTITUTION §I).
    """

    def __init__(
        self,
        api_key_id: str,
        api_key_secret: str,
        auth_url: str,
        base_url: str = "https://api.greeninvoice.co.il/api/v1",
        refresh_before_seconds: int = 300,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = MorningAuth(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            auth_url=auth_url,
            refresh_before_seconds=refresh_before_seconds,
        )
        self.session = _build_session(retries=retries)

    def _auth_headers(self) -> dict:
        token = self.auth.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, headers: dict, timeout: int, json_payload: dict = None) -> requests.Response:
        """One real HTTP call to Morning, with full request/response logging (user
        request, 2026-08-12: "log EVERYTHING sent back and forth between the mcp and
        morning" - a live investigation into a resolve_client_name discrepancy had no
        way to see the actual search_clients traffic, since audit logging only covers
        mutations and only logs at the tool boundary, not the raw HTTP layer). Every
        public method below goes through this one spot, so no future addition can
        silently skip logging.

        Logged at DEBUG deliberately - full request/response bodies are noisy and this
        should be off in prod by default. Requires `server.py`'s `main()` to have
        called `reconfigure_package_log_level(config.mcp_log_level)` after loading
        config for this to actually respect `config.dev.json`'s `mcp.log_level` -
        `get_logger()`'s own default is INFO, set at each module's import time,
        before config exists (see that function's docstring for the full story).
        A direct script that constructs MorningClient without going through
        server.py's main() (e.g. an ad-hoc diagnostic) never gets that reconfigure
        call, so it stays at the INFO default and won't show these DEBUG lines
        either, unless it calls reconfigure_package_log_level itself.

        Logs the response BEFORE `raise_for_status()` is called by the caller, so a
        4xx/5xx body (often the most useful part) is always captured even though the
        caller still raises on it afterward - unchanged behavior, just observed first.
        """
        logger.debug(
            "Morning API request: %s %s headers=%s json=%s",
            method, url, _redact_headers(headers), json_payload,
        )
        resp = self.session.request(method, url, json=json_payload, headers=headers, timeout=timeout)
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = resp.text
        logger.debug("Morning API response: status=%s body=%s", resp.status_code, body)
        return resp

    def create_invoice(self, payload: dict) -> dict:
        url = f"{self.base_url}/documents"
        headers = self._auth_headers()
        resp = self._request("POST", url, headers, timeout=15, json_payload=payload)
        resp.raise_for_status()
        return resp.json()

    def list_invoices(self, params: dict = None) -> List[dict]:
        url = f"{self.base_url}/documents/search"
        headers = self._auth_headers()
        # The Morning API expects a POST to /documents/search with a JSON body (see Postman collection).
        resp = self._request("POST", url, headers, timeout=20, json_payload=params or {})
        resp.raise_for_status()
        return resp.json()

    def get_invoice(self, invoice_id: str) -> dict:
        url = f"{self.base_url}/documents/{invoice_id}"
        headers = self._auth_headers()
        resp = self._request("GET", url, headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def close_invoice(self, invoice_id: str) -> dict:
        """Mark a document as closed/paid (POST /documents/{id}/close, empty body)."""
        url = f"{self.base_url}/documents/{invoice_id}/close"
        headers = self._auth_headers()
        resp = self._request("POST", url, headers, timeout=15)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def open_invoice(self, invoice_id: str) -> dict:
        """Reopen a document/mark unpaid (POST /documents/{id}/open, empty body)."""
        url = f"{self.base_url}/documents/{invoice_id}/open"
        headers = self._auth_headers()
        resp = self._request("POST", url, headers, timeout=15)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def add_client(self, payload: dict) -> dict:
        """Create a new client (POST /clients)."""
        url = f"{self.base_url}/clients"
        headers = self._auth_headers()
        resp = self._request("POST", url, headers, timeout=15, json_payload=payload)
        resp.raise_for_status()
        return resp.json()

    def search_clients(self, payload: dict) -> dict:
        """Search/list clients (POST /clients/search). Response items are already
        full records - no separate GET-by-id call is needed anywhere."""
        url = f"{self.base_url}/clients/search"
        headers = self._auth_headers()
        resp = self._request("POST", url, headers, timeout=15, json_payload=payload)
        resp.raise_for_status()
        return resp.json()

    def update_client(self, client_id: str, payload: dict) -> dict:
        """Update a client (PUT /clients/{id}). Payload is partial - only the
        fields being changed."""
        url = f"{self.base_url}/clients/{client_id}"
        headers = self._auth_headers()
        resp = self._request("PUT", url, headers, timeout=15, json_payload=payload)
        resp.raise_for_status()
        return resp.json()
