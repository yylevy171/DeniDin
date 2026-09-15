"""Real-sandbox integration test: Feature 072 User Story 3 - a stale cache
entry (a client renamed directly in Morning, bypassing this app's own
update_client write-through) self-heals via the periodic reconciliation
sweep.

Revised 2026-09-15 (operator design review, post-implementation): under the
current cache-first design, `get_client_details` trusts a cache hit outright
(no per-call live re-verification - that's the whole point of caching it at
all now that the cache stores full records, see client_cache.py's module
docstring), so a rename done entirely outside this app is no longer caught
by a live per-call check on a READ tool - only `run_cache_sweep` (the
periodic reconciliation job) corrects it. This replaces the pre-redesign
version of this test, which asserted a live per-call ClientNotFoundError -
that assumption belonged to the old always-live architecture this feature
now intentionally moves away from for read tools.

The genuinely NEW failure mode this redesign introduces - a WRITE tool
attempting to use a cached client_id that Morning has actually deleted -
is covered separately by
test_client_cache_stale_client_id_at_write_time.py.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.cache_sweep_service import run_cache_sweep
from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.models import Client
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import get_client_details

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

_POLL_ATTEMPTS = 6
_POLL_INTERVAL_SECONDS = 2.0


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


def test_a_rename_outside_this_app_is_served_stale_until_the_next_sweep_then_corrected(
    morning_client, cache
):
    unique_marker = f"DENIDIN_CACHE_STALE_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    old_name = f"Stale Cache Test {unique_marker}"
    new_name = f"Renamed Cache Test {unique_marker}"

    # Create directly via the raw client (need the real id back for the
    # rename step below - tools.add_client deliberately never discloses it,
    # REQ-CLIENT-018), then cache it manually under the old name - exactly
    # what a real write-through would have done at the time it was created.
    response = morning_client.add_client(
        {"name": old_name, "emails": [f"{unique_marker}@example.com"], "phone": "050-1234567"}
    )
    client_id = response["id"]
    cache.write_through(Client(id=client_id, name=old_name))
    assert cache.lookup_exact(old_name) is not None  # sanity: really cached

    # Rename directly via the raw client - bypasses tools.update_client, so
    # its own write-through never runs; the cache is now genuinely stale.
    morning_client.update_client(client_id, {"name": new_name})

    # Cache-first by design (client_cache.py's 2026-09-15 redesign): a READ
    # of the old name is still served straight from the (now-stale) cache -
    # no live Morning call, no exception. This is the intended, accepted
    # trade-off - staleness bounded by the sweep interval, not eliminated on
    # every read.
    stale_result = get_client_details(morning_client, old_name, name_resolved=True, cache=cache)
    assert old_name in stale_result

    # The periodic reconciliation sweep is what actually catches this -
    # fetches Morning's live roster (via search_clients, same eventual-
    # consistency lag every other sandbox test in this app already
    # tolerates) and upserts every row, including this renamed one. Poll a
    # few sweeps rather than assuming one pass lands after the search index
    # has caught up.
    fresh_hit = None
    for _ in range(_POLL_ATTEMPTS):
        run_cache_sweep(morning_client, cache)
        fresh_hit = cache.lookup_exact(new_name)
        if fresh_hit is not None:
            break
        time.sleep(_POLL_INTERVAL_SECONDS)

    assert cache.lookup_exact(old_name) is None, "sweep did not evict the stale old-name entry"
    assert fresh_hit is not None and fresh_hit.id == client_id, (
        f"sweep did not pick up the rename after {_POLL_ATTEMPTS} attempts - Morning's "
        "search index never reflected it within the poll budget"
    )

    # And the read tool now serves the corrected name straight from cache.
    fresh_result = get_client_details(morning_client, new_name, name_resolved=True, cache=cache)
    assert new_name in fresh_result
