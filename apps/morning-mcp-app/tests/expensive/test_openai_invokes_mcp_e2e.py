"""Real E2E test: an external OpenAI call drives the running MCP server (Phase 5, T021).

@pytest.mark.expensive — uses real, billed OpenAI API calls. Per this repo's
expensive-test rules (CONSTITUTION §VII / CLAUDE.md): human approval is
required before every single run, run alone (never as part of a batch), read
logs/test_logs/ before re-running, only re-run after a confident fix.

No mocks anywhere: real FastMCP server (streamable-HTTP), real ngrok tunnel,
real OpenAI Responses API call with this server registered as a remote MCP
tool, real Morning sandbox document verification. This proves the thing
tests/integration/test_mcp_server_e2e.py cannot: that an *external* MCP
client neither this app nor its own test suite controls can actually
discover and drive these tools over the real MCP protocol, over the public
internet, exactly as a production integration would.

MCP output-item schema used below (`type == "mcp_call"`, `.name`,
`.arguments`, `.output`, `.error`) was confirmed directly against the
installed `openai` SDK's `openai.types.responses.response_output_item.McpCall`
class — not guessed from documentation, which is thinner on this than the
SDK's own type definitions.
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import uvicorn

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.json"
sys.path.insert(0, str(APP_ROOT))

from tests.expensive.e2e_helpers import NgrokError, ngrok_tunnel  # noqa: E402

from denidin_mcp_morning.config import load_config  # noqa: E402
from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402
from denidin_mcp_morning.server import build_asgi_app, create_server  # noqa: E402

TEST_HOST = "127.0.0.1"
TEST_PORT = 8792

# NOTE: verify this is still a current, available OpenAI model before running.
OPENAI_MODEL = "gpt-4.1"


@pytest.fixture(scope="module")
def config():
    if not CONFIG_PATH.exists():
        pytest.skip("config/config.json not found")

    cfg = load_config(CONFIG_PATH)
    if not cfg.openai_api_key:
        pytest.skip("No openai_api_key configured in config/config.json")
    if not cfg.mcp_ngrok_authtoken:
        pytest.skip("No mcp.ngrok_authtoken configured in config/config.json")
    if not (cfg.api_key_id and cfg.api_key_secret):
        pytest.skip("No Morning credentials in config/config.json")
    return cfg


@pytest.fixture(scope="module")
def running_server(config):
    """Start the real MCP server locally, bearer-auth protected, for the
    tunnel to expose."""
    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    auth_token = config.mcp_auth_token or "expensive-test-token"
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

    yield auth_token

    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.expensive
def test_openai_invokes_create_invoice_via_remote_mcp(config, running_server):
    """A real OpenAI Responses API call, given a natural-language prompt and
    this server registered as a remote MCP tool (over a real public ngrok
    tunnel), must actually invoke create_invoice and produce a real document
    in the Morning sandbox — verified independently, not just trusted from
    the model's own textual claim of success.
    """
    from openai import OpenAI

    auth_token = running_server
    unique_marker = f"DENIDIN_OPENAI_E2E_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Corp {unique_marker}"

    try:
        with ngrok_tunnel(port=TEST_PORT, authtoken=config.mcp_ngrok_authtoken) as public_url:
            openai_client = OpenAI(api_key=config.openai_api_key)

            response = openai_client.responses.create(
                model=OPENAI_MODEL,
                input=(
                    f"Create an invoice for a client named '{client_name}' for 50 NIS, "
                    f"description 'Consulting services {unique_marker}'."
                ),
                tools=[
                    {
                        "type": "mcp",
                        "server_label": "morning-invoices",
                        "server_url": f"{public_url}/mcp",
                        "require_approval": "never",
                        "headers": {"Authorization": f"Bearer {auth_token}"},
                    }
                ],
            )
    except NgrokError as exc:
        pytest.skip(f"ngrok tunnel unavailable: {exc}")

    mcp_calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]
    create_invoice_calls = [call for call in mcp_calls if call.name == "create_invoice"]

    assert create_invoice_calls, (
        f"Model did not invoke create_invoice via the remote MCP server. "
        f"Full output: {response.output!r}"
    )
    assert all(call.error is None for call in create_invoice_calls), (
        f"create_invoice call(s) reported an error: {[c.error for c in create_invoice_calls]}"
    )

    # Independently verify: a real document actually landed in the Morning
    # sandbox, not just that the model/tool claimed success.
    morning_client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )
    found = False
    last_items = None
    for _ in range(12):
        resp = morning_client.list_invoices(params={"clientName": client_name})
        items = (resp.get("items") or resp.get("data") or []) if isinstance(resp, dict) else resp
        last_items = items
        if any(
            (item.get("client") or {}).get("name") == client_name
            or unique_marker in (item.get("description") or "")
            for item in items
        ):
            found = True
            break
        time.sleep(1.5)

    assert found, (
        f"No invoice for {client_name!r} found in Morning after the OpenAI-driven call; "
        f"last search results: {last_items}"
    )
