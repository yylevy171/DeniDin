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
from types import SimpleNamespace
from unittest.mock import Mock, patch
from src.managers.session_manager import SessionManager, Session, Message
from src.handlers.media_handler import MediaHandler


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
        session_timeout_hours=24
    )
    yield manager


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
        assert message_data["session_id"] == session.session_id  # Field should be session_id, not chat_id
        assert "chat_id" not in message_data  # Ensure old field name is not present
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


class TestTokenLimits:
    """Test role-based token limiting."""
    
    def test_get_token_limit_client(self, session_manager):
        """Test client token limit is 4000."""
        # Mock the get_token_limit method
        session_manager.get_token_limit = Mock(return_value=4000)
        limit = session_manager.get_token_limit("client")
        assert limit == 4000
    
    def test_get_token_limit_godfather(self, session_manager):
        """Test godfather token limit is 100000."""
        # Mock the get_token_limit method
        session_manager.get_token_limit = Mock(return_value=100000)
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
        
        # Create new manager (simulates restart)
        manager2 = SessionManager(storage_dir=str(temp_session_dir))
        session = manager2.get_session(chat_id)
        
        assert session.session_id == session_id
        assert len(session.message_ids) == 1
        
        # Verify can retrieve message
        history = manager2.get_conversation_history(chat_id, "client")
        assert history[0]["content"] == "Persisted message"


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
        session.last_active = old_time.isoformat()
        session_manager._save_session(session)
        
        # Trigger archival (simulates what background cleanup does)
        session_manager.archive_session(session)
        
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
        session.last_active = old_time.isoformat()
        session_manager._save_session(session)
        
        # Trigger archival (simulates what background cleanup does)
        session_manager.archive_session(session)
        
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
        session.last_active = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        session_manager._save_session(session)
        session_manager.archive_session(session)
        session_manager.remove_from_index(session)
        
        # Verify session removed from index
        assert chat_id not in session_manager.chat_to_session
    
    def test_new_session_created_after_expiration(self, session_manager):
        """Test accessing expired session creates new session."""
        chat_id = "1234567890@c.us"
        
        # Create and expire session
        session_manager.add_message(chat_id, "user", "Old message", "client")
        old_session_id = session_manager.get_session(chat_id).session_id
        
        session = session_manager.get_session(chat_id)
        session.last_active = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        session_manager._save_session(session)
        
        # Cleanup (simulates what background cleanup does)
        session_manager.archive_session(session)
        session_manager.remove_from_index(session)
        
        # Get session again - should create new one
        new_session = session_manager.get_session(chat_id)
        assert new_session.session_id != old_session_id
        assert len(new_session.message_ids) == 0  # Fresh session


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


class TestImagePathStorage:
    """Test image path field for media persistence."""

    def test_image_path_storage(self, session_manager, tmp_path):
        """bugfix-009 (reopened 2026-07-30): asserting SessionManager.add_message
        stores image_path when GIVEN one (the old version of this test) proves
        nothing about whether the real caller, MediaHandler, actually provides
        one - that's exactly how the original bugfix-009 fix regressed silently
        when bugfix-017 rewrote the call site (MediaHandler._store_media_turn)
        without carrying image_path forward. This exercises the real call site
        instead of SessionManager directly."""
        chat_id = "1234567890@c.us"
        sender_phone = "1234567890"
        saved_file_path = tmp_path / "media" / "DD-1234567890-abc123.jpg"

        denidin_context = SimpleNamespace(
            config=SimpleNamespace(
                data_root=str(tmp_path),
                ai_vision_model="gpt-4o-mini",
                ai_model="gpt-4o-mini",
            ),
            ai_handler=SimpleNamespace(session_manager=session_manager),
        )
        media_handler = MediaHandler(denidin_context)

        media_handler._store_media_turn(
            chat_id=chat_id,
            sender_phone=sender_phone,
            media_type="image",
            caption="Check out this image!",
            summary="AI analysis of the image",
            image_path=str(saved_file_path.relative_to(tmp_path)),
        )

        session = session_manager.get_session(chat_id)
        user_message_id = session.message_ids[0]

        session_dir = Path(session_manager.storage_dir) / session.session_id
        message_file = session_dir / "messages" / f"{user_message_id}.json"
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["role"] == "user"
        assert message_data["image_path"] == "media/DD-1234567890-abc123.jpg"
    
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


class TestPendingLedgerEvents:
    """Test SessionManager.add_pending_ledger_event (Ledger Event Recognition,
    see runtime_constitution.md)."""

    def test_new_session_has_empty_pending_ledger_events(self, session_manager):
        """A freshly created session starts with an empty pending_ledger_events list."""
        session = session_manager.get_session("1234567890@c.us")
        assert session.pending_ledger_events == []

    def test_add_pending_ledger_event_appends_with_pointer(self, session_manager):
        """The stored record carries the original event fields plus the hard
        pointer (message_timestamp resolved to ISO8601, sender) and a capture time."""
        chat_id = "1234567890@c.us"
        event = {
            "source_type": "הסכם",
            "event_subtype": "יצירה",
            "client_name": "ישראל ישראלי",
            "amount": "5000",
        }
        epoch = 1770000000  # fixed, arbitrary real epoch

        session_manager.add_pending_ledger_event(
            chat_id=chat_id,
            event=event,
            message_timestamp=epoch,
            sender="972500000000@c.us",
        )

        session = session_manager.get_session(chat_id)
        assert len(session.pending_ledger_events) == 1
        record = session.pending_ledger_events[0]

        assert record["source_type"] == "הסכם"
        assert record["client_name"] == "ישראל ישראלי"
        assert record["sender"] == "972500000000@c.us"
        assert record["message_timestamp"] == datetime.fromtimestamp(
            epoch, tz=timezone.utc
        ).isoformat()
        assert "captured_at" in record

    def test_add_pending_ledger_event_does_not_mutate_input_dict(self, session_manager):
        """The caller's event dict must not be mutated (it's reused/logged elsewhere)."""
        event = {"source_type": "בנק", "event_subtype": "הפקדה"}
        original = dict(event)

        session_manager.add_pending_ledger_event(
            chat_id="1234567890@c.us",
            event=event,
            message_timestamp=1770000000,
            sender="972500000000@c.us",
        )

        assert event == original

    def test_add_pending_ledger_event_persists_across_reload(self, session_manager, temp_session_dir):
        """A second SessionManager instance pointed at the same storage dir must see
        the pending event - it's saved to disk, not just held in memory."""
        chat_id = "1234567890@c.us"
        session_manager.add_pending_ledger_event(
            chat_id=chat_id,
            event={"source_type": "הסכם", "event_subtype": "עדכון"},
            message_timestamp=1770000000,
            sender="972500000000@c.us",
        )

        reloaded_manager = SessionManager(storage_dir=str(temp_session_dir), session_timeout_hours=24)
        session = reloaded_manager.get_session(chat_id)
        assert len(session.pending_ledger_events) == 1
        assert session.pending_ledger_events[0]["event_subtype"] == "עדכון"

    def test_add_pending_ledger_event_appends_multiple(self, session_manager):
        """Multiple captured events in the same session accumulate, not overwrite."""
        chat_id = "1234567890@c.us"
        for i in range(3):
            session_manager.add_pending_ledger_event(
                chat_id=chat_id,
                event={"source_type": "הסכם", "amount": str(i)},
                message_timestamp=1770000000 + i,
                sender="972500000000@c.us",
            )

        session = session_manager.get_session(chat_id)
        assert [r["amount"] for r in session.pending_ledger_events] == ["0", "1", "2"]

    def test_add_pending_ledger_event_missing_timestamp(self, session_manager):
        """A None message_timestamp (should never happen in practice - AIRequest
        always auto-fills one - but must not crash) stores a None pointer rather
        than raising."""
        session_manager.add_pending_ledger_event(
            chat_id="1234567890@c.us",
            event={"source_type": "בנק"},
            message_timestamp=None,
            sender="972500000000@c.us",
        )

        session = session_manager.get_session("1234567890@c.us")
        assert session.pending_ledger_events[0]["message_timestamp"] is None
