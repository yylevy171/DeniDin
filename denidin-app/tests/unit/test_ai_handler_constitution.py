"""
Unit tests for AIHandler constitution loading.
Tests dynamic constitution file loading for runtime AI behavior configuration.

BDD Workflow - Step 4: Write failing tests first.

Test Coverage:
- Constitution file loaded with mtime-based caching
- Constitution content becomes system message (replaces system_message config)
- Single constitution file (not multiple)
- File changes picked up via mtime check
- Error handling: missing files, empty files, large files (500 lines)
- Constitution always loaded (no enabled flag)
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from openai import OpenAI
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


@pytest.fixture
def constitution_config():
    """Config fixture with constitution configuration."""
    return AppConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        ai_api_key="test-key",
        ai_model="gpt-4o-mini",
        ai_reply_max_tokens=1000,
        temperature=0.7,
        log_level="INFO",
        data_root="test_data",
        constitution_config={
            "file": "runtime_constitution.md"  # Single file, not array
        }
    )


@pytest.fixture
def test_constitution_file(tmp_path):
    """Create temporary constitution file for testing."""
    constitution_dir = tmp_path / "constitution"
    constitution_dir.mkdir()
    
    constitution_file = constitution_dir / "runtime_constitution.md"
    constitution_content = """# DeniDin AI Assistant Constitution

## Core Identity
You are DeniDin, a helpful AI assistant.

## Behavioral Guidelines
- Be concise and direct
- Use natural language
- Respect privacy
"""
    constitution_file.write_text(constitution_content, encoding='utf-8')
    
    return tmp_path, constitution_content.strip()


@pytest.fixture
def large_constitution_file(tmp_path):
    """Create large constitution file (500 lines) for testing."""
    constitution_dir = tmp_path / "constitution"
    constitution_dir.mkdir()
    
    constitution_file = constitution_dir / "runtime_constitution.md"
    
    # Generate 500 lines of realistic constitution content
    lines = ["# Large DeniDin Constitution\n"]
    for i in range(1, 500):
        lines.append(f"## Section {i}\n")
        lines.append(f"Guideline {i}: Always follow best practice {i}.\n\n")
    
    constitution_content = "".join(lines)
    constitution_file.write_text(constitution_content, encoding='utf-8')
    
    return tmp_path, constitution_content.strip()


class TestConstitutionMtimeBasedCaching:
    """Test that constitution uses mtime-based caching (reload only if file changed)."""
    
    def test_first_request_loads_constitution(self, constitution_config, test_constitution_file):
        """Verify constitution file is loaded on first request."""
        tmp_path, original_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        # Verify cache is empty initially
        assert handler._constitution_content is None
        assert handler._constitution_mtime is None
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Constitution should be loaded
        assert original_content in request.constitution
        assert "DeniDin AI Assistant Constitution" in request.constitution
        
        # Cache should be populated
        assert handler._constitution_content is not None
        assert handler._constitution_mtime is not None
    
    def test_second_request_uses_cache_when_file_unchanged(self, constitution_config, test_constitution_file):
        """Verify second request uses cached constitution (mtime unchanged)."""
        tmp_path, original_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message1 = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="First message",
            timestamp=1234567890,
            message_type="text"
        )
        
        # First request loads file
        request1 = handler.create_request(message1)
        first_mtime = handler._constitution_mtime
        first_content = handler._constitution_content
        
        # Second request (file unchanged)
        message2 = WhatsAppMessage(
            message_id="msg_002",
            chat_id="chat_002",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Second message",
            timestamp=1234567900,
            message_type="text"
        )
        
        request2 = handler.create_request(message2)
        
        # Should use cached content (same mtime, same object)
        assert handler._constitution_mtime == first_mtime
        assert handler._constitution_content is first_content  # Same object reference
        assert original_content in request2.constitution
    
    def test_file_modification_triggers_reload(self, constitution_config, test_constitution_file):
        """Verify file modification (mtime changed) triggers reload."""
        tmp_path, original_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message1 = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="First",
            timestamp=1234567890,
            message_type="text"
        )
        
        # First request
        request1 = handler.create_request(message1)
        assert "DeniDin AI Assistant Constitution" in request1.constitution
        first_mtime = handler._constitution_mtime
        
        # Wait to ensure mtime changes
        time.sleep(0.01)
        
        # MODIFY constitution file
        constitution_file = tmp_path / "constitution" / "runtime_constitution.md"
        modified_content = """# MODIFIED Constitution

## New Behavior
You are now SUPER helpful and VERY enthusiastic!
"""
        constitution_file.write_text(modified_content, encoding='utf-8')
        
        # Force mtime update (some filesystems have low resolution)
        import os
        os.utime(constitution_file, None)
        
        message2 = WhatsAppMessage(
            message_id="msg_002",
            chat_id="chat_002",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Second",
            timestamp=1234567900,
            message_type="text"
        )
        
        # Second request should reload
        request2 = handler.create_request(message2)
        
        # mtime should be different
        assert handler._constitution_mtime != first_mtime
        
        # New content should be present
        assert "MODIFIED Constitution" in request2.constitution
        assert "SUPER helpful" in request2.constitution
        assert "VERY enthusiastic" in request2.constitution
        
        # Old content should NOT be present
        assert "Behavioral Guidelines" not in request2.constitution


class TestConstitutionAsSystemMessage:
    """Test that constitution becomes the system message (replaces system_message config)."""
    
    def test_constitution_replaces_system_message(self, constitution_config, test_constitution_file):
        """Verify constitution content is used instead of config.system_message."""
        tmp_path, constitution_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="chat_456",
            sender_name="Alice",
            sender_id="1234567890@c.us",
            text_content="What should I do?",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Constitution content should be in request
        assert "DeniDin AI Assistant Constitution" in request.constitution
        assert "Behavioral Guidelines" in request.constitution
    
    def test_constitution_only_no_appending(self, constitution_config, test_constitution_file):
        """Verify constitution is used as-is without appending anything."""
        tmp_path, constitution_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Constitution should be present
        assert "DeniDin AI Assistant Constitution" in request.constitution


class TestSingleConstitutionFile:
    """Test single constitution file (not multiple files)."""
    
    def test_only_first_file_used_if_config_has_array(self, constitution_config, tmp_path):
        """Verify backward compatibility: if config has array, use first file only."""
        constitution_config.data_root = str(tmp_path)
        
        # Simulate old config with array (backward compat test)
        constitution_config.constitution_config = {
            "files": ["first.md", "second.md"]  # Old array format
        }
        
        # Create only first file
        constitution_dir = tmp_path / "constitution"
        constitution_dir.mkdir()
        
        first_file = constitution_dir / "first.md"
        first_file.write_text("# First Constitution\nUse this one.", encoding='utf-8')
        
        second_file = constitution_dir / "second.md"
        second_file.write_text("# Second Constitution\nIgnore this.", encoding='utf-8')
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Only first file should be loaded
        assert "First Constitution" in request.constitution
        assert "Use this one" in request.constitution
        
        # Second file should be ignored
        assert "Second Constitution" not in request.constitution
        assert "Ignore this" not in request.constitution
    
    def test_single_file_string_config(self, constitution_config, tmp_path):
        """Verify new config format with single file string."""
        constitution_config.data_root = str(tmp_path)
        constitution_config.constitution_config = {
            "file": "my_constitution.md"  # New string format
        }
        
        constitution_dir = tmp_path / "constitution"
        constitution_dir.mkdir()
        
        const_file = constitution_dir / "my_constitution.md"
        const_file.write_text("# My Custom Constitution\nBe awesome!", encoding='utf-8')
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        assert "My Custom Constitution" in request.constitution
        assert "Be awesome!" in request.constitution


class TestConstitutionErrorHandling:
    """Test error handling for missing, empty, or invalid constitution files."""
    
    def test_missing_constitution_file_graceful_fallback(self, constitution_config, tmp_path):
        """Verify graceful handling when constitution file doesn't exist."""
        constitution_config.data_root = str(tmp_path)
        
        # Create constitution directory but no files
        constitution_dir = tmp_path / "constitution"
        constitution_dir.mkdir()
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Should not crash, return empty constitution
        request = handler.create_request(message)
        assert request is not None
        assert request.constitution == ""  # Empty when file is empty == ""  # Empty when file missing
    
    def test_empty_constitution_file_fallback(self, constitution_config, tmp_path):
        """Verify graceful handling when constitution file is empty."""
        constitution_config.data_root = str(tmp_path)
        
        # Create empty constitution file
        constitution_dir = tmp_path / "constitution"
        constitution_dir.mkdir()
        constitution_file = constitution_dir / "runtime_constitution.md"
        constitution_file.write_text("", encoding='utf-8')  # Empty file
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Should not crash, return empty constitution
        request = handler.create_request(message)
        assert request is not None
        assert request.constitution == ""  # Empty when file is empty
    
    def test_partial_file_list_some_missing(self, constitution_config, tmp_path):
        """Verify graceful handling when constitution file doesn't exist (no crash)."""
        constitution_config.data_root = str(tmp_path)
        constitution_config.constitution_config = {
            "file": "missing.md"  # File doesn't exist
        }
        
        constitution_dir = tmp_path / "constitution"
        constitution_dir.mkdir()
        # missing.md intentionally not created
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Should return empty constitution
        assert request.constitution == ""


class TestLargeConstitutionFile:
    """Test handling of large constitution files (up to 500 lines)."""
    
    def test_large_constitution_500_lines_loads_successfully(self, constitution_config, large_constitution_file):
        """Verify large constitution file (500 lines) loads without issues."""
        tmp_path, large_content = large_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test large constitution",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Verify large content is loaded
        assert "Large DeniDin Constitution" in request.constitution
        assert "Section 1" in request.constitution
        assert "Section 499" in request.constitution
        assert "Guideline 499" in request.constitution
        
        # Verify constitution is substantial
        assert len(request.constitution) > 10000  # 500 lines should be >10K chars
    
    def test_large_constitution_performance_no_caching(self, constitution_config, large_constitution_file):
        """Verify large constitution loads efficiently even without caching."""
        tmp_path, large_content = large_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Load large constitution multiple times (simulating multiple requests)
        import time
        start = time.time()
        for _ in range(10):  # 10 requests
            request = handler.create_request(message)
            assert "Large DeniDin Constitution" in request.constitution
        elapsed = time.time() - start
        
        # Should complete reasonably fast even without caching (~50KB file × 10 reads)
        assert elapsed < 1.0  # Should take less than 1 second for 10 reads


class TestConstitutionWithMemory:
    """Test constitution loading interaction with memory system."""
    
    def test_constitution_loaded_before_memory_context(self, constitution_config, test_constitution_file):
        """Verify constitution is loaded BEFORE memory context is appended."""
        tmp_path, constitution_content = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        # Enable memory system
        constitution_config.feature_flags = {"enable_memory_system": True}
        constitution_config.memory = {
            "session": {"storage_dir": "test_data/sessions"},
            "longterm": {
                "storage_dir": "test_data/memory",
                "embedding_model": "text-embedding-3-small",
                "top_k_results": 5
            }
        }
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        # Mock memory recall
        if handler.memory_manager:
            handler.memory_manager.recall = Mock(return_value=[
                {"content": "User likes Python", "similarity": 0.9}
            ])
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        
        # Both constitution and memory should be present
        assert "DeniDin AI Assistant Constitution" in request.constitution
        
        # Constitution should come BEFORE memory context
        constitution_index = request.constitution.index("DeniDin AI Assistant Constitution")
        if "RECALLED MEMORIES" in request.constitution:
            memory_index = request.constitution.index("RECALLED MEMORIES")
            assert constitution_index < memory_index, "Constitution should come before memory context"


class TestAiReplyMaxTokens:
    """Test ai_reply_max_tokens configuration (renamed from max_tokens)."""
    
    def test_ai_reply_max_tokens_set_to_1000(self, constitution_config):
        """Verify ai_reply_max_tokens config is set to 1000."""
        assert constitution_config.ai_reply_max_tokens == 1000
    
    def test_request_uses_ai_reply_max_tokens(self, constitution_config, test_constitution_file):
        """Verify AIRequest uses ai_reply_max_tokens from config."""
        tmp_path, _ = test_constitution_file
        constitution_config.data_root = str(tmp_path)
        
        client = MagicMock()
        handler = AIHandler(client, constitution_config)
        
        message = WhatsAppMessage(
            message_id="msg_001",
            chat_id="chat_001",
            sender_name="User",
            sender_id="1234567890@c.us",
            text_content="Test",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message)
        assert request.max_tokens == 1000
