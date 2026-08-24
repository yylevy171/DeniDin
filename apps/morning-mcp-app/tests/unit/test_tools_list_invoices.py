"""Tests for feature 038's rewritten `list_invoices` fetch-loop, item-count
cap, and token-budget truncation logic.

Uses a fake MorningClient (dependency-injected, matching the real
`list_invoices` contract) - this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V), mirroring the established
pattern in test_tools_client_management.py.
"""
import pytest
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
        self.search_clients_calls = []

    def list_invoices(self, params=None):
        self.list_invoices_calls.append(params or {})
        return self._responses[len(self.list_invoices_calls) - 1]

    def search_clients(self, payload=None):
        # No test in this file exercises a client_name that actually
        # resolves - only the not-found/not-resolved paths, which need
        # every prefix/word lookup resolve_client_by_name makes to come
        # back empty, same as a genuinely nonexistent client would.
        self.search_clients_calls.append(payload or {})
        return {"items": [], "total": 0}


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


def test_list_invoices_multi_word_client_name_not_found_raises():
    """Unification (2026-08-12, user decision): a multi-word client_name
    that resolves to zero real clients used to fall through silently to
    the raw query below, which also finds nothing but only ever produces
    a generic "no invoices matched" message - never telling the user
    their CLIENT specifically wasn't found. Now it raises the same
    ClientNotFoundError every other client-resolving tool raises. Requires
    name_resolved=True (architecture fix, 2026-08-12) - the caller must
    have already gone through resolve_client_name."""
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    with pytest.raises(tools.ClientNotFoundError) as exc_info:
        tools.list_invoices(client, client_name="Nonexistent Client XYZ", name_resolved=True)

    assert "לא נמצא" in str(exc_info.value) or "אין" in str(exc_info.value)
    assert client.list_invoices_calls == []  # never even reaches the raw query


def test_list_invoices_multi_word_client_name_not_resolved_refuses_without_any_lookup():
    """Architecture fix (2026-08-12): list_invoices no longer does its own
    fuzzy/word-growth matching for a multi-word client_name - it requires
    name_resolved=True and refuses immediately, with zero Morning calls at
    all (neither search_clients nor list_invoices), otherwise. Follow-up
    (2026-08-12): this is now a real raise, not ordinary refusal text - two
    outcomes only, succeed or raise."""
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.list_invoices(client, client_name="Nonexistent Client XYZ")

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.list_invoices_calls == []


def test_list_invoices_single_word_client_name_is_untouched_by_the_gate():
    """Regression: a single-word client_name is a deliberate plain substring
    search (this tool's own long-standing policy, unrelated to the
    resolution architecture) - it must NOT require name_resolved, and must
    NOT go through search_clients at all, regardless of name_resolved."""
    item = _raw_document("1", client_name="Cohen Industries")
    client = _FakeMorningClient([_page_response([item], total=1, page=1, pages=1)])

    result = tools.list_invoices(client, client_name="Cohen")

    assert "חשבונית #1" in result
    assert client.search_clients_calls == []  # never resolved - single word, untouched
    assert client.list_invoices_calls == [{"clientName": "Cohen"}]


# ============================================================================
# `number` filter (bugfix, 2026-08-07): Morning's real /documents/search
# endpoint has always accepted a `number` param (confirmed via the checked-in
# Postman collection's "Search Documents" example) - never wired up here,
# so any bare "invoice number X" reference had no real way to resolve short
# of an unfiltered search, which fails outright once the sandbox holds more
# documents than the fetch cap.
# ============================================================================


def test_map_list_invoices_filters_includes_number_as_an_int():
    assert tools._map_list_invoices_filters(document_display_number="51365") == {"number": 51365}


def test_map_list_invoices_filters_ignores_non_numeric_number():
    assert tools._map_list_invoices_filters(document_display_number="not-a-number") == {}


def test_map_list_invoices_filters_number_combines_with_other_filters():
    params = tools._map_list_invoices_filters(client_name="Test Client", document_display_number="51365")
    assert params == {"clientName": "Test Client", "number": 51365}


def test_list_invoices_passes_number_filter_to_search():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    tools.list_invoices(client, document_display_number="51365")

    assert client.list_invoices_calls == [{"number": 51365}]


def test_list_invoices_finds_document_by_number():
    item = _raw_document("51365")
    client = _FakeMorningClient([_page_response([item], total=1, page=1, pages=1)])

    result = tools.list_invoices(client, document_display_number="51365")

    assert "חשבונית #51365" in result


def test_list_invoices_number_not_found_returns_unchanged_no_results_message():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    result = tools.list_invoices(client, document_display_number="99999999")

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


# ============================================================================
# Feature 025 Phase 9: output_format
# ============================================================================

def test_list_invoices_defaults_to_hebrew_prose_unchanged():
    """The default path MUST stay byte-for-byte what conversations get today -
    only the reconciliation sweep opts into JSON."""
    import json as _json
    from denidin_mcp_morning import tools as _tools

    class _StubClient:
        def list_invoices(self, params=None):
            return {"total": 1, "page": 1, "pages": 1, "items": [{
                "id": "abc", "number": 40406, "type": 300, "status": 1,
                "client": {"id": "c1", "name": "נאדר קרא"},
                "documentDate": "2026-08-20", "creationDate": 1787241168,
                "description": "תחזוקה", "amount": 51.92,
            }]}

    text = _tools.list_invoices(_StubClient(), from_date="2026-08-20")
    assert "חשבונית #40406" in text
    with pytest.raises(_json.JSONDecodeError):
        _json.loads(text)


def test_list_invoices_json_format_returns_parseable_machine_output():
    import json as _json
    from denidin_mcp_morning import tools as _tools

    class _StubClient:
        def list_invoices(self, params=None):
            return {"total": 1, "page": 1, "pages": 1, "items": [{
                "id": "abc", "number": 40406, "type": 300, "status": 1,
                "client": {"id": "c1", "name": "נאדר קרא"},
                "documentDate": "2026-08-20", "creationDate": 1787241168,
                "description": "תחזוקה", "amount": 51.92,
            }]}

    payload = _json.loads(_tools.list_invoices(
        _StubClient(), from_date="2026-08-20", output_format="json"))

    assert payload["total_matched"] == 1
    doc = payload["documents"][0]
    assert doc["display_number"] == "40406"
    assert doc["status_label"] == "מסמך סגור"
    assert doc["creation_date"].startswith("2026-08-20T18:52:48")


def test_list_invoices_json_is_not_token_budget_truncated():
    """A reconciliation consumer needs EVERY match - the prose path's token
    budget (which silently showed 8 of 18 real documents) must not apply."""
    import json as _json
    from denidin_mcp_morning import tools as _tools

    many = [{
        "id": f"id-{i}", "number": 40000 + i, "type": 300, "status": 1,
        "client": {"id": "c1", "name": "לקוח ארוך שם מאוד לצורך בדיקה"},
        "documentDate": "2026-08-20", "creationDate": 1787241168,
        "description": "תיאור ארוך מאוד כדי לצרוך תקציב טוקנים" * 5,
        "amount": 100.0,
    } for i in range(40)]

    class _StubClient:
        def list_invoices(self, params=None):
            return {"total": len(many), "page": 1, "pages": 1, "items": many}

    payload = _json.loads(_tools.list_invoices(
        _StubClient(), from_date="2026-08-20", output_format="json", token_budget=50))

    assert payload["total_matched"] == 40
    assert len(payload["documents"]) == 40


def _stub_client_factory(calls, search_item, detail):
    class _StubClient:
        def list_invoices(self, params=None):
            return {"total": 1, "page": 1, "pages": 1, "items": [search_item]}
        def get_invoice(self, invoice_id):
            calls["get"] += 1
            return detail
    return _StubClient()


_SEARCH_ITEM = {
    "id": "abc", "number": 60443, "type": 320, "status": 1,
    "client": {"id": "c1", "name": "לקוח"}, "documentDate": "2026-08-20",
    "creationDate": 1787178090, "description": "יועץ משפטי", "amount": 1500,
    "payment": [{"date": "2026-07-12", "type": 4, "name": "העברה בנקאית",
                 "description": "בנק 31 / סניף 109", "amount": 1500}],
}
_DETAIL = dict(_SEARCH_ITEM, payment=[{
    "date": "2026-07-12", "type": 4, "name": "העברה בנקאית", "amount": 1500,
    "bankName": "31", "bankBranch": "109", "bankAccount": "105542585",
}], linkedDocuments=[{"id": "L1", "type": 305, "number": 52203,
                      "documentDate": "2026-08-20", "amount": 1500}])


def test_include_full_details_fans_out_to_full_details_server_side():
    """Feature 025 Phase 9: structured bank details and linkedDocuments exist
    ONLY on the single-document GET. Asking the MODEL to chain those N calls
    proved unreliable (it stopped after two captures without ever calling
    get_invoice_details), so the fan-out is deterministic server-side code."""
    import json as _json
    from denidin_mcp_morning import tools as _tools
    calls = {"get": 0}

    payload = _json.loads(_tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", output_format="json", include_full_details=True))

    assert calls["get"] == 1
    doc = payload["documents"][0]
    assert doc["payment"]["bank_number"] == "31"
    assert doc["linked_document"]["number"] == "52203"


def test_json_output_alone_never_fans_out():
    """The decisive separation (user catch, 2026-08-23): the fan-out is gated on
    include_full_details, NOT on the output format. Phase 9b makes JSON the
    format for every read tool - a format-based gate would make every ordinary
    list explode into N per-document GETs.

    Note this is about the DEFAULT, not a prohibition: a conversation that
    genuinely needs bank details or linked documents may pass
    include_full_details=True itself (see the test below). The only cost is
    latency, which is acceptable - it just should not happen unasked."""
    import json as _json
    from denidin_mcp_morning import tools as _tools
    calls = {"get": 0}

    payload = _json.loads(_tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", output_format="json"))   # default purpose

    assert calls["get"] == 0, "a conversational call must never fan out"
    assert payload["documents"][0]["display_number"] == "60443"


def test_text_output_alone_never_fans_out():
    from denidin_mcp_morning import tools as _tools
    calls = {"get": 0}

    text = _tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL), from_date="2026-08-20")

    assert calls["get"] == 0
    assert "60443" in text


def test_include_full_details_survives_a_failing_detail_fetch():
    """One unreachable document must not lose the whole sweep."""
    import json as _json
    from denidin_mcp_morning import tools as _tools

    class _Failing:
        def list_invoices(self, params=None):
            return {"total": 1, "page": 1, "pages": 1, "items": [_SEARCH_ITEM]}
        def get_invoice(self, invoice_id):
            raise RuntimeError("boom")

    payload = _json.loads(_tools.list_invoices(
        _Failing(), from_date="2026-08-20", output_format="json",
        include_full_details=True))

    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["display_number"] == "60443"


def test_a_conversation_may_opt_into_full_details_too():
    """User clarification (2026-08-23): fan-out is a capability available in ANY
    context, not something reserved for the ledger sweep. A conversational turn
    that needs bank details or linked documents ("which account was I paid
    into?") can ask for them - it is simply not the default."""
    import json as _json
    from denidin_mcp_morning import tools as _tools
    calls = {"get": 0}

    payload = _json.loads(_tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", output_format="json", include_full_details=True))

    assert calls["get"] == 1
    assert payload["documents"][0]["payment"]["bank_number"] == "31"


def test_full_details_works_in_text_mode_as_well():
    """The two parameters are independent: a prose-answering conversation can
    still opt into full details."""
    from denidin_mcp_morning import tools as _tools
    calls = {"get": 0}

    _tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", include_full_details=True)

    assert calls["get"] == 1
