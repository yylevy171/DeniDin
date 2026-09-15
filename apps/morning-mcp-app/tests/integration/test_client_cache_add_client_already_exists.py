"""Real-sandbox integration test: add_client's already-exists recovery
(operator design review, 2026-09-15). Verified live: Morning's real error
shape for this is HTTP 400, {"errorCode": 1010, "errorMessage":
"<existing client_id>"} - the existing client's own id, handed back
directly in the error body.

Without this recovery, a duplicate add_client call would just raise and the
cache would stay a permanent miss for this client (until the next periodic
sweep) even though the client demonstrably exists. With it, add_client
fetches the real pre-existing record and write-throughs it.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import add_client

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


def test_add_client_on_duplicate_populates_the_cache_instead_of_just_failing(morning_client, cache):
    unique_marker = f"DENIDIN_ALREADY_EXISTS_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Already Exists Test {unique_marker}"
    email = f"{unique_marker}@example.com"

    first = add_client(morning_client, name=name, email=email, phone="050-1234567", cache=cache)
    assert name in first
    assert cache.lookup_exact(name) is not None  # first call's own write-through

    cache.evict_by_name(name)  # simulate a cold cache - only the DUPLICATE call should repopulate it
    assert cache.lookup_exact(name) is None

    second = add_client(morning_client, name=name, email=email, phone="050-1234567", cache=cache)
    assert name in second  # same success-shaped result, not a raised error

    hit = cache.lookup_exact(name)
    assert hit is not None, "the already-exists recovery did not populate the cache"
    # Morning's search_clients (used to fetch the pre-existing record) is
    # confirmed live to return the email lowercased, even though create
    # preserves the original case - a real Morning quirk, not a bug here.
    assert hit.email.lower() == email.lower()
