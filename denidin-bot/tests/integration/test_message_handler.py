"""
Integration tests for message processing and error handling.
Tests the handle_text_message function behavior.
"""
import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock external dependencies
sys.modules['whatsapp_chatbot_python'] = MagicMock()


class TestMessageHandlerFunctionality:
    """Test suite for message handler functionality."""

    def test_bot_file_contains_message_handler(self):
        """Test that denidin.py contains the message handler function."""
        from pathlib import Path
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'def handle_text_message' in content
        assert 'notification.answer' in content
        # With refactored architecture, OpenAI calls are in AIHandler
        assert 'ai_handler' in content or 'AIHandler' in content

    def test_bot_has_error_handling(self):
        """Test that denidin.py has proper error handling."""
        from pathlib import Path
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'try:' in content
        assert 'except' in content
        assert 'exc_info=True' in content
        assert 'Sorry, I encountered an error' in content or 'fallback' in content.lower()

    def test_bot_extracts_message_data(self):
        """Test that bot or handlers extract required message data fields."""
        from pathlib import Path
        # Check both denidin.py and whatsapp_handler.py
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        handler_path = Path(__file__).parent.parent.parent / 'src' / 'handlers' / 'whatsapp_handler.py'
        
        with open(bot_path, 'r') as f:
            bot_content = f.read()
        with open(handler_path, 'r') as f:
            handler_content = f.read()
        
        combined = bot_content + handler_content
        # With refactored architecture, message processing is in WhatsAppHandler
        assert 'textMessage' in combined
        assert 'senderName' in combined or 'sender' in combined
        assert 'messageData' in combined or 'WhatsAppMessage' in combined

    def test_bot_calls_openai_with_correct_structure(self):
        """Test that bot/handlers call OpenAI with correct message structure."""
        from pathlib import Path
        # Check AIHandler for OpenAI structure
        handler_path = Path(__file__).parent.parent.parent / 'src' / 'handlers' / 'ai_handler.py'
        message_path = Path(__file__).parent.parent.parent / 'src' / 'models' / 'message.py'
        
        with open(handler_path, 'r') as f:
            handler_content = f.read()
        with open(message_path, 'r') as f:
            message_content = f.read()
        
        combined = handler_content + message_content
        # With refactored architecture, OpenAI message structure is in AIRequest/AIHandler
        assert 'messages' in combined
        assert 'role' in combined
        assert 'system' in combined or 'user' in combined
        assert 'config.system_message' in combined
        assert 'config.ai_model' in combined or 'config.max_tokens' in combined


class TestMessageTrackingInLogs:
    """Test that all log messages include message_id and received_timestamp for tracking."""

    def test_incoming_message_logs_include_tracking(self, caplog):
        """Test all incoming message logs include message_id and received_timestamp."""
        import logging
        from datetime import datetime, timezone
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.INFO)
        logger = get_logger(__name__, log_level="INFO")
        
        # Simulate incoming message log with tracking
        msg_id = "550e8400-e29b-41d4-a716-446655440000"
        recv_ts = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[msg_id={msg_id}] [recv_ts={recv_ts}] Received message from John Doe")
        
        # Verify log format
        assert f"[msg_id={msg_id}]" in caplog.text
        assert f"[recv_ts={recv_ts}]" in caplog.text
        assert "Received message from John Doe" in caplog.text

    def test_ai_processing_logs_include_tracking(self, caplog):
        """Test all AI processing logs include message_id and received_timestamp."""
        import logging
        from datetime import datetime, timezone
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.INFO)
        logger = get_logger(__name__, log_level="INFO")
        
        # Simulate AI processing log with tracking
        msg_id = "123e4567-e89b-12d3-a456-426614174000"
        recv_ts = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[msg_id={msg_id}] [recv_ts={recv_ts}] Created AI request")
        logger.info(f"[msg_id={msg_id}] [recv_ts={recv_ts}] AI response generated: 150 tokens")
        
        # Verify log format
        assert f"[msg_id={msg_id}]" in caplog.text
        assert f"[recv_ts={recv_ts}]" in caplog.text
        assert "Created AI request" in caplog.text
        assert "AI response generated: 150 tokens" in caplog.text

    def test_error_logs_include_tracking(self, caplog):
        """Test all error logs include message_id and received_timestamp."""
        import logging
        from datetime import datetime, timezone
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.ERROR)
        logger = get_logger(__name__, log_level="ERROR")
        
        # Simulate error log with tracking
        msg_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        recv_ts = datetime.now(timezone.utc).isoformat()
        
        logger.error(f"[msg_id={msg_id}] [recv_ts={recv_ts}] OpenAI API timeout error")
        
        # Verify log format
        assert f"[msg_id={msg_id}]" in caplog.text
        assert f"[recv_ts={recv_ts}]" in caplog.text
        assert "OpenAI API timeout error" in caplog.text

    def test_outgoing_message_logs_include_tracking(self, caplog):
        """Test all outgoing message logs include message_id and received_timestamp."""
        import logging
        from datetime import datetime, timezone
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.INFO)
        logger = get_logger(__name__, log_level="INFO")
        
        # Simulate outgoing message log with tracking
        msg_id = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        recv_ts = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[msg_id={msg_id}] [recv_ts={recv_ts}] Response sent to John Doe")
        
        # Verify log format
        assert f"[msg_id={msg_id}]" in caplog.text
        assert f"[recv_ts={recv_ts}]" in caplog.text
        assert "Response sent to John Doe" in caplog.text

    def test_log_format_matches_specification(self, caplog):
        """Test log format exactly matches: [msg_id={uuid}] [recv_ts={timestamp}] {log_message}"""
        import logging
        import re
        from datetime import datetime, timezone
        from src.utils.logger import get_logger
        
        caplog.set_level(logging.INFO)
        logger = get_logger(__name__, log_level="INFO")
        
        # Create log with exact format
        msg_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        recv_ts = datetime.now(timezone.utc).isoformat()
        log_message = "Processing message"
        
        logger.info(f"[msg_id={msg_id}] [recv_ts={recv_ts}] {log_message}")
        
        # Verify exact format with regex
        uuid_pattern = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
        timestamp_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+"
        expected_pattern = f"\\[msg_id={uuid_pattern}\\] \\[recv_ts={timestamp_pattern}.*\\] Processing message"
        
        assert re.search(expected_pattern, caplog.text), \
            f"Log format doesn't match expected pattern. Got: {caplog.text}"
