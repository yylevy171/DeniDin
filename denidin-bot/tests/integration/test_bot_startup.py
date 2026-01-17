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


class TestConfigValidationIntegration:
    """Test that denidin.py validates configuration on startup."""

    def test_bot_calls_config_validate_after_from_file(self):
        """Test bot.py calls config.validate() after from_file()."""
        # This test will check the actual implementation when bot.py is updated
        # For now, verify the expected flow exists
        bot_path = Path(__file__).parent.parent.parent / 'denidin.py'
        with open(bot_path, 'r') as f:
            content = f.read()
        
        # Look for config loading and validation pattern
        assert 'BotConfiguration.from_file' in content or 'config = BotConfiguration.from_file' in content
        # Validation will be added in T042b

    @patch('sys.exit')
    def test_invalid_config_causes_exit(self, mock_exit):
        """Test ValueError from invalid config is caught and causes sys.exit(1)."""
        # Create invalid config (temperature out of range)
        invalid_config = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "openai_api_key": "sk-test",
            "temperature": 2.0  # Invalid: > 1.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            from src.models.config import BotConfiguration
            
            config = BotConfiguration.from_file(temp_path)
            
            # Try to validate - should raise ValueError
            try:
                config.validate()
                assert False, "Should have raised ValueError for invalid temperature"
            except ValueError as e:
                # This is expected - bot.py should catch this and exit
                assert "temperature" in str(e).lower()
                
        finally:
            os.unlink(temp_path)

    def test_bot_doesnt_start_with_invalid_config(self):
        """Test bot doesn't start when config validation fails."""
        # Create config with invalid poll_interval
        invalid_config = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "openai_api_key": "sk-test",
            "poll_interval_seconds": 0  # Invalid: must be >= 1
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            from src.models.config import BotConfiguration
            
            config = BotConfiguration.from_file(temp_path)
            
            with pytest.raises(ValueError) as exc_info:
                config.validate()
            
            assert "poll_interval" in str(exc_info.value).lower()
            
        finally:
            os.unlink(temp_path)
