"""Tests for feature 038's `list_invoices` fetch-loop and item-count cap
logic, updated for the 2026-09-04 JSON-only contract (Feature 069 US2
follow-up): `list_invoices` now always returns JSON
(`format_invoice_list_json`'s shape) - there is no more `output_format`
parameter, no more prose default, and no more token-budget truncation (a
reconciliation/automation consumer needs every match, so the JSON reply is
always the complete match set with `total_matched` stated explicitly).

Uses a fake MorningClient (dependency-injected, matching the real
`list_invoices` contract) - this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V), mirroring the established
pattern in test_tools_client_management.py.
"""
import json

import pytest

from denidin_mcp_morning import tools


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
    """A raw Morning /documents(/search) item, matching the real shape."""
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


def _numbers(payload) -> list:
    return [doc["display_number"] for doc in payload["documents"]]


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

    payload = json.loads(tools.list_invoices(client))

    assert len(client.list_invoices_calls) == 2
    assert client.list_invoices_calls[1]["page"] == 2
    assert set(_numbers(payload)) == {str(n) for n in range(1, 16)}


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

    payload = json.loads(tools.list_invoices(client))

    assert len(client.list_invoices_calls) == 1
    assert payload["status"] == "too_many"
    assert payload["total"] == 101
    assert payload["kind"] == "invoices"


def test_list_invoices_defaults_missing_page_and_pages_fields():
    """Missing page/pages in a response defaults to 1/1, matching
    list_clients' existing fallback (REQ-INVOICE-007) - the loop must
    terminate after page 1 rather than erroring."""
    items = [_raw_document(str(n)) for n in range(1, 6)]
    response = {"total": 5, "items": items}  # no "page"/"pages" keys at all
    client = _FakeMorningClient([response])

    payload = json.loads(tools.list_invoices(client))

    assert len(client.list_invoices_calls) == 1
    assert set(_numbers(payload)) == {str(n) for n in range(1, 6)}


def test_list_invoices_zero_matches_returns_empty_documents_list():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    payload = json.loads(tools.list_invoices(client))

    assert payload["total_matched"] == 0
    assert payload["documents"] == []


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

    payload = json.loads(tools.list_invoices(client, client_name="Cohen"))

    assert _numbers(payload) == ["1"]
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

    payload = json.loads(tools.list_invoices(client, document_display_number="51365"))

    assert _numbers(payload) == ["51365"]


def test_list_invoices_number_not_found_returns_empty_documents_list():
    client = _FakeMorningClient([_page_response([], total=0, page=1, pages=1)])

    payload = json.loads(tools.list_invoices(client, document_display_number="99999999"))

    assert payload["total_matched"] == 0
    assert payload["documents"] == []


# ============================================================================
# 2026-09-04 JSON-only contract: always JSON, never truncated
# ============================================================================


def test_list_invoices_always_returns_parseable_json():
    """No more output_format parameter, no more prose default - every call
    returns the same machine-readable shape."""
    client = _FakeMorningClient([_page_response([{
        "id": "abc", "number": "40406", "type": 300, "status": 1,
        "client": {"id": "c1", "name": "נאדר קרא"},
        "documentDate": "2026-08-20", "creationDate": 1787241168,
        "description": "תחזוקה", "amount": 51.92,
    }], total=1, page=1, pages=1)])

    payload = json.loads(tools.list_invoices(client, from_date="2026-08-20"))

    assert payload["total_matched"] == 1
    doc = payload["documents"][0]
    assert doc["display_number"] == "40406"
    assert doc["status_label"] == "מסמך סגור"
    assert doc["creation_date"].startswith("2026-08-20T18:52:48")


def test_list_invoices_is_never_truncated_regardless_of_result_size():
    """A reconciliation consumer needs EVERY match - the old prose path's
    token-budget truncation (which used to silently show 8 of 18 real
    documents) is gone entirely; every match is always present."""
    many = [{
        "id": f"id-{i}", "number": 40000 + i, "type": 300, "status": 1,
        "client": {"id": "c1", "name": "לקוח ארוך שם מאוד לצורך בדיקה"},
        "documentDate": "2026-08-20", "creationDate": 1787241168,
        "description": "תיאור ארוך מאוד כדי לצרוך תקציב טוקנים" * 5,
        "amount": 100.0,
    } for i in range(40)]
    client = _FakeMorningClient([_page_response(many, total=len(many), page=1, pages=1)])

    payload = json.loads(tools.list_invoices(client, from_date="2026-08-20"))

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
    calls = {"get": 0}

    payload = json.loads(tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", include_full_details=True))

    assert calls["get"] == 1
    doc = payload["documents"][0]
    assert doc["payment"]["bank_number"] == "31"
    assert doc["linked_document"]["number"] == "52203"


def test_default_call_never_fans_out():
    """The fan-out is gated on include_full_details alone (user catch,
    2026-08-23) - not the default, since most questions don't need it. The
    only cost of opting in is latency, which is acceptable when asked for."""
    calls = {"get": 0}

    payload = json.loads(tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL), from_date="2026-08-20"))

    assert calls["get"] == 0, "a conversational call must never fan out unasked"
    assert payload["documents"][0]["display_number"] == "60443"


def test_include_full_details_survives_a_failing_detail_fetch():
    """One unreachable document must not lose the whole sweep."""
    class _Failing:
        def list_invoices(self, params=None):
            return {"total": 1, "page": 1, "pages": 1, "items": [_SEARCH_ITEM]}
        def get_invoice(self, invoice_id):
            raise RuntimeError("boom")

    payload = json.loads(tools.list_invoices(
        _Failing(), from_date="2026-08-20", include_full_details=True))

    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["display_number"] == "60443"


def test_a_conversation_may_opt_into_full_details_too():
    """User clarification (2026-08-23): fan-out is a capability available in ANY
    context, not something reserved for the ledger sweep. A conversational turn
    that needs bank details or linked documents ("which account was I paid
    into?") can ask for them - it is simply not the default."""
    calls = {"get": 0}

    payload = json.loads(tools.list_invoices(
        _stub_client_factory(calls, _SEARCH_ITEM, _DETAIL),
        from_date="2026-08-20", include_full_details=True))

    assert calls["get"] == 1
    assert payload["documents"][0]["payment"]["bank_number"] == "31"
