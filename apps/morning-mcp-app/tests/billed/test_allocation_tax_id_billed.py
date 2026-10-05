"""Feature 098 acceptance - UAT 4.1: Morning-MCP refuses on its own.

@pytest.mark.billed - a real, text-only OpenAI Responses API call drives the
real MCP server over a real ngrok tunnel; the result is verified against the
real Morning sandbox. No DeniDin involved.

Reuses test_openai_invokes_mcp_e2e.py's `config` / `mcp_endpoint` fixtures
(imported below), so it prefers an already-running `./run_morning_mcp.sh dev`
server. That container must run an image that includes Feature 098, or this
test exercises stale code - rebuild it first (needs explicit approval).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from tests.billed.test_openai_invokes_mcp_e2e import (  # noqa: F401 - pytest fixtures
    OPENAI_MODEL,
    _seed_client,
    config,
    mcp_endpoint,
)
from tests.e2e_helpers import OPENAI_ASSISTANT_INSTRUCTIONS

from denidin_mcp_morning.morning_client import MorningClient


def _call_text(call) -> str:
    return f"{call.output or ''} {call.error or ''}"


@pytest.mark.billed
def test_openai_create_combo_refused_without_client_id(config, mcp_endpoint):
    """UAT 4.1: OpenAI is told to create a 320 for 12,000 ₪ for a client with
    no ID. Morning-MCP's create_combo_document returns the refusal - which
    says the client's ID is required above 5,000 ₪ before VAT - and Morning
    holds no document for the client."""
    from openai import OpenAI

    server_url, auth_token = mcp_endpoint
    marker = f"DENIDIN_098_UAT41_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test098 {marker}"

    morning_client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )
    _seed_client(morning_client, client_name, marker)
    client_id = morning_client.search_clients({"name": client_name})["items"][0]["id"]

    today = datetime.now(timezone.utc).date().isoformat()
    response = OpenAI(api_key=config.openai_api_key).responses.create(
        model=OPENAI_MODEL,
        instructions=OPENAI_ASSISTANT_INSTRUCTIONS,
        input=(
            f"Resolve the client '{client_name}' with resolve_client_name, then call "
            f"create_combo_document for that client: 12,000 NIS including VAT, "
            f"description 'Consulting {marker}', paid by bank transfer on {today}. "
            f"Call create_combo_document directly - do not look up client details first."
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

    mcp_calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]
    combo_calls = [call for call in mcp_calls if call.name == "create_combo_document"]
    assert combo_calls, f"Model never called create_combo_document. Full output: {response.output!r}"

    refusals = [call for call in combo_calls if "ת.ז / ח.פ" in _call_text(call)]
    assert refusals, f"create_combo_document did not return the ID refusal: {[_call_text(c) for c in combo_calls]!r}"
    assert "5,000" in _call_text(refusals[0])

    # Independently verify nothing was created, allowing for search-index lag.
    time.sleep(9)
    docs = morning_client.list_invoices({"clientId": client_id})
    items = docs.get("items", docs) if isinstance(docs, dict) else docs
    assert [d for d in items if d.get("type") in (305, 320)] == [], f"a document was created: {items!r}"
