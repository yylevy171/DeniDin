"""Real E2E test for per-tenant Morning credential threading (Feature 055:
Multi-Tenancy, tasks.md Phase 6, T025a).

**Downgraded 2026-08-17 (no second real Morning account available yet, per
spec.md Clarifications)**: this proves the per-tenant credential-threading
PLUMBING against a real API call - the bearer token presented resolves to the
right tenant_id (BearerTokenMiddleware), which resolves to the right
MorningClient (server.py's `create_server`/`_current_client`), which reaches
the real Morning sandbox successfully. It uses the *existing* real Morning
sandbox account (config.test.json's real api_key_id/api_key_secret),
referenced by TWO distinct synthetic tenant_ids - it does **not** prove true
cross-account isolation (both synthetic tenants hit the same real backend
account). That stronger guarantee is `tasks.md` T025c, explicitly deferred
pending a real second Morning sandbox/account - logged there as a known,
documented coverage gap, not silently assumed covered by this file.

Real FastMCP server (streamable-HTTP) in a background uvicorn thread, real MCP
client, real Morning sandbox call - no mocking, per CONSTITUTION §V. Same
infrastructure pattern as the existing `test_mcp_server_e2e.py`.
"""
import asyncio
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from denidin_mcp_morning.config import TenantMorningCredentials, load_config
from denidin_mcp_morning.server import build_asgi_app, create_server

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

TEST_HOST = "127.0.0.1"
TEST_PORT = 8797

TENANT_A_TOKEN = "multi-tenant-e2e-token-a"
TENANT_B_TOKEN = "multi-tenant-e2e-token-b"


@pytest.fixture(scope="module")
def multi_tenant_server_url():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")

    # Two SYNTHETIC tenants, both pointing at the one real sandbox account
    # (config.test.json's real credentials) - see module docstring for why
    # this proves plumbing, not cross-account isolation.
    config = replace(
        config,
        tenants=(
            TenantMorningCredentials(
                tenant_id="tenant-a", api_key_id=config.api_key_id,
                api_key_secret=config.api_key_secret, mcp_auth_token=TENANT_A_TOKEN,
            ),
            TenantMorningCredentials(
                tenant_id="tenant-b", api_key_id=config.api_key_id,
                api_key_secret=config.api_key_secret, mcp_auth_token=TENANT_B_TOKEN,
            ),
        ),
    )

    mcp = create_server(config)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    tenant_tokens = {t.mcp_auth_token: t.tenant_id for t in config.tenants}
    app = build_asgi_app(mcp, tenant_tokens=tenant_tokens)
    uv_config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    uv_server = uvicorn.Server(uv_config)

    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    for _ in range(50):
        if uv_server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Multi-tenant FastMCP server did not start in time")

    yield f"http://{TEST_HOST}:{TEST_PORT}{mcp.settings.streamable_http_path}"

    uv_server.should_exit = True
    thread.join(timeout=5)


def _call_get_financial_summary(server_url: str, bearer_token: str):
    """Cheap, read-only real Morning sandbox call - one aggregation over
    /documents/search, no document created."""
    import httpx

    async def _run():
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {bearer_token}"}) as http_client:
            async with streamable_http_client(server_url, http_client=http_client) as (
                read, write, _get_session_id,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(
                        "get_financial_summary", {"period": "month"}
                    )

    return asyncio.run(_run())


def test_tenant_a_token_reaches_the_real_sandbox_via_its_own_resolved_client(multi_tenant_server_url):
    result = _call_get_financial_summary(multi_tenant_server_url, TENANT_A_TOKEN)

    assert result.isError is not True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert text  # a real, non-empty Hebrew summary came back


def test_tenant_b_token_reaches_the_real_sandbox_via_its_own_resolved_client(multi_tenant_server_url):
    result = _call_get_financial_summary(multi_tenant_server_url, TENANT_B_TOKEN)

    assert result.isError is not True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert text


def test_unrecognized_token_is_rejected_before_ever_reaching_morning(multi_tenant_server_url):
    """The auth boundary is checked before any tool/Morning call - a bad
    token never gets as far as the resolved-client logic at all."""
    import httpx

    async def _run():
        async with httpx.AsyncClient(
            headers={"Authorization": "Bearer not-a-configured-tenant-token"}
        ) as http_client:
            return await http_client.post(
                multi_tenant_server_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            )

    response = asyncio.run(_run())
    assert response.status_code == 401
