"""Real Morning-sandbox tests for Feature 098 (mandatory client ID above the
allocation threshold).

A tax invoice (305) or tax invoice/receipt (320) whose pre-VAT amount exceeds
`allocation_threshold_nis` must never be sent to Morning for a client with no
9-digit ID - Morning needs the ID to request the allocation number (מספר הקצאה).

No mocks: every test drives the real tools against the real sandbox and
verifies the persisted state with an independent follow-up call.
"""
import asyncio
import json
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.server import create_server
from denidin_mcp_morning.tools import (
    ClientTaxIdRequiredError,
    InvoicingRules,
    _build_create_invoice_payload,
    _build_transaction_account_payload,
    create_combo_document,
    create_combo_document_as_reference,
    create_credit_note,
    create_invoice,
    create_receipt,
    create_transaction_account,
)
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

VALID_TAX_ID = "308253681"  # check-digit valid; Morning rejects invalid ones (errorCode 1111)

TEST_HOST = "127.0.0.1"
TEST_PORT = 8791

PAYMENT_DATE = "2026-10-01"

# Search-index eventual-consistency lag (Feature 026 research.md Decision 8).
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


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


def _marker(label):
    return f"DENIDIN_098_{label}_{int(now_local().timestamp())}"


def _poll(predicate, action):
    result = None
    for _ in range(_POLL_ATTEMPTS):
        result = action()
        if predicate(result):
            return result
        time.sleep(_POLL_INTERVAL_SECONDS)
    return result


# ---------------------------------------------------------------------------
# T003 - live verification of GET /clients/{id} (research.md R1)
# ---------------------------------------------------------------------------


def test_get_client_by_id_returns_tax_id(morning_client):
    """GET /clients/{id} exists on the sandbox and returns the client's taxId."""
    marker = _marker("GETCLIENT")
    name = f"Test Client {marker}"
    response = morning_client.add_client(
        {"name": name, "emails": [f"{marker}@example.com"], "phone": "050-1234567", "taxId": VALID_TAX_ID}
    )
    client_id = response["id"]

    record = morning_client.get_client(client_id)

    assert record.get("id") == client_id
    assert record.get("taxId") == VALID_TAX_ID, f"GET /clients/{{id}} did not return taxId: {record!r}"


def test_tax_id_added_later_is_visible_by_id_and_by_search(morning_client):
    """A taxId added to an existing ID-less client (UAT 2.1's update step) is
    returned by both GET /clients/{id} and POST /clients/search afterward."""
    client_id, name = seed_real_client(morning_client, _marker("LATERID"))
    assert not morning_client.get_client(client_id).get("taxId")

    morning_client.update_client(client_id, {"taxId": VALID_TAX_ID})

    by_id = _poll(lambda r: r.get("taxId") == VALID_TAX_ID, lambda: morning_client.get_client(client_id))
    assert by_id.get("taxId") == VALID_TAX_ID, f"GET by id never showed the new taxId: {by_id!r}"

    items = _poll(
        lambda items: any(i.get("taxId") == VALID_TAX_ID for i in items),
        lambda: morning_client.search_clients({"name": name}).get("items") or [],
    )
    assert any(i.get("taxId") == VALID_TAX_ID for i in items), f"search never showed the new taxId: {items!r}"


# ---------------------------------------------------------------------------
# T008 - the backstop against the real sandbox (UAT 4.1's Morning side)
# ---------------------------------------------------------------------------


def _seed_client(morning_client, label, tax_id=None):
    """A real client, optionally with a tax id, findable by name."""
    client_id, name = seed_real_client(morning_client, _marker(label))
    if tax_id:
        morning_client.update_client(client_id, {"taxId": tax_id})
        _poll(
            lambda items: any(i.get("taxId") == tax_id for i in items),
            lambda: morning_client.search_clients({"name": name}).get("items") or [],
        )
    return client_id, name


def _documents_of_type(morning_client, client_id, doc_type):
    docs = morning_client.list_invoices({"clientId": client_id})
    items = docs.get("items", docs) if isinstance(docs, dict) else docs
    return [d for d in items if d.get("type") == doc_type]


def _assert_no_document_appears(morning_client, client_id, doc_type):
    """Absence check, given the search index's lag: wait the same window a
    positive poll would, then confirm nothing of this type exists."""
    time.sleep(_POLL_ATTEMPTS * _POLL_INTERVAL_SECONDS / 2)
    assert _documents_of_type(morning_client, client_id, doc_type) == []


def _seed_transaction_account(morning_client, client_id, amount):
    """A real open 300 for `amount` before VAT. Closing it in full (amount
    omitted) closes for its VAT-inclusive total, so the close itself is
    issued with the default vat_included=True - anything else is Morning's
    errorCode 2422 (income vs payment mismatch)."""
    payload = _build_transaction_account_payload(
        client_id=client_id, amount=amount, description=_marker("TA"), vat_included=False
    )
    response = morning_client.create_invoice(payload)
    return str(response.get("id") or response.get("documentId"))


def test_tax_invoice_above_threshold_without_id_is_refused(morning_client):
    client_id, name = _seed_client(morning_client, "305NOID")

    with pytest.raises(ClientTaxIdRequiredError):
        create_invoice(morning_client, name, 8000.0, _marker("305"), vat_included=False, name_resolved=True)

    _assert_no_document_appears(morning_client, client_id, 305)


def test_combo_above_threshold_without_id_is_refused(morning_client):
    client_id, name = _seed_client(morning_client, "320NOID")

    with pytest.raises(ClientTaxIdRequiredError):
        create_combo_document(
            morning_client, name, 12000.0, _marker("320"), vat_included=True,
            payment_date=PAYMENT_DATE, name_resolved=True,
        )

    _assert_no_document_appears(morning_client, client_id, 320)


def test_closing_a_transaction_account_above_threshold_without_id_is_refused(morning_client):
    client_id, _ = _seed_client(morning_client, "CLOSENOID")
    original_id = _seed_transaction_account(morning_client, client_id, 10000.0)

    with pytest.raises(ClientTaxIdRequiredError):
        create_combo_document_as_reference(morning_client, original_id, payment_date=PAYMENT_DATE)

    original = morning_client.get_invoice(original_id)
    assert original.get("status") == 0, f"the transaction account must still be open: {original!r}"
    assert not original.get("linkedDocuments"), f"nothing may be linked to it: {original!r}"


def test_tax_invoice_above_threshold_with_id_is_created(morning_client):
    client_id, name = _seed_client(morning_client, "305ID", tax_id=VALID_TAX_ID)

    result = json.loads(
        create_invoice(morning_client, name, 8000.0, _marker("305"), vat_included=False, name_resolved=True)
    )

    assert result["client_name"] == name
    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 305))


def test_combo_above_threshold_with_id_is_created(morning_client):
    client_id, name = _seed_client(morning_client, "320ID", tax_id=VALID_TAX_ID)

    create_combo_document(
        morning_client, name, 12000.0, _marker("320"), vat_included=True,
        payment_date=PAYMENT_DATE, name_resolved=True,
    )

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 320))


def test_closing_a_transaction_account_after_the_id_was_added_is_created(morning_client):
    """UAT 2.1's shape: the 300 was created while the client had no ID; the
    ID is added afterwards; closing now succeeds (the check reads the
    client's current record, not the 300's snapshot)."""
    client_id, name = _seed_client(morning_client, "CLOSELATERID")
    original_id = _seed_transaction_account(morning_client, client_id, 10000.0)
    morning_client.update_client(client_id, {"taxId": VALID_TAX_ID})
    _poll(lambda r: r.get("taxId") == VALID_TAX_ID, lambda: morning_client.get_client(client_id))

    create_combo_document_as_reference(morning_client, original_id, payment_date=PAYMENT_DATE)

    original = morning_client.get_invoice(original_id)
    assert original.get("status") in (1, 2), f"the transaction account should now be closed: {original!r}"


def test_combo_below_threshold_without_id_is_created(morning_client):
    client_id, name = _seed_client(morning_client, "320LOW")

    create_combo_document(
        morning_client, name, 4500.0, _marker("320LOW"), vat_included=True,
        payment_date=PAYMENT_DATE, name_resolved=True,
    )

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 320))


def test_transaction_account_above_threshold_without_id_is_created(morning_client):
    """A 300 never gets an allocation number - out of scope."""
    client_id, name = _seed_client(morning_client, "300NOID")

    create_transaction_account(morning_client, name, 12000.0, _marker("300"), vat_included=True, name_resolved=True)

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 300))


def test_standalone_receipt_above_threshold_without_id_is_created(morning_client):
    """A 400 never gets an allocation number - out of scope."""
    client_id, name = _seed_client(morning_client, "400NOID")

    create_receipt(
        morning_client, client_name=name, amount=12000.0, description=_marker("400"),
        payment_date=PAYMENT_DATE, name_resolved=True,
    )

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 400))


def test_credit_note_above_threshold_without_id_is_created(morning_client):
    """A 330 never gets an allocation number - out of scope. Its original 305
    is created directly through the API (the tool would now refuse it)."""
    client_id, _ = _seed_client(morning_client, "330NOID")
    original = morning_client.create_invoice(
        _build_create_invoice_payload(
            client_id=client_id, amount=8000.0, description=_marker("305SEED"), vat_included=False
        )
    )
    original_id = str(original.get("id") or original.get("documentId"))

    create_credit_note(morning_client, original_id)

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 330))


def test_a_higher_configured_threshold_lets_a_smaller_document_through(morning_client):
    """Threshold configured to 10,000: a 7,000 (before VAT) tax invoice for an
    ID-less client is created."""
    client_id, name = _seed_client(morning_client, "THRESH10K")
    rules = InvoicingRules(allocation_threshold_nis=10000.0, vat_rate=0.18)

    create_invoice(
        morning_client, name, 7000.0, _marker("305"), vat_included=False, name_resolved=True, rules=rules
    )

    assert _poll(bool, lambda: _documents_of_type(morning_client, client_id, 305))


# Not covered here: a stored client ID that is not 9 digits. Morning itself
# refuses to store one (PUT /clients/{id} with "12345678" or "1234567890" ->
# errorCode 1111, probed live 2026-10-05), so the sandbox can't hold that
# state. The 9-digit check is covered by the unit tests.


# ---------------------------------------------------------------------------
# T009 - through the real MCP server (contract C2)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server_url(morning_client):
    config = load_config(CONFIG_PATH)
    mcp = create_server(config, client=morning_client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    uv_server = uvicorn.Server(
        uvicorn.Config(mcp.streamable_http_app(), host=TEST_HOST, port=TEST_PORT, log_level="warning")
    )
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if uv_server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("FastMCP server did not start in time")

    yield f"http://{TEST_HOST}:{TEST_PORT}{mcp.settings.streamable_http_path}"

    uv_server.should_exit = True
    thread.join(timeout=5)


def test_mcp_refusal_is_an_error_carrying_the_hebrew_message(morning_client, server_url):
    client_id, name = _seed_client(morning_client, "MCPNOID")

    async def _run():
        async with streamable_http_client(server_url) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(
                    "create_combo_document",
                    {
                        "client_name": name,
                        "amount": 12000.0,
                        "description": _marker("MCP"),
                        "vat_included": True,
                        "payment_date": PAYMENT_DATE,
                        "name_resolved": True,
                    },
                )

    result = asyncio.run(_run())

    assert result.isError is True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert "אין ת.ז / ח.פ" in text
    assert "5,000" in text
    assert name in text
    _assert_no_document_appears(morning_client, client_id, 320)
