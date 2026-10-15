"""HTTP client for denidin-app's Agreements API (Feature 089).

The browser never talks to denidin-app: the webapp backend is the only caller, authenticating
with the shared bearer token from config (`denidin_agreements_token`), and it stamps
`actor: "webapp"` on every write. A connection failure surfaces as `AgreementsUnavailable`,
which the server maps to `502 agreements_unavailable` - never to a silently empty result.
"""
import logging
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger("webapp_backend")

ACTOR = "webapp"
DEFAULT_TIMEOUT_SECONDS = 10.0


class AgreementsUnavailable(RuntimeError):
    """denidin-app's Agreements API could not be reached (or is not configured)."""


class AgreementsClient:
    def __init__(self, base_url: str, token: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._token = token or ""
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._token)

    def request(
        self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        """One call; returns (status_code, parsed JSON body). Writes get `actor` added."""
        if not self.configured:
            raise AgreementsUnavailable("agreements API is not configured")
        query = dict(params or {})
        payload: Optional[Dict[str, Any]] = None
        if method in ("POST", "PATCH"):
            payload = {**(body or {}), "actor": ACTOR}
        elif method == "DELETE":
            query["actor"] = ACTOR
        try:
            response = requests.request(
                method, f"{self._base_url}{path}", params=query, json=payload,
                headers={"Authorization": f"Bearer {self._token}"}, timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.warning("agreements API unreachable: %s %s (%s)", method, path, exc)
            raise AgreementsUnavailable(str(exc)) from exc
        try:
            data = response.json()
        except ValueError:
            data = {"error": {"code": "bad_gateway", "message": "unexpected response from the agreements API"}}
        return response.status_code, data

    def totals(self) -> Dict[str, float]:
        """Per-client sum of non-Cancelled component amounts (one bulk call)."""
        status, data = self.request("GET", "/agreements/totals")
        if status != 200 or not isinstance(data, dict) or "totals" not in data:
            raise AgreementsUnavailable(f"unexpected totals response ({status})")
        return {name: float(total) for name, total in data["totals"].items()}
