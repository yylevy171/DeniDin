"""
Unit tests for the logging utility (Phase 5, T019).
Adapted from apps/denidin-app/tests/unit/test_logger.py — same contract,
default log filename is 'morning-mcp.log' instead of 'denidin.log'.
"""
import os
import re
import shutil
import tempfile
import uuid

import pytest
from logging.handlers import RotatingFileHandler

from denidin_mcp_morning.utils.logger import get_logger, setup_logger


class TestLogger:
    """Test suite for logger utility."""

    @pytest.fixture
    def temp_logs_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_logger_creates_logs_directory_if_missing(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')
        if os.path.exists(logs_path):
            shutil.rmtree(logs_path)

        setup_logger('test_logger', logs_dir=logs_path)

        assert os.path.exists(logs_path)
        assert os.path.isdir(logs_path)

    def test_file_handler_writes_to_logs_file(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger_name = f'test_file_{uuid.uuid4().hex[:8]}'
        logger = setup_logger(logger_name, logs_dir=logs_path, log_level='INFO')

        test_message = 'Test log message for file handler'
        logger.info(test_message)

        for handler in logger.handlers:
            handler.flush()

        log_file = os.path.join(logs_path, 'morning-mcp.log')
        assert os.path.exists(log_file)

        with open(log_file, 'r') as f:
            content = f.read()
        assert test_message in content

    def test_console_handler_outputs_to_stderr(self, temp_logs_dir, capsys):
        logger = setup_logger('test_console', logs_dir=temp_logs_dir, log_level='INFO')

        test_message = 'Test console output'
        logger.info(test_message)

        captured = capsys.readouterr()
        assert test_message in captured.err

    def test_log_format_includes_timestamp_name_level_message(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_format', logs_dir=logs_path, log_level='INFO')

        test_message = 'Format test message'
        logger.info(test_message)

        log_file = os.path.join(logs_path, 'morning-mcp.log')
        with open(log_file, 'r') as f:
            log_line = f.read()

        assert 'INFO' in log_line
        assert test_message in log_line
        assert 'test_format' in log_line
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, log_line)

    def test_log_level_parameter_controls_info_vs_debug_verbosity(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')

        info_logger = setup_logger('test_info', logs_dir=logs_path, log_level='INFO')
        info_logger.debug('This is a DEBUG message')
        info_logger.info('This is an INFO message')

        log_file = os.path.join(logs_path, 'morning-mcp.log')
        with open(log_file, 'r') as f:
            content = f.read()

        assert 'This is an INFO message' in content
        assert 'This is a DEBUG message' not in content

        os.unlink(log_file)

        debug_logger = setup_logger('test_debug', logs_dir=logs_path, log_level='DEBUG')
        debug_logger.debug('This is a DEBUG message')
        debug_logger.info('This is an INFO message')

        with open(log_file, 'r') as f:
            content = f.read()

        assert 'This is a DEBUG message' in content
        assert 'This is an INFO message' in content

    def test_get_logger_returns_configured_logger(self, temp_logs_dir):
        import logging as _logging

        logger = get_logger('test_get', logs_dir=temp_logs_dir, log_level='INFO')

        assert logger is not None
        assert isinstance(logger, _logging.Logger)
        assert logger.name == 'test_get'


class TestLogRotation:
    """Test suite for log rotation."""

    @pytest.fixture
    def temp_logs_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rotating_file_handler_maxbytes_10mb_default(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_10mb', logs_dir=logs_path, log_level='INFO')

        rotating_handler = None
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                rotating_handler = handler
                break

        assert rotating_handler is not None, "RotatingFileHandler not found"
        assert rotating_handler.maxBytes == 10 * 1024 * 1024

    def test_backup_count_creates_backup_files_on_rotation(self, temp_logs_dir):
        logs_path = os.path.join(temp_logs_dir, 'logs')

        logger = setup_logger(
            'test_backups',
            logs_dir=logs_path,
            log_level='INFO',
            max_bytes=500,
            backup_count=5
        )

        large_message = 'X' * 100
        for i in range(50):
            logger.info(f'Log {i}: {large_message}')

        log_file = os.path.join(logs_path, 'morning-mcp.log')
        assert os.path.exists(log_file)

        backup_files_found = sum(
            1 for i in range(1, 6) if os.path.exists(f"{log_file}.{i}")
        )
        assert backup_files_found >= 1, "No backup files created during rotation"
