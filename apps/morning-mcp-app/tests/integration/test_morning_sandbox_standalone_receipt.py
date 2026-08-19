"""Real Morning-sandbox test for create_receipt's standalone branch (feature
056): a receipt for money that isn't business income and has no prior
invoice behind it at all - a deposit, a loan repayment, or an advance
payment ahead of a not-yet-completed transaction.

No mocks: seeds a real client, calls the real create_receipt function with
no original_internal_morning_id, and drives the real Morning sandbox. Per
CONSTITUTION §V - real system, real external service, no unittest.mock.

The EXISTING linked-original create_receipt flow (payment against a real
type-305 invoice) is intentionally NOT re-tested here - it's already fully
covered by test_morning_sandbox_invoice_status_tools.py, and REQ-INV-016's
regression guarantee (unchanged byte-for-byte) is proven by that file
continuing to pass unchanged, not by duplicating it in this one.
"""
import time
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import ClientNotFoundError, _resolve_client_by_name, create_invoice, create_receipt
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


def _poll_for_document_type(morning_client, client_id, doc_type, attempts=12, delay=1.5):
    """Poll list_invoices({"clientId": ...}) until a document of `doc_type`
    shows up for this client, tolerating the sandbox's real search-index
    propagation lag right after a write (research.md Finding 4 - the same
    characteristic documented for client search, confirmed here to apply to
    document search too)."""
    for _ in range(attempts):
        docs = morning_client.list_invoices({"clientId": client_id})
        items = docs.get("items", docs) if isinstance(docs, dict) else docs
        matches = [d for d in items if d.get("type") == doc_type]
        if matches:
            return matches
        time.sleep(delay)
    return []


def test_standalone_receipt_happy_path_creates_no_invoice(morning_client):
    """(1) A standalone receipt is a real type-400 document with no
    linkedDocumentIds and no income/VAT line at all - REQ-INV-014/015/017."""
    marker = f"DENIDIN_056_STANDALONE_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)

    result = create_receipt(
        morning_client,
        client_name=client_name,
        amount=250.0,
        description=f"פיקדון - {marker}",
        payment_date="2026-08-01",
        name_resolved=True,
    )
    assert result

    resolved_client, _ = _resolve_client_by_name(morning_client, client_name)
    assert resolved_client is not None, f"Seeded client {client_name!r} unexpectedly not found"

    receipts = _poll_for_document_type(morning_client, resolved_client.id, 400)
    assert len(receipts) == 1, f"Expected exactly one type-400 receipt for {client_name!r}"

    doc = morning_client.get_invoice(receipts[0]["id"])
    assert doc.get("type") == 400
    assert not doc.get("linkedDocuments"), f"Standalone receipt must have no linked documents: {doc!r}"
    assert "income" not in doc or not doc.get("income"), f"Standalone receipt must carry no income line: {doc!r}"


def test_standalone_receipt_does_not_require_a_later_invoice_to_link_back(morning_client):
    """(2) An advance-payment standalone receipt and the real invoice issued
    later for the same completed transaction are fully independent documents
    - REQ-INV-019 (Clarification Q3)."""
    marker = f"DENIDIN_056_ADVANCE_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)

    receipt_result = create_receipt(
        morning_client,
        client_name=client_name,
        amount=100.0,
        description=f"מקדמה על עבודה עתידית - {marker}",
        payment_date="2026-08-01",
        name_resolved=True,
    )
    assert receipt_result

    invoice_result = create_invoice(
        morning_client,
        client_name,
        100.0,
        f"עבודה שהושלמה - {marker}",
        name_resolved=True,
    )
    assert "חשבונית" in invoice_result and "מזהה פנימי" in invoice_result

    resolved_client, _ = _resolve_client_by_name(morning_client, client_name)
    invoice_docs = _poll_for_document_type(morning_client, resolved_client.id, 305)
    assert len(invoice_docs) == 1, f"Expected exactly one type-305 invoice for {client_name!r}"

    full_invoice = morning_client.get_invoice(invoice_docs[0]["id"])
    assert not full_invoice.get("linkedDocuments"), (
        f"The later invoice must not reference the earlier standalone receipt: {full_invoice!r}"
    )


def test_standalone_receipt_refuses_for_an_unresolved_client(morning_client):
    """(3) A client name that doesn't resolve to exactly one real client
    behaves exactly like create_invoice's own non-exact-match case: raises,
    creates nothing - mirrors
    test_create_invoice_zero_matches_raises_and_creates_nothing."""
    marker = f"DENIDIN_056_NOTFOUND_{int(now_local().timestamp())}"
    nonexistent_name = f"Test Client {marker}"  # deliberately never seeded

    with pytest.raises(ClientNotFoundError) as exc_info:
        create_receipt(
            morning_client,
            client_name=nonexistent_name,
            amount=50.0,
            description=marker,
            payment_date="2026-08-01",
            name_resolved=True,
        )

    assert "לא נמצא" in str(exc_info.value)
    assert "מזהה פנימי" not in str(exc_info.value)  # no document confirmation shape at all
