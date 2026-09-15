"""Real-sandbox integration test: Feature 072 User Story 3 - a stale cache
entry (a client renamed directly in Morning, bypassing this app's own
update_client write-through) self-heals: the next attempt to resolve it by
its old, now-stale name fails with the existing ClientNotFoundError
(unchanged behavior - see tasks.md's "Correction" note and
contracts/cache-contract.md), and the cache entry is evicted so a retry
under the correct name resolves live rather than repeating a phantom hit.

Uses get_client_details (read-only) rather than a document-creating write
tool to exercise `_require_resolved_client`'s eviction hook without leaving
stray sandbox documents behind.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.models import Client
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import ClientNotFoundError, get_client_details

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


def test_a_name_renamed_outside_this_apps_write_through_evicts_on_next_use(morning_client, cache):
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

    # The next attempt to use the (now-stale) old name must fail exactly the
    # same way it always has - ClientNotFoundError, unchanged - once
    # Morning's search index reflects the rename (eventual consistency,
    # same lag every other sandbox test in this app already tolerates).
    last_exc = None
    for _ in range(_POLL_ATTEMPTS):
        try:
            get_client_details(morning_client, old_name, name_resolved=True, cache=cache)
        except ClientNotFoundError as exc:
            last_exc = exc
            break
        time.sleep(_POLL_INTERVAL_SECONDS)
    assert last_exc is not None, (
        f"old name still resolved after {_POLL_ATTEMPTS} attempts - the rename "
        "was never reflected by Morning's search index within the poll budget"
    )

    assert cache.lookup_exact(old_name) is None, "stale cache entry was not evicted"
