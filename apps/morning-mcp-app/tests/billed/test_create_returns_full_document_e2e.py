"""Real E2E: a `create_*` tool result carries the COMPLETE Morning document.

@pytest.mark.billed — real, text-only OpenAI Responses call driving the
running MCP server over the real ngrok tunnel, plus a real Morning sandbox
document. No mocks (CONSTITUTION §V).

@pytest.mark.sanity — a broken create→re-fetch→JSON path silently strips
every field the ledger's synchronous `חשבונית` capture (denidin-app Feature
069) needs, so this belongs in the fast "is anything obviously broken"
subset.

Background: `POST /documents` returns only a minimal echo (id/number/client/
type/…), never amount, dates, VAT breakdown, payments or line items. Until
2026-09-06 `create_invoice` / `create_transaction_account` /
`create_combo_document` fed that sparse echo straight into
`format_invoice_json`, so their tool result came back with `document_date`,
`vat`/`amount_excl_vat`, `payment`, `line_items` and `creation_date` all
`null`/empty even though Morning had them. They now re-fetch the full
document (`GET /documents/{id}`) first, exactly as `get_invoice_details`
already does — so the create result and the details result are the same
document.

This test proves, against the live sandbox:
  1. the fields that used to be null are now populated, AND
  2. the existing always-present fields are still correct, AND
  3. the create result equals an independent `get_invoice_details` fetch of
     the same document (the real "returns the full document" claim).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import uvicorn

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"
sys.path.insert(0, str(APP_ROOT))

from tests.e2e_helpers import (  # noqa: E402
    OPENAI_ASSISTANT_INSTRUCTIONS,
    NgrokError,
    discover_running_server,
    ngrok_tunnel,
)

from denidin_mcp_morning.config import load_config  # noqa: E402
from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402
from denidin_mcp_morning.server import build_asgi_app, create_server  # noqa: E402
from denidin_mcp_morning.tools import get_invoice_details  # noqa: E402

TEST_HOST = "127.0.0.1"
TEST_PORT = 8793
OPENAI_MODEL = "gpt-4o-mini"

DEV_STATUS_FILE_PATH = APP_ROOT.parent.parent / "shared" / "mcp-status-dev" / "morning_mcp_status.dev.json"

# The document-level fields that were silently `null`/empty before the
# 2026-09-06 re-fetch fix and MUST now be populated for a fresh type-320
# "חשבונית מס / קבלה" (per proposal-full-document-capture.md §1: a 320 carries
# line items AND a payment array AND amountExcludeVat).
_PREVIOUSLY_EMPTY_FIELDS = (
    "document_date",
    "creation_date",
    "amount_excl_vat",
    "status_code",
    "status_label",
)


def _seed_client(morning_client: MorningClient, client_name: str, unique_marker: str) -> None:
    morning_client.add_client(
        {"name": client_name, "emails": [f"{unique_marker}@example.com"], "phone": "050-1234567"}
    )
    for _ in range(12):
        if morning_client.search_clients({"name": client_name}).get("items"):
            return
        time.sleep(1.5)


@pytest.fixture(scope="module")
def config():
    if not CONFIG_PATH.exists():
        pytest.skip("config/config.test.json not found")
    cfg = load_config(CONFIG_PATH)
    if not cfg.openai_api_key:
        pytest.skip("No openai_api_key configured in config/config.test.json")
    if not cfg.mcp_ngrok_authtoken:
        pytest.skip("No mcp.ngrok_authtoken configured in config/config.test.json")
    if not (cfg.api_key_id and cfg.api_key_secret):
        pytest.skip("No Morning credentials in config/config.test.json")
    return cfg


@pytest.fixture(scope="module")
def morning_client(config):
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )


@pytest.fixture(scope="module")
def mcp_endpoint(config):
    """(server_url, auth_token) for a real, reachable MCP server — prefers an
    already-running `./run_morning_mcp.sh dev` (warm tunnel), else a local
    server + ephemeral tunnel. Mirrors test_openai_invokes_mcp_e2e.py."""
    discovered = discover_running_server(DEV_STATUS_FILE_PATH, config.mcp_auth_token)
    if discovered is not None:
        yield discovered
        return

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT
    auth_token = config.mcp_auth_token or "billed-test-token"
    app = build_asgi_app(mcp, auth_token=auth_token)
    uv_config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(uv_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Local MCP server did not start in time")
    try:
        with ngrok_tunnel(port=TEST_PORT, authtoken=config.mcp_ngrok_authtoken) as public_url:
            yield f"{public_url}/mcp", auth_token
    except NgrokError as exc:
        pytest.skip(f"ngrok tunnel unavailable: {exc}")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _mcp_call_output(response, tool_name):
    calls = [
        item for item in response.output
        if getattr(item, "type", None) == "mcp_call" and item.name == tool_name
    ]
    assert calls, (
        f"Model did not invoke {tool_name} via the remote MCP server. "
        f"Full output: {response.output!r}"
    )
    assert all(c.error is None for c in calls), (
        f"{tool_name} call(s) reported an error: {[c.error for c in calls]}"
    )
    return json.loads(calls[-1].output)


@pytest.mark.billed
@pytest.mark.sanity
def test_create_combo_document_result_carries_the_full_document(config, morning_client, mcp_endpoint):
    """The `create_combo_document` MCP tool result must be the COMPLETE Morning
    document — every field `get_invoice_details` would return — not the sparse
    `POST /documents` echo."""
    from openai import OpenAI

    server_url, auth_token = mcp_endpoint
    unique_marker = f"DENIDIN_FULLDOC_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Full Doc Corp {unique_marker}"
    _seed_client(morning_client, client_name, unique_marker)

    openai_client = OpenAI(api_key=config.openai_api_key)
    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        instructions=OPENAI_ASSISTANT_INSTRUCTIONS,
        input=(
            f"Create a combined tax-invoice-and-receipt (חשבונית מס/קבלה, type 320) for the "
            f"client '{client_name}' for 120 NIS including VAT, description "
            f"'Consulting {unique_marker}', already paid today by bank transfer."
        ),
        tools=[
            {
                "type": "mcp",
                "server_label": "morning-invoices",
                "server_url": server_url,
                "require_approval": "never",
                "headers": {"Authorization": f"Bearer {auth_token}"},
            }
        ],
    )

    doc = _mcp_call_output(response, "create_combo_document")
    doc.pop("amount_mismatch", None)

    internal_id = doc.get("internal_morning_id")
    assert internal_id, f"create result has no internal_morning_id: {doc!r}"

    # --- (1) existing, always-present fields still correct -------------------
    assert doc["display_number"], f"missing display_number: {doc!r}"
    assert doc["type"] == 320, f"expected type 320, got {doc['type']!r}"
    assert doc["type_name"], f"missing type_name: {doc!r}"
    assert doc["client_name"] == client_name, (
        f"client_name mismatch: {doc['client_name']!r} != {client_name!r}"
    )
    assert doc["currency"] == "ILS", f"unexpected currency: {doc['currency']!r}"
    assert abs(float(doc["amount"]) - 120.0) < 0.01, f"amount not ~120: {doc['amount']!r}"

    # --- (2) fields that were null before the re-fetch fix ------------------
    for field in _PREVIOUSLY_EMPTY_FIELDS:
        assert doc.get(field) is not None, (
            f"{field!r} is still None in the create_combo_document result — the sparse "
            f"POST /documents echo was used instead of a full re-fetch. Full doc: {doc!r}"
        )
    assert isinstance(doc.get("line_items"), list) and doc["line_items"], (
        f"line_items missing/empty in the create result: {doc!r}"
    )
    assert doc["line_items"][0].get("description"), (
        f"first line item has no description: {doc['line_items']!r}"
    )
    assert doc.get("payment") is not None, f"payment block missing in the create result: {doc!r}"
    assert doc["payment"].get("method"), f"payment.method missing: {doc['payment']!r}"
    assert doc["payment"].get("date"), f"payment.date missing: {doc['payment']!r}"

    # --- (3) the create result == an independent get_invoice_details fetch ---
    details = None
    for _ in range(12):
        details = json.loads(get_invoice_details(morning_client, internal_morning_id=internal_id))
        if all(details.get(f) is not None for f in _PREVIOUSLY_EMPTY_FIELDS):
            break
        time.sleep(1.5)
    assert details is not None
    for field in (*_PREVIOUSLY_EMPTY_FIELDS, "display_number", "type", "type_name",
                  "client_name", "amount", "line_items", "payment"):
        assert doc.get(field) == details.get(field), (
            f"create_combo_document result disagrees with get_invoice_details on {field!r}: "
            f"{doc.get(field)!r} != {details.get(field)!r}"
        )
