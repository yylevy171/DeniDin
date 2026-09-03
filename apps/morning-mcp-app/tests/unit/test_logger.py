"""
Unit tests for the logging utility.

Feature 070 (US5) rewrote the handler model: one handler set on the **root**
logger (not one per module), `TimedRotatingFileHandler(backupCount=0)` + gzip
instead of size-based `RotatingFileHandler` with numbered backups. The
rotation/retention specifics live in `test_logger_retention.py`; this file keeps
the format / level-filtering / version-stamp / directory-creation coverage,
adapted to the root-handler model.
"""
import logging
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from denidin_mcp_morning.utils.logger import _our_file_handler, get_logger, setup_logger


@pytest.fixture
def isolated_root():
    root = logging.getLogger()
    saved_handlers, saved_filters, saved_level = root.handlers[:], root.filters[:], root.level
    root.handlers, root.filters = [], []
    try:
        yield root
    finally:
        for h in root.handlers[:]:
            h.close()
            root.removeHandler(h)
        root.handlers, root.filters = saved_handlers, saved_filters
        root.setLevel(saved_level)


@pytest.fixture
def temp_logs_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _flush_root():
    for h in logging.getLogger().handlers:
        h.flush()


def _read_log(logs_path: str) -> str:
    with open(os.path.join(logs_path, "morning-mcp.log"), "r", encoding="utf-8") as f:
        return f.read()


class TestLogger:
    def test_logger_creates_logs_directory_if_missing(self, isolated_root, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, "logs")
        if os.path.exists(logs_path):
            shutil.rmtree(logs_path)
        setup_logger("test_logger", logs_dir=logs_path)
        assert os.path.isdir(logs_path)

    def test_file_handler_writes_to_logs_file(self, isolated_root, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger(f"test_file_{uuid.uuid4().hex[:8]}", logs_dir=logs_path, log_level="INFO")
        msg = "Test log message for file handler"
        logger.info(msg)
        _flush_root()
        assert msg in _read_log(logs_path)

    def test_console_handler_outputs_to_stderr(self, isolated_root, temp_logs_dir, capsys):
        logger = setup_logger("test_console", logs_dir=temp_logs_dir, log_level="INFO")
        logger.info("Test console output")
        assert "Test console output" in capsys.readouterr().err

    def test_root_has_one_file_and_one_stream_handler(self, isolated_root, temp_logs_dir):
        for i in range(3):
            setup_logger(f"test_handlers_{i}", logs_dir=temp_logs_dir, log_level="INFO")
        assert _our_file_handler(isolated_root) is not None
        # pytest keeps its own capture handlers on root; count only plain StreamHandlers
        streams = [h for h in isolated_root.handlers if type(h) is logging.StreamHandler]
        assert len(streams) == 1  # no per-name stacking

    def test_log_format_includes_timestamp_name_level_message(self, isolated_root, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger("test_format", logs_dir=logs_path, log_level="INFO")
        logger.info("Format test message")
        _flush_root()
        line = _read_log(logs_path)
        assert "INFO" in line
        assert "Format test message" in line
        assert "test_format" in line
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line)

    def test_log_level_parameter_controls_info_vs_debug_verbosity(self, isolated_root, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, "logs")
        info_logger = setup_logger("test_info", logs_dir=logs_path, log_level="INFO")
        info_logger.debug("This is a DEBUG message")
        info_logger.info("This is an INFO message")
        _flush_root()
        content = _read_log(logs_path)
        assert "This is an INFO message" in content
        assert "This is a DEBUG message" not in content

    def test_info_logs_messages_and_errors_only(self, isolated_root, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger("test_info_only", logs_dir=logs_path, log_level="INFO")
        logger.debug("Debug message - should not appear")
        logger.info("Info message - should appear")
        logger.warning("Warning message - should appear")
        logger.error("Error message - should appear")
        _flush_root()
        content = _read_log(logs_path)
        assert "Debug message" not in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_get_logger_returns_configured_logger(self, isolated_root, temp_logs_dir):
        logger = get_logger("test_get", logs_dir=temp_logs_dir, log_level="INFO")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_get"
        assert logger.propagate is True


class TestVersionFilter:
    """Feature 034 (REQ-VER-003): every log line carries the app's current version."""

    @pytest.fixture
    def temp_version_file(self):
        d = tempfile.mkdtemp()
        yield Path(d) / "VERSION"
        shutil.rmtree(d, ignore_errors=True)

    def test_log_line_includes_version_from_version_file(self, isolated_root, temp_logs_dir, temp_version_file):
        temp_version_file.write_text("1.4.2\n")
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger(f"test_version_{uuid.uuid4().hex[:8]}", logs_dir=logs_path,
                              log_level="INFO", version_file=temp_version_file)
        logger.info("hello")
        _flush_root()
        content = _read_log(logs_path)
        assert "[v1.4.2]" in content and "hello" in content

    def test_log_line_falls_back_to_unknown_when_version_file_missing(
        self, isolated_root, temp_logs_dir, temp_version_file
    ):
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger(f"test_version_missing_{uuid.uuid4().hex[:8]}", logs_dir=logs_path,
                              log_level="INFO", version_file=temp_version_file)
        logger.info("hello")
        _flush_root()
        assert "[vunknown]" in _read_log(logs_path)

    def test_log_line_falls_back_to_unknown_when_version_file_malformed(
        self, isolated_root, temp_logs_dir, temp_version_file
    ):
        temp_version_file.write_text("not-a-version-at-all!!\n")
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger(f"test_version_malformed_{uuid.uuid4().hex[:8]}", logs_dir=logs_path,
                              log_level="INFO", version_file=temp_version_file)
        logger.info("hello")
        _flush_root()
        assert "[vunknown]" in _read_log(logs_path)

    def test_log_line_accepts_preinit_placeholder_verbatim(
        self, isolated_root, temp_logs_dir, temp_version_file
    ):
        temp_version_file.write_text("0.0.0-preinit\n")
        logs_path = os.path.join(temp_logs_dir, "logs")
        logger = setup_logger(f"test_version_preinit_{uuid.uuid4().hex[:8]}", logs_dir=logs_path,
                              log_level="INFO", version_file=temp_version_file)
        logger.info("hello")
        _flush_root()
        assert "[v0.0.0-preinit]" in _read_log(logs_path)

    def test_get_logger_also_includes_version(self, temp_version_file, caplog):
        # get_logger's test-environment shortcut attaches the version Filter to the
        # child logger itself (records are initiated there), so it survives even
        # though the child has no handlers of its own.
        temp_version_file.write_text("2.0.0\n")
        logger_name = f"test_get_version_{uuid.uuid4().hex[:8]}"
        logger = get_logger(logger_name, log_level="INFO", version_file=temp_version_file)
        with caplog.at_level("INFO", logger=logger_name):
            logger.info("via get_logger")
        assert len(caplog.records) == 1
        assert caplog.records[0].version == "2.0.0"
