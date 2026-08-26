"""Localhost-only /health HTTP endpoint for the prod-only external health-check
prober (bugfix-043).

denidin-app has never had an HTTP listener before this - it's a polling
WhatsApp bot, not a webhook receiver. This is deliberately a small stdlib-only
server (http.server.ThreadingHTTPServer), not a new framework dependency, for
exactly one route.

Each check is a plain, independently-testable function taking only the
already-live object it needs (the OpenAI client, the Green API client, etc.)
- the HTTP-handling code itself (build_health_check_fns/start_health_server)
never touches those objects directly, only the zero-arg callables bound to
them, so the wiring and the check logic can be tested completely separately
(see tests/unit/test_health_server.py).
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, Optional

import requests

from src.handlers.morning_mcp_locator import MorningMcpLocator
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Matches morning-mcp-app's own health_checks.py convention (bugfix-043) -
# the heartbeat writer runs on this interval, and the log-freshness check's
# default staleness budget matches it exactly.
HEARTBEAT_INTERVAL_SECONDS = 600  # 10 minutes

# Real, cheap HTTP timeouts for the checks that make a live call - short
# enough that a single hung dependency can't stall the whole /health response
# past what the 1-minute prober cadence can tolerate.
CHECK_TIMEOUT_SECONDS = 5


def check_ai_connectivity(openai_client) -> bool:
    """Cheap, real OpenAI call (list models) - not a completion, which would
    be a real, non-trivial cost on every ~1-minute probe."""
    try:
        openai_client.models.list()
        return True
    except Exception:  # noqa: BLE001
        logger.warning("check_ai_connectivity: failed", exc_info=True)
        return False


def check_whatsapp_connectivity(green_api) -> bool:
    """Real Green API call, purpose-built for this (account.getStateInstance -
    'aimed for getting the account state'). The library never raises on an
    HTTP-level failure - it returns a Response with .code/.error instead - so
    a real failure must be checked via .code, not just try/except."""
    try:
        response = green_api.account.getStateInstance()
        return response.code == 200
    except Exception:  # noqa: BLE001
        logger.warning("check_whatsapp_connectivity: failed", exc_info=True)
        return False


def check_morning_connectivity_via_tunnel(mcp_config: dict) -> bool:
    """Discovers the current Morning MCP tunnel URL the same way AIHandler
    does (MorningMcpLocator, the shared status file - never a direct import
    of morning-mcp-app code) and calls its deliberately-minimal /is_alive
    endpoint (not /health - that would trigger a real, non-free Morning API
    call on morning-mcp-app's side on every single probe here)."""
    server_url = MorningMcpLocator(mcp_config).current_server_url()
    if not server_url:
        return False
    base_url = server_url[: -len("/mcp")] if server_url.endswith("/mcp") else server_url
    try:
        response = requests.get(f"{base_url}/is_alive", timeout=CHECK_TIMEOUT_SECONDS)
        return response.status_code == 200
    except requests.RequestException:
        logger.warning("check_morning_connectivity_via_tunnel: failed", exc_info=True)
        return False


def check_chromadb_connectivity(memory_manager) -> bool:
    """memory_manager.client is the real ChromaDB client (see
    MemoryManager.__init__) - .heartbeat() is ChromaDB's own native, cheap
    liveness call (confirmed against the real installed client, bugfix-043
    design session)."""
    try:
        memory_manager.client.heartbeat()
        return True
    except Exception:  # noqa: BLE001
        logger.warning("check_chromadb_connectivity: failed", exc_info=True)
        return False


def check_log_freshness(log_path: Path, max_age_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> bool:
    """True iff `log_path` exists and was modified within the last
    `max_age_seconds` - paired with write_heartbeat_log's periodic write so
    a genuinely idle app never false-positives (see that function)."""
    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) <= max_age_seconds


def write_heartbeat_log() -> None:
    """Writes one lightweight log line every HEARTBEAT_INTERVAL_SECONDS
    (see start_heartbeat_thread), independent of real request traffic, so
    check_log_freshness has something to observe even during a genuinely
    idle period. A real break in the logging pipeline (or the disk/volume
    underneath it) means this line silently fails to land too - exactly
    what the freshness check is meant to catch."""
    logger.info("[heartbeat] logging pipeline alive")


def resolve_log_path(logs_dir: str = "logs", log_filename: str = "denidin.log") -> Path:
    """Resolves the real on-disk log file path the same way
    utils.logger.setup_logger does."""
    return Path(logs_dir) / log_filename


def start_heartbeat_thread(interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> threading.Thread:
    """Daemon background thread, same rationale as morning-mcp-app's own
    start_heartbeat_thread (bugfix-043) - one trivial periodic timer, not
    worth a scheduling dependency."""

    def _loop() -> None:
        while True:
            time.sleep(interval_seconds)
            write_heartbeat_log()

    thread = threading.Thread(target=_loop, name="heartbeat-writer", daemon=True)
    thread.start()
    return thread


def build_health_check_fns(
    ai_client=None,
    green_api=None,
    mcp_config: Optional[dict] = None,
    memory_manager=None,
    log_path: Optional[Path] = None,
) -> Dict[str, Callable[[], bool]]:
    """Binds each live object to its check via closure, once, producing the
    zero-arg callables start_health_server actually calls per request. Any
    argument left None simply omits that check from the response (same
    "optional, backward-compatible" shape as morning-mcp-app's /health) -
    lets tests/callers exercise a subset without needing every dependency."""
    checks: Dict[str, Callable[[], bool]] = {}
    if ai_client is not None:
        checks["ai_connectivity"] = lambda: check_ai_connectivity(ai_client)
    if green_api is not None:
        checks["whatsapp_connectivity"] = lambda: check_whatsapp_connectivity(green_api)
    if mcp_config is not None:
        checks["morning_connectivity_via_tunnel"] = lambda: check_morning_connectivity_via_tunnel(mcp_config)
    if memory_manager is not None:
        checks["chromadb_connectivity"] = lambda: check_chromadb_connectivity(memory_manager)
    if log_path is not None:
        checks["logs_writing"] = lambda: check_log_freshness(log_path)
    return checks


def _make_handler_class(check_fns: Dict[str, Callable[[], bool]]) -> type:
    """Builds a BaseHTTPRequestHandler subclass closing over check_fns -
    ThreadingHTTPServer instantiates a fresh handler per request, so the
    checks have to be reachable via a class attribute, not a constructor arg."""

    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return

            body = {"app_up": "success"}
            all_ok = True
            for name, check_fn in check_fns.items():
                try:
                    ok = check_fn()
                except Exception:  # noqa: BLE001 - a check that raises is a failed check, not a 500
                    logger.warning("health check %r raised", name, exc_info=True)
                    ok = False
                body[name] = "success" if ok else "fail"
                all_ok = all_ok and ok
            body["status"] = "ok" if all_ok else "fail"

            payload = json.dumps(body).encode("utf-8")
            self.send_response(200 if all_ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args) -> None:  # noqa: D102 - silence default stderr access logging
            pass

    return _HealthHandler


def start_health_server(port: int, check_fns: Dict[str, Callable[[], bool]]) -> ThreadingHTTPServer:
    """Starts the /health server bound to 127.0.0.1 only (bugfix-043 design:
    "local http health endpoint available only at localhost") in a daemon
    background thread, and returns the server object (tests/callers that
    need to shut it down explicitly can call .shutdown())."""
    handler_cls = _make_handler_class(check_fns)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    logger.info("Health check server listening on 127.0.0.1:%s", port)
    return server
