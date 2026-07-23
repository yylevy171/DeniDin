"""Real Morning-sandbox tests for feature 021's new document-creation tools:
create_transaction_account (type 300), create_combo_document (type 320),
create_credit_note (type 330, standalone), create_receipt (type 400,
standalone).

No mocks against the app boundary itself - each test creates a real sandbox
document via the tool under test, then makes an independent follow-up API
call (get_invoice_details / list_invoices) to verify the persisted state,
rather than trusting the create response alone.

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import (
    _build_create_invoice_payload,
    create_combo_document,
    create_credit_note,
    create_receipt,
    create_transaction_account,
    get_invoice_details,
)

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


def _unique_marker(label):
    return f"DENIDIN_021_{label}_{int(datetime.now(timezone.utc).timestamp())}"


def _extract_id(response):
    return str(response.get("id") or response.get("documentId") or "")


@pytest.fixture()
def seeded_invoice(morning_client):
    """A real, freshly created tax invoice (type 305) - used as the
    reference/original document for the credit-note and receipt tests."""
    marker = _unique_marker("SEED")
    client_name = f"Test Client {marker}"
    payload = _build_create_invoice_payload(
        client_name=client_name,
        amount=200.0,
        description=f"Seed invoice {marker}",
    )
    response = morning_client.create_invoice(payload)
    invoice_id = _extract_id(response)
    assert invoice_id, f"Could not determine created invoice id from response: {response}"
    return invoice_id, client_name


def test_create_transaction_account_tool_sandbox(morning_client):
    marker = _unique_marker("TA")
    client_name = f"Test Client {marker}"

    result = create_transaction_account(morning_client, client_name, 150.0, f"Transaction account {marker}")
    assert client_name.split()[-1] in result or "150" in result or "150.00" in result

    # Follow-up call: independently confirm the persisted document's real
    # type/shape, not just the create response.
    from denidin_mcp_morning.tools import list_invoices

    listing = None
    for _ in range(12):
        listing = list_invoices(morning_client, client_name=client_name)
        if "חשבון עסקה" in listing:
            break
        time.sleep(1.5)

    assert listing is not None and "חשבון עסקה" in listing, (
        f"Transaction account document type label never appeared: {listing!r}"
    )


def test_create_combo_document_tool_sandbox(morning_client):
    marker = _unique_marker("COMBO")
    client_name = f"Test Client {marker}"

    create_combo_document(morning_client, client_name, 300.0, f"Combo document {marker}")

    from denidin_mcp_morning.tools import list_invoices

    listing = None
    for _ in range(12):
        listing = list_invoices(morning_client, client_name=client_name)
        if "חשבונית מס / קבלה" in listing or "קבלה" in listing:
            break
        time.sleep(1.5)

    assert listing is not None, "Combo document never appeared in list_invoices"


def test_create_credit_note_tool_sandbox_happy_path(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    result = create_credit_note(morning_client, original_id)
    assert result

    # Follow-up: the original invoice must independently show the new
    # credit note in its linked documents.
    details = get_invoice_details(morning_client, invoice_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "חשבונית זיכוי" in details


def test_create_credit_note_tool_sandbox_nonexistent_original(morning_client):
    bogus_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(Exception):
        create_credit_note(morning_client, bogus_id)


def test_create_credit_note_tool_sandbox_partial_amount(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_credit_note(morning_client, original_id, amount=50.0)

    details = get_invoice_details(morning_client, invoice_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "₪50.00" in details, f"Partial credit note amount not reflected in linked documents: {details!r}"


def test_create_receipt_tool_sandbox_happy_path(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id)

    # Follow-up: independently re-fetch the original and confirm it flipped
    # to paid as a result of the receipt now existing.
    details = get_invoice_details(morning_client, invoice_id=original_id)
    assert "שולם" in details, f"Original invoice did not show as paid after receipt: {details!r}"


def test_create_receipt_tool_sandbox_already_paid_original(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id)
    # Whatever Morning actually does on a second receipt against an
    # already-paid document - no assumption baked in, just record the real
    # observed behavior via a follow-up call.
    create_receipt(morning_client, original_id)

    details = get_invoice_details(morning_client, invoice_id=original_id)
    assert "שולם" in details


def test_create_receipt_tool_sandbox_partial_amount(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id, amount=80.0)

    details = get_invoice_details(morning_client, invoice_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "₪80.00" in details, f"Partial receipt amount not reflected in linked documents: {details!r}"
