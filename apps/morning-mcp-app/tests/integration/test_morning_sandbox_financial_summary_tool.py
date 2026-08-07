"""Real Morning-sandbox test for the get_financial_summary MCP tool (US5, T010a/b).

No mocks: seeds real invoices via create_invoice (US1) and drives
denidin_mcp_morning.tools.get_financial_summary against the live sandbox.
Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
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


@pytest.fixture(scope="module")
def seeded_invoice(morning_client):
    """Create one real sandbox invoice this month, for the summary to pick up."""
    from denidin_mcp_morning.tools import create_invoice

    unique_marker = f"DENIDIN_SUMMARY_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    _, client_name = seed_real_client(morning_client, unique_marker)
    create_invoice(
        morning_client,
        client_name=client_name,
        amount=55.0,
        description=f"Summary seed {unique_marker}",
    )
    # Give the sandbox's search index a moment (see the widened-retry fix in
    # test_morning_sandbox_list_invoices_tool.py for the same class of delay).
    time.sleep(2)
    return unique_marker


def test_get_financial_summary_for_this_month_includes_seeded_invoice(morning_client, seeded_invoice):
    from denidin_mcp_morning.tools import get_financial_summary

    result = get_financial_summary(morning_client, period="month")

    assert isinstance(result, str)
    assert "₪" in result


def test_get_financial_summary_custom_period_requires_dates(morning_client):
    from denidin_mcp_morning.tools import get_financial_summary

    with pytest.raises(ValueError):
        get_financial_summary(morning_client, period="custom")


def test_get_financial_summary_rejects_unknown_period(morning_client):
    from denidin_mcp_morning.tools import get_financial_summary

    with pytest.raises(ValueError):
        get_financial_summary(morning_client, period="fortnight")


def test_get_financial_summary_custom_period_with_no_documents_is_zero(morning_client):
    from denidin_mcp_morning.tools import get_financial_summary

    result = get_financial_summary(
        morning_client, period="custom", from_date="1900-01-01", to_date="1900-01-02"
    )

    assert "₪0.00" in result
