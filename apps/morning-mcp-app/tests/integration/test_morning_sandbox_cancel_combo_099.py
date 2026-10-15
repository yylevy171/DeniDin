"""Real Morning-sandbox test for Feature 099: create_receipt cancels a 320 with
a negative receipt. No mocks (CONSTITUTION §V): seeds a real client, creates a
real 320 and a real 330, then drives the real create_receipt."""
import json
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import create_combo_document, create_credit_note, create_receipt
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


def _make_320(morning_client, marker):
    _, client_name = seed_real_client(morning_client, marker)
    created = json.loads(create_combo_document(
        morning_client, client_name=client_name, amount=1000.0, description=f"099 {marker}",
        payment_date=now_local().date().isoformat(), vat_included=True,
        payment_method="bank_transfer", bank_number="12", bank_branch="345", bank_account="678901",
        name_resolved=True))
    return created["internal_morning_id"]


def test_a_320_that_already_has_a_330_is_refused(morning_client):
    marker = f"DENIDIN_099_{int(now_local().timestamp())}"
    doc_320 = _make_320(morning_client, marker)
    credit_note = json.loads(create_credit_note(morning_client, doc_320))
    assert credit_note["type"] == 330

    refused = json.loads(create_receipt(morning_client, doc_320))

    assert refused == {"status": "error", "reason": "original_already_cancelled"}


def test_cancelling_receipt_is_negative_linked_and_copies_the_payment(morning_client):
    marker = f"DENIDIN_099B_{int(now_local().timestamp())}"
    doc_320 = _make_320(morning_client, marker)

    receipt = json.loads(create_receipt(morning_client, doc_320))

    assert receipt["type"] == 400
    assert receipt["amount"] == -1000.0
    stored = morning_client.get_invoice(receipt["internal_morning_id"])
    assert stored["type"] == 400
    assert stored["amount"] == -1000
    assert [ld["id"] for ld in stored["linkedDocuments"]] == [doc_320]
    line = stored["payment"][0]
    assert (line["type"], line["price"], line["bankName"], line["bankBranch"], line["bankAccount"]) == (
        4, -1000, "12", "345", "678901")
    original = morning_client.get_invoice(doc_320)
    assert any(ld["type"] == 400 and ld["amount"] == -1000 for ld in original["linkedDocuments"])


def test_a_second_cancelling_receipt_is_refused(morning_client):
    marker = f"DENIDIN_099C_{int(now_local().timestamp())}"
    doc_320 = _make_320(morning_client, marker)
    json.loads(create_receipt(morning_client, doc_320))

    refused = json.loads(create_receipt(morning_client, doc_320))

    assert refused == {"status": "error", "reason": "original_already_cancelled"}
