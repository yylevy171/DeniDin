"""Real Morning-sandbox test for the list_clients MCP tool (Feature 026, US1).

No mocks: drives denidin_mcp_morning.tools.list_clients against the live
sandbox, per CONSTITUTION §V and this app's testing policy.
"""
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"


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


def test_list_clients_includes_seeded_clients(morning_client):
    """Feature 026 follow-up (research.md Decision 11/12): the real sandbox
    now has 270+ clients, so an UNFILTERED list_clients call correctly hits
    the "too many, narrow your search" branch and returns no names at all -
    this test narrows by the shared unique_marker (exactly the production
    fix: a caller facing "too many" results narrows via the name filter)
    rather than asserting on a bare, unfiltered call."""
    from denidin_mcp_morning.tools import add_client, list_clients

    unique_marker = f"DENIDIN_LIST_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name_a = f"Test Client A {unique_marker}"
    name_b = f"Test Client B {unique_marker}"

    creation_a = add_client(
        morning_client, name=name_a, email=f"{unique_marker}-a@example.com", phone="050-1234567"
    )
    creation_b = add_client(
        morning_client, name=name_b, email=f"{unique_marker}-b@example.com", phone="050-1234567"
    )
    assert name_a in creation_a
    assert name_b in creation_b

    # Same search-index eventual-consistency lag as elsewhere in this file -
    # poll up to 12x/1.5s (18s) before giving up.
    result = ""
    for _ in range(12):
        result = list_clients(morning_client, name=unique_marker)
        if name_a in result and name_b in result:
            break
        time.sleep(1.5)

    assert name_a in result
    assert name_b in result


def test_list_clients_over_cap_reports_real_total(morning_client):
    """The real sandbox already has 270+ clients (research.md Decision 11) -
    a bare, unfiltered call must never silently truncate; it must report the
    real total and ask to narrow, matching the unit-level contract exactly."""
    from denidin_mcp_morning.tools import list_clients

    result = list_clients(morning_client)

    assert "יותר מדי" in result or "צמצם" in result
    assert re.search(r"\d{2,}", result), f"Expected a real (2+ digit) total in: {result!r}"


def test_list_clients_never_includes_raw_client_id(morning_client):
    """REQ-CLIENT-018: the internal Morning client_id must never appear in
    any reply shown to the WhatsApp user. Fetches the created client's real
    id directly via search_clients (not by parsing add_client's Hebrew
    string, which is independently being corrected by this same feature to
    stop including it - REQ-CLIENT-014/018)."""
    from denidin_mcp_morning.tools import add_client, list_clients

    unique_marker = f"DENIDIN_LIST_ID_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")

    # The sandbox's search index can lag briefly after a write (same class of
    # eventual-consistency observed for documents - see
    # test_morning_sandbox_invoices_crud.py's test_search_invoice_by_fields).
    # Poll up to 12x/1.5s (18s) before giving up.
    items = []
    for _ in range(12):
        search_response = morning_client.search_clients({"name": name})
        items = search_response.get("items") or []
        if items:
            break
        time.sleep(1.5)
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    result = list_clients(morning_client)

    assert client_id not in result
