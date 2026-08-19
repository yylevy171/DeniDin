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
from src.managers.ledger_event_manager import LedgerEventManager
from src.models.user import Role


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


class TestSenderRecipientRealIdentifiers:
    """
    2026-08-19: supersedes the old "AI sentinel retirement" scheme (Feature 039),
    which forced recipient=None for a user message and sender=None for an
    assistant message. That's now REVERSED: sender/recipient are real WhatsApp
    identifiers on both roles, always populated exactly as the caller passes
    them - `add_message` no longer nulls either one out based on role.
    """

    def test_user_message_sender_and_recipient_both_populated(self, session_manager):
        message_id = session_manager.add_message(
            chat_id="1234567890@c.us",
            role="user",
            content="Hi",
            user_role="client",
            sender="972501234567@c.us",
            sender_name="Godfather",
            recipient="972500000001@c.us",
            recipient_name="DeniDin",
        )
        session = session_manager.get_session("1234567890@c.us")
        message_file = (
            Path(session_manager.storage_dir) / session.session_id / "messages" / f"{message_id}.json"
        )
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["sender"] == "972501234567@c.us"
        assert message_data["sender_name"] == "Godfather"
        assert message_data["recipient"] == "972500000001@c.us"
        assert message_data["recipient_name"] == "DeniDin"

    def test_assistant_message_sender_and_recipient_both_populated(self, session_manager):
        message_id = session_manager.add_message(
            chat_id="1234567890@c.us",
            role="assistant",
            content="Reply",
            user_role="client",
            sender="972500000001@c.us",
            sender_name="DeniDin",
            recipient="972501234567@c.us",
            recipient_name="Godfather",
        )
        session = session_manager.get_session("1234567890@c.us")
        message_file = (
            Path(session_manager.storage_dir) / session.session_id / "messages" / f"{message_id}.json"
        )
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["sender"] == "972500000001@c.us"
        assert message_data["sender_name"] == "DeniDin"
        assert message_data["recipient"] == "972501234567@c.us"
        assert message_data["recipient_name"] == "Godfather"


class TestRealRoleAndAiRequiredRole:
    """2026-08-19: Message.role is now the REAL role ("admin"/"godfather"/
    "client"/"assistant"), computed from the caller's structural role
    ("user"/"assistant") + user_role (a Role enum, or a raw string on the
    RBAC-disabled fallback path). Message.ai_required_role is the separately
    derived "user"/"assistant" value OpenAI's API actually needs."""

    def test_user_role_enum_becomes_real_lowercase_role(self, session_manager):
        message_id = session_manager.add_message(
            chat_id="1234567890@c.us", role="user", content="Hi",
            user_role=Role.GODFATHER,
        )
        session = session_manager.get_session("1234567890@c.us")
        message_file = (
            Path(session_manager.storage_dir) / session.session_id / "messages" / f"{message_id}.json"
        )
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["role"] == "godfather"
        assert message_data["ai_required_role"] == "user"

    def test_user_role_string_fallback_becomes_real_lowercase_role(self, session_manager):
        message_id = session_manager.add_message(
            chat_id="1234567890@c.us", role="user", content="Hi",
            user_role="client",
        )
        session = session_manager.get_session("1234567890@c.us")
        message_file = (
            Path(session_manager.storage_dir) / session.session_id / "messages" / f"{message_id}.json"
        )
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["role"] == "client"
        assert message_data["ai_required_role"] == "user"

    def test_assistant_role_is_always_assistant_regardless_of_user_role(self, session_manager):
        message_id = session_manager.add_message(
            chat_id="1234567890@c.us", role="assistant", content="Reply",
            user_role=Role.ADMIN,  # irrelevant for an assistant turn
        )
        session = session_manager.get_session("1234567890@c.us")
        message_file = (
            Path(session_manager.storage_dir) / session.session_id / "messages" / f"{message_id}.json"
        )
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["role"] == "assistant"
        assert message_data["ai_required_role"] == "assistant"


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
        # 2026-08-19: role is now the REAL role ("client", derived from
        # user_role="client") - ai_required_role is the "user"/"assistant"
        # value OpenAI's API needs.
        assert message_data["role"] == "client"
        assert message_data["ai_required_role"] == "user"
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

    def test_group_session_history_prefixes_user_turns_with_sender(self, session_manager):
        """
        Feature 039 (US3): for a group session (chat_id contains @g.us), each user-role
        history entry's content is prefixed "[<sender>] " so the model can tell members
        apart in a shared session. Assistant-role entries are unprefixed (unambiguous).
        """
        chat_id = "120363012345678901@g.us"

        # 2026-08-19: the group-turn prefix now comes from sender_name (the
        # resolved display name) - `sender` itself is a real WhatsApp JID.
        session_manager.add_message(chat_id, "user", "מה המצב?", "client", sender_name="Godfather")
        session_manager.add_message(chat_id, "assistant", "הכל טוב", "client")
        session_manager.add_message(chat_id, "user", "תודה", "client", sender_name="Admin")

        history = session_manager.get_conversation_history(chat_id, "client")

        assert history[0]["content"] == "[Godfather] מה המצב?"
        assert history[1]["content"] == "הכל טוב"  # assistant: unprefixed
        assert history[2]["content"] == "[Admin] תודה"

    def test_one_on_one_session_history_unprefixed(self, session_manager):
        """1:1 sessions (no @g.us) keep today's unprefixed output shape - no ambiguity
        to resolve, since there's only ever one human counterpart."""
        chat_id = "972501234567@c.us"

        session_manager.add_message(chat_id, "user", "Hello", "client", sender="Godfather")

        history = session_manager.get_conversation_history(chat_id, "client")

        assert history[0]["content"] == "Hello"


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
            ai_handler=SimpleNamespace(
                session_manager=session_manager,
                # Feature 033: MediaHandler.__init__ now also wires a
                # LedgerEventManager - real instance (not a Mock), matching
                # this suite's real-internal-components convention, even
                # though this specific test never exercises it directly.
                ledger_event_manager=LedgerEventManager(storage_dir=str(tmp_path / "events")),
                # 2026-08-19: _store_media_turn now resolves role/own-number via
                # these - RBAC disabled here since this test is about
                # image_path/extracted_text storage, not RBAC.
                rbac_enabled=False,
                user_manager=None,
                own_whatsapp_number="",
            ),
        )
        media_handler = MediaHandler(denidin_context)

        media_handler._store_media_turn(
            chat_id=chat_id,
            sender_phone=sender_phone,
            sender_display=sender_phone,
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

        # 2026-08-19: role is the real role - "client" (RBAC disabled fallback,
        # same as AIHandler._finalize_response's own RBAC-disabled path).
        assert message_data["role"] == "client"
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


class TestExtractedTextStorage:
    """Feature 043 (2026-08-18): extracted_text field for media-extractor content,
    replacing LedgerEvent.raw_message_excerpt's old per-ledger-event duplication
    of the same content - see Message.extracted_text's own docstring. Same
    real-call-site discipline as TestImagePathStorage above (exercises
    MediaHandler._store_media_turn, not SessionManager.add_message directly)."""

    def test_extracted_text_storage(self, session_manager, tmp_path):
        chat_id = "1234567890@c.us"
        sender_phone = "1234567890"
        saved_file_path = tmp_path / "media" / "DD-1234567890-abc123.jpg"

        denidin_context = SimpleNamespace(
            config=SimpleNamespace(
                data_root=str(tmp_path),
                ai_vision_model="gpt-4o-mini",
                ai_model="gpt-4o-mini",
            ),
            ai_handler=SimpleNamespace(
                session_manager=session_manager,
                ledger_event_manager=LedgerEventManager(storage_dir=str(tmp_path / "events")),
                rbac_enabled=False,
                user_manager=None,
                own_whatsapp_number="",
            ),
        )
        media_handler = MediaHandler(denidin_context)

        media_handler._store_media_turn(
            chat_id=chat_id,
            sender_phone=sender_phone,
            sender_display=sender_phone,
            media_type="image",
            caption="Check out this image!",
            summary="AI analysis of the image",
            image_path=str(saved_file_path.relative_to(tmp_path)),
            extracted_text="טקסט שחולץ מהתמונה",
        )

        session = session_manager.get_session(chat_id)
        user_message_id = session.message_ids[0]

        session_dir = Path(session_manager.storage_dir) / session.session_id
        message_file = session_dir / "messages" / f"{user_message_id}.json"
        with open(message_file) as f:
            message_data = json.load(f)

        assert message_data["extracted_text"] == "טקסט שחולץ מהתמונה"

    def test_extracted_text_optional_defaults_to_none(self, session_manager):
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

        assert message_data["extracted_text"] is None


class TestNoPendingLedgerEventsOnSession:
    """Feature 033: ledger events moved out of session.json entirely, into their own
    permanent storage (LedgerEventManager, tests/unit/test_ledger_event_manager.py).
    Session must no longer carry any ledger-event state."""

    def test_session_dataclass_has_no_pending_ledger_events_field(self):
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(Session)}
        assert "pending_ledger_events" not in field_names

    def test_session_manager_has_no_add_pending_ledger_event_method(self, session_manager):
        assert not hasattr(session_manager, "add_pending_ledger_event")


class TestMessageLedgerEventIds:
    """Feature 033: Message gains ledger_event_ids, the reverse link to
    LedgerEvent.message_id - the id(s) of any ledger event(s) captured from this
    specific message."""

    def test_message_dataclass_has_ledger_event_ids_field(self):
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(Message)}
        assert "ledger_event_ids" in field_names

    def test_new_message_defaults_to_empty_ledger_event_ids(self, session_manager):
        chat_id = "1234567890@c.us"
        message_id = session_manager.add_message(
            chat_id=chat_id, role="user", content="hello", user_role="client"
        )
        session = session_manager.get_session(chat_id)
        session_dir = session_manager.storage_dir / session.session_id
        with open(session_dir / "messages" / f"{message_id}.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ledger_event_ids"] == []

    def test_message_with_ledger_event_ids_persists_them(self, session_manager):
        chat_id = "1234567890@c.us"
        message_id = session_manager.add_message(
            chat_id=chat_id, role="user", content="hello",
            user_role="client", ledger_event_ids=["A28072614060", "A28072614061"],
        )
        session = session_manager.get_session(chat_id)
        session_dir = session_manager.storage_dir / session.session_id
        with open(session_dir / "messages" / f"{message_id}.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ledger_event_ids"] == ["A28072614060", "A28072614061"]

    def test_message_ledger_event_ids_persists_across_reload(self, session_manager, temp_session_dir):
        chat_id = "1234567890@c.us"
        message_id = session_manager.add_message(
            chat_id=chat_id, role="user", content="hello",
            user_role="client", ledger_event_ids=["B28072614260"],
        )
        session = session_manager.get_session(chat_id)
        session_dir = session_manager.storage_dir / session.session_id

        reloaded_manager = SessionManager(storage_dir=str(temp_session_dir), session_timeout_hours=24)
        with open(session_dir / "messages" / f"{message_id}.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ledger_event_ids"] == ["B28072614260"]
        # sanity: the reloaded manager sees the same session/message on disk
        assert reloaded_manager.get_session(chat_id).session_id == session.session_id


class TestAddMessageIdOverride:
    """Feature 033 (confirmed design, 2026-07-30): a caller that already decided
    this message's id at arrival time (e.g. WhatsAppMessage.from_notification)
    MUST be able to make add_message use that exact id, rather than always
    getting a silently-different, freshly-generated one - the id must be
    identical across the persisted message's filename, its own message_id
    field, and the session's message_ids entry."""

    def test_add_message_uses_supplied_message_id_as_filename(self, session_manager):
        chat_id = "1234567890@c.us"
        returned_id = session_manager.add_message(
            chat_id=chat_id, role="user", content="hello",
            user_role="client", message_id="supplied-id-1",
        )
        assert returned_id == "supplied-id-1"

        session = session_manager.get_session(chat_id)
        session_dir = session_manager.storage_dir / session.session_id
        assert (session_dir / "messages" / "supplied-id-1.json").exists()
        with open(session_dir / "messages" / "supplied-id-1.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["message_id"] == "supplied-id-1"
        assert "supplied-id-1" in session.message_ids

    def test_add_message_without_message_id_still_generates_a_fresh_one(self, session_manager):
        chat_id = "1234567890@c.us"
        message_id = session_manager.add_message(
            chat_id=chat_id, role="assistant", content="hi there", user_role="client",
        )
        assert message_id  # non-empty
        assert message_id != "supplied-id-1"

    def test_add_message_with_tokens_threads_supplied_message_id(self, session_manager):
        chat_id = "1234567890@c.us"
        returned_id = session_manager.add_message_with_tokens(
            chat_id=chat_id, role="user", content="hello",
            user_role="client", message_id="supplied-id-2",
        )
        assert returned_id == "supplied-id-2"

    def test_add_message_with_token_limit_threads_supplied_message_id(self, session_manager):
        chat_id = "1234567890@c.us"
        returned_id = session_manager.add_message_with_token_limit(
            chat_id=chat_id, role="user", content="hello",
            user_role="client", token_limit=4000, message_id="supplied-id-3",
        )
        assert returned_id == "supplied-id-3"
