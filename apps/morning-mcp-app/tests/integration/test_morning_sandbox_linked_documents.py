"""Real Morning-sandbox test for linkedDocuments exposure (bugfix-014).

No mocks: seeds a real invoice via create_invoice, marks it paid (issuing a
real linked receipt), then confirms get_invoice_details and list_invoices
both surface the link and its translated document type - the plumbing
bugfix-014's constitution-side fix depends on to net paid/owed itself instead
of double-counting the receipt as a separate charge.

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from tests.integration._seed_helpers import seed_real_client

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


@pytest.fixture()
def paid_invoice(morning_client):
    """Seed a real sandbox invoice and mark it paid (issuing a real, linked
    receipt) - returns (internal_morning_id, client_name) for the tests below."""
    from denidin_mcp_morning.tools import _build_create_invoice_payload, create_receipt

    unique_marker = f"DENIDIN_LINKEDDOCS_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    client_id, client_name = seed_real_client(morning_client, unique_marker)
    payload = _build_create_invoice_payload(
        client_id=client_id,
        amount=77.0,
        description=f"Linked documents test {unique_marker}",
    )
    response = morning_client.create_invoice(payload)
    internal_morning_id = str(response.get("id") or response.get("documentId") or "")
    assert internal_morning_id, f"Could not determine created invoice id from response: {response}"

    create_receipt(morning_client, internal_morning_id, payment_date="2026-07-12")

    return internal_morning_id, client_name


def test_get_invoice_details_shows_linked_receipt(morning_client, paid_invoice):
    from denidin_mcp_morning.tools import get_invoice_details

    internal_morning_id, _ = paid_invoice

    result = get_invoice_details(morning_client, internal_morning_id=internal_morning_id)

    assert "מסמכים מקושרים" in result
    assert "קבלה" in result
    assert "₪77.00" in result


def test_list_invoices_shows_receipt_document_type(morning_client, paid_invoice):
    """The receipt itself, when it comes back as its own line item from
    list_invoices (bugfix-014: it is not filtered out), must be visibly
    labeled as a receipt - not indistinguishable from a real invoice."""
    from denidin_mcp_morning.tools import ClientNotFoundError, list_invoices

    _, client_name = paid_invoice

    # Morning's search index can lag behind document creation (see the same
    # pattern in test_morning_sandbox_list_invoices_tool.py) - both the
    # original invoice and the receipt created by marking it paid need to
    # land in the index before list_invoices' search-based lookup sees them.
    # name_resolved=True (architecture fix, 2026-08-12) - client_name here is
    # the real seeded, exact name. A ClientNotFoundError on an early attempt
    # is tolerated the same as an empty/incomplete result - the same index
    # lag this retry loop already exists to ride out can make even an exact
    # name resolve to zero candidates for a moment.
    result = None
    for _ in range(12):
        try:
            result = list_invoices(morning_client, client_name=client_name, name_resolved=True)
        except ClientNotFoundError:
            result = None
        else:
            if "קבלה" in result and "חשבונית מס" in result:
                break
        time.sleep(1.5)

    assert result is not None and "קבלה" in result, (
        f"Receipt document type label never appeared: {result!r}"
    )
    assert "חשבונית מס" in result, f"Invoice document type label never appeared: {result!r}"
