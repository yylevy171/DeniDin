"""Real-sandbox integration test: Feature 072 User Story 3 - the periodic
cache sweep (run_cache_sweep -> fetch_all_clients + cache.reconcile) brings
a real, previously-uncached client into the cache, catching what
event-driven write-through alone cannot (a client this app never itself
created/resolved, e.g. one added directly in Morning's own UI - simulated
here via the raw client, same as test_client_cache_miss_then_hit.py).

Runs one sweep tick directly (not on a timer) - the scheduler wiring itself
(start_cache_sweep_scheduler) is plumbing, not business logic worth a real
Morning round-trip to exercise.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.cache_sweep_service import run_cache_sweep
from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

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


def test_sweep_discovers_a_client_added_outside_this_apps_write_through(morning_client, cache):
    unique_marker = f"DENIDIN_CACHE_SWEEP_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Sweep Test {unique_marker}"

    morning_client.add_client({"name": name, "emails": [f"{unique_marker}@example.com"], "phone": "050-1234567"})
    assert cache.lookup_exact(name) is None  # sanity: genuinely not cached yet

    hit = None
    for _ in range(_POLL_ATTEMPTS):
        run_cache_sweep(morning_client, cache)
        hit = cache.lookup_exact(name)
        if hit is not None:
            break
        time.sleep(_POLL_INTERVAL_SECONDS)

    assert hit is not None, (
        f"sweep never picked up the client after {_POLL_ATTEMPTS} attempts "
        "(search-index lag exceeded the poll budget)"
    )
    assert hit.name == name
