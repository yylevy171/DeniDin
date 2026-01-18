"""
Unit tests for SessionManager.

Tests conversation history management with role-based token limits.
Written following TDD workflow - tests BEFORE implementation.
"""

import pytest
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.memory.session_manager import SessionManager, Session, Message


@pytest.fixture
def temp_session_dir(tmp_path):
    """Create temporary directory for session storage."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def session_manager(temp_session_dir):
    """Create SessionManager instance for testing."""
    manager = SessionManager(
        storage_dir=str(temp_session_dir),
        session_timeout_hours=24,
        cleanup_interval_seconds=10  # Fast cleanup for tests
    )
    yield manager
    # Stop cleanup thread after test
    manager.stop_cleanup_thread()


class TestSessionCreation:
    """Test session creation and initialization."""
    
    def test_create_new_session(self, session_manager):
        """Test creating a new session with correct chat_id."""
        chat_id = "1234567890@c.us"
        session = session_manager.get_session(chat_id)
        
        assert session.session_id is not None
        assert session.whatsapp_chat == chat_id
        assert len(session.message_ids) == 0
        assert session.created_at is not None
        assert session.last_active is not None
        assert session.total_tokens == 0
    
    def test_session_has_uuid(self, session_manager):
        """Test that session_id is a valid UUID."""
        chat_id = "1234567890@c.us"
        session = session_manager.get_session(chat_id)
        
        # UUID format: 8-4-4-4-12 characters
        assert len(session.session_id) == 36
        assert session.session_id.count('-') == 4
    
    def test_message_counter_increments(self, session_manager):
        """Test that message_counter increments with each message."""
        chat_id = "1234567890@c.us"
        
        # Initial session should have counter at 0
        session = session_manager.get_session(chat_id)
        assert session.message_counter == 0
        
        # Add messages and verify counter increments
        session_manager.add_message(chat_id, "user", "Message 1", "client")
        session = session_manager.get_session(chat_id)
        assert session.message_counter == 1
        
        session_manager.add_message(chat_id, "assistant", "Response 1", "client")
        session = session_manager.get_session(chat_id)
        assert session.message_counter == 2
        
        session_manager.add_message(chat_id, "user", "Message 2", "client")
        session = session_manager.get_session(chat_id)
        assert session.message_counter == 3


class TestMessageHandling:
    """Test message addition and retrieval."""
    
    def test_add_message_to_session(self, session_manager):
        """Test adding a message with all fields."""
        chat_id = "1234567890@c.us"
        
        message_id = session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Hello, DeniDin!",
            user_role="client"
        )
        
        # Verify message was added
        session = session_manager.get_session(chat_id)
        assert len(session.message_ids) == 1
        assert message_id in session.message_ids
        
        # Verify message file exists inside session directory
        session_dir = Path(session_manager.storage_dir) / session.session_id
        message_file = session_dir / "messages" / f"{message_id}.json"
        assert message_file.exists()
        
        # Verify message content
        with open(message_file) as f:
            message_data = json.load(f)
        assert message_data["role"] == "user"
        assert message_data["content"] == "Hello, DeniDin!"
        assert message_data["chat_id"] == session.session_id
        assert "timestamp" in message_data
        assert "received_at" in message_data
    
    def test_get_conversation_history(self, session_manager):
        """Test retrieving conversation history in AI format."""
        chat_id = "1234567890@c.us"
        
        # Add multiple messages
        session_manager.add_message(chat_id, "user", "Hello", "client")
        session_manager.add_message(chat_id, "assistant", "Hi there!", "client")
        session_manager.add_message(chat_id, "user", "How are you?", "client")
        
        history = session_manager.get_conversation_history(chat_id, "client")
        
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"


@pytest.mark.skip(reason="Token limits deferred to RBAC phase (006)")
class TestTokenLimits:
    """Test role-based token limiting."""
    
    def test_get_token_limit_client(self, session_manager):
        """Test client token limit is 4000."""
        limit = session_manager.get_token_limit("client")
        assert limit == 4000
    
    def test_get_token_limit_godfather(self, session_manager):
        """Test godfather token limit is 100000."""
        limit = session_manager.get_token_limit("godfather")
        assert limit == 100000


class TestPersistence:
    """Test session persistence to disk."""
    
    def test_session_persistence_to_disk(self, session_manager, temp_session_dir):
        """Test session is saved as JSON file."""
        chat_id = "1234567890@c.us"
        
        session_manager.add_message(chat_id, "user", "Test message", "client")
        session = session_manager.get_session(chat_id)
        
        # Verify session directory exists
        session_dir = Path(temp_session_dir) / session.session_id
        assert session_dir.exists()
        assert session_dir.is_dir()
        
        # Verify session metadata file exists
        session_file = session_dir / "session.json"
        assert session_file.exists()
        
        # Verify content
        with open(session_file) as f:
            data = json.load(f)
        assert data["whatsapp_chat"] == chat_id
        assert len(data["message_ids"]) == 1
    
    def test_load_session_from_disk(self, temp_session_dir):
        """Test session loaded correctly after restart."""
        chat_id = "1234567890@c.us"
        
        # Create session with first manager
        manager1 = SessionManager(storage_dir=str(temp_session_dir))
        manager1.add_message(chat_id, "user", "Persisted message", "client")
        session_id = manager1.get_session(chat_id).session_id
        manager1.stop_cleanup_thread()
        
        # Create new manager (simulates restart)
        manager2 = SessionManager(storage_dir=str(temp_session_dir))
        session = manager2.get_session(chat_id)
        
        assert session.session_id == session_id
        assert len(session.message_ids) == 1
        
        # Verify can retrieve message
        history = manager2.get_conversation_history(chat_id, "client")
        assert history[0]["content"] == "Persisted message"
        
        manager2.stop_cleanup_thread()


class TestSessionExpiration:
    """Test session timeout and expiration."""
    
    def test_session_moved_to_expired_folder_by_date(self, session_manager, temp_session_dir):
        """Test expired sessions moved to expired/YYYY-MM-DD/ folder, not deleted."""
        chat_id = "1234567890@c.us"
        
        # Create session with message
        session_manager.add_message(chat_id, "user", "Test message", "client")
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        
        # Manually set old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        session.last_active = old_time
        session_manager._save_session(session)
        
        # Trigger cleanup
        session_manager._cleanup_expired_sessions()
        
        # Session directory should be moved to expired/YYYY-MM-DD/
        active_dir = Path(temp_session_dir) / session_id
        # Expected date folder based on when session last_active date
        expected_date = old_time.strftime("%Y-%m-%d")
        expired_dir = Path(temp_session_dir) / "expired" / expected_date / session_id
        
        assert not active_dir.exists()
        assert expired_dir.exists()
        
        # Verify expired session content preserved
        session_file = expired_dir / "session.json"
        assert session_file.exists()
        with open(session_file) as f:
            data = json.load(f)
        assert data["session_id"] == session_id
        assert data["whatsapp_chat"] == chat_id
    
    def test_expired_session_messages_also_moved(self, session_manager, temp_session_dir):
        """Test messages from expired sessions moved with session directory."""
        chat_id = "1234567890@c.us"
        
        # Create session with messages
        msg_id_1 = session_manager.add_message(chat_id, "user", "Message 1", "client")
        msg_id_2 = session_manager.add_message(chat_id, "assistant", "Response 1", "client")
        
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        session.last_active = old_time
        session_manager._save_session(session)
        
        # Trigger cleanup
        session_manager._cleanup_expired_sessions()
        
        # Entire session directory should be moved to dated subfolder
        active_dir = Path(temp_session_dir) / session_id
        expected_date = old_time.strftime("%Y-%m-%d")
        expired_dir = Path(temp_session_dir) / "expired" / expected_date / session_id
        
        assert not active_dir.exists()
        assert expired_dir.exists()
        
        # Messages should be in expired session directory
        expired_msg_1 = expired_dir / "messages" / f"{msg_id_1}.json"
        expired_msg_2 = expired_dir / "messages" / f"{msg_id_2}.json"
        
        assert expired_msg_1.exists()
        assert expired_msg_2.exists()
    
    def test_expired_session_not_in_index(self, session_manager):
        """Test expired sessions removed from chat_to_session mapping."""
        chat_id = "1234567890@c.us"
        
        # Create and expire session
        session_manager.add_message(chat_id, "user", "Old message", "client")
        session = session_manager.get_session(chat_id)
        old_session_id = session.session_id
        
        # Verify session is in index
        assert session_manager.chat_to_session.get(chat_id) == old_session_id
        
        # Expire and cleanup
        session.last_active = datetime.now(timezone.utc) - timedelta(hours=25)
        session_manager._save_session(session)
        session_manager._cleanup_expired_sessions()
        
        # Verify session removed from index
        assert chat_id not in session_manager.chat_to_session
    
    def test_new_session_created_after_expiration(self, session_manager):
        """Test accessing expired session creates new session."""
        chat_id = "1234567890@c.us"
        
        # Create and expire session
        session_manager.add_message(chat_id, "user", "Old message", "client")
        old_session_id = session_manager.get_session(chat_id).session_id
        
        session = session_manager.get_session(chat_id)
        session.last_active = datetime.now(timezone.utc) - timedelta(hours=25)
        session_manager._save_session(session)
        
        # Cleanup
        session_manager._cleanup_expired_sessions()
        
        # Get session again - should create new one
        new_session = session_manager.get_session(chat_id)
        assert new_session.session_id != old_session_id
        assert len(new_session.message_ids) == 0  # Fresh session
    
    def test_cleanup_thread_runs_periodically(self, temp_session_dir):
        """Test cleanup thread runs at configured interval."""
        # Create manager with very short interval for testing
        manager = SessionManager(
            storage_dir=str(temp_session_dir),
            session_timeout_hours=24,
            cleanup_interval_seconds=1  # 1 second for fast test
        )
        
        chat_id = "1234567890@c.us"
        manager.add_message(chat_id, "user", "Test", "client")
        
        # Expire the session
        session = manager.get_session(chat_id)
        session_id = session.session_id
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        session.last_active = old_time
        manager._save_session(session)
        
        # Wait for cleanup thread to run
        time.sleep(2.5)  # Wait for at least 2 cleanup cycles
        
        # Session directory should be moved to expired/YYYY-MM-DD/
        expected_date = old_time.strftime("%Y-%m-%d")
        expired_dir = Path(temp_session_dir) / "expired" / expected_date / session_id
        assert expired_dir.exists()
        
        manager.stop_cleanup_thread()
    
    def test_active_sessions_not_moved(self, session_manager, temp_session_dir):
        """Test active sessions remain in place during cleanup."""
        chat_id = "1234567890@c.us"
        
        # Create active session (recent timestamp)
        session_manager.add_message(chat_id, "user", "Active message", "client")
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        
        # Run cleanup
        session_manager._cleanup_expired_sessions()
        
        # Session directory should still be in active location
        active_dir = Path(temp_session_dir) / session_id
        assert active_dir.exists()
        
        # Session should still be in index
        assert session_manager.chat_to_session.get(chat_id) == session_id


class TestSessionManagement:
    """Test session lifecycle management."""
    
    def test_clear_session(self, session_manager):
        """Test session cleared completely."""
        chat_id = "1234567890@c.us"
        
        # Add messages
        session_manager.add_message(chat_id, "user", "Message 1", "client")
        session_manager.add_message(chat_id, "user", "Message 2", "client")
        
        # Clear session
        session_manager.clear_session(chat_id)
        
        # Verify cleared
        session = session_manager.get_session(chat_id)
        assert len(session.message_ids) == 0
        assert session.total_tokens == 0
    
    def test_multiple_sessions_isolated(self, session_manager):
        """Test different chats have isolated sessions."""
        chat1 = "1111111111@c.us"
        chat2 = "2222222222@c.us"
        
        session_manager.add_message(chat1, "user", "Chat 1 message", "client")
        session_manager.add_message(chat2, "user", "Chat 2 message", "client")
        
        session1 = session_manager.get_session(chat1)
        session2 = session_manager.get_session(chat2)
        
        assert session1.session_id != session2.session_id
        assert len(session1.message_ids) == 1
        assert len(session2.message_ids) == 1
        
        history1 = session_manager.get_conversation_history(chat1, "client")
        history2 = session_manager.get_conversation_history(chat2, "client")
        
        assert history1[0]["content"] == "Chat 1 message"
        assert history2[0]["content"] == "Chat 2 message"


@pytest.mark.skip(reason="Image support deferred to feature 003")
class TestImagePathStorage:
    """Test image path field for future media support."""
    
    def test_image_path_storage(self, session_manager):
        """Test image_path field stored in message."""
        chat_id = "1234567890@c.us"
        image_path = "data/images/abc123.jpg"  # Global images folder
        
        message_id = session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Check out this image!",
            user_role="client",
            image_path=image_path
        )
        
        session = session_manager.get_session(chat_id)
        
        # Verify image_path stored (references global images folder)
        session_dir = Path(session_manager.storage_dir) / session.session_id
        message_file = session_dir / "messages" / f"{message_id}.json"
        with open(message_file) as f:
            message_data = json.load(f)
        
        assert message_data["image_path"] == image_path
    
    def test_image_path_optional(self, session_manager):
        """Test image_path is optional (defaults to None)."""
        chat_id = "1234567890@c.us"
        
        message_id = session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Text only message",
            user_role="client"
        )
        
        session = session_manager.get_session(chat_id)
        session_dir = Path(session_manager.storage_dir) / session.session_id
        message_file = session_dir / "messages" / f"{message_id}.json"
        with open(message_file) as f:
            message_data = json.load(f)
        
        assert message_data["image_path"] is None
