"""Tests for the bounded-retry ngrok public-URL poller (bugfix-043).

Real HTTP calls to a local fixture server standing in for ngrok's own local
agent API (127.0.0.1:4040) - not mocking of internal code, matching
CONSTITUTION SS V's "local HTTP fixture servers" guidance for third-party/
external-process boundaries. `sleep_fn`/`now_fn` are injected so the retry
loop's timing is deterministic and the test suite stays fast.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from denidin_mcp_morning.ngrok_discovery import fetch_ngrok_public_url


class _FakeTimeline:
    """A fake clock/sleep pair: advances a counter on sleep() instead of blocking."""

    def __init__(self):
        self.elapsed = 0.0

    def now(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds


def _start_fixture_server(handler_cls):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_fixture_server(server, thread):
    server.shutdown()
    thread.join(timeout=5)


def _tunnels_response(handler, public_url):
    body = json.dumps({"tunnels": [{"public_url": public_url}]}).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def test_fetch_ngrok_public_url_succeeds_immediately_when_tunnel_already_up():
    public_url = "https://abc123.ngrok-free.app"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib method name
            _tunnels_response(self, public_url)

        def log_message(self, *args):
            pass

    server, thread = _start_fixture_server(Handler)
    try:
        api_url = f"http://127.0.0.1:{server.server_port}/api/tunnels"
        result = fetch_ngrok_public_url(api_url=api_url, timeout_seconds=5.0, poll_interval_seconds=0.1)
        assert result == public_url
    finally:
        _stop_fixture_server(server, thread)


def test_fetch_ngrok_public_url_retries_until_tunnel_establishes():
    """Reproduces the actual incident: the API is reachable but reports no
    tunnels yet for the first few checks (tunnel session still establishing),
    then succeeds - the exact shape of the 2026-08-25 production race."""
    public_url = "https://zookeeper-gutter-hatchling.ngrok-free.dev"
    state = {"calls": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            state["calls"] += 1
            if state["calls"] < 4:
                body = json.dumps({"tunnels": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                _tunnels_response(self, public_url)

        def log_message(self, *args):
            pass

    server, thread = _start_fixture_server(Handler)
    try:
        api_url = f"http://127.0.0.1:{server.server_port}/api/tunnels"
        clock = _FakeTimeline()
        result = fetch_ngrok_public_url(
            api_url=api_url,
            timeout_seconds=30.0,
            poll_interval_seconds=1.5,
            sleep_fn=clock.sleep,
            now_fn=clock.now,
        )
        assert result == public_url
        assert state["calls"] == 4
    finally:
        _stop_fixture_server(server, thread)


def test_fetch_ngrok_public_url_gives_up_after_budget_exhausted_returns_none():
    """The pre-fix bug: a single failed check silently gave up forever with
    no way to ever recover. The fixed version must still eventually give up
    (never hang the container startup indefinitely) - but only after a real
    bounded budget, not after one early check."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps({"tunnels": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _start_fixture_server(Handler)
    try:
        api_url = f"http://127.0.0.1:{server.server_port}/api/tunnels"
        clock = _FakeTimeline()
        result = fetch_ngrok_public_url(
            api_url=api_url,
            timeout_seconds=10.0,
            poll_interval_seconds=2.0,
            sleep_fn=clock.sleep,
            now_fn=clock.now,
        )
        assert result is None
        # Retried more than once - not the old one-shot-and-give-up behavior.
        assert clock.elapsed >= 10.0
    finally:
        _stop_fixture_server(server, thread)


def test_fetch_ngrok_public_url_returns_none_when_api_unreachable():
    """Simulates the other real failure mode: ngrok's web API isn't even
    listening yet (nothing bound to the port)."""
    clock = _FakeTimeline()
    result = fetch_ngrok_public_url(
        api_url="http://127.0.0.1:1/api/tunnels",  # nothing listens on port 1
        timeout_seconds=0.3,
        poll_interval_seconds=0.1,
        request_timeout_seconds=0.2,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )
    assert result is None
