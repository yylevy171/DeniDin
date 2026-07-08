"""Real Morning-sandbox test for the download_invoice_pdf MCP tool (US7, T012a/b).

No mocks: seeds a real invoice via create_invoice (US1) and drives
denidin_mcp_morning.tools.download_invoice_pdf against the live sandbox.
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
    from denidin_mcp_morning.tools import _build_create_invoice_payload

    unique_marker = f"DENIDIN_PDF_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    payload = _build_create_invoice_payload(
        client_name=f"Test Client {unique_marker}", amount=15.0, description=unique_marker
    )
    created = morning_client.create_invoice(payload)
    invoice_id = str(created.get("id") or created.get("documentId") or "")
    assert invoice_id
    return invoice_id


def test_download_invoice_pdf_returns_a_real_download_url(morning_client, seeded_invoice_id):
    from denidin_mcp_morning.tools import download_invoice_pdf

    result = download_invoice_pdf(morning_client, invoice_id=seeded_invoice_id)

    assert isinstance(result, str)
    assert "https://" in result
    assert "documents/download" in result


def test_download_invoice_pdf_rejects_nonexistent_invoice(morning_client):
    from denidin_mcp_morning.tools import download_invoice_pdf

    with pytest.raises(Exception):
        download_invoice_pdf(morning_client, invoice_id="00000000-0000-0000-0000-000000000000")
