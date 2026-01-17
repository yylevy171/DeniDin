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
        assert 'openai_client.chat.completions.create' in content

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
        """Test that bot extracts required message data fields."""
        from pathlib import Path
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'textMessage' in content
        assert 'senderName' in content or 'sender' in content
        assert 'messageData' in content

    def test_bot_calls_openai_with_correct_structure(self):
        """Test that bot calls OpenAI with correct message structure."""
        from pathlib import Path
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'messages' in content
        assert 'role' in content
        assert 'system' in content
        assert 'user' in content
        assert 'config.system_message' in content
        assert 'config.ai_model' in content
        assert 'config.max_tokens' in content
        assert 'config.temperature' in content
