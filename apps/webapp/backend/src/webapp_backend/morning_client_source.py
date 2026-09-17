"""Live Morning client-list fetch for the Clients tab (Feature 087).

Per the feature's Clarifications (2026-09-17): webapp-backend talks to Morning
*directly* — importing ``denidin_mcp_morning.morning_client.MorningClient`` and
calling ``search_clients()`` with its own Morning API credentials. No MCP
protocol, no AI/OpenAI call, no dependency on ``morning-mcp-app``'s container,
ngrok tunnel, or status file. This mirrors the existing precedent of
``ledger_reader.py`` importing ``denidin-app``'s code directly, just pointed at
``morning-mcp-app``'s ``src/`` instead.

The list is fetched fresh on every call — no caching — per the explicit user
decision to keep this simple given the small client roster.
"""
import sys
from pathlib import Path
from typing import List

_MORNING_SRC = Path(__file__).resolve().parents[4] / "morning-mcp-app" / "src"
if _MORNING_SRC.is_dir() and str(_MORNING_SRC) not in sys.path:
    sys.path.insert(0, str(_MORNING_SRC))


class MorningClientSourceError(RuntimeError):
    """Raised when the live Morning client list can't be fetched — the caller
    (server.py's ``GET /api/clients`` handler) turns this into a 503, never a
    silently-empty client list."""


class MorningClientSource:
    def __init__(self, api_key_id: str, api_key_secret: str, auth_url: str, api_url: str) -> None:
        self._api_key_id = api_key_id
        self._api_key_secret = api_key_secret
        self._auth_url = auth_url
        self._api_url = api_url

    def _build_client(self):
        from denidin_mcp_morning.morning_client import MorningClient  # deferred: needs sys.path above

        return MorningClient(
            api_key_id=self._api_key_id,
            api_key_secret=self._api_key_secret,
            auth_url=self._auth_url,
            base_url=self._api_url,
        )

    def list_active_client_names(self) -> List[str]:
        """The full, live official-client-name list — one page-walked call, no
        local persistence. Raises ``MorningClientSourceError`` on any failure."""
        try:
            client = self._build_client()
            payload: dict = {}
            first_page = client.search_clients(payload)
            items = list(first_page.get("items") or [])
            page_num = first_page.get("page", 1) or 1
            total = first_page.get("total", len(items)) or len(items)
            total_pages = first_page.get("pages", 1) or 1
            while len(items) < total and page_num < total_pages:
                page_num += 1
                next_page = client.search_clients({**payload, "page": page_num})
                items.extend(next_page.get("items") or [])
        except Exception as exc:  # noqa: BLE001 - any failure here becomes a 503, never a silent []
            raise MorningClientSourceError(str(exc)) from exc

        names = [str(item.get("name", "")).strip() for item in items]
        return sorted({n for n in names if n})
