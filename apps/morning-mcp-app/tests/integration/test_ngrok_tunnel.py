"""Real test that the ngrok tunnel mechanism actually works (Phase 5, T021).

No mocks, and NOT an OpenAI-billing test (that's tests/expensive/
test_openai_invokes_mcp_e2e.py) — this only proves that a real ngrok tunnel
started via tests/expensive/e2e_helpers.ngrok_tunnel() actually routes real
internet traffic to our locally-running MCP server, by hitting the tunnel's
public HTTPS URL from this same machine (any HTTP client works to prove
this — it doesn't have to be OpenAI).

Skips gracefully if `ngrok` isn't installed or no authtoken is configured
(both real possibilities during normal local dev).
"""
import sys
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.json"
sys.path.insert(0, str(APP_ROOT))

from tests.expensive.e2e_helpers import NgrokError, ngrok_tunnel  # noqa: E402

from denidin_mcp_morning.config import load_config  # noqa: E402
from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402
from denidin_mcp_morning.server import build_asgi_app, create_server  # noqa: E402

TEST_HOST = "127.0.0.1"
TEST_PORT = 8793


@pytest.fixture(scope="module")
def config():
    if not CONFIG_PATH.exists():
        pytest.skip("config/config.json not found")
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def running_server(config):
    """Start the real MCP server locally (auth-protected, matching how it
    would actually be exposed) for the tunnel to point at."""
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No Morning credentials in config/config.json")

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    auth_token = config.mcp_auth_token or "test-tunnel-token"
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


def test_ngrok_tunnel_routes_real_internet_traffic_to_local_server(config, running_server):
    """Proves the tunnel mechanism end-to-end: a request to the PUBLIC ngrok
    URL reaches our local server (verified via the bearer-auth check —
    wrong/missing token -> 401, correct token -> not 401 — since a live
    Morning tool call isn't needed just to prove routing works)."""
    if not config.mcp_ngrok_authtoken:
        pytest.skip("No mcp.ngrok_authtoken configured in config/config.json")

    auth_token = running_server

    def _post_once_tunnel_is_live(headers: dict, attempts: int = 8, delay: float = 1.0):
        """Retry briefly on 404 — ngrok's local agent can report a tunnel as
        active before the request actually reaches our app (confirmed live:
        a 404 came back from ngrok's own edge, not our BearerTokenMiddleware,
        which never returns 404 — global edge propagation lags the local
        agent's "active" status by a second or so). A persistent 404 past
        the retry budget is a real failure, not propagation lag.
        """
        last_response = None
        for _ in range(attempts):
            last_response = requests.post(
                f"{public_url}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers=headers,
                timeout=15,
            )
            if last_response.status_code != 404:
                return last_response
            time.sleep(delay)
        return last_response

    try:
        with ngrok_tunnel(port=TEST_PORT, authtoken=config.mcp_ngrok_authtoken) as public_url:
            # Request 1: no auth header -> the LOCAL server's own middleware
            # should reject it. If this succeeds, the public URL is truly
            # reaching our process (not some other server / a cached page).
            unauthenticated = _post_once_tunnel_is_live(
                {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            )
            assert unauthenticated.status_code == 401

            # Request 2: correct token -> should NOT be rejected as
            # unauthorized (proves the tunnel carries headers through
            # correctly, not just that *some* response comes back).
            authenticated = _post_once_tunnel_is_live(
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {auth_token}",
                }
            )
            assert authenticated.status_code != 401
    except NgrokError as exc:
        pytest.skip(f"ngrok tunnel unavailable: {exc}")
