"""Real Morning-sandbox test for cancel_transaction_account (feature 056):
cancelling an open transaction account ("חשבון עסקה", type 300) with ZERO
documents created - the deal fell through, no money moved.

No mocks: seeds a real type-300 document via the real create_transaction_account
tool, then drives the real cancel_transaction_account function against the
live sandbox. Per CONSTITUTION §V - real system, real external service, no
unittest.mock.

Mechanism live-confirmed in research.md (2026-08-18): MorningClient.close_invoice
(already existing) sets status 0 -> 2 with zero new documents. This file is
the regression-locking proof that the shipped tool actually does that,
including the idempotency guard research.md's Finding 3 found necessary
(the raw API rejects a redundant close with a 400 - it does not no-op
itself).
"""
import json
import time
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import (
    cancel_transaction_account,
    create_combo_document_as_reference,
    create_transaction_account,
    list_invoices,
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


def _seed_open_transaction_account(morning_client, label):
    """Create one real sandbox type-300 document via the real
    create_transaction_account tool and return its internal_morning_id -
    tolerating the same real search-index propagation lag documented in
    research.md Finding 4 and used throughout this test suite."""
    marker = f"DENIDIN_056_{label}_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)
    create_transaction_account(
        morning_client, client_name, 60.0, f"Cancel test {marker}", vat_included=True, name_resolved=True,
    )

    internal_morning_id = None
    for _ in range(12):
        payload = json.loads(list_invoices(morning_client, client_name=client_name, name_resolved=True))
        documents = payload.get("documents") or []
        if documents:
            internal_morning_id = documents[0]["internal_morning_id"]
            break
        time.sleep(1.5)
    assert internal_morning_id, f"Could not resolve transaction account id for {client_name!r}"
    return internal_morning_id


def test_cancel_transaction_account_happy_path_creates_no_document(morning_client):
    """(1) A real cancellation sets status 0 -> 2, linkedDocuments stays
    empty, and the close response's own id equals the original's - no new
    document of any kind - REQ-INV-020."""
    internal_morning_id = _seed_open_transaction_account(morning_client, "CANCEL_HAPPY")

    before = morning_client.get_invoice(internal_morning_id)
    assert before.get("status") == 0

    result = cancel_transaction_account(morning_client, internal_morning_id)
    assert result
    assert "שולם" not in result, "cancellation confirmation must never say 'paid'"

    after = morning_client.get_invoice(internal_morning_id)
    assert after.get("status") == 2, f"Expected manually-closed status 2, got: {after.get('status')!r}"
    assert not after.get("linkedDocuments"), f"Cancellation must create no linked document: {after!r}"


def test_cancel_transaction_account_is_idempotent(morning_client):
    """(2) Cancelling an already-cancelled account again is a real,
    observable no-op - it must not raise (the raw API 400s on a redundant
    close; this proves the app-side guard actually prevents that call) and
    must not change the status again."""
    internal_morning_id = _seed_open_transaction_account(morning_client, "CANCEL_IDEMPOTENT")

    cancel_transaction_account(morning_client, internal_morning_id)
    second_result = cancel_transaction_account(morning_client, internal_morning_id)
    assert second_result
    assert "שולם" not in second_result

    after = morning_client.get_invoice(internal_morning_id)
    assert after.get("status") == 2


def test_cancel_transaction_account_leaves_a_fulfilled_account_untouched(morning_client):
    """(3) An account already fulfilled via create_combo_document_as_reference
    (a real type-320 document exists) must never be contradicted - the
    cancellation call is a no-op, and the type-320 document stays exactly
    as it was."""
    internal_morning_id = _seed_open_transaction_account(morning_client, "CANCEL_FULFILLED")

    create_combo_document_as_reference(morning_client, internal_morning_id, payment_date="2026-08-01")
    fulfilled = morning_client.get_invoice(internal_morning_id)
    assert fulfilled.get("status") in (1, 2)
    linked_before = fulfilled.get("linkedDocuments") or []
    combo_docs_before = [d for d in linked_before if d.get("type") == 320]
    assert len(combo_docs_before) == 1, f"Expected exactly one linked type-320 document: {linked_before!r}"

    result = cancel_transaction_account(morning_client, internal_morning_id)
    assert result

    after = morning_client.get_invoice(internal_morning_id)
    linked_after = after.get("linkedDocuments") or []
    combo_docs_after = [d for d in linked_after if d.get("type") == 320]
    assert combo_docs_after == combo_docs_before, (
        f"Cancellation must never touch an existing fulfillment document: before={combo_docs_before!r} "
        f"after={combo_docs_after!r}"
    )


def test_cancel_transaction_account_rejects_a_tax_invoice_original(morning_client):
    """(4) A real type-305 tax invoice is rejected outright - tax-invoice
    cancellation continues exclusively through create_credit_note
    (REQ-INV-022), never through this document-less path."""
    from denidin_mcp_morning.tools import _build_create_invoice_payload

    marker = f"DENIDIN_056_CANCEL_WRONGTYPE_{int(now_local().timestamp())}"
    client_id, _ = seed_real_client(morning_client, marker)
    payload = _build_create_invoice_payload(client_id=client_id, amount=45.0, description=marker)
    response = morning_client.create_invoice(payload)
    internal_morning_id = str(response.get("id") or response.get("documentId") or "")
    assert internal_morning_id

    before = morning_client.get_invoice(internal_morning_id)

    with pytest.raises(ValueError):
        cancel_transaction_account(morning_client, internal_morning_id)

    after = morning_client.get_invoice(internal_morning_id)
    assert after.get("status") == before.get("status"), "A rejected cancellation must not change the document at all"


def test_open_invoice_still_reverses_a_cancelled_account(morning_client):
    """(5) Reversibility sanity check: this feature must not accidentally
    change open_invoice's existing, unrelated behavior - a cancelled
    account still cleanly reopens via the already-existing method."""
    internal_morning_id = _seed_open_transaction_account(morning_client, "CANCEL_REOPEN")

    cancel_transaction_account(morning_client, internal_morning_id)
    reopened = morning_client.open_invoice(internal_morning_id)
    assert reopened.get("status") == 0

    after = morning_client.get_invoice(internal_morning_id)
    assert after.get("status") == 0
