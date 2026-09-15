"""Real-sandbox integration test: Feature 072 User Story 2 - Cache Miss
Fallback + write-through. An unknown name still resolves via the existing
live flow (unchanged output), and gets cached for next time.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import resolve_client_name

from ._cache_test_helpers import SearchCountingClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# Morning's real search index is eventually consistent (research.md
# Decision 8, same lag every other sandbox test in this app already
# tolerates) - a client created via the RAW Morning API (bypassing this
# app's own cache write-through, to genuinely exercise the miss path) may
# not be immediately searchable.
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


@pytest.fixture
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )


@pytest.fixture
def cache(tmp_path: Path) -> ClientCache:
    return ClientCache(tmp_path / "client_cache.db")


def test_first_resolution_is_live_second_is_a_cache_hit(morning_client, cache):
    unique_marker = f"DENIDIN_CACHE_MISS_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    # Two sandbox-unique tokens, deliberately NOT ordinary English words -
    # this sandbox accumulates leftover clients across many test runs, and a
    # generic word ("Test", "Cache") can word-growth-match unrelated
    # leftover clients, turning what should be an exact single match into a
    # spurious multi-candidate "ambiguous" result (found live while writing
    # this test).
    name = f"ZQ{unique_marker} ZR{unique_marker}"

    # Created via the RAW client, deliberately bypassing tools.add_client's
    # own cache write-through - this client genuinely is NOT cached yet.
    morning_client.add_client({"name": name, "emails": [f"{unique_marker}@example.com"], "phone": "050-1234567"})

    # First resolution: cache miss, falls through to the existing live flow.
    # Poll to ride out the search-index lag (an ordinary "not found" result
    # on an early attempt, not an error - resolve_client_name never raises
    # for a genuine zero-match).
    first_result = None
    for _ in range(_POLL_ATTEMPTS):
        first_result = resolve_client_name(morning_client, name, cache=cache)
        if name in first_result:
            break
        time.sleep(_POLL_INTERVAL_SECONDS)
    assert first_result is not None and name in first_result, (
        f"resolve_client_name never found the client after {_POLL_ATTEMPTS} "
        "attempts (search-index lag exceeded the poll budget)"
    )

    # Second resolution: now a cache hit - zero further Morning calls.
    spy = SearchCountingClient(morning_client)
    second_result = resolve_client_name(spy, name, cache=cache)

    assert name in second_result
    assert second_result == first_result
    assert spy.search_clients_call_count == 0
