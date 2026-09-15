"""Real-sandbox integration test: Feature 072 User Story 2 - add_client's
own success path write-throughs into the cache immediately, so the very
first resolve_client_name for that exact name is already a hit - no
Morning search_clients call needed at all, sidestepping the search-index
eventual-consistency lag entirely (the whole point of event-driven
write-through, distinct from the live-miss write-through covered by
test_client_cache_miss_then_hit.py).
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


def test_add_client_write_through_makes_the_very_first_resolution_a_hit(morning_client, cache):
    unique_marker = f"DENIDIN_CACHE_ADD_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Add Client Cache Test {unique_marker}"

    add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
        cache=cache,
    )

    # Immediately, no polling/waiting for search-index lag at all.
    spy = SearchCountingClient(morning_client)
    result = resolve_client_name(spy, name, cache=cache)

    assert name in result
    assert spy.search_clients_call_count == 0
