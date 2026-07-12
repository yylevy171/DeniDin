"""Real E2E test for the FastMCP server (Phase 3, T014a/b).

No mocks: starts the actual FastMCP server (streamable-HTTP) in a background
thread, connects a real MCP client to it, lists tools, and invokes one
against the live Morning sandbox. This is this app's equivalent of
denidin-app's "does the router actually catch the webhook" integration-test
requirement (CONSTITUTION §V) — proving tool registration/dispatch actually
works end-to-end, not just that the tools.py functions work in isolation.
"""
import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.server import build_asgi_app, create_server

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

TEST_HOST = "127.0.0.1"
TEST_PORT = 8799

EXPECTED_TOOL_NAMES = {
    "create_invoice",
    "list_invoices",
    "get_invoice_details",
    "update_invoice_status",
    "add_client",
    "get_financial_summary",
    "download_invoice_pdf",
}


@pytest.fixture(scope="module")
def server_url():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    app = mcp.streamable_http_app()
    uv_config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    uv_server = uvicorn.Server(uv_config)

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


def test_mcp_server_registers_all_7_tools(server_url):
    async def _run():
        async with streamable_http_client(server_url) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return {tool.name for tool in result.tools}

    tool_names = asyncio.run(_run())

    assert tool_names == EXPECTED_TOOL_NAMES


def test_mcp_client_can_invoke_create_invoice_tool_end_to_end(server_url):
    """Proves dispatch, not just registration: a real MCP tool call reaches
    tools.create_invoice, which hits the real Morning sandbox."""
    unique_marker = f"DENIDIN_E2E_TEST_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Client {unique_marker}"

    async def _run():
        async with streamable_http_client(server_url) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(
                    "create_invoice",
                    {
                        "client_name": client_name,
                        "amount": 33.0,
                        "description": unique_marker,
                    },
                )

    result = asyncio.run(_run())

    assert result.isError is not True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert client_name in text
    assert "₪33.00" in text


def test_mcp_tool_error_is_friendly_not_a_raw_stack_trace(server_url):
    """CONSTITUTION §X: user-facing errors must be friendly, never raw technical
    detail. Without a mapping layer, FastMCP's default behavior surfaces the raw
    exception string (confirmed live: 'Error executing tool ...: 404 Client
    Error: Not Found for url: https://sandbox.d.greeninvoice.co.il/...'),
    leaking the internal API URL to the caller."""

    async def _run():
        async with streamable_http_client(server_url) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(
                    "get_invoice_details",
                    {"invoice_id": "00000000-0000-0000-0000-000000000000"},
                )

    result = asyncio.run(_run())

    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert "greeninvoice.co.il" not in text
    assert "Traceback" not in text
    assert "Client Error" not in text
    assert "❌" in text


AUTH_TEST_PORT = 8798
AUTH_TEST_TOKEN = "test-shared-secret-token"


@pytest.fixture(scope="module")
def server_url_with_auth():
    """Same real-server pattern as `server_url`, but with BearerTokenMiddleware
    enabled (Phase 5, T021-auth) — proves auth is enforced against the actual
    running server, not just the isolated middleware unit tests."""
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = AUTH_TEST_PORT

    app = build_asgi_app(mcp, auth_token=AUTH_TEST_TOKEN)
    uv_config = uvicorn.Config(app, host=TEST_HOST, port=AUTH_TEST_PORT, log_level="warning")
    uv_server = uvicorn.Server(uv_config)

    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    for _ in range(50):
        if uv_server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("FastMCP server (with auth) did not start in time")

    yield f"http://{TEST_HOST}:{AUTH_TEST_PORT}{mcp.settings.streamable_http_path}"

    uv_server.should_exit = True
    thread.join(timeout=5)


def test_real_server_with_auth_rejects_request_without_token(server_url_with_auth):
    response = requests.post(
        server_url_with_auth,
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        timeout=5,
    )

    assert response.status_code == 401


def test_real_server_with_auth_rejects_wrong_token(server_url_with_auth):
    response = requests.post(
        server_url_with_auth,
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer wrong-token",
        },
        timeout=5,
    )

    assert response.status_code == 401


def test_real_server_with_auth_accepts_correct_token_and_serves_mcp_protocol(server_url_with_auth):
    """With the correct token, requests reach the real MCP server (proven by
    a full tool-listing round trip through the actual auth-wrapped app)."""
    import httpx

    async def _run():
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {AUTH_TEST_TOKEN}"}) as http_client:
            async with streamable_http_client(server_url_with_auth, http_client=http_client) as (
                read,
                write,
                _get_session_id,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return {tool.name for tool in result.tools}

    tool_names = asyncio.run(_run())

    assert tool_names == EXPECTED_TOOL_NAMES
