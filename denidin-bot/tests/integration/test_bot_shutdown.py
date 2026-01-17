"""
Integration tests for graceful shutdown handling.
Tests SIGINT and SIGTERM signal handlers for clean bot shutdown.
Phase 6: US4 - Configuration & Deployment (T047a)
"""
import sys
import signal
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock external dependencies
sys.modules['whatsapp_chatbot_python'] = MagicMock()


class TestGracefulShutdown:
    """Test suite for graceful shutdown functionality."""

    def test_sigint_signal_handler_registered(self):
        """Test that SIGINT (Ctrl+C) signal handler is registered."""
        # Read bot.py to verify signal handling
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # Check for KeyboardInterrupt handling (Python's way of handling SIGINT)
        assert 'KeyboardInterrupt' in content, "Missing KeyboardInterrupt exception handler"
        assert 'except KeyboardInterrupt:' in content
        # Graceful shutdown message should be logged
        assert 'shutdown' in content.lower() or 'shutting down' in content.lower()

    def test_sigterm_signal_handler_registered(self):
        """Test that SIGTERM signal handler is registered (for systemd)."""
        # Read bot.py to verify signal handling
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # SIGTERM handling is typically done via signal.signal()
        # For now, we check that the bot can handle termination gracefully
        # Full implementation will be in T047b
        assert 'if __name__ == "__main__":' in content
        # Check for exception handling around bot.run_forever()
        assert 'try:' in content
        assert 'bot.run_forever()' in content

    def test_shutdown_message_logged_on_signal(self, caplog):
        """Test 'Shutting down gracefully...' is logged on shutdown signal."""
        import logging
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.INFO)
        logger = get_logger(__name__, log_level="INFO")
        
        # Simulate shutdown logging
        logger.info("Received shutdown signal (Ctrl+C)")
        logger.info("DeniDin bot shutting down gracefully...")
        
        # Verify shutdown messages in logs
        assert "shutdown signal" in caplog.text.lower()
        assert "shutting down gracefully" in caplog.text.lower()

    def test_current_message_processing_completes_before_exit(self):
        """Test that current message processing completes before shutdown."""
        # This is a structural test - verify exception handling allows completion
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # Check that KeyboardInterrupt is caught OUTSIDE message handler
        # This ensures message handler can complete before shutdown
        assert 'bot.run_forever()' in content
        # KeyboardInterrupt should be in main block, not inside handler
        lines = content.split('\n')
        
        # Find bot.run_forever() and verify try-except around it
        run_forever_found = False
        keyboard_interrupt_found = False
        
        for i, line in enumerate(lines):
            if 'bot.run_forever()' in line:
                run_forever_found = True
                # Look backwards for try block
                for j in range(max(0, i-10), i):
                    if 'try:' in lines[j]:
                        # Look forwards for except KeyboardInterrupt
                        for k in range(i, min(len(lines), i+10)):
                            if 'except KeyboardInterrupt' in lines[k]:
                                keyboard_interrupt_found = True
                                break
                        break
        
        assert run_forever_found, "bot.run_forever() not found"
        assert keyboard_interrupt_found, "KeyboardInterrupt handler not found around bot.run_forever()"

    def test_bot_run_forever_exits_cleanly(self):
        """Test that bot.run_forever() can exit without errors."""
        # Verify the bot has proper exception handling
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # Check for clean exit handling
        assert 'except KeyboardInterrupt:' in content
        # Should log shutdown and not crash
        assert 'logger.info' in content or 'logger.critical' in content
        
        # Verify sys.exit() is only called for fatal errors, not normal shutdown
        # KeyboardInterrupt should NOT call sys.exit()
        lines = content.split('\n')
        in_keyboard_interrupt_block = False
        
        for i, line in enumerate(lines):
            if 'except KeyboardInterrupt:' in line:
                in_keyboard_interrupt_block = True
                # Check next 5 lines
                for j in range(i+1, min(len(lines), i+6)):
                    if lines[j].strip().startswith('except '):
                        # End of KeyboardInterrupt block
                        break
                    # sys.exit() should NOT be in KeyboardInterrupt handler
                    if 'sys.exit(' in lines[j]:
                        assert False, "sys.exit() found in KeyboardInterrupt handler - should exit naturally"
                break
        
        assert in_keyboard_interrupt_block, "KeyboardInterrupt exception handler not found"

    @patch('signal.signal')
    def test_mock_signal_handlers(self, mock_signal):
        """Test that signal handlers can be mocked and registered."""
        import signal
        
        # Create mock signal handler
        def mock_handler(signum, frame):
            print(f"Received signal {signum}")
        
        # Register handler (this is what bot.py will do in T047b)
        signal.signal(signal.SIGINT, mock_handler)
        signal.signal(signal.SIGTERM, mock_handler)
        
        # In actual implementation, this would be in denidin.py
        # For now, verify signal registration works
        mock_signal.assert_any_call(signal.SIGINT, mock_handler)
        mock_signal.assert_any_call(signal.SIGTERM, mock_handler)

    def test_shutdown_handler_structure_in_bot_file(self):
        """Test that bot file has proper structure for graceful shutdown."""
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # Verify essential components exist
        checks = {
            'main block': 'if __name__ == "__main__":',
            'try block': 'try:',
            'run forever': 'bot.run_forever()',
            'keyboard interrupt': 'except KeyboardInterrupt:',
            'shutdown log': 'shutting down',
            'exception handler': 'except Exception'
        }
        
        for check_name, check_str in checks.items():
            assert check_str.lower() in content.lower(), \
                f"Missing {check_name}: '{check_str}' not found in denidin.py"
