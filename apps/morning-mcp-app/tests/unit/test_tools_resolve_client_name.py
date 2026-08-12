"""Tests for `resolve_client_name` — client-name-resolution architecture fix
(scoped sub-piece of bugfix-028, see
specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster/
client-name-resolution-*.md).

THE canonical, sole entry point for fuzzy/word-growth client-name resolution
(built on `resolve_client_by_name`, bugfix-039) — the model calls this first,
before any other tool that needs one specific client, then passes the
confirmed exact name back into the target tool together with
`name_resolved=True`.

Uses a fake MorningClient (dependency-injected, matching the real
search_clients contract) — this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V), mirroring
test_tools_client_resolution.py's existing fake.
"""
import pytest

from denidin_mcp_morning import tools


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary. Mirrors test_tools_client_resolution.py's
    fake exactly."""

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
    """A raw Morning /clients/search item (same shape used across this
    test suite)."""
    return {
        "id": client_id,
        "name": name,
        "active": True,
        "taxId": tax_id,
        "phone": phone,
        "emails": [],
    }


def test_resolve_client_name_exact_match_returns_the_stored_name_quoted():
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.resolve_client_name(client, "Test Client")

    assert '"Test Client"' in result
    assert "כן" not in result and "לא" not in result  # not a confirmation question


def test_resolve_client_name_never_mentions_client_id():
    """REQ-CLIENT-018 (feature 026): the internal Morning client_id must
    never reach the model, regardless of which of resolve_client_name's four
    outcomes fires."""
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.resolve_client_name(client, "Test Client")

    assert "c-1" not in result


def test_resolve_client_name_non_exact_single_match_asks_for_confirmation():
    record = _client_record(client_id="c-1", name="Test Client International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.resolve_client_name(client, "Test Client")

    assert "Test Client International" in result
    assert "כן" in result and "לא" in result


def test_resolve_client_name_ambiguous_lists_candidates():
    record_a = _client_record(client_id="c-1", name="Test Client A")
    record_b = _client_record(client_id="c-2", name="Test Client B")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    result = tools.resolve_client_name(client, "Test Client")

    assert "Test Client A" in result
    assert "Test Client B" in result


def test_resolve_client_name_zero_matches_returns_a_string_never_raises():
    """Unlike the six tools that consume a resolved name, resolve_client_name
    itself is the EXPLORATORY first call - a genuine zero-match here is an
    ordinary, expected outcome of exploring a name, not a failed
    mutation/lookup attempt. Must never raise ClientNotFoundError."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    result = tools.resolve_client_name(client, "Nonexistent Client")

    assert isinstance(result, str)
    assert "לא נמצא" in result


def test_resolve_client_name_is_read_only_never_mutates():
    """No create/update call should ever be attempted by this tool - it only
    ever calls search_clients, regardless of outcome."""
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    tools.resolve_client_name(client, "Test Client")

    assert not hasattr(client, "update_client_calls")
    assert not hasattr(client, "create_invoice_calls")
