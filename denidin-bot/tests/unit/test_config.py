"""
Unit tests for BotConfiguration model.
Tests configuration loading from JSON/YAML files and validation.
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from src.models.config import BotConfiguration


class TestBotConfiguration:
    """Test suite for BotConfiguration model."""

    @pytest.fixture
    def valid_config_data(self):
        """Provide valid configuration data."""
        return {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "openai_api_key": "sk-test123",
            "ai_model": "gpt-4",
            "system_message": "You are a helpful assistant.",
            "max_tokens": 1000,
            "temperature": 0.7,
            "log_level": "INFO",
            "poll_interval_seconds": 5,
            "max_retries": 3
        }

    @pytest.fixture
    def temp_json_config(self, valid_config_data):
        """Create a temporary JSON config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config_data, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def temp_yaml_config(self, valid_config_data):
        """Create a temporary YAML config file."""
        import yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_config_data, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_from_file_loads_json_correctly(self, temp_json_config):
        """Test that from_file() loads JSON config correctly."""
        config = BotConfiguration.from_file(temp_json_config)
        
        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.openai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.system_message == "You are a helpful assistant."
        assert config.max_tokens == 1000
        assert config.temperature == 0.7
        assert config.log_level == "INFO"
        assert config.poll_interval_seconds == 5
        assert config.max_retries == 3

    def test_from_file_loads_yaml_correctly(self, temp_yaml_config):
        """Test that from_file() loads YAML config correctly."""
        config = BotConfiguration.from_file(temp_yaml_config)
        
        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.openai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.system_message == "You are a helpful assistant."
        assert config.max_tokens == 1000
        assert config.temperature == 0.7
        assert config.log_level == "INFO"
        assert config.poll_interval_seconds == 5
        assert config.max_retries == 3

    def test_from_file_missing_required_field_raises_error(self):
        """Test that from_file() raises ValueError when required fields are missing."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            # missing green_api_token
            "openai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                BotConfiguration.from_file(temp_path)
            assert "green_api_token" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)

    def test_validate_passes_with_valid_ranges(self, valid_config_data):
        """Test that validate() passes with valid value ranges."""
        config = BotConfiguration(**valid_config_data)
        
        # Should not raise any exception
        config.validate()

    def test_validate_fails_with_invalid_temperature_low(self, valid_config_data):
        """Test that validate() fails when temperature < 0.0."""
        valid_config_data['temperature'] = -0.1
        config = BotConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "temperature" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_temperature_high(self, valid_config_data):
        """Test that validate() fails when temperature > 1.0."""
        valid_config_data['temperature'] = 1.5
        config = BotConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "temperature" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_max_tokens(self, valid_config_data):
        """Test that validate() fails when max_tokens < 1."""
        valid_config_data['max_tokens'] = 0
        config = BotConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "max_tokens" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_poll_interval(self, valid_config_data):
        """Test that validate() fails when poll_interval < 1."""
        valid_config_data['poll_interval_seconds'] = 0
        config = BotConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "poll_interval" in str(exc_info.value).lower()

    def test_log_level_validates_info_debug_only(self, valid_config_data):
        """Test that log_level only accepts INFO or DEBUG."""
        # Test valid values
        for valid_level in ["INFO", "DEBUG"]:
            valid_config_data['log_level'] = valid_level
            config = BotConfiguration(**valid_config_data)
            config.validate()  # Should not raise
        
        # Test invalid value
        valid_config_data['log_level'] = "INVALID"
        config = BotConfiguration(**valid_config_data)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "log_level" in str(exc_info.value).lower()

    def test_config_dataclass_attributes_exist(self, valid_config_data):
        """Test that all required dataclass attributes exist."""
        config = BotConfiguration(**valid_config_data)
        
        # Verify all attributes are accessible
        assert hasattr(config, 'green_api_instance_id')
        assert hasattr(config, 'green_api_token')
        assert hasattr(config, 'openai_api_key')
        assert hasattr(config, 'ai_model')
        assert hasattr(config, 'system_message')
        assert hasattr(config, 'max_tokens')
        assert hasattr(config, 'temperature')
        assert hasattr(config, 'log_level')
        assert hasattr(config, 'poll_interval_seconds')
        assert hasattr(config, 'max_retries')
