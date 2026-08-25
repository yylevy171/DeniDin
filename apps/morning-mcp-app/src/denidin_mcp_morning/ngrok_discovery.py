"""Polls ngrok's local agent API for the tunnel's public URL, with bounded retry.

Extracted from docker-entrypoint.sh's inline one-shot fetch (bugfix-043) - the
entrypoint used to `sleep 2` then check ngrok's local API (127.0.0.1:4040) exactly
once. On a normal cold start that's usually enough, but on a post-reboot restart
(an unattended Windows Update reboot, 2026-08-25) the tunnel session hadn't finished
establishing yet at the 2-second mark; the single check came back empty, and the
shared status file was left reporting "not running" permanently - nothing ever
re-checked it, even though the tunnel itself came up cleanly a few seconds later.
See CONSTITUTION.md SS XVIII: startup-time external dependency handshakes must poll
with bounded retry, never check once and silently give up.
"""
import json
import time
import urllib.error
import urllib.request
from typing import Callable, Optional


def fetch_ngrok_public_url(
    api_url: str = "http://127.0.0.1:4040/api/tunnels",
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 1.5,
    request_timeout_seconds: float = 5.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> Optional[str]:
    """Poll ngrok's local API for the first tunnel's public_url.

    Retries every `poll_interval_seconds` until a tunnel is reported or
    `timeout_seconds` has elapsed since the first attempt - the tunnel can
    still be establishing for a few seconds after the ngrok process starts,
    so a single early check is not sufficient to conclude it never came up.

    Never raises. Returns the public URL (e.g. "https://abc123.ngrok-free.app")
    as soon as one is available, or None if the budget is exhausted first -
    the caller decides how to treat "didn't come up in time" (it is not
    necessarily a hard failure of the container itself).
    """
    deadline = now_fn() + timeout_seconds
    while True:
        url = _try_fetch_once(api_url, request_timeout_seconds)
        if url:
            return url
        if now_fn() >= deadline:
            return None
        sleep_fn(poll_interval_seconds)


def _try_fetch_once(api_url: str, request_timeout_seconds: float) -> Optional[str]:
    try:
        with urllib.request.urlopen(api_url, timeout=request_timeout_seconds) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    tunnels = data.get("tunnels") or []
    if not tunnels:
        return None
    return tunnels[0].get("public_url") or None
