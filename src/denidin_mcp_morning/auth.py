import threading
import time
from typing import Optional
import requests


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

        resp = requests.post(url, json=body, timeout=10)
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
