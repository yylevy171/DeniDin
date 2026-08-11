"""Tests for feature 027 (mandatory client reference for document creation):

- `_resolve_client_for_document_creation` — the shared Group A helper used by
  create_invoice/create_transaction_account/create_combo_document to resolve
  a free-text client_name to a real client_id (or a refusal message),
  wrapping Feature 026's `_resolve_client_by_name`/`_is_exact_name_match`.
- `_extract_linked_client_id` — the shared Group B helper used by
  create_credit_note/create_receipt/close_transaction_account to read a
  real client_id off an already-fetched original document, if present.

Uses a fake MorningClient (dependency-injected, matching the real
search_clients contract) — this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V).
"""
import pytest

from denidin_mcp_morning import tools


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary. Mirrors test_tools_client_management.py's
    fake exactly (only the parts this feature's helpers need).

    `search_clients_response_sequence` returns a different response per call,
    for tests that need to distinguish successive search_clients calls."""

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
    """A raw Morning /clients/search item (same shape as
    test_tools_client_management.py's helper of the same name)."""
    return {
        "id": client_id,
        "name": name,
        "active": True,
        "taxId": tax_id,
        "phone": phone,
        "emails": [],
    }


# --- _resolve_client_for_document_creation (REQ-INV-001/002/003/005/011) ---


def test_resolve_client_for_document_creation_zero_matches_raises():
    """bugfix-028 B4(c) - CHANGED 2026-08-09. This previously asserted a friendly
    refusal message was RETURNED. That is precisely the defect: returned as
    ordinary output with error=None, "client not found" was indistinguishable
    from success at every layer above, and one ₪40,000 document was approved
    eight times, created zero times, with the user never told why.

    A tool asked to create a document that creates none has failed, and must say
    so in the only way the layers above can see. Resolution itself is delegated
    to bugfix-039's `resolve_client_by_name` (round 3, 2026-08-11) - the old
    B4(a) `(ח.פ …)`-decoration-stripping retry is retired, superseded by that
    algorithm's general word-by-word/letter-by-letter matching (reconciled
    2026-08-12: only the raise-on-zero-candidates behavior survives from B4(c),
    see ClientNotFoundError's docstring).
    """
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNotFoundError) as exc_info:
        tools._resolve_client_for_document_creation(client, "Nonexistent Client")

    assert "לא נמצא" in str(exc_info.value)
    assert client.search_clients_calls == [{"name": "Nonexistent Client"}]


def test_resolve_client_for_document_creation_exact_match_resolves():
    record = _client_record(client_id="c-1", name="Test Client")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    resolution = tools._resolve_client_for_document_creation(client, "Test Client")

    assert resolution.client_id == "c-1"
    assert resolution.refusal_message is None


def test_resolve_client_for_document_creation_non_exact_match_asks_for_confirmation():
    """bugfix-039 (expanded 2026-08-11): a non-exact single match must never
    proceed to create a document - it refuses with a closed yes/no
    confirmation question naming the real matched client instead, same as
    the ambiguous/not-found cases. No document should be created on this
    call; the caller must re-invoke with the confirmed exact name."""
    record = _client_record(client_id="c-1", name="Test Client International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    resolution = tools._resolve_client_for_document_creation(client, "Test Client")

    assert resolution.client_id is None
    assert resolution.refusal_message is not None
    assert "Test Client International" in resolution.refusal_message
    assert "כן" in resolution.refusal_message and "לא" in resolution.refusal_message


def test_resolve_client_for_document_creation_multiple_matches_returns_refusal_with_candidates():
    record_a = _client_record(client_id="c-1", name="Test Client A")
    record_b = _client_record(client_id="c-2", name="Test Client B")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    resolution = tools._resolve_client_for_document_creation(client, "Test Client")

    assert resolution.client_id is None
    assert resolution.refusal_message is not None
    assert "Test Client A" in resolution.refusal_message
    assert "Test Client B" in resolution.refusal_message


# --- _extract_linked_client_id (REQ-INV-012/013) ---


def test_extract_linked_client_id_present():
    original = {"id": "doc-1", "client": {"id": "c-1", "name": "Test Client"}}

    assert tools._extract_linked_client_id(original) == "c-1"


def test_extract_linked_client_id_absent_when_client_has_no_id():
    original = {"id": "doc-1", "client": {"name": "Test Client"}}

    assert tools._extract_linked_client_id(original) is None


def test_extract_linked_client_id_absent_when_no_client_key_at_all():
    original = {"id": "doc-1"}

    assert tools._extract_linked_client_id(original) is None
