"""Real Morning-sandbox test for the get_client_details MCP tool (Feature 026, US2).

No mocks: drives denidin_mcp_morning.tools.get_client_details against the live
sandbox, per CONSTITUTION §V and this app's testing policy.
"""
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# Search-index eventual-consistency lag (research.md Decision 8) - poll up to
# 12x/1.5s (18s) before giving up, same pattern as test_morning_sandbox_list_clients_tool.py.
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


def _poll_until(predicate, action):
    """Call `action()` up to _POLL_ATTEMPTS times until `predicate(result)` is
    true, sleeping _POLL_INTERVAL_SECONDS between attempts. Returns the last result."""
    result = None
    for _ in range(_POLL_ATTEMPTS):
        result = action()
        if predicate(result):
            return result
        time.sleep(_POLL_INTERVAL_SECONDS)
    return result


@pytest.fixture(scope="module")
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )


def test_get_client_details_returns_full_record(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_DETAILS_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    # Phone given already in normalized form (050-1234567) since add_client's
    # own phone normalization (REQ-CLIENT-016) is Phase 4/US3's concern, not
    # get_client_details' - this test only verifies the *read* side displays
    # whatever is stored, stably regardless of when normalization lands.
    add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
        tax_id="308253681",
    )

    result = _poll_until(
        lambda r: name in r,
        lambda: get_client_details(morning_client, name),
    )

    assert name in result
    assert "308253681" in result
    assert "050-1234567" in result
    # Morning lowercases email addresses server-side (observed live) -
    # compare case-insensitively rather than assuming case is preserved.
    assert f"{unique_marker}@example.com".lower() in result.lower()


def test_get_client_details_never_includes_raw_client_id(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_DETAILS_ID_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    result = get_client_details(morning_client, name)

    assert client_id not in result


def test_get_client_details_discloses_non_exact_match(morning_client):
    """New requirement: when the query resolves to exactly one client via a
    non-exact (partial/prefix) match, the reply must explicitly disclose
    which client was found, distinct from the exact-match phrasing."""
    from denidin_mcp_morning.tools import add_client, get_client_details

    # A random hex marker (not a timestamp) - sequential timestamps taken
    # seconds apart share almost all their LEADING digits, so truncating a
    # suffix off one can accidentally still prefix-match a different test's
    # similarly-timestamped client under a busy full-suite run. A random
    # string has no such structural correlation between tests.
    unique_marker = uuid.uuid4().hex[:16].upper()
    name = f"Test Client {unique_marker}"
    partial_reference = f"Test Client {unique_marker[:-3]}"  # drops the last 3
        # chars - a valid prefix match at the API level, not the literal name

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    result = _poll_until(
        lambda r: name in r,
        lambda: get_client_details(morning_client, partial_reference),
    )

    assert "מצאתי את הלקוח" in result
    assert name in result


def test_get_client_details_exact_match_uses_standard_phrasing(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_EXACT_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    result = _poll_until(
        lambda r: name in r,
        lambda: get_client_details(morning_client, name),
    )

    assert result.startswith("לקוח:")
    assert "מצאתי את הלקוח" not in result
