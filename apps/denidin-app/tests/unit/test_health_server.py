"""Tests for src/services/health_server.py (bugfix-043 - health monitoring &
auto-restart). Real objects throughout: real HTTP fixture servers standing
in for morning-mcp-app's tunnel and for the health server itself (real
requests library calls, no mocking of internal code per CONSTITUTION SS V),
fake stand-ins only for third-party SDK clients (OpenAI/Green API) that
would otherwise require live credentials.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from src.services.health_server import (
    HEARTBEAT_INTERVAL_SECONDS,
    build_health_check_fns,
    build_health_info_fns,
    check_ai_connectivity,
    check_chromadb_connectivity,
    check_log_freshness,
    check_morning_connectivity_via_tunnel,
    check_whatsapp_connectivity,
    check_whatsapp_authorized,
    resolve_log_path,
    start_health_server,
    write_heartbeat_log,
)


# ---------------------------------------------------------------------------
# check_ai_connectivity
# ---------------------------------------------------------------------------

class _FakeModels:
    def __init__(self, should_succeed: bool):
        self._should_succeed = should_succeed

    def list(self):
        if not self._should_succeed:
            raise ConnectionError("simulated OpenAI failure")
        return ["gpt-5.6-luna"]


class _FakeOpenAIClient:
    def __init__(self, should_succeed: bool):
        self.models = _FakeModels(should_succeed)


def test_check_ai_connectivity_true_when_models_list_succeeds():
    assert check_ai_connectivity(_FakeOpenAIClient(should_succeed=True)) is True


def test_check_ai_connectivity_false_when_models_list_raises():
    assert check_ai_connectivity(_FakeOpenAIClient(should_succeed=False)) is False


# ---------------------------------------------------------------------------
# check_whatsapp_connectivity
# ---------------------------------------------------------------------------

class _FakeGreenApiResponse:
    def __init__(self, code: int):
        self.code = code
        self.data = {"stateInstance": "authorized"} if code == 200 else None
        self.error = None if code == 200 else "boom"


class _FakeAccount:
    def __init__(self, code: int):
        self._code = code

    def getStateInstance(self):
        return _FakeGreenApiResponse(self._code)


class _FakeGreenApi:
    def __init__(self, code: int):
        self.account = _FakeAccount(code)


def test_check_whatsapp_connectivity_true_on_200():
    assert check_whatsapp_connectivity(_FakeGreenApi(code=200)) is True


def test_check_whatsapp_connectivity_false_on_non_200():
    """The library never raises on an HTTP-level failure - it returns a
    Response with .code/.error - so this must be checked via .code, not
    just try/except."""
    assert check_whatsapp_connectivity(_FakeGreenApi(code=500)) is False


def test_check_whatsapp_connectivity_false_when_call_raises():
    class _RaisingAccount:
        def getStateInstance(self):
            raise ConnectionError("simulated")

    class _RaisingGreenApi:
        account = _RaisingAccount()

    assert check_whatsapp_connectivity(_RaisingGreenApi()) is False



# ---------------------------------------------------------------------------
# check_whatsapp_authorized (bugfix-069) - HTTP 200 alone is NOT "linked"
# ---------------------------------------------------------------------------

class _StateResponse:
    def __init__(self, code: int, state):
        self.code = code
        self.data = {"stateInstance": state} if state is not None else None
        self.error = None if code == 200 else "boom"


class _StateGreenApi:
    """Green API answers HTTP 200 for every instance state (confirmed live on prod,
    2026-10-04: 200 + {"stateInstance": "notAuthorized"} during the outage)."""

    def __init__(self, code: int, state):
        response = _StateResponse(code, state)

        class _Account:
            def getStateInstance(self):
                return response

        self.account = _Account()


def test_check_whatsapp_authorized_true_only_when_authorized():
    assert check_whatsapp_authorized(_StateGreenApi(200, "authorized")) is True


def test_check_whatsapp_authorized_false_when_not_authorized_despite_200():
    """The exact 2026-10-01..04 prod incident: logged out, yet HTTP 200."""
    assert check_whatsapp_authorized(_StateGreenApi(200, "notAuthorized")) is False


@pytest.mark.parametrize("state", ["yellowCard", "blocked", "starting", "sleepMode"])
def test_check_whatsapp_authorized_false_for_other_states(state):
    assert check_whatsapp_authorized(_StateGreenApi(200, state)) is False


def test_check_whatsapp_authorized_false_on_non_200():
    assert check_whatsapp_authorized(_StateGreenApi(500, None)) is False


def test_check_whatsapp_authorized_false_when_call_raises():
    class _RaisingAccount:
        def getStateInstance(self):
            raise ConnectionError("simulated")

    class _RaisingGreenApi:
        account = _RaisingAccount()

    assert check_whatsapp_authorized(_RaisingGreenApi()) is False


def test_build_health_info_fns_empty_without_green_api():
    assert build_health_info_fns() == {}


def test_build_health_info_fns_includes_whatsapp_authorized():
    fns = build_health_info_fns(green_api=_StateGreenApi(200, "notAuthorized"))
    assert set(fns.keys()) == {"whatsapp_authorized"}
    assert fns["whatsapp_authorized"]() is False

# ---------------------------------------------------------------------------
# check_morning_connectivity_via_tunnel - real HTTP fixture server
# ---------------------------------------------------------------------------

def _start_fixture_server(handler_cls):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_fixture_server(server, thread):
    server.shutdown()
    thread.join(timeout=5)


def test_check_morning_connectivity_via_tunnel_true_when_is_alive_reachable(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            assert self.path == "/is_alive"
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _start_fixture_server(Handler)
    try:
        status_file = tmp_path / "morning_mcp_status.json"
        status_file.write_text(json.dumps({
            "status": "running",
            "server_url": f"http://127.0.0.1:{server.server_port}/mcp",
        }))
        mcp_config = {"morning_status_file": str(status_file)}

        assert check_morning_connectivity_via_tunnel(mcp_config) is True
    finally:
        _stop_fixture_server(server, thread)


def test_check_morning_connectivity_via_tunnel_false_when_status_not_running(tmp_path):
    status_file = tmp_path / "morning_mcp_status.json"
    status_file.write_text(json.dumps({"status": "not running", "server_url": None}))
    mcp_config = {"morning_status_file": str(status_file)}

    assert check_morning_connectivity_via_tunnel(mcp_config) is False


def test_check_morning_connectivity_via_tunnel_false_when_endpoint_unreachable(tmp_path):
    status_file = tmp_path / "morning_mcp_status.json"
    status_file.write_text(json.dumps({
        "status": "running",
        "server_url": "http://127.0.0.1:1/mcp",  # nothing listens on port 1
    }))
    mcp_config = {"morning_status_file": str(status_file)}

    assert check_morning_connectivity_via_tunnel(mcp_config) is False


# ---------------------------------------------------------------------------
# check_chromadb_connectivity
# ---------------------------------------------------------------------------

class _FakeChromaClient:
    def __init__(self, should_succeed: bool):
        self._should_succeed = should_succeed

    def heartbeat(self):
        if not self._should_succeed:
            raise RuntimeError("simulated chromadb failure")
        return 123456789


class _FakeMemoryManager:
    def __init__(self, should_succeed: bool):
        self.client = _FakeChromaClient(should_succeed)


def test_check_chromadb_connectivity_true_when_heartbeat_succeeds():
    assert check_chromadb_connectivity(_FakeMemoryManager(should_succeed=True)) is True


def test_check_chromadb_connectivity_false_when_heartbeat_raises():
    assert check_chromadb_connectivity(_FakeMemoryManager(should_succeed=False)) is False


# ---------------------------------------------------------------------------
# check_log_freshness / write_heartbeat_log / resolve_log_path
# ---------------------------------------------------------------------------

def test_check_log_freshness_true_for_a_just_written_file(tmp_path):
    log_path = tmp_path / "denidin.log"
    log_path.write_text("just wrote this\n")

    assert check_log_freshness(log_path, max_age_seconds=600) is True


def test_check_log_freshness_false_for_a_stale_file(tmp_path):
    import os

    log_path = tmp_path / "denidin.log"
    log_path.write_text("old\n")
    old_time = time.time() - 3600
    os.utime(log_path, (old_time, old_time))

    assert check_log_freshness(log_path, max_age_seconds=600) is False


def test_check_log_freshness_false_when_file_missing(tmp_path):
    assert check_log_freshness(tmp_path / "never-written.log", max_age_seconds=600) is False


def test_write_heartbeat_log_does_not_raise():
    write_heartbeat_log()


def test_resolve_log_path_matches_setup_logger_convention(tmp_path):
    assert resolve_log_path(str(tmp_path), "denidin.log") == tmp_path / "denidin.log"


def test_heartbeat_interval_is_ten_minutes():
    assert HEARTBEAT_INTERVAL_SECONDS == 600


# ---------------------------------------------------------------------------
# build_health_check_fns
# ---------------------------------------------------------------------------

def test_build_health_check_fns_omits_checks_for_none_args():
    fns = build_health_check_fns()
    assert fns == {}


def test_build_health_check_fns_includes_only_supplied_checks():
    fns = build_health_check_fns(ai_client=_FakeOpenAIClient(should_succeed=True))
    assert set(fns.keys()) == {"ai_connectivity"}
    assert fns["ai_connectivity"]() is True


# ---------------------------------------------------------------------------
# start_health_server - real ThreadingHTTPServer, real requests.get
# ---------------------------------------------------------------------------

def test_health_server_returns_200_and_app_up_when_no_checks_registered():
    server = start_health_server(0, {})
    try:
        port = server.server_address[1]
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)

        assert response.status_code == 200
        body = response.json()
        assert body["app_up"] == "success"
        assert body["status"] == "ok"
    finally:
        server.shutdown()


def test_health_server_returns_503_when_a_check_fails():
    server = start_health_server(0, {"ai_connectivity": lambda: False})
    try:
        port = server.server_address[1]
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)

        assert response.status_code == 503
        body = response.json()
        assert body["ai_connectivity"] == "fail"
        assert body["status"] == "fail"
    finally:
        server.shutdown()


def test_health_server_returns_200_when_all_checks_pass():
    server = start_health_server(0, {"ai_connectivity": lambda: True, "chromadb_connectivity": lambda: True})
    try:
        port = server.server_address[1]
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)

        assert response.status_code == 200
        body = response.json()
        assert body["ai_connectivity"] == "success"
        assert body["chromadb_connectivity"] == "success"
    finally:
        server.shutdown()


def test_health_server_treats_a_raising_check_as_a_failure_not_a_500():
    def _raising_check():
        raise RuntimeError("simulated check crash")

    server = start_health_server(0, {"ai_connectivity": _raising_check})
    try:
        port = server.server_address[1]
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)

        assert response.status_code == 503
        assert response.json()["ai_connectivity"] == "fail"
    finally:
        server.shutdown()


def test_health_server_returns_404_for_unknown_path():
    server = start_health_server(0, {})
    try:
        port = server.server_address[1]
        response = requests.get(f"http://127.0.0.1:{port}/nope", timeout=5)

        assert response.status_code == 404
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# start_health_server - report-only fields (bugfix-069): visible, never fail status
# (the prober restarts prod on status != ok, and a restart cannot re-link a phone)
# ---------------------------------------------------------------------------

def _get_health(server):
    port = server.server_address[1]
    return requests.get(f"http://127.0.0.1:{port}/health", timeout=5)


def test_failing_report_only_field_shows_fail_but_status_stays_ok():
    server = start_health_server(0, {"ai_connectivity": lambda: True}, {"whatsapp_authorized": lambda: False})
    try:
        response = _get_health(server)
        assert response.status_code == 200
        body = response.json()
        assert body["whatsapp_authorized"] == "fail"
        assert body["status"] == "ok"
    finally:
        server.shutdown()


def test_passing_report_only_field_shows_success():
    server = start_health_server(0, {}, {"whatsapp_authorized": lambda: True})
    try:
        body = _get_health(server).json()
        assert body["whatsapp_authorized"] == "success"
        assert body["status"] == "ok"
    finally:
        server.shutdown()


def test_raising_report_only_field_is_fail_not_500():
    def _raising():
        raise RuntimeError("simulated")

    server = start_health_server(0, {}, {"whatsapp_authorized": _raising})
    try:
        response = _get_health(server)
        assert response.status_code == 200
        assert response.json()["whatsapp_authorized"] == "fail"
        assert response.json()["status"] == "ok"
    finally:
        server.shutdown()


def test_failing_real_check_still_fails_status_alongside_report_only_fields():
    server = start_health_server(0, {"ai_connectivity": lambda: False}, {"whatsapp_authorized": lambda: True})
    try:
        response = _get_health(server)
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "fail"
        assert body["whatsapp_authorized"] == "success"
    finally:
        server.shutdown()
