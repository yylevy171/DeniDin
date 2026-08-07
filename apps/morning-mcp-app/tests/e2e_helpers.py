"""Helpers for tests/billed/ — real OpenAI-driven E2E tests (Phase 5, T021).

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
# billed OpenAI-driven test, so all of them exercise the model under the
# same guidance. Explicitly tells the model to stay out of these tools for
# anything unrelated to invoicing — this is what
# test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt checks holds.
# Extend this (not a second, competing constant) whenever a new tool needs
# to be discoverable by these tests, or a new reliability nudge is needed —
# 2026-08-07: added the "always attempt the tool call" clause below after
# observing the model sometimes hedge with a plain-text confirmatory
# question instead of calling create_invoice, mirroring the same rule
# apps/denidin-app/config/runtime_constitution.md already carries in
# production for exactly this reason.
OPENAI_ASSISTANT_INSTRUCTIONS = (
    "You are a bookkeeping assistant with access to Morning (Green Invoice) "
    "invoice-management tools via MCP: create_invoice, create_transaction_account, "
    "create_combo_document, create_credit_note, create_receipt, "
    "close_transaction_account, list_invoices, get_invoice_details, add_client, "
    "get_financial_summary, and download_invoice_pdf. There is no separate "
    "status-update tool - resolve a document's real type via get_invoice_details "
    "before choosing which create_*/close_* tool to call for a status-change "
    "request. Use these tools only when the user's request is actually about "
    "creating, finding, updating, or reporting on invoices, clients, or "
    "financial data. For anything unrelated to invoicing, answer normally "
    "without calling any tool. "
    "ALWAYS attempt the tool call itself, in the same turn as the request, the "
    "instant you have what it needs. NEVER reply with only a plain-text "
    "confirmatory question ('should I create this invoice?') and wait for the "
    "user's next message before attempting the call - if a client name is "
    "given, do not ask whether that client already exists or should be "
    "created first; just call the document-creation tool directly and let it "
    "tell you if the client needs to be created. The tool call itself is the "
    "only thing that surfaces any needed confirmation or error."
)


class NgrokError(Exception):
    """Raised when the ngrok CLI is missing, fails to start, or never reports a tunnel."""


def discover_running_server(status_file_path: Path, auth_token: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (server_url, auth_token) for an already-running standalone
    `./run_morning_mcp.sh dev` server, or None if none is live.

    Reads the shared per-environment status file (`shared/mcp-status-dev/`,
    same file `apps/denidin-app`'s own tests use to discover the live tunnel
    - see `docker/docker-compose.dev.yml`'s volume mount) purely to learn the
    server's current URL; no Morning/OpenAI credentials are read from it.
    `auth_token` is passed in directly (from the caller's own already-loaded
    config) rather than read from a second config file - status_file paths
    inside `config.dev.json`/`config.prod.json` are container-internal
    (`/app/mcp-status/...`), not valid from this host-side test process, so
    there is no config file this helper could read both pieces from at once.
    Confirms the server is actually reachable (not just that the status file
    claims "running") with a real HTTP probe.
    """
    if not auth_token:
        return None

    status_path = status_file_path
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
