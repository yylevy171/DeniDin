from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import MorningAuth


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

    Accepts either a single `api_key` string or `api_key_id` + `api_key_secret` pair.
    """

    def __init__(
        self,
        api_key: str = None,
        api_key_id: str = None,
        api_key_secret: str = None,
        base_url: str = "https://api.greeninvoice.co.il/api/v1",
        token_ttl_seconds: int = 3600,
        refresh_before_seconds: int = 300,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = MorningAuth(
            api_key=api_key,
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            base_url=self.base_url,
            token_ttl_seconds=token_ttl_seconds,
            refresh_before_seconds=refresh_before_seconds,
        )
        self.session = _build_session(retries=retries)

    def _auth_headers(self) -> dict:
        token = self.auth.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def create_invoice(self, payload: dict) -> dict:
        url = f"{self.base_url}/documents"
        headers = self._auth_headers()
        resp = self.session.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def list_invoices(self, params: dict = None) -> List[dict]:
        url = f"{self.base_url}/documents/search"
        headers = self._auth_headers()
        # The Morning API expects a POST to /documents/search with a JSON body (see Postman collection).
        resp = self.session.post(url, json=params or {}, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def get_invoice(self, invoice_id: str) -> dict:
        url = f"{self.base_url}/documents/{invoice_id}"
        headers = self._auth_headers()
        resp = self.session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
