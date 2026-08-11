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
from denidin_mcp_morning import tools


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary. Mirrors test_tools_client_management.py's
    fake exactly (only the parts this feature's helpers need)."""

    def __init__(self, search_clients_response=None):
        self._search_clients_response = search_clients_response or {"items": [], "total": 0}
        self.search_clients_calls = []

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
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


def test_resolve_client_for_document_creation_zero_matches_returns_refusal():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    resolution = tools._resolve_client_for_document_creation(client, "Nonexistent Client")

    assert resolution.client_id is None
    assert resolution.refusal_message is not None
    assert "לא נמצא" in resolution.refusal_message or "אין" in resolution.refusal_message
    # bugfix-039 (expanded 2026-08-11): a multi-word query with zero direct
    # matches now also tries the per-word/truncation fallback
    # (_resolve_client_by_name_words) before giving up - more than the one
    # original whole-string call, but the first is still that exact call.
    assert client.search_clients_calls[0] == {"name": "Nonexistent Client"}


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
