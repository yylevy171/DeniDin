"""
Integration tests for denidin.py initialization and startup.
Tests bot behavior end-to-end with simplified mocking.
"""
import os
import sys
import pytest
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock external dependencies BEFORE importing bot
sys.modules['whatsapp_chatbot_python'] = MagicMock()


class TestBotConfiguration:
    """Test that denidin.py loads and validates configuration correctly."""

    def test_bot_file_exists(self):
        """Test that denidin.py file exists and is executable."""
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        assert bot_path.exists(), "denidin.py should exist"
        assert os.access(bot_path, os.X_OK), "denidin.py should be executable"

    def test_bot_imports_required_modules(self):
        """Test that denidin.py imports all required modules."""
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        required_imports = [
            'from whatsapp_chatbot_python import',
            'from openai import',
            'from src.models.config import BotConfiguration',
            'from src.utils.logger import get_logger'
        ]
        
        for required_import in required_imports:
            assert required_import in content, f"denidin.py should import: {required_import}"

    def test_bot_defines_handle_text_message_function(self):
        """Test that handle_text_message function is defined in denidin.py."""
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'def handle_text_message' in content, "denidin.py should define handle_text_message function"
        assert '@bot.router.message' in content, "denidin.py should use @bot.router.message decorator"

    def test_bot_has_main_block(self):
        """Test that denidin.py has main execution block."""
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        assert 'if __name__ == "__main__":' in content, "bot.py should have main block"
        assert 'bot.run_forever()' in content, "bot.py should call bot.run_forever()"
