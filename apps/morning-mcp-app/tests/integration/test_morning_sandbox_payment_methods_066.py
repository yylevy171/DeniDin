"""Real Morning-sandbox test for Feature 066: each deposit method is stored with
the right payment type and details, read back from Morning itself."""
import json
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import create_combo_document
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.test.json"


@pytest.fixture(scope="module")
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret,
                         base_url=config.api_url, auth_url=config.auth_url)


def _stored_payment(morning_client, marker, **kwargs):
    _, client_name = seed_real_client(morning_client, marker)
    created = json.loads(create_combo_document(
        morning_client, client_name=client_name, amount=500.0, description=f"066 {marker}",
        payment_date=now_local().date().isoformat(), vat_included=True, name_resolved=True, **kwargs))
    return morning_client.get_invoice(created["internal_morning_id"])["payment"][0]


def test_cheque_is_stored_with_number_and_account(morning_client):
    line = _stored_payment(morning_client, f"DENIDIN_066_CHQ_{int(now_local().timestamp())}",
                           payment_method="cheque", bank_number="12", bank_branch="345",
                           bank_account="678901", cheque_number="987654")
    assert line["type"] == 2
    assert str(line["chequeNum"]) == "987654"
    assert (str(line["bankName"]), str(line["bankBranch"]), str(line["bankAccount"])) == ("12", "345", "678901")


@pytest.mark.parametrize("method,app_type", [("bit", 1), ("paybox", 3)])
def test_app_payment_is_stored_with_its_app_type(morning_client, method, app_type):
    line = _stored_payment(morning_client, f"DENIDIN_066_{method}_{int(now_local().timestamp())}", payment_method=method)
    assert (line["type"], line["appType"]) == (10, app_type)


def test_cash_is_stored_as_type_1(morning_client):
    line = _stored_payment(morning_client, f"DENIDIN_066_CASH_{int(now_local().timestamp())}", payment_method="cash")
    assert line["type"] == 1
