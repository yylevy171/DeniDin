"""Shared helpers for Feature 072 client-cache integration tests.

Not a test module itself (no test_ prefix) - a thin call-counting SPY around
the real MorningClient (not a mock - it delegates every call to the real
client, it just also counts them), used to prove a cache hit made zero
additional Morning API calls. Constitution-compliant: the real sandbox is
still hit on every call the spy forwards; nothing here fabricates a response.
"""
from denidin_mcp_morning.morning_client import MorningClient


class SearchCountingClient:
    """Wraps a real MorningClient, counting `search_clients` calls only -
    the one Morning endpoint a cache hit must avoid entirely."""

    def __init__(self, real_client: MorningClient):
        self._real = real_client
        self.search_clients_call_count = 0

    def search_clients(self, payload: dict) -> dict:
        self.search_clients_call_count += 1
        return self._real.search_clients(payload)

    def __getattr__(self, item):
        # Delegate everything else (add_client, update_client, ...) straight
        # to the real client, uncounted.
        return getattr(self._real, item)
