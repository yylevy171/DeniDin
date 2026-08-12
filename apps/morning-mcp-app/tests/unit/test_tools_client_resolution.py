"""Tests for feature 027's `_extract_linked_client_id` — the shared Group B
helper used by create_credit_note/create_receipt/close_transaction_account
to read a real client_id off an already-fetched original document, if
present.

(This file used to also cover `_resolve_client_for_document_creation`,
feature 027's Group A resolution helper - that function was deleted as part
of the client-name-resolution architecture fix, 2026-08-12, superseded by
`_require_resolved_client`/`resolve_client_name`. Its coverage now lives in
test_tools_resolved_client_gate.py (the exact-only gate) and
test_tools_resolve_client_name.py (the fuzzy/disambiguation tool).)

Uses a fake MorningClient (dependency-injected, matching the real
search_clients contract) — this mocks a third-party API boundary, not an
internal component (CONSTITUTION.md §I/§V).
"""
from denidin_mcp_morning import tools


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
