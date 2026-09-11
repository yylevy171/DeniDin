"""Real Morning-sandbox test for the list_invoices MCP tool (US2, T007a/b).

No mocks: this test creates a real invoice via the create_invoice tool (US1,
already implemented) and then drives denidin_mcp_morning.tools.list_invoices
to confirm it's findable — the real external behavior an MCP client depends
on. Per CONSTITUTION §V and this app's testing policy (spec.md §Testing
Strategy).
"""
import json
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
        auth_url=config.auth_url,
    )


@pytest.fixture(scope="module")
def seeded_invoice(morning_client):
    """Create one real sandbox invoice via the already-working create_invoice tool."""
    from denidin_mcp_morning.tools import create_invoice

    unique_marker = f"DENIDIN_LIST_TEST_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker)

    create_invoice(
        morning_client,
        client_name=client_name,
        amount=75.0,
        description=f"List-invoices seed {unique_marker}",
        name_resolved=True,
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
        result = list_invoices(morning_client, client_name=client_name, name_resolved=True)
        if client_name in result:
            found = True
            break
        time.sleep(1.5)

    assert found, f"Seeded invoice for {client_name!r} not found in list_invoices result: {result!r}"
    documents = json.loads(result)["documents"]
    assert any(d["client_name"] == client_name for d in documents)


def test_list_invoices_tool_finds_seeded_invoice_by_non_prefix_substring(morning_client):
    """Morning's real /documents/search `clientName` param does full-text
    substring matching, not prefix-only (confirmed live 2026-07-30, see
    specs/in-progress/031-fuzzy-client-lookup-by-name/research.md Decision 1
    - Feature 031). Regression-locks that finding: a query matching a
    *middle* word of the stored name (not a prefix of the whole name) still
    finds the invoice.
    """
    from denidin_mcp_morning.tools import create_invoice, list_invoices

    unique_marker = f"DENIDIN_SUBSTRING_TEST_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker, name=f"Yossi Cohen {unique_marker} Ltd")

    create_invoice(
        morning_client,
        client_name=client_name,
        amount=42.0,
        description=f"Substring-match seed {unique_marker}",
        name_resolved=True,
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


def test_list_invoices_tool_non_exact_multi_word_with_name_resolved_raises_not_found(morning_client):
    """Architecture fix (2026-08-12): list_invoices no longer asks its own
    confirmation question on a non-exact multi-word client_name (bugfix-039)
    - that disclosure now lives entirely in resolve_client_name (see
    test_morning_sandbox_resolve_client_name_tool.py). Asserting
    name_resolved=True against a name that's still only a prefix variant
    (real production shape: "דוד אדלר" typed against stored "דודי אדלר",
    2026-08-10) is a contract violation and raises ClientNotFoundError -
    never silently lists under a guessed name, and never silently claims
    "not found" for a name that actually IS resolvable via
    resolve_client_name first."""
    from denidin_mcp_morning.tools import ClientNotFoundError, create_invoice, list_invoices

    unique_marker = f"DENIDIN_BUG039_{int(now_local().timestamp())}"
    stored_first_name = "Yossef"
    queried_first_name = "Yoss"  # genuine prefix of the stored word, not its literal spelling
    client_name = f"{stored_first_name} {unique_marker} Cohenberg"
    _, client_name = seed_real_client(morning_client, unique_marker, name=client_name)

    create_invoice(
        morning_client,
        client_name=client_name,
        amount=63.0,
        description=f"Name-variant seed {unique_marker}",
        name_resolved=True,
    )

    query = f"{queried_first_name} {unique_marker}"  # two words; first is a prefix variant

    with pytest.raises(ClientNotFoundError):
        list_invoices(morning_client, client_name=query, name_resolved=True)


def test_list_invoices_tool_multi_word_not_resolved_refuses_without_any_lookup(morning_client):
    """Architecture fix (2026-08-12): a multi-word client_name requires
    name_resolved=True and refuses immediately, with zero Morning calls at
    all, otherwise. Follow-up (2026-08-12): this is now a real raise, not
    ordinary refusal text - two outcomes only, succeed or raise."""
    from denidin_mcp_morning.tools import ClientNameNotResolvedError, list_invoices

    with pytest.raises(ClientNameNotResolvedError) as exc_info:
        list_invoices(morning_client, client_name="NO_SUCH_CLIENT_XXXXXXXX NO_SUCH_SURNAME_YYYYYYYY")

    assert "resolve_client_name" in str(exc_info.value)


def test_list_invoices_tool_reports_not_found_when_no_word_resolves(morning_client):
    """Regression test for bugfix-039, updated for the architecture fix
    (2026-08-12): a multi-word client_name query where no word matches any
    real client at all must raise ClientNotFoundError once name_resolved=True
    is asserted - never an ambiguous-refusal or a confirmation question with
    nothing to confirm (user decision, 2026-08-10: "if truly no match on any
    prefix(es) - decide that there is no match")."""
    from denidin_mcp_morning.tools import ClientNotFoundError, list_invoices

    with pytest.raises(ClientNotFoundError):
        list_invoices(
            morning_client,
            client_name="NO_SUCH_CLIENT_XXXXXXXX NO_SUCH_SURNAME_YYYYYYYY",
            name_resolved=True,
        )


def test_list_invoices_tool_returns_readable_string_for_no_matches(morning_client):
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, client_name="NO_SUCH_CLIENT_XXXXXXXX")

    assert isinstance(result, str)
    payload = json.loads(result)
    assert payload["total_matched"] == 0
    assert payload["documents"] == []


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

    Asserts on the JSON `total_matched` field, not a bare-number substring
    check - a bare `"81" in result` false-positives on the old (buggy) code,
    since "81" coincidentally appears inside unrelated document GUIDs in the
    reply (confirmed while writing this test, back when the tool returned
    prose)."""
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, **_US1_LARGE_IN_CAP_RANGE)
    payload = json.loads(result)

    assert payload["total_matched"] == _US1_LARGE_IN_CAP_TOTAL, (
        f"Expected total_matched={_US1_LARGE_IN_CAP_TOTAL}, proving the fetch loop retrieved "
        f"the complete set (and disclosed the real total) rather than stopping at one "
        f"Morning page. Reply: {result!r}"
    )
    assert payload["shown"] == _US1_LARGE_IN_CAP_TOTAL


def test_list_invoices_tool_refuses_when_over_cap(morning_client):
    """US2: a query whose real Morning total (103) exceeds the 100-item
    fetch cap must refuse to fetch further pages and clearly state the
    real total, asking the user to narrow the search - never a silent
    partial list.

    Asserts on the JSON `status`/`total` fields, not a bare-number substring
    check - see test_list_invoices_tool_fetches_complete_set_within_cap's
    docstring for why a bare number check is unreliable against real data."""
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, **_US2_OVER_CAP_RANGE)
    payload = json.loads(result)

    assert payload["status"] == "too_many"
    assert payload["total"] == _US2_OVER_CAP_TOTAL, f"Reply: {result!r}"
    assert "documents" not in payload, (
        f"Over-cap refusal must not include itemized invoice content. Reply: {result!r}"
    )


# ============================================================================
# `number` filter (bugfix, 2026-08-07) - Morning's real /documents/search
# has always accepted a `number` param; confirms it live against the sandbox.
# ============================================================================


def test_list_invoices_tool_finds_document_by_number(morning_client, seeded_invoice):
    from denidin_mcp_morning.tools import list_invoices

    client_name = seeded_invoice["client_name"]

    # Resolve the seeded invoice's real number first (via client name, as
    # the existing tool already supports), then search by that number alone.
    by_name_result = None
    documents = []
    for _ in range(12):
        by_name_result = list_invoices(morning_client, client_name=client_name, name_resolved=True)
        documents = json.loads(by_name_result).get("documents") or []
        if documents:
            break
        time.sleep(1.5)
    assert documents, (
        f"Could not resolve the seeded invoice's number to search by: {by_name_result!r}"
    )
    number = documents[0]["display_number"]

    result = None
    for _ in range(12):
        result = list_invoices(morning_client, document_display_number=number)
        payload = json.loads(result)
        if payload.get("documents") and payload["documents"][0]["display_number"] == number:
            break
        time.sleep(1.5)

    payload = json.loads(result)
    assert payload["documents"] and payload["documents"][0]["display_number"] == number, (
        f"Searching by number={number!r} alone did not find the seeded invoice: {result!r}"
    )
    assert payload["documents"][0]["client_name"] == client_name, (
        f"Result found by number should still show the real client name: {result!r}"
    )


def test_list_invoices_tool_number_not_found_is_friendly(morning_client):
    from denidin_mcp_morning.tools import list_invoices

    result = list_invoices(morning_client, document_display_number="99999999")

    payload = json.loads(result)
    assert payload["total_matched"] == 0
    assert payload["documents"] == []
