"""Real Morning-sandbox test for get_invoice_details and the direct
document-creation tools that replace `update_invoice_status` (removed,
feature 023): create_receipt, create_credit_note, create_combo_document_as_reference.

Formerly this file drove `update_invoice_status(status=...)` directly.
Feature 023 removed that tool entirely - Morning has no real "status" field
to update; there is only document creation, and the model now resolves which
direct tool to call itself (via get_invoice_details) instead of a
status-word-matching code path. Each scenario below is ported to call the
tool that now reaches the same real Morning state, rather than deleted.

No mocks: seeds a real invoice via create_invoice (US1), then drives
get_invoice_details and the direct tools against the live sandbox.
Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
import json
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
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


@pytest.fixture()
def seeded_internal_morning_id(morning_client):
    """Create one real sandbox invoice and return its Morning document id."""
    from denidin_mcp_morning.tools import _build_create_invoice_payload

    unique_marker = f"DENIDIN_STATUS_TEST_{int(now_local().timestamp())}"
    client_id, _ = seed_real_client(morning_client, unique_marker)
    payload = _build_create_invoice_payload(
        client_id=client_id,
        amount=90.0,
        description=f"Status tools test {unique_marker}",
    )
    response = morning_client.create_invoice(payload)
    internal_morning_id = str(response.get("id") or response.get("documentId") or "")
    assert internal_morning_id, f"Could not determine created invoice id from response: {response}"
    return internal_morning_id


def test_get_invoice_details_returns_status_and_dates(morning_client, seeded_internal_morning_id):
    from denidin_mcp_morning.tools import get_invoice_details

    result = get_invoice_details(morning_client, internal_morning_id=seeded_internal_morning_id)

    assert isinstance(result, str)
    payload = json.loads(result)
    assert payload["status"] == "unpaid"  # freshly created documents are open


def test_create_receipt_then_get_details_reflects_paid(morning_client, seeded_internal_morning_id):
    """Formerly update_invoice_status(status="paid") - now create_receipt
    directly (the model resolves the target's real type as 305 first, per
    US4, and calls this tool instead of a status-update tool)."""
    from denidin_mcp_morning.tools import create_receipt, get_invoice_details

    create_result = create_receipt(morning_client, seeded_internal_morning_id, payment_date="2026-07-12")
    assert create_result

    details = json.loads(get_invoice_details(morning_client, internal_morning_id=seeded_internal_morning_id))
    assert details["status"] == "paid"


def test_repeated_create_receipt_is_idempotent_no_op(morning_client, seeded_internal_morning_id):
    """Formerly update_invoice_status(status="paid")'s idempotency guarantee
    - now implemented directly in create_receipt (feature 023), since
    Morning itself does not reject a duplicate receipt (verified live)."""
    from denidin_mcp_morning.tools import create_receipt, get_invoice_details

    create_receipt(morning_client, seeded_internal_morning_id, payment_date="2026-07-12")
    create_receipt(morning_client, seeded_internal_morning_id, payment_date="2026-07-12")

    raw = morning_client.get_invoice(seeded_internal_morning_id)
    linked = raw.get("linkedDocuments") or []
    receipts = [doc for doc in linked if doc.get("type") == 400]
    assert len(receipts) == 1, f"Expected exactly one linked receipt, got: {linked!r}"

    details = json.loads(get_invoice_details(morning_client, internal_morning_id=seeded_internal_morning_id))
    assert details["status"] == "paid"


def test_there_is_no_mark_as_unpaid_action_anymore(morning_client, seeded_internal_morning_id):
    """Feature 023 (human-directed architecture decision, 2026-07-29): there
    is no such thing as "marking something unpaid" - only document creation.
    Formerly `_mark_invoice_unpaid`/`update_invoice_status(status="unpaid")`
    provided an idempotent no-op / clear-refusal pair; both are intentionally
    removed with no tool-level replacement (US6: the model must explain this
    is unsupported, not attempt any tool call - a conversational behavior
    this test cannot exercise without a real OpenAI call, see the expensive
    E2E suite). This test only confirms the removal is real, not accidental."""
    from denidin_mcp_morning import tools

    assert not hasattr(tools, "update_invoice_status")
    assert not hasattr(tools, "_mark_invoice_unpaid")
    assert not hasattr(tools, "_mark_invoice_paid")


def test_create_credit_note_issues_a_linked_credit_invoice(morning_client, seeded_internal_morning_id):
    """Use case: the user made a mistake creating the invoice (wrong amount,
    typo, etc.) and needs it voided so a corrected one can be created instead.
    Israeli law forbids deleting/voiding an issued tax invoice outright — the
    real mechanism (confirmed live via GET /documents/types: 330 = "חשבונית
    זיכוי") is a linked credit invoice that offsets it. Formerly
    update_invoice_status(status="cancelled") - now create_credit_note
    directly (US5)."""
    from denidin_mcp_morning.tools import create_credit_note, get_invoice_details

    result = json.loads(create_credit_note(morning_client, seeded_internal_morning_id))

    assert result["type_name"] == "חשבונית זיכוי"

    details = json.loads(get_invoice_details(morning_client, internal_morning_id=seeded_internal_morning_id))
    assert details["linked_document"] is not None
    assert "זיכוי" in details["linked_document"]["type_name"]


def test_create_receipt_rejects_a_transaction_account_original(morning_client):
    """Formerly update_invoice_status's `else: raise ValueError(unsupported
    status)` branch (an invalid/unhandled input must be rejected, not
    guessed) - the closest surviving equivalent is each direct tool
    defending its own document-type boundary. Ported here at the sandbox
    level: create_receipt must reject a real type-300 original rather than
    issuing the wrong document type against real Morning data."""
    from denidin_mcp_morning.tools import create_transaction_account, create_receipt, list_invoices
    import time

    unique_marker = f"DENIDIN_REJECT_TEST_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker)
    create_transaction_account(
        morning_client, client_name, 80.0, f"Reject test {unique_marker}", vat_included=True,
        name_resolved=True,
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

    with pytest.raises(ValueError):
        create_receipt(morning_client, internal_morning_id, payment_date="2026-07-12")


@pytest.fixture()
def seeded_transaction_account_id(morning_client):
    """Create one real sandbox type-300 ('חשבון עסקה') document via the real
    create_transaction_account tool (021) - deliberately not a hand-built
    payload, so this test exercises the exact shape create_combo_document_as_reference
    must handle in real usage (a VAT-less original, per feature 023's
    vat_included fix)."""
    from denidin_mcp_morning.tools import create_transaction_account, list_invoices

    unique_marker = f"DENIDIN_TX_ACCOUNT_TEST_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker)
    create_transaction_account(
        morning_client, client_name, 40.0, f"Transaction account test {unique_marker}",
        vat_included=True, name_resolved=True,
    )

    import time

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


def test_create_combo_document_as_reference_issues_a_type_320_combo_document(
    morning_client, seeded_transaction_account_id
):
    """Spec 020 / bugfix-014 Flow 4, now reached via create_combo_document_as_reference
    directly (feature 023 removed update_invoice_status): a type-300 original
    must be closed by a linked type-320 combo document, not the type-400
    receipt used for type-305 - confirms the real payload shape Morning
    actually accepts, and that the vat_included fix (feature 023) works
    against a real VAT-less type-300 original created via the real
    create_transaction_account tool."""
    from denidin_mcp_morning.tools import create_combo_document_as_reference, get_invoice_details

    close_result = create_combo_document_as_reference(
        morning_client, seeded_transaction_account_id, payment_date="2026-07-12"
    )
    assert close_result

    details = json.loads(get_invoice_details(morning_client, internal_morning_id=seeded_transaction_account_id))
    assert details["status"] == "paid"

    raw = morning_client.get_invoice(seeded_transaction_account_id)
    assert raw.get("status") in (1, 2), f"Expected a closed/paid status code, got: {raw.get('status')!r}"
    linked = raw.get("linkedDocuments") or []
    assert any(doc.get("type") == 320 for doc in linked), (
        f"Expected a linked type-320 combo document, got linkedDocuments: {linked!r}"
    )
    assert not any(doc.get("type") == 400 for doc in linked), (
        f"Type-300 original must not be closed by a type-400 receipt: {linked!r}"
    )


def test_create_combo_document_as_reference_is_idempotent(
    morning_client, seeded_transaction_account_id
):
    """Marking an already-closed type-300 document paid again must not
    create a second linked closing document (feature 023's idempotency
    guard in create_combo_document_as_reference, replacing update_invoice_status's
    same guarantee)."""
    from denidin_mcp_morning.tools import create_combo_document_as_reference

    create_combo_document_as_reference(morning_client, seeded_transaction_account_id, payment_date="2026-07-12")
    create_combo_document_as_reference(morning_client, seeded_transaction_account_id, payment_date="2026-07-12")

    raw = morning_client.get_invoice(seeded_transaction_account_id)
    linked = raw.get("linkedDocuments") or []
    combo_docs = [doc for doc in linked if doc.get("type") == 320]
    assert len(combo_docs) == 1, f"Expected exactly one linked type-320 document, got: {linked!r}"
