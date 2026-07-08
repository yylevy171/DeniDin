"""Real Morning-sandbox test for get_invoice_details / update_invoice_status (US3, T008a/b).

No mocks: seeds a real invoice via create_invoice (US1), then drives
get_invoice_details and update_invoice_status against the live sandbox.
Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

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


@pytest.fixture()
def seeded_invoice_id(morning_client):
    """Create one real sandbox invoice and return its Morning document id."""
    from denidin_mcp_morning.tools import _build_create_invoice_payload

    unique_marker = f"DENIDIN_STATUS_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    payload = _build_create_invoice_payload(
        client_name=f"Test Client {unique_marker}",
        amount=90.0,
        description=f"Status tools test {unique_marker}",
    )
    response = morning_client.create_invoice(payload)
    invoice_id = str(response.get("id") or response.get("documentId") or "")
    assert invoice_id, f"Could not determine created invoice id from response: {response}"
    return invoice_id


def test_get_invoice_details_returns_status_and_dates(morning_client, seeded_invoice_id):
    from denidin_mcp_morning.tools import get_invoice_details

    result = get_invoice_details(morning_client, invoice_id=seeded_invoice_id)

    assert isinstance(result, str)
    assert "לא שולם" in result  # freshly created documents are open ("unpaid")


def test_update_invoice_status_to_paid_then_get_details_reflects_it(morning_client, seeded_invoice_id):
    from denidin_mcp_morning.tools import get_invoice_details, update_invoice_status

    update_result = update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="paid")
    assert "שולם" in update_result

    details = get_invoice_details(morning_client, invoice_id=seeded_invoice_id)
    assert "לא שולם" not in details
    assert "שולם" in details


def test_update_invoice_status_unpaid_is_a_noop_when_already_unpaid(morning_client, seeded_invoice_id):
    from denidin_mcp_morning.tools import update_invoice_status

    result = update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="unpaid")

    assert "לא שולם" in result


def test_update_invoice_status_unpaid_rejected_once_already_paid(morning_client, seeded_invoice_id):
    """Real Morning behavior (confirmed live): /documents/{id}/open refuses to
    reopen a document that was closed via a linked receipt rather than /close
    itself ("לא ניתן לפתוח מסמך שאינו סגור ידנית") — there is no supported
    reversal, so this must fail clearly rather than silently do nothing."""
    from denidin_mcp_morning.tools import update_invoice_status

    update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="paid")

    with pytest.raises(ValueError):
        update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="unpaid")


def test_update_invoice_status_cancelled_issues_a_linked_credit_invoice(morning_client, seeded_invoice_id):
    """Use case: the user made a mistake creating the invoice (wrong amount,
    typo, etc.) and needs it voided so a corrected one can be created instead.
    Israeli law forbids deleting/voiding an issued tax invoice outright — the
    real mechanism (confirmed live via GET /documents/types: 330 = "חשבונית
    זיכוי") is a linked credit invoice that offsets it."""
    from denidin_mcp_morning.tools import update_invoice_status

    result = update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="cancelled")

    assert "בוטלה" in result
    assert "זיכוי" in result


def test_update_invoice_status_rejects_unknown_status(morning_client, seeded_invoice_id):
    from denidin_mcp_morning.tools import update_invoice_status

    with pytest.raises(ValueError):
        update_invoice_status(morning_client, invoice_id=seeded_invoice_id, status="not_a_real_status")
