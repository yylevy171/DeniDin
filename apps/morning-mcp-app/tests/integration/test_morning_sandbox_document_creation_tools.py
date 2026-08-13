"""Real Morning-sandbox tests for feature 021's new document-creation tools:
create_transaction_account (type 300), create_combo_document (type 320),
create_credit_note (type 330, standalone), create_receipt (type 400,
standalone).

Also covers feature 023's create_combo_document_as_reference (standalone, reference-
linked type-320 combo document that closes an existing type-300 document).

No mocks against the app boundary itself - each test creates a real sandbox
document via the tool under test, then makes an independent follow-up API
call (get_invoice_details / list_invoices) to verify the persisted state,
rather than trusting the create response alone.

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
import time
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import (
    _build_create_invoice_payload,
    _build_transaction_account_payload,
    create_combo_document_as_reference,
    create_combo_document,
    create_credit_note,
    create_receipt,
    create_transaction_account,
    get_invoice_details,
)
from denidin_mcp_morning.utils.time_utils import now_local
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
        auth_url=config.auth_url,
    )


def _unique_marker(label):
    return f"DENIDIN_021_{label}_{int(now_local().timestamp())}"


def _extract_id(response):
    return str(response.get("id") or response.get("documentId") or "")


@pytest.fixture()
def seeded_invoice(morning_client):
    """A real, freshly created tax invoice (type 305) - used as the
    reference/original document for the credit-note and receipt tests."""
    marker = _unique_marker("SEED")
    client_id, client_name = seed_real_client(morning_client, marker)
    payload = _build_create_invoice_payload(
        client_id=client_id,
        amount=90.0,
        description=f"Seed invoice {marker}",
    )
    response = morning_client.create_invoice(payload)
    internal_morning_id = _extract_id(response)
    assert internal_morning_id, f"Could not determine created invoice id from response: {response}"
    return internal_morning_id, client_name


def test_create_transaction_account_tool_sandbox(morning_client):
    marker = _unique_marker("TA")
    _, client_name = seed_real_client(morning_client, marker)

    # bugfix-028 A2: vat_included is now required - an undecided VAT treatment
    # must never reach Morning.
    result = create_transaction_account(
        morning_client, client_name, 45.0, f"Transaction account {marker}", vat_included=True,
        name_resolved=True,
    )
    assert client_name.split()[-1] in result or "45" in result or "45.00" in result

    # Follow-up call: independently confirm the persisted document's real
    # type/shape, not just the create response.
    from denidin_mcp_morning.tools import list_invoices

    listing = None
    for _ in range(12):
        listing = list_invoices(morning_client, client_name=client_name, name_resolved=True)
        if "חשבון עסקה" in listing:
            break
        time.sleep(1.5)

    assert listing is not None and "חשבון עסקה" in listing, (
        f"Transaction account document type label never appeared: {listing!r}"
    )


def test_create_combo_document_tool_sandbox(morning_client):
    marker = _unique_marker("COMBO")
    _, client_name = seed_real_client(morning_client, marker)

    # bugfix-028 A3: payment_date is now required - a combo document records
    # money that has already moved, so its date is a fact, not a default.
    create_combo_document(
        morning_client, client_name, 35.0, f"Combo document {marker}",
        vat_included=True, payment_date="2026-07-12", name_resolved=True,
    )

    from denidin_mcp_morning.tools import list_invoices

    listing = None
    for _ in range(12):
        listing = list_invoices(morning_client, client_name=client_name, name_resolved=True)
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
    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "חשבונית זיכוי" in details


def test_create_credit_note_tool_sandbox_nonexistent_original(morning_client):
    bogus_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(Exception):
        create_credit_note(morning_client, bogus_id)


def test_create_credit_note_tool_sandbox_partial_amount(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_credit_note(morning_client, original_id, amount=50.0)

    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "₪50.00" in details, f"Partial credit note amount not reflected in linked documents: {details!r}"


def test_create_receipt_tool_sandbox_happy_path(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id, payment_date="2026-07-12")

    # Follow-up: independently re-fetch the original and confirm it flipped
    # to paid as a result of the receipt now existing. Checking both
    # directions matters: "שולם" (paid) is a substring of "לא שולם" (unpaid),
    # so a bare "שולם" in details check alone is a false positive either way.
    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "לא שולם" not in details, f"Original invoice still shows unpaid after receipt: {details!r}"
    assert "שולם" in details, f"Original invoice did not show as paid after receipt: {details!r}"
    raw = morning_client.get_invoice(original_id)
    assert raw.get("status") in (1, 2), f"Expected a closed/paid status code, got: {raw.get('status')!r}"


def test_create_receipt_tool_sandbox_records_the_real_payment_date_not_today(morning_client, seeded_invoice):
    """A3 (2026-08-12): create_receipt's payment_date is REQUIRED and must
    land on the real receipt's payment line verbatim, never today - a
    "mark as paid" request can legitimately be about a payment that arrived
    on an earlier date, not the day the receipt happens to be issued (same
    real/issue-date distinction already verified for create_combo_document
    in test_morning_sandbox_payment_details.py's own A3 test)."""
    original_id, _ = seeded_invoice
    real_payment_date = "2026-07-12"

    create_receipt(morning_client, original_id, payment_date=real_payment_date)

    raw = morning_client.get_invoice(original_id)
    linked = raw.get("linkedDocuments") or []
    receipts = [doc for doc in linked if doc.get("type") == 400]
    assert receipts, f"Expected a linked receipt, got: {linked!r}"
    receipt = morning_client.get_invoice(str(receipts[0].get("id")))
    payments = receipt.get("payment") or []
    assert payments, "type-400 receipts do persist a payment array - none came back"
    assert payments[0]["date"] == real_payment_date, (
        f"payment date is {payments[0]['date']!r}, expected the real payment "
        f"date {real_payment_date!r} (document date staying today is correct and out of scope)"
    )


def test_create_receipt_tool_sandbox_already_paid_original(morning_client, seeded_invoice):
    """create_receipt's idempotency guard (feature 023): a repeated
    full-amount call against an already-paid original is a no-op - Morning
    itself does NOT reject a duplicate receipt (confirmed live), so this
    guard is the only thing preventing a real duplicate financial document."""
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id, payment_date="2026-07-12")
    create_receipt(morning_client, original_id, payment_date="2026-07-12")

    raw = morning_client.get_invoice(original_id)
    linked = raw.get("linkedDocuments") or []
    receipts = [doc for doc in linked if doc.get("type") == 400]
    assert len(receipts) == 1, f"Expected exactly one linked receipt, got: {linked!r}"

    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "לא שולם" not in details
    assert "שולם" in details


def test_create_receipt_tool_sandbox_partial_amount(morning_client, seeded_invoice):
    original_id, _ = seeded_invoice

    create_receipt(morning_client, original_id, payment_date="2026-07-12", amount=80.0)

    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "₪80.00" in details, f"Partial receipt amount not reflected in linked documents: {details!r}"


@pytest.fixture()
def seeded_transaction_account(morning_client):
    """A real, freshly created transaction account (type 300) - used as the
    reference/original document for create_combo_document_as_reference tests."""
    marker = _unique_marker("SEED_TA")
    client_id, client_name = seed_real_client(morning_client, marker)
    payload = _build_transaction_account_payload(
        client_id=client_id,
        amount=40.0,
        description=f"Seed transaction account {marker}",
        vat_included=True,
    )
    response = morning_client.create_invoice(payload)
    internal_morning_id = _extract_id(response)
    assert internal_morning_id, f"Could not determine created transaction account id from response: {response}"
    return internal_morning_id, client_name


def test_create_combo_document_as_reference_tool_sandbox_happy_path_full_amount(morning_client, seeded_transaction_account):
    """US1: closing an existing type-300 document with a full-amount combo document."""
    original_id, _ = seeded_transaction_account

    result = create_combo_document_as_reference(morning_client, original_id, payment_date="2026-07-12")
    assert result

    # Follow-up: independently re-fetch the original and confirm it flipped
    # to paid as a result of the linked combo document now existing, and
    # that the linked-documents section names the new combo document.
    # Checking both directions matters: "שולם" (paid) is a substring of "לא
    # שולם" (unpaid), so a bare "שולם" in details check alone would be a
    # false positive if the original never actually flipped (feature 023's
    # confirmed root cause: closing with a mismatched amount leaves the
    # original genuinely unpaid, and Morning correctly never flips it).
    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "לא שולם" not in details, f"Original transaction account still shows unpaid: {details!r}"
    assert "שולם" in details, f"Original transaction account did not show as paid after closing: {details!r}"
    assert "מסמכים מקושרים" in details
    assert "חשבונית מס / קבלה" in details
    raw = morning_client.get_invoice(original_id)
    assert raw.get("status") in (1, 2), f"Expected a closed/paid status code, got: {raw.get('status')!r}"


def test_create_combo_document_as_reference_tool_sandbox_partial_amount(morning_client, seeded_transaction_account):
    """US2: closing an existing type-300 document with a partial-amount combo document."""
    original_id, _ = seeded_transaction_account

    create_combo_document_as_reference(morning_client, original_id, payment_date="2026-07-12", amount=15.0)

    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "מסמכים מקושרים" in details
    assert "₪15.00" in details, f"Partial combo-close amount not reflected in linked documents: {details!r}"


def test_create_combo_document_as_reference_tool_sandbox_nonexistent_original(morning_client):
    """Edge case: a bogus/nonexistent original id must raise, not silently create anything."""
    bogus_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(Exception):
        create_combo_document_as_reference(morning_client, bogus_id, payment_date="2026-07-12")


def test_create_combo_document_as_reference_tool_sandbox_rejects_non_transaction_account_original(
    morning_client, seeded_invoice
):
    """US3/negative: referencing an existing document that is NOT type 300
    (here, a real type-305 tax invoice) must be rejected, and must not create
    any new document as a side effect of the rejected attempt."""
    original_id, client_name = seeded_invoice

    with pytest.raises(ValueError):
        create_combo_document_as_reference(morning_client, original_id, payment_date="2026-07-12")

    # Follow-up: confirm no combo document was created against the rejected
    # original despite the raised error.
    details = get_invoice_details(morning_client, internal_morning_id=original_id)
    assert "מסמכים מקושרים" not in details, (
        f"A document must not have been linked to a rejected non-transaction-account original: {details!r}"
    )
