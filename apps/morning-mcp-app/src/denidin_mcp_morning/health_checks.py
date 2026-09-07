"""Health-check primitives for the /health and /is_alive endpoints (bugfix-043).

Kept as small, dependency-free, independently testable functions so
server.py's route handlers stay thin wiring - each function here answers
exactly one question and is exercised directly in
tests/unit/test_health_checks.py, without needing a running ASGI app.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from .morning_client import MorningClient
from .utils.logger import get_logger

logger = get_logger(__name__)

# How often the heartbeat writer (see write_heartbeat_log) is expected to
# run - the log-freshness check's default staleness budget matches this
# exactly, so a single missed heartbeat doesn't false-positive but two in a
# row (a real stuck logging pipeline) does.
HEARTBEAT_INTERVAL_SECONDS = 600  # 10 minutes


def check_morning_connectivity(client: MorningClient) -> bool:
    """Verifies real, live connectivity to Morning's own API - not just that
    this process has a MorningClient object.

    Deliberately mints/validates a real auth token (client.auth.get_token())
    rather than a document-search call: it's the cheapest possible real round
    trip to Morning's actual infrastructure (confirms the auth endpoint is
    reachable and the configured credentials are valid) without guessing at
    document-search payload shape or risking pulling back real data on every
    health check.
    """
    try:
        client.auth.get_token()
        return True
    except Exception:  # noqa: BLE001 - any failure here means "not healthy", full stop
        logger.warning("check_morning_connectivity: failed", exc_info=True)
        return False


def check_log_freshness(log_path: Path, max_age_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> bool:
    """True iff `log_path` exists and was modified within the last
    `max_age_seconds`.

    Paired with write_heartbeat_log's periodic write (every
    HEARTBEAT_INTERVAL_SECONDS regardless of real app activity) so this never
    false-positives during a genuinely idle period - only a real break in the
    logging pipeline (or the underlying disk/volume) leaves the file stale.
    """
    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) <= max_age_seconds


def write_heartbeat_log() -> None:
    """Writes one lightweight log line - called on a periodic scheduler
    (see server.py's APScheduler wiring), independent of real request
    traffic, purely so check_log_freshness has something to observe even
    during a genuinely idle period. A real break in the logging pipeline
    (or the disk/volume underneath it) means this line silently fails to
    land too, which is exactly what the freshness check is meant to catch."""
    logger.info("[heartbeat] logging pipeline alive")


def resolve_log_path(logs_dir: str, log_filename: str = "morning-mcp.log") -> Path:
    """Resolves the real on-disk log file path the same way
    utils.logger.setup_logger does, so the freshness check looks at the
    actual file being written to, not a guessed path."""
    return Path(logs_dir) / log_filename


def start_heartbeat_thread(interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> threading.Thread:
    """Starts a daemon background thread that calls write_heartbeat_log()
    every `interval_seconds`, for the life of the process.

    A plain daemon thread rather than pulling in a scheduling dependency
    (e.g. APScheduler, already used elsewhere in this project but not
    currently a dependency of this app) - this is one trivial periodic
    timer, not a real job scheduler with multiple jobs/cron semantics, so a
    new dependency isn't warranted. Daemon=True so it never blocks process
    shutdown.
    """

    def _loop() -> None:
        while True:
            time.sleep(interval_seconds)
            write_heartbeat_log()

    thread = threading.Thread(target=_loop, name="heartbeat-writer", daemon=True)
    thread.start()
    return thread
