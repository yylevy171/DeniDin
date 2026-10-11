"""Logging setup for webapp-backend (Feature 068).

Small on purpose - one rotating file handler + console, on the ``webapp_backend`` logger that
``server.py`` and ``health_checks.py`` already use. The file exists so ``/health``'s
``logs_writing`` check (paired with the heartbeat writer) has a real artifact to observe, the
same way denidin-app's and morning-mcp-app's own health checks do.
"""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = "logs"
LOG_FILENAME = "webapp-backend.log"

# apps/webapp/VERSION - parents: [0]=webapp_backend [1]=src [2]=backend [3]=webapp
_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


# Every line carries [v<version>] - same convention as denidin-app / morning-mcp-app (Feature
# 034 REQ-VER-003), and what deploy_release*.sh's fast "right image was loaded" check greps for.
# The version can't change mid-process, so it's baked into the format string at setup, no filter.
_FORMAT = f"%(asctime)s - [v{_read_version()}] - %(name)s - %(levelname)s - %(message)s"


def resolve_log_path(log_dir: str = DEFAULT_LOG_DIR, log_filename: str = LOG_FILENAME) -> Path:
    """The real on-disk path setup_logging writes to - health_checks.check_log_freshness looks
    at exactly this."""
    return Path(log_dir) / log_filename


def setup_logging(log_dir: str = DEFAULT_LOG_DIR, level: str = "INFO") -> Path:
    """Attach a daily-rotating file handler (14 days kept) + a console handler to the
    ``webapp_backend`` logger. Idempotent - safe to call more than once (won't stack handlers).
    Returns the resolved log-file path."""
    path = resolve_log_path(log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("webapp_backend")
    root.setLevel(level.upper())
    root.propagate = False

    have_file = any(isinstance(h, TimedRotatingFileHandler) for h in root.handlers)
    have_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, TimedRotatingFileHandler)
        for h in root.handlers
    )
    formatter = logging.Formatter(_FORMAT)

    if not have_file:
        file_handler = TimedRotatingFileHandler(
            path, when="midnight", backupCount=14, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if not have_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    return path
