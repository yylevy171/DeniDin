"""Real Morning-sandbox test for the update_client MCP tool (Feature 026, US4).

No mocks: drives denidin_mcp_morning.tools.update_client (and, for the
gatekeeper test below, the lower-level MorningClient.update_client directly)
against the live sandbox, per CONSTITUTION §V and this app's testing policy.
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


def test_update_client_partial_payload_preserves_other_fields(morning_client):
    """GATEKEEPER (research.md Decision 3): confirms empirically, using the
    already-existing low-level MorningClient.update_client (not
    tools.update_client, which doesn't exist yet), that a PUT /clients/{id}
    with only {"phone": ...} changes just that field and leaves
    name/email/taxId untouched. If this assertion ever fails, STOP - do not
    trust a straightforward partial-payload tools.update_client
    implementation; a GET-then-merge-then-PUT design needs human re-approval
    instead (see tasks.md T018b)."""
    from denidin_mcp_morning.tools import add_client

    unique_marker = f"DENIDIN_UPDATE_GATE_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"
    original_email = f"{unique_marker}@example.com"
    original_tax_id = "308253681"

    add_client(morning_client, name=name, email=original_email, phone="050-1234567", tax_id=original_tax_id)

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    morning_client.update_client(client_id, {"phone": "054-7654321"})

    updated = _poll_until(
        lambda items: bool(items) and items[0].get("phone") == "054-7654321",
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert updated, "expected the updated phone to round-trip via search_clients"
    record = updated[0]

    assert record["phone"] == "054-7654321"
    assert record["name"] == name
    assert record["taxId"] == original_tax_id
    assert (record.get("emails") or [None])[0].lower() == original_email.lower()


def test_update_client_tool_updates_name(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_NAME_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    original_name = f"Test Client {unique_marker}"
    new_name = f"Test Client Renamed {unique_marker}"

    add_client(morning_client, name=original_name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: original_name in r, lambda: get_client_details(morning_client, original_name))

    result = update_client(morning_client, name=original_name, new_name=new_name)
    assert new_name in result

    verify = _poll_until(lambda r: new_name in r, lambda: get_client_details(morning_client, new_name))
    assert new_name in verify


def test_update_client_tool_updates_email(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_EMAIL_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"
    new_email = f"{unique_marker}-new@example.com"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    update_client(morning_client, name=name, email=new_email)

    verify = _poll_until(lambda r: new_email.lower() in r.lower(), lambda: get_client_details(morning_client, name))
    assert new_email.lower() in verify.lower()


def test_update_client_tool_updates_and_normalizes_phone(morning_client):
    """REQ-CLIENT-016/017: phone is normalized before sending, and the
    normalized value round-trips through Morning - same standard as
    add_client's own phone-normalization test."""
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_PHONE_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    update_client(morning_client, name=name, phone="+972541234567")  # international input format

    verify = _poll_until(lambda r: "054-1234567" in r, lambda: get_client_details(morning_client, name))
    assert "054-1234567" in verify  # normalized Israeli local dashed format


def test_update_client_tool_updates_tax_id(morning_client):
    """tax_id must be a real Israeli business-number with a valid checksum -
    reusing the known-valid example ID from the Postman collection."""
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_TAXID_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"
    new_tax_id = "308253681"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    update_client(morning_client, name=name, tax_id=new_tax_id)

    verify = _poll_until(lambda r: new_tax_id in r, lambda: get_client_details(morning_client, name))
    assert new_tax_id in verify


def test_update_client_tool_rejects_no_fields_to_change(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_NOOP_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    with pytest.raises(ValueError):
        update_client(morning_client, name=name)


def test_update_client_tool_not_found_is_friendly(morning_client):
    from denidin_mcp_morning.tools import update_client

    result = update_client(morning_client, name="Nonexistent Client XYZ 12345", email="new@example.com")

    assert isinstance(result, str)
    assert "לא נמצא" in result or "אין" in result


def test_update_client_tool_ambiguous_name_lists_candidates(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_AMBIG_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    shared_stem = f"Test Ambiguous {unique_marker}"
    name_a = f"{shared_stem} A"
    name_b = f"{shared_stem} B"

    add_client(morning_client, name=name_a, email=f"{unique_marker}-a@example.com", phone="050-1234567")
    add_client(morning_client, name=name_b, email=f"{unique_marker}-b@example.com", phone="050-7654321")
    _poll_until(lambda r: name_a in r, lambda: get_client_details(morning_client, name_a))
    _poll_until(lambda r: name_b in r, lambda: get_client_details(morning_client, name_b))

    result = update_client(morning_client, name=shared_stem, email="new@example.com")

    assert name_a in result
    assert name_b in result


def test_update_client_tool_rejects_malformed_email_before_network_call(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_BADEMAIL_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    with pytest.raises(ValueError):
        update_client(morning_client, name=name, email="not-an-email")


def test_update_client_tool_rejects_implausible_phone_before_network_call(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_BADPHONE_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    with pytest.raises(ValueError):
        update_client(morning_client, name=name, phone="123")


def test_update_client_tool_confirmation_never_includes_raw_client_id(morning_client):
    """REQ-CLIENT-018: the internal Morning client_id must never appear in
    any reply shown to the WhatsApp user."""
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_ID_LEAK_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the client to be found via search_clients"
    client_id = items[0]["id"]

    result = update_client(morning_client, name=name, tax_id="308253681")

    assert client_id not in result


def test_update_client_tool_discloses_non_exact_match(morning_client):
    """New requirement: when the target resolves via a non-exact (partial/
    prefix) match, the confirmation must explicitly disclose which client
    was actually updated, distinct from the exact-match phrasing."""
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    # Random hex marker, not a timestamp - see the analogous comment in
    # test_morning_sandbox_get_client_details_tool.py's disclosure test.
    unique_marker = uuid.uuid4().hex[:16].upper()
    name = f"Test Client {unique_marker}"
    partial_reference = f"Test Client {unique_marker[:-3]}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    result = update_client(morning_client, name=partial_reference, tax_id="308253681")

    assert "מצאתי ועדכנתי את הלקוח הבא" in result
    assert name in result


def test_update_client_tool_exact_match_uses_standard_phrasing(morning_client):
    from denidin_mcp_morning.tools import add_client, get_client_details, update_client

    unique_marker = f"DENIDIN_UPDATE_EXACT_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    name = f"Test Client {unique_marker}"

    add_client(morning_client, name=name, email=f"{unique_marker}@example.com", phone="050-1234567")
    _poll_until(lambda r: name in r, lambda: get_client_details(morning_client, name))

    result = update_client(morning_client, name=name, tax_id="308253681")

    assert result.startswith("עודכנו פרטי הלקוח:")
    assert "מצאתי ועדכנתי" not in result
