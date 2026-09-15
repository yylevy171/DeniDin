"""Shared helpers for Feature 072 client-cache integration tests.

Not a test module itself (no test_ prefix) - thin call-counting/timestamping
SPYs around the real MorningClient (not mocks - they delegate every call to
the real client, they just also observe it), used to prove a cache hit made
zero additional Morning API calls, and (for Phase 1.a's latency proof) to
record the exact wall-clock timing of every real call made underneath.
Constitution-compliant: the real sandbox is still hit on every call the spy
forwards; nothing here fabricates a response.
"""
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.utils.time_utils import local_isoformat, now_local


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


class TimestampingSearchClient:
    """Wraps a real MorningClient, recording the exact Israel-local
    wall-clock start/end timestamp (CONSTITUTION §II - now_local()/
    local_isoformat(), never a bare datetime.now()) of every real
    `search_clients` call it forwards - the one Morning endpoint
    resolve_client_name's cache-first fast path touches. Used by Phase
    1.a's latency proof so each of the underlying Morning calls (not just
    each MCP-level resolve_client_name call) has an exact recorded time,
    for post-hoc correlation - e.g. confirming a cache-ON run made exactly
    one such call (the warming miss) across all 50 resolve_client_name
    calls, versus one per call on cache-OFF.

    `self.calls` is a list of dicts, each:
        {"started_at": <ISO Israel-local>, "ended_at": <ISO Israel-local>,
         "duration_s": float}
    in call order.
    """

    def __init__(self, real_client: MorningClient):
        self._real = real_client
        self.calls: list = []

    def search_clients(self, payload: dict) -> dict:
        started = now_local()
        result = self._real.search_clients(payload)
        ended = now_local()
        self.calls.append(
            {
                "started_at": local_isoformat(started),
                "ended_at": local_isoformat(ended),
                "duration_s": (ended - started).total_seconds(),
            }
        )
        return result

    def __getattr__(self, item):
        return getattr(self._real, item)
