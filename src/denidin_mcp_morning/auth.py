import threading
import time
from typing import Optional
import requests


class MorningAuth:
    """Manage JWT tokens obtained from Morning /account/token using an API key.

    - Caches token and expiration
    - Proactively refreshes token when within `refresh_before_seconds` window
    """

    def __init__(self, api_key: str, base_url: str, token_ttl_seconds: int = 3600, refresh_before_seconds: int = 300):
        self.api_key = api_key
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
        # Morning's docs describe obtaining a JWT via POST with API key. We'll send json body {api_key}.
        resp = requests.post(url, json={"apiKey": self.api_key}, timeout=10)
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
