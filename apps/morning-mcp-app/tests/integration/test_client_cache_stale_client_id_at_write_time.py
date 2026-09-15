"""Real-sandbox integration test: the ONE genuinely new failure mode the
2026-09-15 cache-first redesign introduces for WRITE tools - a cached
client_id Morning no longer recognizes (verified live: Morning's real error
shape for this is HTTP 400, {"errorCode": 2411, "errorMessage": "לקוח לא
קיים"} - see tools.py's `_MORNING_CLIENT_NOT_FOUND_ERROR_CODE`). Under the
old always-live design this could never happen (the identify step always
re-verified before any write); trusting a cache hit means the write call
itself is now where staleness can surface.

There is no delete-client endpoint in this app's Morning client, so a truly
dead client_id can't be produced against the live sandbox honestly - this
test instead seeds the cache with a client_id that was never real to begin
with (a syntactically-valid but nonexistent UUID), which produces the exact
same Morning error Feature 072's clarify-round-2 probe confirmed live for a
genuinely deleted client.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.models import Client
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import ClientNotFoundError, create_transaction_account

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


def test_write_tool_evicts_and_raises_client_not_found_on_a_dead_cached_id(morning_client, cache):
    unique_marker = f"DENIDIN_STALE_ID_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Dead Cache Entry {unique_marker}"
    dead_id = str(uuid.uuid4())  # never a real Morning client

    cache.write_through(Client(id=dead_id, name=name))
    assert cache.lookup_exact(name) is not None  # sanity: really cached

    with pytest.raises(ClientNotFoundError):
        create_transaction_account(
            morning_client, name, amount=10.0, description="test",
            vat_included=True, name_resolved=True, cache=cache,
        )

    assert cache.lookup_exact(name) is None, "the dead cache entry was not evicted"
