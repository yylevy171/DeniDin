"""Real-sandbox integration test: Feature 072 User Story 1 - Cache Hit Fast
Path. A previously-resolved exact client name resolves with zero further
Morning `search_clients` calls.

No mocking (CONSTITUTION §V) - the real sandbox is used throughout; the only
test double is `SearchCountingClient`, a thin pass-through counting SPY
(see _cache_test_helpers.py), never a stand-in for a response.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import add_client, resolve_client_name

from ._cache_test_helpers import SearchCountingClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"


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


def test_second_resolution_of_a_cached_client_makes_no_search_call(morning_client, cache):
    unique_marker = f"DENIDIN_CACHE_HIT_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Cache Hit Test {unique_marker}"

    # add_client's own success path write-throughs into the cache
    # immediately (User Story 2) - this is the fastest, lag-free way to get
    # a real, cache-populated client for this test (no need to wait out
    # Morning's search-index eventual consistency, since the cache write
    # never goes through search_clients at all).
    add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
        cache=cache,
    )

    spy = SearchCountingClient(morning_client)
    result = resolve_client_name(spy, name, cache=cache)

    assert name in result
    assert spy.search_clients_call_count == 0, (
        "resolve_client_name made a real Morning search_clients call for a "
        "client that was already cached - the cache-hit fast path did not "
        "engage"
    )


def test_cache_hit_is_word_order_and_case_independent(morning_client, cache):
    unique_marker = f"DENIDIN_CACHE_HIT_ORDER_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    # Two sandbox-unique tokens (not ordinary English words - see
    # test_client_cache_miss_then_hit.py's comment on why), so a
    # word-order-swapped query is a meaningful, collision-free check.
    name = f"ZA{unique_marker} ZB{unique_marker}"

    add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
        cache=cache,
    )

    spy = SearchCountingClient(morning_client)
    swapped_query = f"zb{unique_marker} za{unique_marker}"
    result = resolve_client_name(spy, swapped_query, cache=cache)

    assert name in result  # discloses the real stored order, not the query's
    assert spy.search_clients_call_count == 0
