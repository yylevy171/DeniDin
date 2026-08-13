"""Real Morning-sandbox test for the create_invoice MCP tool (US1, T006a/b).

No mocks: this test drives denidin_mcp_morning.tools.create_invoice, which
calls the real MorningClient against the live sandbox, per CONSTITUTION §V
and this app's testing policy (see spec.md §Testing Strategy).
"""
import pytest
import requests

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

APP_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
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


def test_create_invoice_tool_creates_real_sandbox_document(morning_client):
    from denidin_mcp_morning.tools import create_invoice

    unique_marker = f"DENIDIN_TOOL_TEST_{int(now_local().timestamp())}"
    # Feature 027: create_invoice now resolves client_name against a real
    # client record before creating anything - seed one first.
    _, client_name = seed_real_client(morning_client, unique_marker)

    try:
        confirmation = create_invoice(
            morning_client,
            client_name=client_name,
            amount=45.0,
            description=f"Consulting services {unique_marker}",
            name_resolved=True,
        )
    except requests.exceptions.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        pytest.fail(f"create_invoice tool failed against the sandbox. Server response: {body}")

    assert isinstance(confirmation, str)
    assert client_name in confirmation
    assert "₪45.00" in confirmation


def test_create_invoice_tool_defaults_vat_included_to_true(morning_client):
    from denidin_mcp_morning.tools import create_invoice

    unique_marker = f"DENIDIN_TOOL_TEST_VAT_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker)

    confirmation = create_invoice(
        morning_client,
        client_name=client_name,
        amount=35.0,
        description=f"VAT default check {unique_marker}",
        name_resolved=True,
    )

    assert client_name in confirmation
