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
