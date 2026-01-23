"""
Unit tests for data_root configuration and storage path construction.
Tests for bugfix 004: data_root config value not respected.

These tests verify that:
1. storage_dir is relative to data_root
2. Changing data_root affects actual storage paths
3. Backward compatibility with old-style full paths
4. Auto-migration strips data_root prefix
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from src.models.config import AppConfiguration


class TestDataRootConfiguration:
    """Test suite for data_root and storage path construction."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal valid configuration."""
        return {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123"
        }

    def test_data_root_defaults_to_data(self, minimal_config):
        """Test that data_root defaults to 'data' when not specified."""
        config = AppConfiguration(**minimal_config)
        assert config.data_root == 'data'

    def test_storage_dir_is_relative_to_data_root(self, tmp_path):
        """
        FAILING TEST (bugfix 004):
        Test that storage_dir values are relative to data_root.
        
        When data_root changes, storage paths should follow.
        """
        temp_config = tmp_path / "config.json"
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "mydata",  # Custom data root
            "memory": {
                "session": {
                    "storage_dir": "sessions"  # Relative path
                },
                "longterm": {
                    "storage_dir": "memory"  # Relative path
                }
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Storage paths should combine data_root + storage_dir
        assert config.memory['session']['storage_dir'] == 'mydata/sessions'
        assert config.memory['longterm']['storage_dir'] == 'mydata/memory'

    def test_changing_data_root_affects_storage_paths(self, tmp_path):
        """
        FAILING TEST (bugfix 004):
        Test that changing ONLY data_root changes all storage paths.
        
        This is the core bug: data_root is currently ignored.
        """
        temp_config = tmp_path / "config.json"
        
        # Configuration with relative storage paths
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "production",
            "memory": {
                "session": {"storage_dir": "sessions"},
                "longterm": {"storage_dir": "memory"}
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config1 = AppConfiguration.from_file(str(temp_config))
        assert config1.memory['session']['storage_dir'] == 'production/sessions'
        assert config1.memory['longterm']['storage_dir'] == 'production/memory'
        
        # Change ONLY data_root
        config_data['data_root'] = 'staging'
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config2 = AppConfiguration.from_file(str(temp_config))
        assert config2.memory['session']['storage_dir'] == 'staging/sessions'
        assert config2.memory['longterm']['storage_dir'] == 'staging/memory'

    def test_default_storage_paths_relative_to_data_root(self, tmp_path):
        """
        Test that default storage paths are relative to data_root.
        
        When memory config exists but storage_dir is not specified,
        defaults should be data_root/sessions and data_root/memory.
        """
        temp_config = tmp_path / "config.json"
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "custom_data",
            "memory": {
                "session": {},  # No storage_dir specified
                "longterm": {}  # No storage_dir specified
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Defaults should use custom data_root
        assert config.memory['session']['storage_dir'] == 'custom_data/sessions'
        assert config.memory['longterm']['storage_dir'] == 'custom_data/memory'

    def test_backward_compatibility_strips_data_root_prefix(self, tmp_path):
        """
        FAILING TEST (bugfix 004):
        Test backward compatibility - auto-migration strips data_root prefix.
        
        Old configs have storage_dir: "data/sessions"
        When data_root is "data", this should auto-migrate to "sessions"
        """
        temp_config = tmp_path / "config.json"
        
        # Old-style config with full paths
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "data",
            "memory": {
                "session": {
                    "storage_dir": "data/sessions"  # Old-style full path
                },
                "longterm": {
                    "storage_dir": "data/memory"  # Old-style full path
                }
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Should auto-migrate by stripping data_root prefix
        # Final path should still be data/sessions (data_root + sessions)
        assert config.memory['session']['storage_dir'] == 'data/sessions'
        assert config.memory['longterm']['storage_dir'] == 'data/memory'

    def test_absolute_paths_not_modified(self, tmp_path):
        """
        Test that absolute paths are used as-is (not relative to data_root).
        
        This allows users to override storage location completely.
        """
        temp_config = tmp_path / "config.json"
        absolute_session_path = "/tmp/custom/sessions"
        absolute_memory_path = "/tmp/custom/memory"
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "data",
            "memory": {
                "session": {
                    "storage_dir": absolute_session_path
                },
                "longterm": {
                    "storage_dir": absolute_memory_path
                }
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Absolute paths should be preserved
        assert config.memory['session']['storage_dir'] == absolute_session_path
        assert config.memory['longterm']['storage_dir'] == absolute_memory_path
