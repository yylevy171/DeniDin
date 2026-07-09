"""Helpers for tests/expensive/ — real OpenAI-driven E2E tests (Phase 5, T021).

`ngrok_tunnel()` manages a real, ephemeral ngrok tunnel (free tier: an
authtoken is required, but no paid plan — a reserved/static domain is only
needed for a stable URL across restarts, which this per-test-run tunnel does
not need). No mocking: this shells out to the real `ngrok` binary and polls
its real local inspector API.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Iterator, Optional

NGROK_LOCAL_API = "http://127.0.0.1:4040/api/tunnels"


class NgrokError(Exception):
    """Raised when the ngrok CLI is missing, fails to start, or never reports a tunnel."""


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
        yield public_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
