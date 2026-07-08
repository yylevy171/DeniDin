"""Real Morning-sandbox test for the list_invoices MCP tool (US2, T007a/b).

No mocks: this test creates a real invoice via the create_invoice tool (US1,
already implemented) and then drives denidin_mcp_morning.tools.list_invoices
to confirm it's findable — the real external behavior an MCP client depends
on. Per CONSTITUTION §V and this app's testing policy (spec.md §Testing
Strategy).
"""
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


@pytest.fixture(scope="module")
def seeded_invoice(morning_client):
    """Create one real sandbox invoice via the already-working create_invoice tool."""
    from denidin_mcp_morning.tools import create_invoice

    unique_marker = f"DENIDIN_LIST_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Client {unique_marker}"

    create_invoice(
        morning_client,
        client_name=client_name,
        amount=175.0,
        description=f"List-invoices seed {unique_marker}",
    )
    return {"client_name": client_name}


def test_list_invoices_tool_finds_seeded_invoice_by_client_name(morning_client, seeded_invoice):
    from denidin_mcp_morning.tools import list_invoices

    client_name = seeded_invoice["client_name"]

    found = False
    result = None
    for _ in range(6):
        result = list_invoices(morning_client, client_name=client_name)
        if client_name in result:
            found = True
            break
        time.sleep(1)

    assert found, f"Seeded invoice for {client_name!r} not found in list_invoices result: {result!r}"


def test_list_invoices_tool_returns_readable_string_for_no_matches(morning_client):
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, client_name="NO_SUCH_CLIENT_XXXXXXXX")

    assert isinstance(result, str)
    assert result.strip() != ""


def test_list_invoices_tool_caps_results_at_ten_items(morning_client):
    """Contract requirement (user-stories.md US2): at most 10 items per response."""
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client)

    # Count invoice-number markers ("חשבונית #") the formatter emits per item.
    assert result.count("חשבונית #") <= 10
