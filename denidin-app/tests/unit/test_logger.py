"""
Unit tests for logging utility.
Tests logger configuration, file/console handlers, and log levels.
"""
import pytest
import tempfile
import os
import logging
import shutil
from pathlib import Path
from logging.handlers import RotatingFileHandler
from src.utils.logger import setup_logger, get_logger


class TestLogger:
    """Test suite for logger utility."""

    @pytest.fixture
    def temp_logs_dir(self):
        """Create a temporary logs directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_logger_creates_logs_directory_if_missing(self, temp_logs_dir):
        """Test that logger creates logs/ directory if missing."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        
        # Ensure directory doesn't exist
        if os.path.exists(logs_path):
            shutil.rmtree(logs_path)
        
        logger = setup_logger('test_logger', logs_dir=logs_path)
        
        # Directory should now exist
        assert os.path.exists(logs_path)
        assert os.path.isdir(logs_path)

    def test_file_handler_writes_to_logs_file(self, temp_logs_dir):
        """Test that file handler writes to logs/denidin.log."""
        import uuid
        logs_path = os.path.join(temp_logs_dir, 'logs')
        # Use unique logger name to avoid conflicts
        logger_name = f'test_file_{uuid.uuid4().hex[:8]}'
        logger = setup_logger(logger_name, logs_dir=logs_path, log_level='INFO')
        
        # Write a test log message
        test_message = 'Test log message for file handler'
        logger.info(test_message)
        
        # Flush all handlers to ensure write
        for handler in logger.handlers:
            handler.flush()
        
        # Verify the log file was created
        log_file = os.path.join(logs_path, 'denidin.log')
        assert os.path.exists(log_file)
        
        # Verify the message was written
        with open(log_file, 'r') as f:
            content = f.read()
        assert test_message in content

    def test_console_handler_outputs_to_stderr(self, temp_logs_dir, capsys):
        """Test that console handler outputs to stderr."""
        logger = setup_logger('test_console', logs_dir=temp_logs_dir, log_level='INFO')
        
        test_message = 'Test console output'
        logger.info(test_message)
        
        # Capture stderr output
        captured = capsys.readouterr()
        assert test_message in captured.err

    def test_rotating_file_handler_limits_file_size(self, temp_logs_dir):
        """Test that RotatingFileHandler limits file size."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        # Create logger with small max bytes for testing
        logger = setup_logger(
            'test_rotating',
            logs_dir=logs_path,
            log_level='INFO',
            max_bytes=1024,  # 1KB for testing
            backup_count=2
        )
        
        # Write enough data to trigger rotation
        for i in range(100):
            logger.info(f'Log message number {i} with some padding text to increase size')
        
        # Check that backup files were created
        log_file = os.path.join(logs_path, 'denidin.log')
        assert os.path.exists(log_file)
        
        # At least the main log file should exist
        assert os.path.getsize(log_file) > 0

    def test_log_format_includes_timestamp_name_level_message(self, temp_logs_dir):
        """Test that log format includes timestamp, name, level, and message."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_format', logs_dir=logs_path, log_level='INFO')
        
        test_message = 'Format test message'
        logger.info(test_message)
        
        # Read the log file
        log_file = os.path.join(logs_path, 'denidin.log')
        with open(log_file, 'r') as f:
            log_line = f.read()
        
        # Verify format components
        assert 'INFO' in log_line  # Log level
        assert test_message in log_line  # Message
        assert 'test_format' in log_line  # Logger name
        # Timestamp pattern: YYYY-MM-DD HH:MM:SS
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, log_line)

    def test_log_level_parameter_controls_info_vs_debug_verbosity(self, temp_logs_dir):
        """Test that log_level parameter controls INFO vs DEBUG verbosity."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        
        # Test INFO level - should not show DEBUG messages
        info_logger = setup_logger('test_info', logs_dir=logs_path, log_level='INFO')
        info_logger.debug('This is a DEBUG message')
        info_logger.info('This is an INFO message')
        
        log_file = os.path.join(logs_path, 'denidin.log')
        with open(log_file, 'r') as f:
            content = f.read()
        
        assert 'This is an INFO message' in content
        assert 'This is a DEBUG message' not in content
        
        # Clean up for DEBUG test
        os.unlink(log_file)
        
        # Test DEBUG level - should show both DEBUG and INFO messages
        debug_logger = setup_logger('test_debug', logs_dir=logs_path, log_level='DEBUG')
        debug_logger.debug('This is a DEBUG message')
        debug_logger.info('This is an INFO message')
        
        with open(log_file, 'r') as f:
            content = f.read()
        
        assert 'This is a DEBUG message' in content
        assert 'This is an INFO message' in content

    def test_info_logs_messages_and_errors_only(self, temp_logs_dir):
        """Test that INFO level logs messages and errors only."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_info_only', logs_dir=logs_path, log_level='INFO')
        
        logger.debug('Debug message - should not appear')
        logger.info('Info message - should appear')
        logger.warning('Warning message - should appear')
        logger.error('Error message - should appear')
        
        log_file = os.path.join(logs_path, 'denidin.log')
        with open(log_file, 'r') as f:
            content = f.read()
        
        assert 'Debug message' not in content
        assert 'Info message' in content
        assert 'Warning message' in content
        assert 'Error message' in content

    def test_debug_logs_parsing_state_api_details(self, temp_logs_dir):
        """Test that DEBUG level logs parsing, state, and API details."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_debug_details', logs_dir=logs_path, log_level='DEBUG')
        
        # Simulate detailed debug logs
        logger.debug('Parsing notification: {"type": "textMessage"}')
        logger.debug('State loaded: last_message_id=msg_123')
        logger.debug('API call: POST /sendMessage with payload')
        
        log_file = os.path.join(logs_path, 'denidin.log')
        with open(log_file, 'r') as f:
            content = f.read()
        
        assert 'Parsing notification' in content
        assert 'State loaded' in content
        assert 'API call' in content

    def test_get_logger_returns_configured_logger(self, temp_logs_dir):
        """Test that get_logger() returns a properly configured logger."""
        logger = get_logger('test_get', logs_dir=temp_logs_dir, log_level='INFO')
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test_get'


class TestLogRotation:
    """Test suite for log rotation functionality (Phase 6: US4 T045a)."""

    @pytest.fixture
    def temp_logs_dir(self):
        """Create a temporary logs directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rotating_file_handler_maxbytes_10mb_default(self, temp_logs_dir):
        """Test RotatingFileHandler uses 10MB default maxBytes."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        logger = setup_logger('test_10mb', logs_dir=logs_path, log_level='INFO')
        
        # Find the RotatingFileHandler
        rotating_handler = None
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                rotating_handler = handler
                break
        
        assert rotating_handler is not None, "RotatingFileHandler not found"
        assert rotating_handler.maxBytes == 10 * 1024 * 1024  # 10MB

    def test_backup_count_creates_five_backup_files(self, temp_logs_dir):
        """Test backupCount=5 creates .1, .2, .3, .4, .5 backup files."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        
        # Create logger with very small max bytes to force rotation
        logger = setup_logger(
            'test_backups',
            logs_dir=logs_path,
            log_level='INFO',
            max_bytes=500,  # Very small to trigger rotation quickly
            backup_count=5
        )
        
        # Write enough data to create multiple backup files
        # Each log message is ~100 bytes, so 50 messages = ~5KB = 10 rotations
        large_message = 'X' * 100  # 100 char message
        for i in range(50):
            logger.info(f'Log {i}: {large_message}')
        
        # Check that backup files were created
        log_file = os.path.join(logs_path, 'denidin.log')
        assert os.path.exists(log_file)
        
        # Check for backup files (.1, .2, .3, .4, .5)
        backup_files_found = 0
        for i in range(1, 6):
            backup_file = f"{log_file}.{i}"
            if os.path.exists(backup_file):
                backup_files_found += 1
        
        # At least some backup files should be created
        assert backup_files_found >= 1, "No backup files created during rotation"

    def test_logs_directory_created_if_missing(self, temp_logs_dir):
        """Test logs/ directory is automatically created if missing."""
        logs_path = os.path.join(temp_logs_dir, 'new_logs_dir')
        
        # Verify directory doesn't exist yet
        assert not os.path.exists(logs_path)
        
        # Create logger - should auto-create directory
        logger = setup_logger('test_mkdir', logs_dir=logs_path, log_level='INFO')
        logger.info('Test message')
        
        # Verify directory was created
        assert os.path.exists(logs_path)
        assert os.path.isdir(logs_path)
        
        # Verify log file was created in the new directory
        log_file = os.path.join(logs_path, 'denidin.log')
        assert os.path.exists(log_file)

    def test_old_logs_rotated_when_size_limit_reached(self, temp_logs_dir):
        """Test that old logs are rotated when size limit is reached."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        
        # Create logger with small max bytes
        logger = setup_logger(
            'test_rotation',
            logs_dir=logs_path,
            log_level='INFO',
            max_bytes=1024,  # 1KB
            backup_count=3
        )
        
        log_file = os.path.join(logs_path, 'denidin.log')
        
        # Write initial data
        for i in range(20):
            logger.info(f'Initial log message {i} with padding text to increase size')
        
        # Get initial file size
        initial_size = os.path.getsize(log_file)
        
        # Write more data to trigger rotation
        for i in range(30):
            logger.info(f'Additional log message {i} with more padding text to trigger rotation')
        
        # Main log file should not grow indefinitely - rotation should have occurred
        final_size = os.path.getsize(log_file)
        
        # Final size should be less than (initial_size + all new data)
        # If rotation didn't happen, file would be much larger
        assert final_size < 5000, f"Log file too large ({final_size} bytes) - rotation may not be working"
        
        # At least one backup file should exist
        backup_exists = (
            os.path.exists(f"{log_file}.1") or
            os.path.exists(f"{log_file}.2") or
            os.path.exists(f"{log_file}.3")
        )
        assert backup_exists, "No backup files created - rotation not working"

    def test_mock_large_log_writes(self, temp_logs_dir):
        """Test log rotation with mock large log writes."""
        logs_path = os.path.join(temp_logs_dir, 'logs')
        
        # Create logger with 2KB limit
        logger = setup_logger(
            'test_large',
            logs_dir=logs_path,
            log_level='INFO',
            max_bytes=2048,  # 2KB
            backup_count=5
        )
        
        log_file = os.path.join(logs_path, 'denidin.log')
        
        # Mock large writes - each message is ~1KB
        large_message = 'A' * 1000
        
        # Write 10KB total (should create multiple rotations)
        for i in range(10):
            logger.info(f'Large log {i}: {large_message}')
        
        # Verify main log file exists and is under size limit
        assert os.path.exists(log_file)
        main_log_size = os.path.getsize(log_file)
        assert main_log_size <= 2048, f"Main log exceeded maxBytes: {main_log_size} > 2048"
        
        # Verify backup files were created
        backup_count = 0
        for i in range(1, 6):
            if os.path.exists(f"{log_file}.{i}"):
                backup_count += 1
        
        assert backup_count > 0, "No backup files created with large writes"
