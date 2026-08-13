"""Real Morning-sandbox test for list_invoices' status filter (bugfix,
2026-07-15): _matches_status compared Morning's raw numeric status codes
(or None for a freshly created, not-yet-paid document) against string
aliases like "unpaid"/"paid", so the filter could never match anything -
any status filter silently returned zero results, always. Fixed by
normalizing the raw code via models._MORNING_STATUS_CODES (same mapping
Invoice._normalize_status already uses) before comparing.

No mocks: seeds two real sandbox invoices (one left unpaid, one marked
paid), then confirms list_invoices' status filter genuinely discriminates
between them - the exact real-world scenario that surfaced the bug (a
freshly created invoice was invisible to status="unpaid"). Per CONSTITUTION
§V and this app's testing policy (spec.md §Testing Strategy).
"""
import time
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.utils.time_utils import now_local
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


@pytest.fixture(scope="module")
def unpaid_invoice(morning_client):
    """A freshly created invoice, deliberately left unpaid - this is the
    exact case that exposed the bug (Morning's raw status for it is None,
    not the string "unpaid")."""
    from denidin_mcp_morning.tools import create_invoice

    marker = f"DENIDIN_STATUSFILTER_UNPAID_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)
    create_invoice(morning_client, client_name=client_name, amount=61.0, description=marker, name_resolved=True)
    return {"client_name": client_name}


@pytest.fixture(scope="module")
def paid_invoice(morning_client):
    """A freshly created invoice, immediately marked paid via a real linked
    receipt (Morning's raw status code afterwards: 1)."""
    from denidin_mcp_morning.tools import create_invoice, create_receipt

    marker = f"DENIDIN_STATUSFILTER_PAID_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)
    response = create_invoice(
        morning_client, client_name=client_name, amount=62.0, description=marker, name_resolved=True
    )

    # Real invoice id is only in the tool's own confirmation text - resolve
    # it via list_invoices by client name, same as the MCP tool's own
    # documented resolution path (there's no other way to get the id here).
    from denidin_mcp_morning.tools import list_invoices

    internal_morning_id = None
    for _ in range(12):
        result = list_invoices(morning_client, client_name=client_name, name_resolved=True)
        if "מזהה פנימי" in result:
            internal_morning_id = result.split("מזהה פנימי (internal_morning_id): ")[1].splitlines()[0].strip()
            break
        time.sleep(1.5)
    assert internal_morning_id, f"Could not resolve internal_morning_id for {client_name!r} to mark it paid: {response!r}"

    create_receipt(morning_client, internal_morning_id, payment_date="2026-07-12")
    return {"client_name": client_name}


def _find_by_client_name(morning_client, client_name: str, status: str) -> str:
    """Poll list_invoices with a status filter until the seeded invoice
    either shows up or we give up (mirrors the existing index-lag tolerance
    in test_morning_sandbox_list_invoices_tool.py)."""
    from denidin_mcp_morning.tools import list_invoices

    result = ""
    for _ in range(12):
        result = list_invoices(morning_client, status=status, client_name=client_name, name_resolved=True)
        if client_name in result:
            return result
        time.sleep(1.5)
    return result


def test_status_unpaid_filter_finds_a_freshly_created_invoice(morning_client, unpaid_invoice):
    """The exact bug scenario: a brand-new, not-yet-paid invoice must be
    found by status="unpaid" - before the fix this always returned nothing,
    since Morning represents this as status=None, not the string "unpaid"."""
    client_name = unpaid_invoice["client_name"]

    result = _find_by_client_name(morning_client, client_name, status="unpaid")

    assert client_name in result, (
        f"status='unpaid' filter did not find freshly-created invoice for "
        f"{client_name!r}: {result!r}"
    )


def test_status_paid_filter_excludes_an_unpaid_invoice(morning_client, unpaid_invoice):
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(
        morning_client, status="paid", client_name=unpaid_invoice["client_name"], name_resolved=True
    )

    assert unpaid_invoice["client_name"] not in result


def test_status_paid_filter_finds_an_invoice_marked_paid(morning_client, paid_invoice):
    client_name = paid_invoice["client_name"]

    result = _find_by_client_name(morning_client, client_name, status="paid")

    assert client_name in result, (
        f"status='paid' filter did not find invoice marked paid for "
        f"{client_name!r}: {result!r}"
    )


def test_status_unpaid_filter_excludes_a_paid_invoice(morning_client, paid_invoice):
    """paid_invoice was just mutated (created, then marked paid) - Morning's
    search index can take a moment to reflect that status change specifically
    (the "found by status=paid" case above already tolerates this same lag;
    the absence case needs the same tolerance, not just one immediate read)."""
    from denidin_mcp_morning.tools import list_invoices

    client_name = paid_invoice["client_name"]
    result = ""
    for _ in range(12):
        result = list_invoices(morning_client, status="unpaid", client_name=client_name, name_resolved=True)
        if client_name not in result:
            break
        time.sleep(1.5)

    assert client_name not in result, (
        f"status='unpaid' filter still shows an invoice marked paid for "
        f"{client_name!r} after waiting for index consistency: {result!r}"
    )
