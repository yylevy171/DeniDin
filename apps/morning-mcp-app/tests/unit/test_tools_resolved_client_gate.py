"""Tests for the shared exact-only resolution gate (client-name-resolution
architecture fix, bugfix-028 sub-piece): `_require_resolved_client`,
`_resolve_exact_client_name`.

This is the ONE gate all six client-name-consuming tools (get_client_details,
list_invoices, create_invoice, create_transaction_account,
create_combo_document, update_client) share once migrated (Phases 3-5) — a
model must have already called `resolve_client_name` and pass
`name_resolved=True` with the confirmed exact name; this gate never does
fuzzy/word-growth matching itself, only a direct exact (word-order-
independent) lookup.

Two-outcomes-only contract (2026-08-12 follow-up, user decision): every call
either returns a resolved `Client` or raises - `_require_resolved_client` no
longer has a third "ordinary refusal text" outcome (`ResolvedClient`/
`refusal_message` removed). `name_resolved` not `True` now raises
`ClientNameNotResolvedError`; the previously-covered zero/non-exact/multi-
match cases under `name_resolved=True` still raise `ClientNotFoundError`,
unchanged.

Uses a fake MorningClient (dependency-injected) — mocks a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
import pytest

from denidin_mcp_morning import tools


class _FakeMorningClient:
    def __init__(self, search_clients_response=None, search_clients_response_sequence=None):
        self._search_clients_response = search_clients_response or {"items": [], "total": 0}
        self._sequence = list(search_clients_response_sequence or [])
        self.search_clients_calls = []

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        if self._sequence:
            return self._sequence.pop(0)
        return self._search_clients_response


def _client_record(client_id="c-1", name="Test Client", phone="0527384938", tax_id="308253681"):
    return {
        "id": client_id,
        "name": name,
        "active": True,
        "taxId": tax_id,
        "phone": phone,
        "emails": [],
    }


# --- _resolve_exact_client_name ---


def test_resolve_exact_client_name_returns_the_client_on_an_exact_match():
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools._resolve_exact_client_name(client, "Test Client")

    assert result is not None
    assert result.id == "c-1"


def test_resolve_exact_client_name_returns_none_on_a_non_exact_match():
    """A partial/prefix match must NOT be accepted here - only Step 0's own
    word-order-independent exact check counts. Fuzzy discovery is
    resolve_client_name's job, not this gate's."""
    record = _client_record(client_id="c-1", name="Test Client International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools._resolve_exact_client_name(client, "Test Client")

    assert result is None


def test_resolve_exact_client_name_returns_none_on_zero_matches():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    result = tools._resolve_exact_client_name(client, "Nonexistent Client")

    assert result is None


def test_resolve_exact_client_name_resolves_apostrophe_query_against_geresh_stored_name():
    """The exact scenario that broke live (2026-08-07; relocated here
    2026-08-12 from test_tools_client_management.py, since
    `_resolve_client_for_document_creation` was deleted): a document-
    creation call retypes the seeded client's name with a different
    apostrophe/geresh variant than what's actually stored - must still
    resolve as exact, not refuse."""
    apostrophe_name = "סידורוביץ'"  # ASCII apostrophe (U+0027)
    geresh_name = "סידורוביץ׳"  # correct Hebrew geresh (U+05F3)
    record = _client_record(client_id="c-1", name=geresh_name)
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools._resolve_exact_client_name(client, apostrophe_name)

    assert result is not None
    assert result.id == "c-1"


# --- _require_resolved_client ---


def test_require_resolved_client_refuses_immediately_when_name_resolved_is_false():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools._require_resolved_client(client, "Any Client", False, "get_client_details")

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []  # zero Morning calls attempted


def test_require_resolved_client_refuses_immediately_when_name_resolved_is_omitted_default():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError):
        tools._require_resolved_client(client, "Any Client", False, "update_client")

    assert client.search_clients_calls == []


def test_require_resolved_client_resolves_when_true_and_exact():
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools._require_resolved_client(client, "Test Client", True, "create_invoice")

    assert result is not None
    assert result.id == "c-1"


def test_require_resolved_client_raises_not_found_when_true_and_non_exact_only():
    """A non-exact-only match collapses to ClientNotFoundError under
    exact-only mode - the model was supposed to have already confirmed the
    exact name via resolve_client_name; passing a still-fuzzy name with
    name_resolved=True is itself a contract violation, not a normal
    disambiguation moment."""
    record = _client_record(client_id="c-1", name="Test Client International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(tools.ClientNotFoundError):
        tools._require_resolved_client(client, "Test Client", True, "create_invoice")


def test_require_resolved_client_raises_not_found_when_true_and_zero_matches():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNotFoundError):
        tools._require_resolved_client(client, "Nonexistent Client", True, "create_invoice")


def test_require_resolved_client_raises_not_found_when_true_and_multiple_matches():
    """Multi-candidate ALSO collapses to ClientNotFoundError under
    exact-only mode - same reasoning as the non-exact-only case above."""
    record_a = _client_record(client_id="c-1", name="Test Client A")
    record_b = _client_record(client_id="c-2", name="Test Client B")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    with pytest.raises(tools.ClientNotFoundError):
        tools._require_resolved_client(client, "Test Client", True, "create_invoice")
