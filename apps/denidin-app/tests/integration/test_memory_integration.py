"""
Integration tests for Memory System (Phase 6)
Tests real component integration without mocks.

Note (2026-08-03): the 4 tests that construct a real OpenAI() client
(test_memory_manager_stores_and_recalls, test_ai_handler_stores_messages_in_session,
test_orphaned_session_recovery_active_session, test_multi_turn_conversation_maintains_context)
were moved to tests/billed/test_memory_integration_billed.py - see that file's docstring.
The tests remaining here exercise SessionManager only and make no OpenAI calls at all.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.managers.session_manager import SessionManager


@pytest.fixture
def temp_storage():
    """Create temporary storage directories for testing."""
    temp_dir = tempfile.mkdtemp()
    session_dir = Path(temp_dir) / "sessions"
    memory_dir = Path(temp_dir) / "memory"

    yield {
        'session_dir': str(session_dir),
        'memory_dir': str(memory_dir),
        'temp_dir': temp_dir
    }

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestMemorySystemIntegration:
    """Test real integration of memory components (SessionManager only - no OpenAI)."""

    def test_session_manager_creates_and_retrieves_sessions(self, temp_storage):
        """Test SessionManager can create and retrieve sessions."""
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=24
        )

        # Create session
        chat_id = "1234567890@c.us"
        session = session_manager.get_session(chat_id)

        assert session.whatsapp_chat == chat_id
        assert session.session_id is not None
        assert len(session.message_ids) == 0

    def test_session_manager_stores_messages(self, temp_storage):
        """Test SessionManager can store and retrieve messages."""
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=24
        )

        chat_id = "1234567890@c.us"

        # Add user message
        session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Hello, how are you?",
            user_role="client",
            sender="whatsapp_tester1",
            recipient="AI_test"
        )

        # Add assistant message
        session_manager.add_message(
            chat_id=chat_id,
            role="assistant",
            content="I'm doing well, thank you!",
            user_role="client",
            sender="AI_test",
            recipient="whatsapp_tester1"
        )

        # Retrieve conversation history
        history = session_manager.get_conversation_history(whatsapp_chat=chat_id)

        assert len(history) == 2
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == "Hello, how are you?"
        assert history[1]['role'] == 'assistant'
        assert history[1]['content'] == "I'm doing well, thank you!"

    def test_session_manager_clears_session(self, temp_storage):
        """Test SessionManager can clear sessions."""
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=24
        )

        chat_id = "1234567890@c.us"

        # Add messages
        session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Message 1",
            user_role="client",
            sender="whatsapp_tester1", recipient="AI_test"
        )
        session_manager.add_message(
            chat_id=chat_id,
            role="assistant",
            content="Response 1",
            user_role="client",
            sender="AI_test", recipient="whatsapp_tester1"
        )

        # Verify messages exist
        history_before = session_manager.get_conversation_history(whatsapp_chat=chat_id)
        assert len(history_before) == 2

        # Clear session
        session_manager.clear_session(chat_id)

        # Verify messages cleared
        history_after = session_manager.get_conversation_history(whatsapp_chat=chat_id)
        assert len(history_after) == 0

    def test_session_expiration_detection(self, temp_storage):
        """Test SessionManager can detect expired sessions using real time."""
        import time

        # Use 1-second timeout for real-time testing
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=1/3600  # 1 second in hours
        )

        chat_id = "1234567890@c.us"

        # Add a message to create session with current time
        session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Test message",
            user_role="client",
            sender="whatsapp_tester1",
            recipient="AI_test"
        )

        session = session_manager.get_session(chat_id)

        # Session should NOT be expired yet
        is_expired = session_manager.is_session_expired(session)
        assert is_expired is False

        # Wait for 1.5 seconds to let it expire
        time.sleep(1.5)

        # Now it should be expired
        is_expired = session_manager.is_session_expired(session)
        assert is_expired is True
