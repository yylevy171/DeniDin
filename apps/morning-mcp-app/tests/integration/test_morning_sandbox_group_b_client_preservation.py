"""Real Morning-sandbox tests for feature 027's Group B client-id
preservation/refusal (create_credit_note, create_receipt,
create_combo_document_as_reference - REQ-INV-012/013).

No mocks: seeds a real original document (with or without a real client.id
attached, per test), drives the Group B tool under test against the live
sandbox, and independently verifies the outcome via a direct
MorningClient.get_invoice call on both documents (REQ-INV-009's standard,
applied to Group B) rather than trusting the tool's own reply text.

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.formatters import format_original_not_linked_to_client
from denidin_mcp_morning.tools import (
    _build_create_invoice_payload,
    _build_transaction_account_payload,
    create_combo_document_as_reference,
    create_credit_note,
    create_receipt,
)
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
    )


def _extract_id(response):
    return str(response.get("id") or response.get("documentId") or "")


def _seed_invoice_with_real_client(morning_client, marker):
    """A real type-305 original, attached to a real client (the 'preserve' shape)."""
    client_id, _ = seed_real_client(morning_client, marker)
    payload = _build_create_invoice_payload(client_id=client_id, amount=70.0, description=marker)
    response = morning_client.create_invoice(payload)
    return _extract_id(response), client_id


def _seed_invoice_with_bare_name_client(morning_client, marker):
    """A real type-305 original, attached only by bare name - simulating a
    document created BEFORE feature 027 shipped (the 'refuse' shape).
    Deliberately bypasses every tool this feature ships (none of them can
    produce this shape anymore) - a raw payload via MorningClient directly."""
    today = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "type": 305,
        "date": today,
        "lang": "he",
        "vatType": 1,
        "currency": "ILS",
        "rounding": False,
        "signed": False,
        "description": marker,
        "client": {"self": False, "name": f"Test Client {marker}"},
        "income": [
            {
                "catalogNum": "",
                "description": marker,
                "quantity": 1,
                "price": 70.0,
                "currency": "ILS",
                "currencyRate": 1,
                "vatRate": 0,
                "vatType": 1,
            }
        ],
        "payment": [{"type": 1, "price": 70.0, "date": today}],
    }
    response = morning_client.create_invoice(payload)
    return _extract_id(response)


def _seed_transaction_account_with_real_client(morning_client, marker):
    client_id, _ = seed_real_client(morning_client, marker)
    payload = _build_transaction_account_payload(
        client_id=client_id, amount=40.0, description=marker, vat_included=True
    )
    response = morning_client.create_invoice(payload)
    return _extract_id(response), client_id


def _seed_transaction_account_with_bare_name_client(morning_client, marker):
    today = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "type": 300,
        "date": today,
        "lang": "he",
        "currency": "ILS",
        "rounding": False,
        "signed": False,
        "description": marker,
        "client": {"self": False, "name": f"Test Client {marker}"},
        "income": [
            {
                "catalogNum": "",
                "description": marker,
                "quantity": 1,
                "price": 40.0,
                "currency": "ILS",
                "currencyRate": 1,
            }
        ],
        "payment": [{"type": 1, "price": 40.0, "date": today}],
    }
    response = morning_client.create_invoice(payload)
    return _extract_id(response)


# --- create_credit_note ---


def test_create_credit_note_preserves_real_client_id(morning_client):
    marker = f"DENIDIN_027_GROUPB_CREDIT_PRESERVE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id, client_id = _seed_invoice_with_real_client(morning_client, marker)

    result = create_credit_note(morning_client, original_id)

    assert result != format_original_not_linked_to_client()
    # Resolve the new credit note's id via the original's own linked-documents view.
    original_after = morning_client.get_invoice(original_id)
    linked = original_after.get("linkedDocuments") or []
    assert linked, f"Expected a linked credit note, got: {original_after!r}"
    credit_note = morning_client.get_invoice(str(linked[0]["id"]))
    assert credit_note.get("client", {}).get("id") == client_id


def test_create_credit_note_refuses_when_original_has_no_real_client(morning_client):
    marker = f"DENIDIN_027_GROUPB_CREDIT_REFUSE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id = _seed_invoice_with_bare_name_client(morning_client, marker)

    result = create_credit_note(morning_client, original_id)

    assert result == format_original_not_linked_to_client()
    original_after = morning_client.get_invoice(original_id)
    assert not (original_after.get("linkedDocuments") or []), "must not have created a linked credit note"


# --- create_receipt ---


def test_create_receipt_preserves_real_client_id(morning_client):
    marker = f"DENIDIN_027_GROUPB_RECEIPT_PRESERVE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id, client_id = _seed_invoice_with_real_client(morning_client, marker)

    result = create_receipt(morning_client, original_id, payment_date="2026-07-12")

    assert result != format_original_not_linked_to_client()
    original_after = morning_client.get_invoice(original_id)
    linked = original_after.get("linkedDocuments") or []
    assert linked, f"Expected a linked receipt, got: {original_after!r}"
    receipt = morning_client.get_invoice(str(linked[0]["id"]))
    assert receipt.get("client", {}).get("id") == client_id


def test_create_receipt_refuses_when_original_has_no_real_client(morning_client):
    marker = f"DENIDIN_027_GROUPB_RECEIPT_REFUSE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id = _seed_invoice_with_bare_name_client(morning_client, marker)

    result = create_receipt(morning_client, original_id, payment_date="2026-07-12")

    assert result == format_original_not_linked_to_client()
    original_after = morning_client.get_invoice(original_id)
    assert not (original_after.get("linkedDocuments") or []), "must not have created a linked receipt"


# --- create_combo_document_as_reference ---


def test_create_combo_document_as_reference_preserves_real_client_id(morning_client):
    marker = f"DENIDIN_027_GROUPB_CLOSE_PRESERVE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id, client_id = _seed_transaction_account_with_real_client(morning_client, marker)

    result = create_combo_document_as_reference(morning_client, original_id, payment_date="2026-07-12")

    assert result != format_original_not_linked_to_client()
    original_after = morning_client.get_invoice(original_id)
    linked = original_after.get("linkedDocuments") or []
    assert linked, f"Expected a linked closing document, got: {original_after!r}"
    closing_doc = morning_client.get_invoice(str(linked[0]["id"]))
    assert closing_doc.get("client", {}).get("id") == client_id


def test_create_combo_document_as_reference_refuses_when_original_has_no_real_client(morning_client):
    marker = f"DENIDIN_027_GROUPB_CLOSE_REFUSE_{int(datetime.now(timezone.utc).timestamp())}"
    original_id = _seed_transaction_account_with_bare_name_client(morning_client, marker)

    result = create_combo_document_as_reference(morning_client, original_id, payment_date="2026-07-12")

    assert result == format_original_not_linked_to_client()
    original_after = morning_client.get_invoice(original_id)
    assert not (original_after.get("linkedDocuments") or []), "must not have created a linked closing document"
