"""
Logging utility for the morning-mcp-app.
Provides file and console logging with time-based rotation and gzip retention.

Feature 070 (US5): one handler set, on the **root** logger.
Every module calls `get_logger(__name__)`; each returns a bare child logger with
`propagate=True` and no handlers of its own. `setup_logger` attaches the single
file handler + the single `StreamHandler` to `logging.getLogger()` exactly once
(guarded against re-stacking). This designs out the pre-070 multi-handler
rotation race: previously each module attached its OWN
`RotatingFileHandler(10MB, backupCount=5)` to the same file with
`propagate=False`, so a rollover in one handler tripped stale-fd cascades in the
others -> tiny out-of-order fragments, history lost. See
`specs/in-progress/070-rolling-memory-window/contracts/logger-retention.md`.

Rotation: `TimedRotatingFileHandler(when=<rotation_when>, backupCount=<backup_count>)`.
`backup_count=0` (the default) => the handler NEVER prunes a rotated segment.
Each rotated segment is gzip-compressed by `_gzip_rotator` (`namer` appends
`.gz`). The rotator is fail-safe: if compression raises, the rotated PLAINTEXT
segment is left in place (never unlinked) and the error re-raised - a segment is
never lost. Within one process `logging`'s handler lock serialises `emit`
against `doRollover`, so a concurrent log call blocks until the swap completes
and then writes to the fresh base file - rotation is lossless.

**This module is byte-mirrored with `apps/denidin-app/src/utils/logger.py` for
the shared core (`_gzip_namer`, `_gzip_rotator`,
`setup_logger`, `get_logger`, `reconfigure_file_rotation`, the formatter/filter
classes).** Documented per-app deltas: the module docstring, the `log_filename`
default, `DEFAULT_VERSION_FILE`, the `log_level` default, and this app's extra `reconfigure_package_log_level`
(a morning-mcp-only import-ordering fix). Keep the core identical.

Feature 034 (REQ-VER-003): every log line carries the app's current version, read
once from VERSION and stamped onto every LogRecord via a Filter on the root
logger, so it survives both `setup_logger`'s handlers and `get_logger`'s
test-environment shortcut.

bugfix-037: log timestamps are Israel local time, with an explicit offset on
every line (LocalTimeFormatter), so a line states its own zone rather than
relying on the reader knowing the process's TZ.
"""
import gzip
import logging
import os
import re
import shutil
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Union

from .time_utils import LOCAL_TZ

DEFAULT_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"

_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+')

# %z renders the real offset (+0300 in IDT, +0200 in IST), so a log line states its own
# zone instead of relying on the reader knowing which one it was written in.
LOCAL_LOG_DATEFMT = '%Y-%m-%d %H:%M:%S%z'

def _our_file_handler(logger: logging.Logger):
    """The root's own gzip-rotating file handler, if setup_logger has attached
    one and it is still present. Identity is `rotator is _gzip_rotator` - this
    distinguishes our handler set from pytest's plain root handlers and survives
    a conftest fixture that strips/re-adds handlers between tests."""
    for handler in logger.handlers:
        if isinstance(handler, TimedRotatingFileHandler) and handler.rotator is _gzip_rotator:
            return handler
    return None


class LocalTimeFormatter(logging.Formatter):
    """Formats every record's timestamp in Asia/Jerusalem (bugfix-037).

    A Formatter subclass, not a reassignment of `logging.Formatter.converter` -
    `converter` works on `time.struct_time`, which cannot render a real UTC offset
    (`%z` on one reports the *system* zone, which is exactly the ambiguity this
    replaces), and patching it at runtime would be monkey-patching (CONSTITUTION §XVII).
    """

    def formatTime(self, record: logging.LogRecord, datefmt: Union[str, None] = None) -> str:
        local_dt = datetime.fromtimestamp(record.created, tz=LOCAL_TZ)
        return local_dt.strftime(datefmt or LOCAL_LOG_DATEFMT)


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


def _ensure_version_filter(target: Union[logging.Logger, logging.Handler],
                           version_file: Union[str, Path]) -> None:
    """Idempotent: attaches a _VersionFilter to `target` (a Logger or a Handler)
    unless one is already there.

    On a Handler (the production path) rather than only a Logger, because a
    `_VersionFilter` on the root *logger* is skipped when a child logger's record
    propagates up - filters run at the logger where logging was initiated, not at
    ancestors - so `%(version)s` would be unresolved. Handler-level filters DO run
    during propagation. The test-environment shortcut still filters on the child
    logger itself (records are initiated there)."""
    if any(isinstance(f, _VersionFilter) for f in target.filters):
        return
    target.addFilter(_VersionFilter(read_version(Path(version_file))))


def _gzip_namer(name: str) -> str:
    """TimedRotatingFileHandler.namer: the rotated segment gets a `.gz` suffix."""
    return name + '.gz'


def _gzip_rotator(source: str, dest: str) -> None:
    """TimedRotatingFileHandler.rotator: gzip-compress the just-rotated plaintext
    segment `source` to `dest` (already `.gz`-suffixed by the namer), then remove
    the plaintext intermediate.

    Fail-safe (contract §4): if compression raises, the plaintext segment is left
    in place (NOT removed) and the error re-raised - a rotated segment is never
    deleted before a readable compressed copy exists. The `os.remove` here is of a
    *log* file the handler itself just produced, not a message/session file -
    outside the US3 no-delete scope.
    """
    try:
        with open(source, 'rb') as src_f, gzip.open(dest, 'wb') as dst_f:
            shutil.copyfileobj(src_f, dst_f)
    except Exception:
        logging.getLogger(__name__).exception(
            'log rotation gzip failed; keeping plaintext segment %s', source
        )
        raise
    os.remove(source)


def _build_file_handler(  # pylint: disable=too-many-positional-arguments
    log_path: str,
    log_level: str,
    rotation_when: str,
    backup_count: int,
    formatter: logging.Formatter,
    version_file: Union[str, Path],
) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        log_path,
        when=rotation_when,
        backupCount=backup_count,
        encoding='utf-8',
    )
    handler.namer = _gzip_namer
    handler.rotator = _gzip_rotator
    handler.setLevel(getattr(logging, log_level))
    handler.setFormatter(formatter)
    _ensure_version_filter(handler, version_file)
    return handler


def _formatter() -> LocalTimeFormatter:
    return LocalTimeFormatter(
        '%(asctime)s - [v%(version)s] - %(name)s - %(levelname)s - %(message)s',
        datefmt=LOCAL_LOG_DATEFMT,
    )


def setup_logger(
    name: str,
    logs_dir: str = 'logs',
    log_filename: str = 'morning-mcp.log',
    log_level: str = 'INFO',  # per-app delta
    *,
    rotation_when: str = 'midnight',
    backup_count: int = 0,
    version_file: Union[str, Path] = DEFAULT_VERSION_FILE
) -> logging.Logger:
    """
    Configure the **root** logger's single handler set (file + console) once, and
    return `logging.getLogger(name)` as a bare child (`propagate=True`, no own
    handlers).

    Args:
        name: Name of the child logger to return.
        logs_dir: Directory to store log files (default: 'logs').
        log_filename: Name of the log file (default: 'morning-mcp.log').
        log_level: Logging level ('NOTSET', 'DEBUG', 'INFO', ...). 'NOTSET' (the
                   default) makes the child logger defer to the root's effective level.
        rotation_when: `TimedRotatingFileHandler(when=...)` unit (default 'midnight').
        backup_count: `TimedRotatingFileHandler(backupCount=...)`. 0 (default) =>
                      never prune a rotated segment.
        version_file: Path to the VERSION file to stamp onto every log line
                      (Feature 034, REQ-VER-003).

    Returns:
        The child logger `logging.getLogger(name)`.
    """
    log_path = os.path.join(logs_dir, log_filename)
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()

    # Guard: attach our handler set exactly once. A second call (any module's
    # import-time get_logger) is a no-op on the root; it still returns its child.
    if _our_file_handler(root_logger) is None:
        formatter = _formatter()

        root_logger.addHandler(
            _build_file_handler(
                log_path, log_level, rotation_when, backup_count, formatter, version_file
            )
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(formatter)
        _ensure_version_filter(console_handler, version_file)
        root_logger.addHandler(console_handler)

    child = logging.getLogger(name)
    child.setLevel(getattr(logging, log_level))
    child.propagate = True
    return child


def reconfigure_file_rotation(
    rotation_when: str,
    backup_count: int,
    *,
    logs_dir: str = 'logs',
    log_filename: str = 'morning-mcp.log',
    log_level: str = 'INFO',  # per-app delta
    version_file: Union[str, Path] = DEFAULT_VERSION_FILE,
) -> None:
    """Swap the root logger's file handler for one built with the real
    `config.logging` values.

    Needed because every module calls `get_logger(__name__)` at import time -
    before `denidin.py` has loaded config - so the first `setup_logger` runs with
    the built-in defaults ('midnight' / 0). Call this once in `denidin.py`
    immediately after config load. If config matches the defaults (the common
    case) this still rebuilds the handler harmlessly. A no-op under pytest (root
    handlers are pytest's; our sentinel is absent).
    """
    root_logger = logging.getLogger()
    existing = _our_file_handler(root_logger)
    if existing is None:
        setup_logger(
            'denidin_mcp_morning', logs_dir, log_filename, log_level,
            rotation_when=rotation_when, backup_count=backup_count, version_file=version_file,
        )
        return

    root_logger.removeHandler(existing)
    existing.close()
    log_path = os.path.join(logs_dir, log_filename)
    root_logger.addHandler(
        _build_file_handler(
            log_path, log_level, rotation_when, backup_count, _formatter(), version_file
        )
    )


def get_logger(
    name: str,
    logs_dir: str = 'logs',
    log_filename: str = 'morning-mcp.log',
    log_level: str = 'INFO',  # per-app delta
    version_file: Union[str, Path] = DEFAULT_VERSION_FILE
) -> logging.Logger:
    """
    Get or create a configured child logger.

    In a test environment (root logger already has handlers - pytest's), returns
    `logging.getLogger(name)` reusing those handlers. In production, delegates to
    `setup_logger` which configures the root once.

    Args:
        name: Name of the logger.
        logs_dir: Directory to store log files (default: 'logs').
        log_filename: Name of the log file (default: 'morning-mcp.log').
        log_level: Logging level ('NOTSET', 'DEBUG', 'INFO', ...). 'NOTSET' (the
                   default) makes the logger defer to the root's level.
        version_file: Path to the VERSION file to stamp onto every log line
                      (Feature 034, REQ-VER-003). Attached even in the
                      test-environment shortcut, which bypasses setup_logger.

    Returns:
        Configured child logger.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers and _our_file_handler(root_logger) is None:
        # Test environment - root configured by pytest's hook, not by us.
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level))
        _ensure_version_filter(logger, version_file)
        return logger

    return setup_logger(name, logs_dir, log_filename, log_level, version_file=version_file)


def reconfigure_package_log_level(level_name: str, package_prefix: str = 'denidin_mcp_morning') -> None:
    """Retroactively set the level of every already-created logger under
    `package_prefix`, plus the root logger's own handlers, to `level_name`.

    Import-ordering fix (found 2026-08-12): every module calls `get_logger(__name__)`
    at IMPORT time (default level 'INFO'), before `main()` loads config and learns
    the real `config.mcp_log_level`. Post-Feature-070 the handlers live on the root
    logger (one set), so this walks the root's handlers too. Call once in `main()`
    right after `load_config()`.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    for name, logger_or_placeholder in list(logging.Logger.manager.loggerDict.items()):
        if not isinstance(logger_or_placeholder, logging.Logger):
            continue  # a logging.PlaceHolder, not a real logger - nothing to reconfigure
        if name != package_prefix and not name.startswith(package_prefix + '.'):
            continue
        logger_or_placeholder.setLevel(level)
        for handler in logger_or_placeholder.handlers:
            handler.setLevel(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)
