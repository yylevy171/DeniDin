"""
Integration tests for data_root configuration with SessionManager and MemoryManager.
Tests for bugfix 004: data_root config value not respected.

These tests verify that:
1. SessionManager uses paths constructed from data_root + storage_dir
2. MemoryManager uses paths constructed from data_root + storage_dir
3. Changing data_root changes actual storage locations
"""
import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from src.managers.session_manager import SessionManager
from src.managers.memory_manager import MemoryManager
from src.models.config import AppConfiguration

class TestDataRootIntegration:
    """Integration tests for data_root with memory managers."""

    @pytest.fixture
    def mock_ai_client(self):
        """Mock OpenAI client for MemoryManager."""
        mock_client = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        mock_client.embeddings = mock_embeddings
        return mock_client

    def test_session_manager_respects_data_root(self, tmp_path):
        """
        FAILING TEST (bugfix 004):
        Test that SessionManager creates storage in data_root/storage_dir.
        
        When we change data_root, SessionManager should create sessions
        in the new location.
        """
        # Custom data root
        custom_data_root = tmp_path / "custom_data"
        session_storage = custom_data_root / "sessions"
        
        # Create SessionManager with relative storage_dir
        # (Code should combine custom_data_root + "sessions")
        sm = SessionManager(
            storage_dir=str(session_storage),
            session_timeout_hours=24
        )
        
        # Verify storage directory was created in custom location
        assert session_storage.exists()
        assert sm.storage_dir == session_storage

    def test_memory_manager_respects_data_root(self, tmp_path, mock_ai_client):
        """
        FAILING TEST (bugfix 004):
        Test that MemoryManager creates storage in data_root/storage_dir.
        
        When we change data_root, MemoryManager should create ChromaDB
        in the new location.
        """
        # Custom data root
        custom_data_root = tmp_path / "custom_data"
        memory_storage = custom_data_root / "memory"
        
        # Create MemoryManager with relative storage_dir
        mm = MemoryManager(
            storage_dir=str(memory_storage),
            embedding_model="text-embedding-3-small",
            ai_client=mock_ai_client
        )
        
        # Verify storage directory was created in custom location
        assert memory_storage.exists()
        # ChromaDB creates a chroma.sqlite3 file
        assert (memory_storage / "chroma.sqlite3").exists()

    def test_config_to_session_manager_path_flow(self, tmp_path, mock_ai_client):
        """
        FAILING TEST (bugfix 004):
        End-to-end test: config.json → AppConfiguration → SessionManager
        
        Verifies the full path construction flow respects data_root.
        """
        # Create config with custom data_root
        config_file = tmp_path / "config.json"
        custom_data_root = tmp_path / "my_data"
        
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": str(custom_data_root),
            "memory": {
                "session": {
                    "storage_dir": "sessions"  # Relative path
                }
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Load config
        config = AppConfiguration.from_file(str(config_file))
        
        # Expected: storage_dir should be data_root + "sessions"
        expected_path = custom_data_root / "sessions"
        assert config.memory['session']['storage_dir'] == str(expected_path)
        
        # Create SessionManager using config value
        sm = SessionManager(
            storage_dir=config.memory['session']['storage_dir'],
            session_timeout_hours=24
        )
        
        # Verify SessionManager created storage in custom location
        assert expected_path.exists()
        assert sm.storage_dir == expected_path

    def test_different_data_roots_create_different_storage(self, tmp_path, mock_ai_client):
        """
        FAILING TEST (bugfix 004):
        Test that different data_root values create storage in different locations.
        
        This proves data_root is actually being used.
        """
        # Config 1: data_root = "test_data"
        config1_file = tmp_path / "config1.json"
        data_root1 = tmp_path / "test_data"
        config1 = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": str(data_root1),
            "memory": {
                "session": {"storage_dir": "sessions"}
            }
        }
        with open(config1_file, 'w') as f:
            json.dump(config1, f)
        
        # Config 2: data_root = "production_data"
        config2_file = tmp_path / "config2.json"
        data_root2 = tmp_path / "production_data"
        config2 = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": str(data_root2),
            "memory": {
                "session": {"storage_dir": "sessions"}
            }
        }
        with open(config2_file, 'w') as f:
            json.dump(config2, f)
        
        # Load configs and create SessionManagers
        cfg1 = AppConfiguration.from_file(str(config1_file))
        sm1 = SessionManager(
            storage_dir=cfg1.memory['session']['storage_dir'],
            session_timeout_hours=24
        )
        
        cfg2 = AppConfiguration.from_file(str(config2_file))
        sm2 = SessionManager(
            storage_dir=cfg2.memory['session']['storage_dir'],
            session_timeout_hours=24
        )
        
        # Verify different storage locations
        expected_path1 = data_root1 / "sessions"
        expected_path2 = data_root2 / "sessions"
        
        assert expected_path1.exists()
        assert expected_path2.exists()
        assert sm1.storage_dir == expected_path1
        assert sm2.storage_dir == expected_path2
        assert sm1.storage_dir != sm2.storage_dir
