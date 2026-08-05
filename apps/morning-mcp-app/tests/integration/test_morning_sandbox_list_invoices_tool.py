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
        amount=75.0,
        description=f"List-invoices seed {unique_marker}",
    )
    return {"client_name": client_name}


def test_list_invoices_tool_finds_seeded_invoice_by_client_name(morning_client, seeded_invoice):
    from denidin_mcp_morning.tools import list_invoices

    client_name = seeded_invoice["client_name"]

    # Widened from an earlier 6x/1s window (up to 6s) after an observed flake
    # under a full-suite run creating many sandbox documents in quick
    # succession — Morning's search index can lag further behind under that
    # load than in isolation. 12x/1.5s (up to 18s) gives realistic headroom
    # while still exiting immediately once found.
    found = False
    result = None
    for _ in range(12):
        result = list_invoices(morning_client, client_name=client_name)
        if client_name in result:
            found = True
            break
        time.sleep(1.5)

    assert found, f"Seeded invoice for {client_name!r} not found in list_invoices result: {result!r}"


def test_list_invoices_tool_finds_seeded_invoice_by_non_prefix_substring(morning_client):
    """Morning's real /documents/search `clientName` param does full-text
    substring matching, not prefix-only (confirmed live 2026-07-30, see
    specs/in-progress/031-fuzzy-client-lookup-by-name/research.md Decision 1
    - Feature 031). Regression-locks that finding: a query matching a
    *middle* word of the stored name (not a prefix of the whole name) still
    finds the invoice.
    """
    from denidin_mcp_morning.tools import create_invoice, list_invoices

    unique_marker = f"DENIDIN_SUBSTRING_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Yossi Cohen {unique_marker} Ltd"

    create_invoice(
        morning_client,
        client_name=client_name,
        amount=42.0,
        description=f"Substring-match seed {unique_marker}",
    )

    # Middle word of client_name - not a prefix of the whole stored name.
    substring_query = "Cohen"

    found = False
    result = None
    for _ in range(12):
        result = list_invoices(morning_client, client_name=substring_query)
        if unique_marker in result:
            found = True
            break
        time.sleep(1.5)

    assert found, (
        f"Substring query {substring_query!r} did not find invoice for "
        f"{client_name!r} in list_invoices result: {result!r}"
    )


def test_list_invoices_tool_returns_readable_string_for_no_matches(morning_client):
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, client_name="NO_SUCH_CLIENT_XXXXXXXX")

    assert isinstance(result, str)
    assert result.strip() != ""


# ============================================================================
# Feature 038: real-pagination fetch cap (10 -> 100), replacing the old
# fixed 10-item display cap this file used to test here (that test was
# deleted, T011 - human-approved - its coverage intent, "a cap exists and
# is enforced," is superseded by the two tests below, which assert the
# actual new behavior at each side of the cap instead of the old truncation
# artifact).
# ============================================================================

# Real, already-existing sandbox date ranges (no invoices seeded for these
# two tests) - found via a live probe, research.md Decision 4. Re-probe
# with the same method if the sandbox's data ever changes enough that these
# totals drift from what's asserted below.
_US1_LARGE_IN_CAP_RANGE = {"from_date": "2026-07-19", "to_date": "2026-07-21"}
_US1_LARGE_IN_CAP_TOTAL = 81
_US2_OVER_CAP_RANGE = {"from_date": "2026-07-13", "to_date": "2026-07-15"}
_US2_OVER_CAP_TOTAL = 103


def test_list_invoices_tool_fetches_complete_set_within_cap(morning_client):
    """US1: a query whose real Morning total (81) is more than the old
    10-item display cap but well within the new 100-item fetch cap must be
    *fetched* completely internally - the tool must know and disclose the
    true total, not silently limit itself to Morning's first page. This is
    the direct regression test for the observed production bug (46 of 62
    returned, 2026-08-04).

    Asserts on the designed count-line phrase ("מתוך {total}"), not a bare
    number - a bare `"81" in result` false-positives on the old (buggy)
    code, since "81" coincidentally appears inside unrelated document GUIDs
    in the reply (confirmed while writing this test)."""
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, **_US1_LARGE_IN_CAP_RANGE)

    expected_phrase = f"מתוך {_US1_LARGE_IN_CAP_TOTAL}"
    assert expected_phrase in result, (
        f"Expected {expected_phrase!r} in the reply, proving the fetch loop retrieved "
        f"the complete set (and disclosed the real total) rather than stopping at one "
        f"Morning page. Reply: {result!r}"
    )


def test_list_invoices_tool_refuses_when_over_cap(morning_client):
    """US2: a query whose real Morning total (103) exceeds the 100-item
    fetch cap must refuse to fetch further pages and clearly state the
    real total, asking the user to narrow the search - never a silent
    partial list.

    Asserts on the designed refusal-message phrase ("נמצאו {total}"), not a
    bare number - see test_list_invoices_tool_fetches_complete_set_within_cap's
    docstring for why a bare number check is unreliable against real data."""
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, **_US2_OVER_CAP_RANGE)

    expected_phrase = f"נמצאו {_US2_OVER_CAP_TOTAL}"
    assert expected_phrase in result, (
        f"Expected {expected_phrase!r} in the refusal message. Reply: {result!r}"
    )
    assert "חשבונית #" not in result, (
        f"Over-cap refusal must not include itemized invoice content. Reply: {result!r}"
    )
    assert "מתוך" not in result, (
        f"Over-cap refusal and token-budget partial-truncation wording are mutually "
        f"exclusive - the over-cap path never reaches formatting. Reply: {result!r}"
    )
