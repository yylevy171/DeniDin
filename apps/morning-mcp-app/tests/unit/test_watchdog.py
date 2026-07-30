"""Regression tests for watchdog.py's external tunnel health check (bugfix, 2026-07-30).

Two related bugs, both fixed here:

1. `_external_tunnel_health_environment` used to append "/health" directly
   onto the status file's `server_url`, which is always the MCP endpoint
   (`status_writer.py` writes `f"{public_url}/mcp"`) - producing "/mcp/health",
   a path `BearerTokenMiddleware` doesn't exempt (only the literal "/health" is
   exempt), so the check always 401'd and silently never fired, ever since
   `server_url` started including the `/mcp` suffix.

2. Even with (1) fixed, a check that fails for any *other* reason (network
   error, timeout, real ngrok outage) was indistinguishable from "nothing to
   check yet" - both produced `None`, so a persistently-failing check was
   silently treated as "no news is good news" instead of surfaced. The
   function now returns (attempted, environment) so callers (main()'s loop)
   can log an ERROR when a check was genuinely attempted and failed, distinct
   from the benign not-yet-running no-op case.

Uses a real local server (bearer-auth enabled, same as production) and drives
the actual watchdog function against it end-to-end - no mocking of internal
code (CONSTITUTION SS I/V).
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from denidin_mcp_morning.server import build_asgi_app  # noqa: E402
from watchdog import _external_tunnel_health_environment  # noqa: E402

TEST_HOST = "127.0.0.1"
TEST_PORT = 8797
AUTH_TOKEN = "test-watchdog-token"


@pytest.fixture(scope="module")
def running_auth_server():
    """A real server, wrapped with BearerTokenMiddleware, whose /mcp endpoint
    is the same shape status_writer.py actually produces (base_url + /mcp)."""
    mcp = FastMCP("test-watchdog-server")
    app = build_asgi_app(mcp, auth_token=AUTH_TOKEN, environment="dev")

    uv_config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    uv_server = uvicorn.Server(uv_config)

    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    for _ in range(50):
        if uv_server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("test server did not start in time")

    yield f"http://{TEST_HOST}:{TEST_PORT}/mcp"

    uv_server.should_exit = True
    thread.join(timeout=5)


def test_external_health_check_reaches_real_health_route_not_mcp_health(running_auth_server, tmp_path):
    """The bug: server_url ends in /mcp, so a naive f"{server_url}/health"
    hits /mcp/health, which 401s. The fix strips /mcp first."""
    status_path = tmp_path / "morning_mcp_status.dev.json"
    status_path.write_text(json.dumps({"status": "running", "server_url": running_auth_server}))

    attempted, environment = _external_tunnel_health_environment(status_path)

    assert attempted is True
    assert environment == "dev"


def test_external_health_check_reports_attempted_when_status_running_but_request_fails(tmp_path):
    """Status file says 'running' with a server_url, but nothing is actually
    listening there - this is genuinely different from "not running yet" and
    must report attempted=True (so the caller logs it loudly), not just a
    bare None indistinguishable from the benign no-op case below."""
    status_path = tmp_path / "morning_mcp_status.dev.json"
    status_path.write_text(
        json.dumps({"status": "running", "server_url": "http://127.0.0.1:1/mcp"})
    )

    attempted, environment = _external_tunnel_health_environment(status_path)

    assert attempted is True
    assert environment is None


def test_external_health_check_not_attempted_when_not_running(tmp_path):
    status_path = tmp_path / "morning_mcp_status.dev.json"
    status_path.write_text(json.dumps({"status": "not running", "server_url": None}))

    attempted, environment = _external_tunnel_health_environment(status_path)

    assert attempted is False
    assert environment is None


def test_external_health_check_not_attempted_when_status_file_missing(tmp_path):
    status_path = tmp_path / "does_not_exist.json"

    attempted, environment = _external_tunnel_health_environment(status_path)

    assert attempted is False
    assert environment is None
