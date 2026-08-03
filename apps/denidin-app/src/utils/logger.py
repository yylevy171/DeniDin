"""
Logging utility for the DeniDin application.
Provides file and console logging with rotation.

Logging Strategy:
- Production/Normal run: All logs go to logs/denidin.log (default)
- Testing: Each test file logs to logs/test_logs/{test_filename}.log

Feature 034 (REQ-VER-003): every log line carries the app's current version, read once from
VERSION (not per-call - a version can't change mid-process, see
specs/in-progress/034-versioning-release-mgmt/research.md Decision 2) and stamped onto every
LogRecord via a Filter attached to the Logger object itself, so it survives both setup_logger()'s
own handlers and get_logger()'s test-environment shortcut (which reuses the root logger's already-
configured handlers instead of creating new ones).
"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union

DEFAULT_VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "VERSION"

_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+')


def read_version(version_file: Path) -> str:
    """Read the app's current version. Falls back to "unknown" for a missing or malformed
    VERSION file rather than raising - this is observability, not a startup precondition."""
    try:
        content = version_file.read_text(encoding='utf-8').strip()
    except OSError:
        return 'unknown'
    if _VERSION_PATTERN.match(content):
        return content
    return 'unknown'


class _VersionFilter(logging.Filter):
    """Stamps every LogRecord passing through this logger with its current version."""

    def __init__(self, version: str) -> None:
        super().__init__()
        self._version = version

    def filter(self, record: logging.LogRecord) -> bool:
        record.version = self._version
        return True


def _ensure_version_filter(logger: logging.Logger, version_file: Union[str, Path]) -> None:
    """Idempotent: attaches a _VersionFilter to `logger` unless one is already there."""
    if any(isinstance(f, _VersionFilter) for f in logger.filters):
        return
    logger.addFilter(_VersionFilter(read_version(Path(version_file))))


def setup_logger(
    name: str,
    logs_dir: str = 'logs',
    log_filename: str = 'denidin.log',
    log_level: str = 'NOTSET',
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    version_file: Union[str, Path] = DEFAULT_VERSION_FILE
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.

    Args:
        name: Name of the logger
        logs_dir: Directory to store log files (default: 'logs')
        log_filename: Name of the log file (default: 'denidin.log')
                     Tests should use 'test_logs/{test_name}.log'
        log_level: Logging level ('NOTSET', 'DEBUG', 'INFO', etc.). 'NOTSET'
                   (the default) makes the logger inherit its effective level
                   from the root logger instead of pinning its own level at
                   creation time.
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        version_file: Path to the VERSION file to stamp onto every log line
                      (Feature 034, REQ-VER-003). Defaults to this app's real VERSION file;
                      tests pass a scratch path.

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = os.path.join(logs_dir, log_filename)
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    _ensure_version_filter(logger, version_file)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - [v%(version)s] - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (outputs to stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # In production, prevent propagation to avoid duplicate output
    # In tests, propagation is enabled by conftest.py
    logger.propagate = False

    return logger


def get_logger(
    name: str,
    logs_dir: str = 'logs',
    log_filename: str = 'denidin.log',
    log_level: str = 'NOTSET',
    version_file: Union[str, Path] = DEFAULT_VERSION_FILE
) -> logging.Logger:
    """
    Get or create a configured logger.

    In test environment (when root logger has handlers), uses root logger configuration.
    In production, creates separate logger with file handlers.

    Args:
        name: Name of the logger
        logs_dir: Directory to store log files (default: 'logs')
        log_filename: Name of the log file (default: 'denidin.log')
        log_level: Logging level ('NOTSET', 'DEBUG', 'INFO', etc.). 'NOTSET'
                   (the default) makes the logger inherit its effective level
                   from the root logger instead of pinning its own level at
                   creation time.
        version_file: Path to the VERSION file to stamp onto every log line (Feature 034,
                      REQ-VER-003). Attached even in the test-environment shortcut below, since
                      that path bypasses setup_logger()'s own handler creation entirely.

    Returns:
        Configured logger instance
    """
    # Check if we're in a test environment (root logger configured by pytest hook)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Use root logger configuration (test environment)
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level))
        _ensure_version_filter(logger, version_file)
        return logger

    # Production environment - set up logger with file handlers
    return setup_logger(name, logs_dir, log_filename, log_level, version_file=version_file)
