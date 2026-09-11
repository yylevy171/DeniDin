"""Health-check primitives for webapp-backend's ``/health`` endpoint (Feature 068).

Same shape and rationale as ``apps/denidin-app/src/services/health_server.py`` and
``apps/morning-mcp-app/src/denidin_mcp_morning/health_checks.py`` (bugfix-043): every check is a
small, dependency-free, independently testable function that answers exactly one question about
a real, live resource - never "does this process hold an object", always "is the thing that
object needs actually reachable right now". ``build_health_check_fns`` binds each live value to
its check once (closure) and produces the zero-arg callables ``server.py``'s ``/health`` handler
calls per request, so the wiring and the check logic are testable separately
(``tests/unit/test_health_checks.py``).

webapp-backend is a read-only viewer. Its real dependencies are: (a) denidin-app's data root,
mounted read-only off disk - if that mount breaks, the UI silently shows nothing; (b) the
password-hash file, mounted read-only - if it breaks, every login fails; (c) its own in-memory
ledger index, built once at startup from that data root; (d) its own logging pipeline. There is
no OpenAI / Green API / Morning / ChromaDB dependency here - the other two apps' checks for
those have no webapp equivalent.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

# Matches the other two apps' convention (bugfix-043) - the heartbeat writer runs on this
# interval and the log-freshness check's default staleness budget matches it exactly, so a
# single missed heartbeat doesn't false-positive but two in a row (a real stuck logging
# pipeline) does.
HEARTBEAT_INTERVAL_SECONDS = 600  # 10 minutes

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

# Same logger name as the rest of the app, so a check that logs a failure lands in the same file.
logger = logging.getLogger("webapp_backend")


def check_denidin_data_readable(data_root: str) -> bool:
    """The denidin-app data root is mounted read-only into this container. True iff it's a real
    directory AND its ``events/`` subdir (the ledger source) can actually be listed right now -
    a broken/dropped bind mount typically leaves the path present but ``iterdir()`` raising, or
    the ``events/`` child gone."""
    try:
        root = Path(data_root)
        if not root.is_dir():
            logger.warning("check_denidin_data_readable: %s is not a directory", data_root)
            return False
        events = root / "events"
        if not events.is_dir():
            logger.warning("check_denidin_data_readable: %s/events missing", data_root)
            return False
        # Force an actual read of the directory - is_dir() alone can be satisfied by a stale
        # mount entry.
        for _ in events.iterdir():
            break
        return True
    except OSError:
        logger.warning("check_denidin_data_readable: failed", exc_info=True)
        return False


def check_password_hash_readable(hash_file: str) -> bool:
    """Fresh read of the password-hash file every probe - NOT a look at the PasswordVerifier
    object built at startup, which would never notice the file's own mount breaking or the file
    being replaced with garbage. True iff it exists, is readable, and holds a 64-hex-char digest
    (the one shape auth.hash_password produces)."""
    try:
        raw = Path(hash_file).read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("check_password_hash_readable: cannot read %s", hash_file, exc_info=True)
        return False
    if not _HEX64.match(raw):
        logger.warning("check_password_hash_readable: %s is not 64 hex chars", hash_file)
        return False
    return True


def check_ledger_index(reader) -> bool:
    """Exercises the real row-shaping path over the in-memory ledger index (built once at
    startup from the data root). ``list_event_rows`` copies the index and formats each row -
    cheap, no disk I/O - so a raise here means the index never built or the parse/format code
    is broken, not just that the data dir is momentarily slow."""
    try:
        result = reader.list_event_rows(1)
        return isinstance(result, dict)
    except Exception:  # noqa: BLE001 - any raise is a failed check, not a 500
        logger.warning("check_ledger_index: failed", exc_info=True)
        return False


def check_log_freshness(log_path: Path, max_age_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> bool:
    """True iff ``log_path`` exists and was modified within the last ``max_age_seconds`` -
    paired with ``write_heartbeat_log``'s periodic write so a genuinely idle backend never
    false-positives."""
    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) <= max_age_seconds


def write_heartbeat_log() -> None:
    """One lightweight log line every ``HEARTBEAT_INTERVAL_SECONDS`` (see
    ``start_heartbeat_thread``), independent of request traffic, so ``check_log_freshness`` has
    something to observe even during a genuinely idle period. A real break in the logging
    pipeline (or the disk/volume underneath it) means this line silently fails to land too -
    exactly what the freshness check is meant to catch."""
    logger.info("[heartbeat] logging pipeline alive")


def start_heartbeat_thread(interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS) -> threading.Thread:
    """Daemon background thread, same rationale as the other two apps' own
    ``start_heartbeat_thread`` (bugfix-043) - one trivial periodic timer, not worth a
    scheduling dependency."""

    def _loop() -> None:
        while True:
            time.sleep(interval_seconds)
            write_heartbeat_log()

    thread = threading.Thread(target=_loop, name="heartbeat-writer", daemon=True)
    thread.start()
    return thread


def build_health_check_fns(
    denidin_data_root: Optional[str] = None,
    password_hash_file: Optional[str] = None,
    ledger_reader=None,
    log_path: Optional[Path] = None,
) -> Dict[str, Callable[[], bool]]:
    """Binds each live value to its check via closure, once, producing the zero-arg callables
    ``server.py``'s ``/health`` handler actually calls per request. Any argument left None
    simply omits that check from the response (same "optional, backward-compatible" shape as
    the other two apps' /health)."""
    checks: Dict[str, Callable[[], bool]] = {}
    if denidin_data_root is not None:
        checks["denidin_data_readable"] = lambda: check_denidin_data_readable(denidin_data_root)
    if password_hash_file is not None:
        checks["password_hash_readable"] = lambda: check_password_hash_readable(password_hash_file)
    if ledger_reader is not None:
        checks["ledger_index"] = lambda: check_ledger_index(ledger_reader)
    if log_path is not None:
        checks["logs_writing"] = lambda: check_log_freshness(log_path)
    return checks
