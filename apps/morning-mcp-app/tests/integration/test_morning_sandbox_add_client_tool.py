"""Real Morning-sandbox test for the add_client MCP tool (US4, T009a/b).

No mocks: drives denidin_mcp_morning.tools.add_client against the live
sandbox, per CONSTITUTION §V and this app's testing policy.
"""
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


def test_add_client_tool_creates_client_with_name_only(morning_client):
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_CLIENT_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    result = add_client(morning_client, name=name)

    assert isinstance(result, str)
    assert name in result


def test_add_client_tool_creates_client_with_full_details(morning_client):
    """tax_id must be a real Israeli business-number with a valid checksum —
    Morning validates it server-side (confirmed live: errorCode 1111,
    "מספר עוסק / ח.פ אינו תקין" for a made-up value). Reusing the known-valid
    example ID from the Postman collection's own "Add Client" sample."""
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_CLIENT_FULL_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    result = add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="+972541234567",
        tax_id="308253681",
        address="Test Address 1",
    )

    assert name in result
