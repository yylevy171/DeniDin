"""Real Morning-sandbox test for the add_client MCP tool (Feature 026, US3).

No mocks: drives denidin_mcp_morning.tools.add_client against the live
sandbox, per CONSTITUTION §V and this app's testing policy.

Feature 026 reworked add_client: name/email/phone are now all required (no
`address` parameter at all), email is validated and phone normalized
client-side before any network call, and the tool is now approval-gated at
the denidin-app layer (unchanged here - that's a different app's concern).
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# Search-index eventual-consistency lag (research.md Decision 8).
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


def _poll_until(predicate, action):
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


def test_add_client_tool_creates_client_with_required_fields_only(morning_client):
    """name/email/phone (all required) with no tax_id - tax_id stays optional."""
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_CLIENT_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    result = add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
    )

    assert isinstance(result, str)
    assert name in result


def test_add_client_tool_creates_client_with_tax_id(morning_client):
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
    )

    assert name in result


def test_add_client_tool_requires_email_and_phone(morning_client):
    """name/email/phone are all mandatory (REQ-CLIENT-012) - omitting either
    is a Python-level required-argument error (the MCP tool schema marks
    both required, so the model can't call the tool without them)."""
    from denidin_mcp_morning.tools import add_client

    with pytest.raises(TypeError):
        add_client(morning_client, name="Missing Email And Phone")


def test_add_client_tool_no_longer_accepts_address(morning_client):
    """address is out of scope (REQ-CLIENT-013) - no longer a parameter at all."""
    from denidin_mcp_morning.tools import add_client

    with pytest.raises(TypeError):
        add_client(
            morning_client,
            name="Test",
            email="test@example.com",
            phone="050-1234567",
            address="Some Street 1",
        )


def test_add_client_tool_normalizes_and_persists_phone(morning_client):
    """REQ-CLIENT-016/017: phone is normalized before sending, and the
    normalized value actually round-trips through Morning - not just that
    the request payload looked right."""
    from denidin_mcp_morning.tools import add_client, get_client_details

    unique_marker = f"DENIDIN_CLIENT_PHONE_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="+972501234567",  # international input format
    )

    result = _poll_until(
        lambda r: name in r,
        lambda: get_client_details(morning_client, name),
    )

    assert "050-1234567" in result  # normalized Israeli local dashed format


def test_add_client_tool_confirmation_never_includes_raw_client_id(morning_client):
    """REQ-CLIENT-018: the internal Morning client_id must never appear in
    any reply shown to the WhatsApp user - corrects the prior behavior of
    this exact tool, which used to include "(מזהה: {client_id})"."""
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_CLIENT_ID_LEAK_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    result = add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}@example.com",
        phone="050-1234567",
    )

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    assert client_id not in result


def test_add_client_tool_second_call_with_same_name_is_try_and_fail(morning_client):
    """REQ-CLIENT-007/F2: no proactive duplicate-name check is performed -
    add_client attempts creation normally even when a client with the same
    name already exists. Whatever Morning's real API actually does with the
    second attempt (creates a second record, or rejects it) is asserted
    explicitly here, not assumed either way."""
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_CLIENT_DUP_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    first_result = add_client(
        morning_client,
        name=name,
        email=f"{unique_marker}-a@example.com",
        phone="050-1234567",
    )
    assert name in first_result

    try:
        second_result = add_client(
            morning_client,
            name=name,
            email=f"{unique_marker}-b@example.com",
            phone="050-7654321",
        )
    except Exception as exc:  # noqa: BLE001 - deliberately observing whatever Morning does
        # Morning itself rejected the duplicate - a real, non-silent failure
        # (server.py's error boundary maps this to a friendly message in
        # production; here we only confirm it's a genuine exception, not a
        # silent no-op that pretends to succeed).
        assert str(exc)
    else:
        # Morning allowed a second client with the same name - confirm it was
        # genuinely created (not a no-op success message), matching
        # REQ-CLIENT-007's "try and fail" contract: no proactive check
        # blocked the attempt.
        assert name in second_result
        items = _poll_until(
            lambda items: len(items) >= 2,
            lambda: (morning_client.search_clients({"name": name}).get("items") or []),
        )
        assert len(items) >= 2, "expected two distinct client records with the same name"
