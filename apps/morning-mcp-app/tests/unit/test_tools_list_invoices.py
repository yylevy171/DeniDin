"""Tests for feature 038's rewritten `list_invoices` fetch-loop, item-count
cap, and token-budget truncation logic.

Uses a fake MorningClient (dependency-injected, matching the real
`list_invoices` contract) - this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V), mirroring the established
pattern in test_tools_client_management.py.
"""
import tiktoken

from denidin_mcp_morning import tools
from denidin_mcp_morning.formatters import format_invoice_confirmation
from denidin_mcp_morning.models import Invoice

_ENCODING = tiktoken.get_encoding("o200k_base")


class _FakeMorningClient:
    """Records calls and returns pre-set per-page responses - stands in for
    the MorningClient network boundary."""

    def __init__(self, responses):
        # One response dict per successive list_invoices() call, keyed by
        # call order (page 1 first, then page 2, ...).
        self._responses = responses
        self.list_invoices_calls = []

    def list_invoices(self, params=None):
        self.list_invoices_calls.append(params or {})
        return self._responses[len(self.list_invoices_calls) - 1]


def _raw_document(number: str, client_name: str = "Test Client") -> dict:
    """A raw Morning /documents(/search) item, matching the real shape
    (see REAL_DOCUMENT_RESPONSE_SAMPLE in test_formatters.py)."""
    return {
        "id": f"doc-{number}",
        "number": number,
        "type": 305,
        "client": {"id": "client-1", "name": client_name},
        "date": "2026-07-08",
        "currency": "ILS",
        "amount": 100.0,
        "total": 100.0,
        "status": 0,
    }


def _page_response(items, total, page=1, pages=1):
    return {"pageSize": 25, "page": page, "total": total, "pages": pages, "items": items}


# ============================================================================
# Fetch-loop / item-count cap boundary (REQ-INVOICE-001/002/003/007)
# ============================================================================


def test_list_invoices_loops_every_page_when_total_within_cap():
    page1_items = [_raw_document(str(n)) for n in range(1, 11)]
    page2_items = [_raw_document(str(n)) for n in range(11, 16)]
    client = _FakeMorningClient(
        [
            _page_response(page1_items, total=15, page=1, pages=2),
            _page_response(page2_items, total=15, page=2, pages=2),
        ]
    )

    result = tools.list_invoices(client)

    assert len(client.list_invoices_calls) == 2
    assert client.list_invoices_calls[1]["page"] == 2
    for n in range(1, 16):
        assert f"חשבונית #{n}" in result


def test_list_invoices_boundary_at_exact_cap_still_fetches_everything():
    """total == _LIST_INVOICES_MAX_ITEMS (100): the cap is a 'fetch no
    further' boundary, not an exclusive one (spec.md Edge Cases) - mirrors
    list_clients' `if total > cap` (strictly greater) boundary."""
    page1_items = [_raw_document(str(n)) for n in range(1, 26)]
    page2_items = [_raw_document(str(n)) for n in range(26, 51)]
    page3_items = [_raw_document(str(n)) for n in range(51, 76)]
    page4_items = [_raw_document(str(n)) for n in range(76, 101)]
    client = _FakeMorningClient(
        [
            _page_response(page1_items, total=100, page=1, pages=4),
            _page_response(page2_items, total=100, page=2, pages=4),
            _page_response(page3_items, total=100, page=3, pages=4),
            _page_response(page4_items, total=100, page=4, pages=4),
        ]
    )

    tools.list_invoices(client)

    assert len(client.list_invoices_calls) == 4


def test_list_invoices_refuses_and_fetches_only_page_one_when_over_cap():
    page1_items = [_raw_document(str(n)) for n in range(1, 26)]
    client = _FakeMorningClient([_page_response(page1_items, total=101, page=1, pages=5)])

    result = tools.list_invoices(client)

    assert len(client.list_invoices_calls) == 1
    assert "נמצאו 101" in result  # designed refusal-message phrase, not a bare digit check
    assert "חשבונית #" not in result


def test_list_invoices_defaults_missing_page_and_pages_fields():
    """Missing page/pages in a response defaults to 1/1, matching
    list_clients' existing fallback (REQ-INVOICE-007) - the loop must
    terminate after page 1 rather than erroring."""
    items = [_raw_document(str(n)) for n in range(1, 6)]
    response = {"total": 5, "items": items}  # no "page"/"pages" keys at all
    client = _FakeMorningClient([response])

    result = tools.list_invoices(client)

    assert len(client.list_invoices_calls) == 1
    for n in range(1, 6):
        assert f"חשבונית #{n}" in result


def test_list_invoices_zero_matches_returns_unchanged_no_results_message():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    result = tools.list_invoices(client)

    assert result == "לא נמצאו חשבוניות התואמות את החיפוש."


# ============================================================================
# `number` filter (bugfix, 2026-08-07): Morning's real /documents/search
# endpoint has always accepted a `number` param (confirmed via the checked-in
# Postman collection's "Search Documents" example) - never wired up here,
# so any bare "invoice number X" reference had no real way to resolve short
# of an unfiltered search, which fails outright once the sandbox holds more
# documents than the fetch cap.
# ============================================================================


def test_map_list_invoices_filters_includes_number_as_an_int():
    assert tools._map_list_invoices_filters(number="51365") == {"number": 51365}


def test_map_list_invoices_filters_ignores_non_numeric_number():
    assert tools._map_list_invoices_filters(number="not-a-number") == {}


def test_map_list_invoices_filters_number_combines_with_other_filters():
    params = tools._map_list_invoices_filters(client_name="Test Client", number="51365")
    assert params == {"clientName": "Test Client", "number": 51365}


def test_list_invoices_passes_number_filter_to_search():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    tools.list_invoices(client, number="51365")

    assert client.list_invoices_calls == [{"number": 51365}]


def test_list_invoices_finds_document_by_number():
    item = _raw_document("51365")
    client = _FakeMorningClient([_page_response([item], total=1, page=1, pages=1)])

    result = tools.list_invoices(client, number="51365")

    assert "חשבונית #51365" in result


def test_list_invoices_number_not_found_returns_unchanged_no_results_message():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    result = tools.list_invoices(client, number="99999999")

    assert result == "לא נמצאו חשבוניות התואמות את החיפוש."


# ============================================================================
# Token-budget truncation (REQ-INVOICE-008/009, research.md Decision 6)
#
# `token_budget` is a config-driven value (MorningMCPConfig.list_invoices_
# token_budget, default 2500 in real deployments - server.py threads it into
# tools.list_invoices via dependency injection, same pattern as every other
# config value in this app). Production behavior stays at the real,
# unmodified default everywhere except here: per explicit user direction,
# this ONE test - the one that specifically needs to exercise the
# truncation boundary deterministically and cheaply - passes an explicitly
# low `token_budget` value directly, exactly like "a testing harness setting
# its own config" would. No other test in this suite touches this
# parameter; every other test call relies on the real default.
# ============================================================================


def _block_tokens(number: str, client_name: str = "Test Client") -> int:
    invoice = Invoice.model_validate(_raw_document(number, client_name))
    return len(_ENCODING.encode(format_invoice_confirmation(invoice)))


def test_list_invoices_truncates_to_a_partial_prefix_within_token_budget():
    numbers = [str(n) for n in range(1, 6)]
    items = [_raw_document(n) for n in numbers]

    # Compute a deliberately low test-only budget from the real block size
    # (not hardcoded) so this test doesn't depend on guessing
    # format_invoice_confirmation's exact output size: big enough for 2
    # blocks to fit, too small for all 5.
    single_block_tokens = _block_tokens(numbers[0])
    low_test_budget = single_block_tokens * 2 + 120  # ~2 blocks + reserve headroom
    assert single_block_tokens * 3 > low_test_budget - 100, (
        "test fixture assumption: 3 blocks must already exceed the smallest possible "
        "item-block budget at this low_test_budget, or this test doesn't actually "
        "exercise truncation"
    )

    client = _FakeMorningClient([_page_response(items, total=len(items), page=1, pages=1)])

    result = tools.list_invoices(client, token_budget=low_test_budget)

    shown = result.count("חשבונית #")
    assert 0 < shown < len(numbers), f"expected a genuine partial prefix, got shown={shown} of {len(numbers)}"
    assert f"מתוך {len(numbers)}" in result  # designed "shown X מתוך Y" phrase, real total still accurate


def test_list_invoices_no_truncation_when_reply_fits_comfortably_within_budget():
    """Uses the real default budget (no override) - confirms production
    behavior for a small reply is unaffected by this feature."""
    numbers = [str(n) for n in range(1, 4)]
    items = [_raw_document(n) for n in numbers]
    client = _FakeMorningClient([_page_response(items, total=len(items), page=1, pages=1)])

    result = tools.list_invoices(client)

    assert result.count("חשבונית #") == len(numbers)
    assert "מתוך" not in result  # untruncated reply uses the simple count line, not "shown X of Y"
