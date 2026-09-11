"""Real Morning-sandbox test for the get_client_details MCP tool (Feature 026, US2;
client-name-resolution architecture fix, bugfix-028 sub-piece, 2026-08-12).

No mocks: drives denidin_mcp_morning.tools.get_client_details against the live
sandbox, per CONSTITUTION §V and this app's testing policy.
"""
import json
import time
import uuid
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.utils.time_utils import now_local

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# Search-index eventual-consistency lag (research.md Decision 8) - poll up to
# 12x/1.5s (18s) before giving up, same pattern as test_morning_sandbox_list_clients_tool.py.
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


def _poll_until(predicate, action):
    """Call `action()` up to _POLL_ATTEMPTS times until `predicate(result)` is
    true, sleeping _POLL_INTERVAL_SECONDS between attempts. Returns the last
    result.

    `action` may raise `ClientNotFoundError` transiently - get_client_details
    (post architecture fix, 2026-08-12) raises on a genuine zero-match, and a
    freshly-created client can legitimately zero-match for a few seconds
    while Morning's search index catches up (this file's own documented
    eventual-consistency lag). That's indistinguishable from a real
    not-found on the FIRST poll attempt, so it's treated as "not ready yet"
    here rather than failing the whole poll immediately - the same
    tolerance the predicate-based retry already gives an unhelpful string
    reply."""
    from denidin_mcp_morning.tools import ClientNotFoundError

    result = None
    for attempt in range(_POLL_ATTEMPTS):
        try:
            result = action()
        except ClientNotFoundError:
            if attempt == _POLL_ATTEMPTS - 1:
                raise
            time.sleep(_POLL_INTERVAL_SECONDS)
            continue
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
        auth_url=config.auth_url,
    )


def test_get_client_details_returns_full_record(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_DETAILS_TEST_{int(now_local().timestamp())}"
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
        lambda r: json.loads(r).get("client", {}).get("name") == name,
        lambda: get_client_details(morning_client, name, name_resolved=True),
    )
    payload = json.loads(result)

    assert payload["client"]["name"] == name
    assert payload["client"]["tax_id"] == "308253681"
    assert payload["client"]["phone"] == "050-1234567"
    # Morning lowercases email addresses server-side (observed live) -
    # compare case-insensitively rather than assuming case is preserved.
    assert payload["client"]["email"].lower() == f"{unique_marker}@example.com".lower()


def test_get_client_details_never_includes_raw_client_id(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_DETAILS_ID_TEST_{int(now_local().timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    result = get_client_details(morning_client, name, name_resolved=True)

    assert client_id not in result


def test_get_client_details_not_resolved_refuses_without_any_lookup(morning_client):
    """Architecture fix (2026-08-12): omitting name_resolved must refuse
    immediately, without attempting any Morning lookup at all - even for a
    name that would otherwise resolve cleanly. Follow-up (2026-08-12): this
    is now a real raise, not ordinary refusal text - two outcomes only,
    succeed or raise."""
    from denidin_mcp_morning.tools import ClientNameNotResolvedError, get_client_details

    with pytest.raises(ClientNameNotResolvedError) as exc_info:
        get_client_details(morning_client, "Any Client Name At All")

    assert "resolve_client_name" in str(exc_info.value)


def test_get_client_details_non_exact_match_with_name_resolved_raises_not_found(morning_client):
    """Architecture fix (2026-08-12): get_client_details no longer discloses
    non-exact matches itself - that disclosure now happens in
    resolve_client_name instead (see
    test_morning_sandbox_resolve_client_name_tool.py). Asserting
    name_resolved=True against a name that's still only a partial/prefix
    reference is a contract violation and raises ClientNotFoundError, same
    as a genuine zero-match."""
    from denidin_mcp_morning import tools
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

    # Poll for search-index readiness via the real full name first (a plain
    # read, no assertion here) - once that settles, the one real
    # assertion call below is meaningful rather than racing eventual
    # consistency.
    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"

    with pytest.raises(tools.ClientNotFoundError):
        get_client_details(morning_client, partial_reference, name_resolved=True)


def test_get_client_details_exact_match_uses_standard_phrasing(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_EXACT_TEST_{int(now_local().timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    result = _poll_until(
        lambda r: json.loads(r).get("client", {}).get("name") == name,
        lambda: get_client_details(morning_client, name, name_resolved=True),
    )
    payload = json.loads(result)

    assert payload["client"]["name"] == name
    assert payload["exact_match"] is True
