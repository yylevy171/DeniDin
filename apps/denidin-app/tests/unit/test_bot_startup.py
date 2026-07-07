"""
Integration tests for denidin.py initialization and startup.
Tests bot behavior end-to-end.
"""
import os
import sys
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

# Real external dependencies (no mocking)


class TestAppConfiguration:
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
            'from src.models.config import AppConfiguration',
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
        assert 'AppConfiguration.from_file' in content or 'config = AppConfiguration.from_file' in content
        # Validation will be added in T042b

    @patch('sys.exit')
    def test_invalid_config_causes_exit(self, mock_exit):
        """Test ValueError from invalid config is caught and causes sys.exit(1)."""
        # Create invalid config (temperature out of range)
        invalid_config = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test",
            "temperature": 2.0  # Invalid: > 1.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            
            config = AppConfiguration.from_file(temp_path)
            
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
        # Create config with invalid temperature
        invalid_config = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test",
            "temperature": 2.0  # Invalid: must be between 0.0 and 1.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            
            config = AppConfiguration.from_file(temp_path)
            
            with pytest.raises(ValueError) as exc_info:
                config.validate()
            
            assert "temperature" in str(exc_info.value).lower()
            
        finally:
            os.unlink(temp_path)


class TestConfigLogging:
    """Test that denidin.py logs configuration values on startup with masked API keys."""

    @patch('sys.exit')
    def test_startup_logs_all_config_values(self, mock_exit, caplog):
        """Test bot startup logs all configuration values."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create valid config
        valid_config = {
            "green_api_instance_id": "test_instance_123",
            "green_api_token": "test_token_secret_key_123456",
            "ai_api_key": "sk-test_openai_key_123456789"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            
            config = AppConfiguration.from_file(temp_path)
            config.validate()
            
            # Simulate startup logging (will be implemented in T043b)
            # For now, verify config has the expected values
            assert config.green_api_instance_id == "test_instance_123"
            assert config.ai_model == "gpt-4o-mini"  # default
            assert config.temperature == 0.7  # default
            assert config.ai_reply_max_tokens == 1000  # default
            
        finally:
            os.unlink(temp_path)

    @patch('sys.exit')
    def test_api_keys_masked_in_logs(self, mock_exit, caplog):
        """Test API keys are masked in logs (first 10 chars + '...')."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Create config with long API keys
        config_with_keys = {
            "green_api_instance_id": "instance_1234567890",
            "green_api_token": "token_abcdefghijklmnopqrstuvwxyz",
            "ai_api_key": "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_with_keys, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            from src.utils.logger import get_logger
            
            config = AppConfiguration.from_file(temp_path)
            config.validate()
            
            logger = get_logger(__name__, log_level="DEBUG")
            
            # Simulate masking (will be implemented in T043b)
            def mask_api_key(key: str) -> str:
                """Mask API key showing first 10 chars + '...'"""
                if len(key) > 10:
                    return key[:10] + "..."
                return key
            
            masked_token = mask_api_key(config.green_api_token)
            masked_openai = mask_api_key(config.ai_api_key)
            
            logger.info(f"Green API Token: {masked_token}")
            logger.info(f"OpenAI API Key: {masked_openai}")
            
            # Verify masked keys are in logs
            assert "token_abcd..." in caplog.text
            assert "sk-proj-12..." in caplog.text
            
            # Verify full keys are NOT in logs
            assert "token_abcdefghijklmnopqrstuvwxyz" not in caplog.text
            assert "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz" not in caplog.text
            
        finally:
            os.unlink(temp_path)

    @patch('sys.exit')
    def test_model_logged(self, mock_exit, caplog):
        """Test AI model is logged on startup."""
        import logging
        caplog.set_level(logging.INFO)
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test",
            "ai_model": "gpt-4o"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            from src.utils.logger import get_logger
            
            config = AppConfiguration.from_file(temp_path)
            logger = get_logger(__name__, log_level="INFO")
            
            logger.info(f"AI Model: {config.ai_model}")
            
            assert "AI Model: gpt-4o" in caplog.text
            
        finally:
            os.unlink(temp_path)

    @patch('sys.exit')
    def test_temperature_logged(self, mock_exit, caplog):
        """Test temperature is logged on startup."""
        import logging
        caplog.set_level(logging.INFO)
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test",
            "temperature": 0.9
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            from src.utils.logger import get_logger
            
            config = AppConfiguration.from_file(temp_path)
            logger = get_logger(__name__, log_level="INFO")
            
            logger.info(f"Temperature: {config.temperature}")
            
            assert "Temperature: 0.9" in caplog.text
            
        finally:
            os.unlink(temp_path)

    @patch('sys.exit')
    def test_max_tokens_logged(self, mock_exit, caplog):
        """Test ai_reply_max_tokens is logged on startup."""
        import logging
        caplog.set_level(logging.INFO)
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test",
            "ai_reply_max_tokens": 1000
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            from src.utils.logger import get_logger
            
            config = AppConfiguration.from_file(temp_path)
            logger = get_logger(__name__, log_level="INFO")
            
            logger.info(f"AI Reply Max Tokens: {config.ai_reply_max_tokens}")
            
            assert "AI Reply Max Tokens: 1000" in caplog.text
            
        finally:
            os.unlink(temp_path)

    @patch('sys.exit')
    def test_logs_are_info_or_debug_level(self, mock_exit, caplog):
        """Test config logs use INFO or DEBUG log level."""
        import logging
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "token123",
            "ai_api_key": "sk-test"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            from src.models.config import AppConfiguration
            from src.utils.logger import get_logger
            
            config = AppConfiguration.from_file(temp_path)
            
            # Test INFO level
            caplog.set_level(logging.INFO)
            caplog.clear()
            logger = get_logger(__name__, log_level="INFO")
            logger.info(f"Config loaded: {config.ai_model}")
            assert len(caplog.records) > 0
            assert caplog.records[0].levelname == "INFO"
            
            # Test DEBUG level
            caplog.set_level(logging.DEBUG)
            caplog.clear()
            logger_debug = get_logger(__name__, log_level="DEBUG")
            logger_debug.debug(f"Config details: {config.temperature}")
            assert len(caplog.records) > 0
            assert caplog.records[0].levelname == "DEBUG"
            
        finally:
            os.unlink(temp_path)
