"""Helpers for tests/expensive/ — real OpenAI-driven E2E tests (Phase 5, T021).

`ngrok_tunnel()` manages a real, ephemeral ngrok tunnel (free tier: an
authtoken is required, but no paid plan — a reserved/static domain is only
needed for a stable URL across restarts, which this per-test-run tunnel does
not need). No mocking: this shells out to the real `ngrok` binary and polls
its real local inspector API.

`discover_running_server()` lets these tests reuse the standalone
`./run_morning_mcp.sh` server + its already-warm ngrok tunnel when one is
running, instead of always spinning up a brand-new tunnel per test run. A
freshly created ngrok tunnel is occasionally not yet reachable from the
public internet the instant its local inspector reports it (OpenAI's first
request gets HTTP 424 Failed Dependency) — reusing an existing, already-live
tunnel sidesteps that cold-start flake entirely.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

NGROK_LOCAL_API = "http://127.0.0.1:4040/api/tunnels"

# Shared `instructions` (OpenAI's system-prompt-level parameter on
# responses.create() — confirmed as a real top-level SDK parameter, distinct
# from the MCP server's own optional `instructions` field) used by every
# expensive OpenAI-driven test, so all of them exercise the model under the
# same guidance. Explicitly tells the model to stay out of these tools for
# anything unrelated to invoicing — this is what
# test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt checks holds.
OPENAI_ASSISTANT_INSTRUCTIONS = (
    "You are a bookkeeping assistant with access to Morning (Green Invoice) "
    "invoice-management tools via MCP: create_invoice, list_invoices, "
    "get_invoice_details, update_invoice_status, add_client, "
    "get_financial_summary, and download_invoice_pdf. Use these tools only "
    "when the user's request is actually about creating, finding, updating, "
    "or reporting on invoices, clients, or financial data. For anything "
    "unrelated to invoicing, answer normally without calling any tool."
)


class NgrokError(Exception):
    """Raised when the ngrok CLI is missing, fails to start, or never reports a tunnel."""


def discover_running_server(production_config_path: Path) -> Optional[Tuple[str, str]]:
    """Return (server_url, auth_token) for an already-running standalone
    `./run_morning_mcp.sh` server, or None if none is live.

    Reads `config/config.json` (the standalone server's own config — separate
    from the sandbox `config.test.json` these tests otherwise use) purely to
    learn its `mcp.status_file` path and `mcp.auth_token`; no Morning/OpenAI
    credentials from it are used. Confirms the server is actually reachable
    (not just that the status file claims "running") with a real HTTP probe.
    """
    if not production_config_path.exists():
        return None

    try:
        raw = json.loads(production_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    mcp_section = raw.get("mcp") or {}
    auth_token = mcp_section.get("auth_token")
    status_file = mcp_section.get("status_file")
    if not auth_token or not status_file:
        return None

    status_path = Path(status_file)
    if not status_path.exists():
        return None

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if status.get("status") != "running":
        return None

    server_url = status.get("server_url")
    if not server_url:
        return None

    try:
        request = urllib.request.Request(server_url, method="GET")
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        # Any HTTP response (401 unauthorized without a bearer token is
        # expected) proves the tunnel is actually live end-to-end.
        if exc.code >= 500:
            return None
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None

    return server_url, auth_token


def _ngrok_available() -> bool:
    return shutil.which("ngrok") is not None


def _fetch_public_url(timeout_seconds: float = 15.0) -> str:
    """Poll ngrok's local inspector API until it reports an active tunnel."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Optional[Exception] = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(NGROK_LOCAL_API, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
            tunnels = data.get("tunnels") or []
            https_tunnels = [t for t in tunnels if t.get("public_url", "").startswith("https://")]
            if https_tunnels:
                return https_tunnels[0]["public_url"]
        except (urllib.error.URLError, ConnectionError, json.JSONDecodeError) as exc:
            last_error = exc

        time.sleep(0.5)

    raise NgrokError(f"ngrok did not report an active tunnel within {timeout_seconds}s: {last_error}")


def _verify_tunnel_health(public_url: str, max_seconds: float = 60.0) -> None:
    """Confirm `public_url` is actually reachable end-to-end (not just that
    ngrok's local inspector registered it) by polling the server's
    unauthenticated `/health` endpoint, with exponential backoff, for up to
    `max_seconds` total.

    A freshly created ngrok tunnel is occasionally not yet reachable from the
    public internet the instant ngrok's local API reports it active — this
    catches that cold-start window before OpenAI's first real request does
    (observed as HTTP 424 Failed Dependency).
    """
    deadline = time.monotonic() + max_seconds
    delay = 0.5
    last_error: Optional[Exception] = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{public_url}/health", timeout=5) as response:
                if response.status == 200:
                    return
                last_error = RuntimeError(f"unexpected status {response.status}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc

        time.sleep(min(delay, max(deadline - time.monotonic(), 0)))
        delay *= 2

    raise NgrokError(f"tunnel health check at {public_url}/health did not succeed within {max_seconds}s: {last_error}")


@contextmanager
def ngrok_tunnel(port: int, authtoken: str) -> Iterator[str]:
    """Start a real, ephemeral ngrok tunnel to `port` and yield its public HTTPS URL.

    Args:
        port: Local port the MCP server is listening on.
        authtoken: A real ngrok account authtoken (free tier is sufficient —
            no paid plan needed for this ephemeral, per-run tunnel).

    Yields:
        The tunnel's public HTTPS URL (e.g. "https://abc123.ngrok-free.app").

    Raises:
        NgrokError: if the `ngrok` CLI isn't installed, the process fails to
            start, or no tunnel is reported within the timeout.
    """
    if not _ngrok_available():
        raise NgrokError("The 'ngrok' CLI is not installed (brew install --cask ngrok).")

    subprocess.run(
        ["ngrok", "config", "add-authtoken", authtoken],
        capture_output=True,
        timeout=15,
        check=False,
    )

    process = subprocess.Popen(
        ["ngrok", "http", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        public_url = _fetch_public_url()
        _verify_tunnel_health(public_url)
        yield public_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
