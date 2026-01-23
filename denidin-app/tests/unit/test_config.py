"""  
Unit tests for AppConfiguration model.
Tests configuration loading from JSON/YAML files and validation.
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from src.models.config import AppConfiguration
class TestAppConfiguration:
    """Test suite for AppConfiguration model."""

    @pytest.fixture
    def valid_config_data(self):
        """Provide valid configuration data."""
        return {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123",
            "ai_model": "gpt-4",
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
        config = AppConfiguration.from_file(temp_json_config)
        
        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.ai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.temperature == 0.7
        assert config.log_level == "INFO"
        assert config.poll_interval_seconds == 5
        assert config.max_retries == 3

    def test_from_file_loads_yaml_correctly(self, temp_yaml_config):
        """Test that from_file() loads YAML config correctly."""
        config = AppConfiguration.from_file(temp_yaml_config)
        
        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.ai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.temperature == 0.7
        assert config.log_level == "INFO"
        assert config.poll_interval_seconds == 5
        assert config.max_retries == 3

    def test_from_file_missing_required_field_raises_error(self):
        """Test that from_file() raises ValueError when required fields are missing."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            # missing green_api_token
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            assert "green_api_token" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_green_api_instance_id(self):
        """Test that from_file() raises ValueError listing missing green_api_instance_id."""
        incomplete_config = {
            # missing green_api_instance_id
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "green_api_instance_id" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_green_api_token(self):
        """Test that from_file() raises ValueError for missing green_api_token."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            # missing green_api_token
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "green_api_token" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_ai_api_key(self):
        """Test that from_file() raises ValueError for missing ai_api_key."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456"
            # missing ai_api_key
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "ai_api_key" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_lists_all_missing_fields(self):
        """Test error message clearly lists ALL missing required fields."""
        incomplete_config = {
            # missing all three required fields
            "ai_model": "gpt-4"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            # All three required fields should be mentioned
            assert "green_api_instance_id" in error_message
            assert "green_api_token" in error_message
            assert "ai_api_key" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_succeeds_with_all_required_fields(self):
        """Test from_file() succeeds with all required fields present in config.json."""
        config_with_required = {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_with_required, f)
            temp_path = f.name
        
        try:
            config = AppConfiguration.from_file(temp_path)
            assert config.green_api_instance_id == "1234567890"
            assert config.green_api_token == "abcdef123456"
            assert config.ai_api_key == "sk-test123"
        finally:
            os.unlink(temp_path)

    def test_validate_passes_with_valid_ranges(self, valid_config_data):
        """Test that validate() passes with valid value ranges."""
        config = AppConfiguration(**valid_config_data)
        
        # Should not raise any exception
        config.validate()

    def test_validate_fails_with_invalid_temperature_low(self, valid_config_data):
        """Test that validate() fails when temperature < 0.0."""
        valid_config_data['temperature'] = -0.1
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "temperature" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_temperature_high(self, valid_config_data):
        """Test that validate() fails when temperature > 1.0."""
        valid_config_data['temperature'] = 1.5
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "temperature" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_max_tokens(self, valid_config_data):
        """Test that validate() fails when ai_reply_max_tokens < 1."""
        valid_config_data['ai_reply_max_tokens'] = 0
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "ai_reply_max_tokens" in str(exc_info.value).lower()

    def test_validate_fails_with_invalid_poll_interval(self, valid_config_data):
        """Test that validate() fails when poll_interval < 1."""
        valid_config_data['poll_interval_seconds'] = 0
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "poll_interval" in str(exc_info.value).lower()

    def test_log_level_validates_info_debug_only(self, valid_config_data):
        """Test that log_level only accepts INFO or DEBUG."""
        # Test valid values
        for valid_level in ["INFO", "DEBUG"]:
            valid_config_data['log_level'] = valid_level
            config = AppConfiguration(**valid_config_data)
            config.validate()  # Should not raise
        
        # Test invalid value
        valid_config_data['log_level'] = "INVALID"
        config = AppConfiguration(**valid_config_data)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "log_level" in str(exc_info.value).lower()

    def test_config_dataclass_attributes_exist(self, valid_config_data):
        """Test that all required dataclass attributes exist."""
        config = AppConfiguration(**valid_config_data)
        
        # Verify all attributes are accessible
        assert hasattr(config, 'green_api_instance_id')
        assert hasattr(config, 'green_api_token')
        assert hasattr(config, 'ai_api_key')
        assert hasattr(config, 'ai_model')
        assert hasattr(config, 'temperature')
        assert hasattr(config, 'log_level')
        assert hasattr(config, 'poll_interval_seconds')
        assert hasattr(config, 'max_retries')
        assert hasattr(config, 'data_root')

    def test_data_root_defaults_to_data(self, valid_config_data):
        """Test that data_root defaults to 'data' when not specified."""
        config = AppConfiguration(**valid_config_data)
        assert config.data_root == 'data'

    def test_data_root_can_be_customized(self, valid_config_data):
        """Test that data_root can be set to custom value (e.g., for test isolation)."""
        valid_config_data['data_root'] = '/tmp/test_data'
        config = AppConfiguration(**valid_config_data)
        assert config.data_root == '/tmp/test_data'

    def test_validate_fails_with_empty_data_root(self, valid_config_data):
        """Test that validate() fails when data_root is empty."""
        valid_config_data['data_root'] = ''
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "data_root" in str(exc_info.value).lower()

    def test_validate_fails_with_whitespace_data_root(self, valid_config_data):
        """Test that validate() fails when data_root is only whitespace."""
        valid_config_data['data_root'] = '   '
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "data_root" in str(exc_info.value).lower()

    def test_memory_storage_paths_use_data_root(self, tmp_path):
        """Test that memory storage paths are constructed relative to data_root."""
        temp_config = tmp_path / "config_with_data_root.json"
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "test_data",
            "memory": {
                "session": {},
                "longterm": {}
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Verify storage paths are relative to data_root
        assert config.memory['session']['storage_dir'] == 'test_data/sessions'
        assert config.memory['longterm']['storage_dir'] == 'test_data/memory'
        
        os.unlink(temp_config)
