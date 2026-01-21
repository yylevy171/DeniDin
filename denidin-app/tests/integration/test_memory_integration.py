"""
Integration tests for Memory System (Phase 6)
Tests real component integration without mocks.
"""
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from src.models.config import AppConfiguration
from src.handlers.ai_handler import AIHandler
from src.memory.session_manager import SessionManager
from src.memory.memory_manager import MemoryManager


@pytest.fixture(scope="module")
def test_config():
    """Load real config for integration tests."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    with open(config_path) as f:
        return json.load(f)


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


@pytest.fixture
def config_with_memory(temp_storage, test_config):
    """Create test configuration with memory system enabled."""
    return AppConfiguration(
        green_api_instance_id="test_instance",
        green_api_token="test_token",
        openai_api_key=test_config['openai_api_key'],
        data_root=temp_storage['temp_dir'],  # Use temp directory as data root for tests
        feature_flags={'enable_memory_system': True},
        memory={
            'session': {
                'storage_dir': f"{temp_storage['temp_dir']}/sessions",
                'session_timeout_hours': 24,
                'max_tokens_by_role': {'client': 4000, 'godfather': 100000}
            },
            'longterm': {
                'enabled': True,
                'storage_dir': f"{temp_storage['temp_dir']}/memory",
                'collection_name': 'test_memory',
                'embedding_model': 'text-embedding-3-small',
                'top_k_results': 5,
                'min_similarity': 0.7
            }
        }
    )


class TestMemorySystemIntegration:
    """Test real integration of memory components."""
    
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
        
        # Stop cleanup thread
        session_manager.stop_cleanup_thread()
    
    def test_session_manager_stores_messages(self, temp_storage):
        """Test SessionManager can store and retrieve messages."""
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=24
        )
        
        chat_id = "1234567890@c.us"
        
        # Add user message
        msg_id_1 = session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Hello, how are you?",
            user_role="client",
            sender="whatsapp_tester1",
            recipient="AI_test"
        )
        
        # Add assistant message
        msg_id_2 = session_manager.add_message(
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
        
        session_manager.stop_cleanup_thread()
    
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
        
        session_manager.stop_cleanup_thread()
    
    def test_memory_manager_stores_and_recalls(self, temp_storage, test_config):
        """Test MemoryManager can store and recall memories (requires real OpenAI API)."""
        openai_client = OpenAI(api_key=test_config['openai_api_key'])
        
        memory_manager = MemoryManager(
            storage_dir=temp_storage['memory_dir'],
            embedding_model='text-embedding-3-small',
            openai_client=openai_client
        )
        
        # Store a memory
        memory_id = memory_manager.remember(
            content="The user loves pizza and pasta",
            collection_name="test_memory",
            metadata={"type": "preference", "topic": "food"}
        )
        
        assert memory_id is not None
        
        # Recall the memory
        results = memory_manager.recall(
            query="What does the user like to eat?",
            collection_names=["test_memory"],
            top_k=5,
            min_similarity=0.5
        )
        
        assert len(results) > 0
        assert "pizza" in results[0]['content'].lower() or "pasta" in results[0]['content'].lower()
    
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
        
        session_manager.stop_cleanup_thread()
    
    def test_cleanup_interval_configurable(self, temp_storage):
        """Test SessionManager cleanup interval is configurable."""
        cleanup_interval = 1  # 1 second for testing
        
        session_manager = SessionManager(
            storage_dir=temp_storage['session_dir'],
            session_timeout_hours=24,
            cleanup_interval_seconds=cleanup_interval
        )
        
        assert session_manager.cleanup_interval_seconds == cleanup_interval
        
        session_manager.stop_cleanup_thread()
    
    def test_periodic_cleanup_transfers_expired_sessions(self, config_with_memory, test_config):
        """Test periodic cleanup actually transfers expired sessions using real time."""
        import time
        
        # Override config for 1-second timeout and cleanup interval
        config_with_memory.memory['session']['session_timeout_hours'] = 1/3600  # 1 second
        
        openai_client = OpenAI(api_key=test_config['openai_api_key'])
        
        # Create AIHandler with 1-second cleanup interval
        ai_handler = AIHandler(
            openai_client,
            config_with_memory,
            cleanup_interval_seconds=1  # Check every 1 second
        )
        
        chat_id = "test_periodic@c.us"
        
        # Add a message to create session
        ai_handler.session_manager.add_message(
            chat_id=chat_id,
            role="user",
            content="Test periodic cleanup",
            user_role="client",
            sender="whatsapp_tester1", recipient="AI_test"
        )
        
        # Verify session exists
        session = ai_handler.session_manager.get_session(chat_id)
        assert session is not None
        
        # Wait for session to expire AND cleanup to run (2.5 seconds total)
        # 1.5 seconds for expiration + 1 second for cleanup cycle
        time.sleep(2.5)
        
        # Check that session was transferred to long-term memory
        # Session should still exist but messages should be in long-term
        expired_dir = Path(config_with_memory.memory['session']['storage_dir']) / "expired"
        assert expired_dir.exists()
        
        # Session should be archived in expired folder
        archived_sessions = list(expired_dir.rglob("*/session.json"))
        assert len(archived_sessions) >= 1
        
        ai_handler.session_manager.stop_cleanup_thread()
    
    def test_ai_handler_stores_messages_in_session(self, config_with_memory, test_config):
        """Test AIHandler stores messages in session (requires real OpenAI API)."""
        openai_client = OpenAI(api_key=test_config['openai_api_key'])
        ai_handler = AIHandler(openai_client, config_with_memory)
        
        chat_id = "1234567890@c.us"
        
        # Create a simple request
        from src.models.message import WhatsAppMessage, AIRequest
        
        message = WhatsAppMessage(
            message_id="test_msg_1",
            chat_id=chat_id,
            sender_id="1234567890@c.us",
            sender_name="Test User",
            text_content="What is 2+2?",
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            message_type="text"
        )
        
        request = ai_handler.create_request(message, chat_id=chat_id, user_role='client')
        
        # Get response (this will call real OpenAI API)
        response = ai_handler.get_response(
            request,
            chat_id=chat_id,
            user_role='client',
            sender="whatsapp_tester1", recipient="AI_test"
        )
        
        # Verify messages were stored
        history = ai_handler.session_manager.get_conversation_history(whatsapp_chat=chat_id)
        
        assert len(history) == 2  # User message + AI response
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == "What is 2+2?"
        assert history[1]['role'] == 'assistant'
        assert len(history[1]['content']) > 0
        
        # Cleanup
        ai_handler.session_manager.stop_cleanup_thread()
    
    def test_orphaned_session_recovery_active_session(self, temp_storage):
        """Test recovery loads active sessions without transfer."""
        # Create a session manually
        session_dir = Path(temp_storage['session_dir'])
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_id = "test-session-123"
        session_path = session_dir / session_id
        session_path.mkdir(parents=True, exist_ok=True)
        
        # Create active session (not expired)
        session_data = {
            "session_id": session_id,
            "whatsapp_chat": "1234567890@c.us",
            "message_ids": [],
            "message_counter": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_active": datetime.now(timezone.utc).isoformat(),  # Recent
            "total_tokens": 0
        }
        
        import json
        with open(session_path / "session.json", 'w') as f:
            json.dump(session_data, f)
        
        # Initialize AIHandler (which calls recover_orphaned_sessions)
        config = AppConfiguration(
            green_api_instance_id="test",
            green_api_token="test",
            openai_api_key="test",
            feature_flags={'enable_memory_system': True},
            memory={
                'session': {
                    'storage_dir': temp_storage['session_dir'],
                    'session_timeout_hours': 24
                },
                'longterm': {'enabled': False}
            }
        )
        
        from unittest.mock import Mock
        mock_client = Mock(spec=OpenAI)
        ai_handler = AIHandler(mock_client, config)
        
        # Manually call recovery
        result = ai_handler.recover_orphaned_sessions()
        
        # Active session should NOT be transferred (loaded to short-term)
        assert result['total_found'] == 1
        assert result['transferred_to_long_term'] == 0
        assert result['loaded_to_short_term'] == 1
        
        ai_handler.session_manager.stop_cleanup_thread()


class TestResetCommandIntegration:
    """Test /reset command integration."""
    
    def test_reset_clears_session(self, temp_storage):
        """Test that clearing a session removes all messages."""
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
        
        # Simulate /reset by clearing session
        session_manager.clear_session(chat_id)
        
        # Verify empty
        history = session_manager.get_conversation_history(whatsapp_chat=chat_id)
        assert len(history) == 0
        
        session_manager.stop_cleanup_thread()


class TestConversationMemory:
    """Test conversation memory across multiple messages."""
    
    def test_multi_turn_conversation_maintains_context(self, config_with_memory, test_config):
        """Test that AI maintains context across multiple messages in a conversation."""
        openai_client = OpenAI(api_key=test_config['openai_api_key'])
        ai_handler = AIHandler(openai_client, config_with_memory)
        
        chat_id = "test_conversation@c.us"
        
        # First message: Start counting
        from src.models.message import WhatsAppMessage
        
        message1 = WhatsAppMessage(
            message_id="test_msg_1",
            chat_id=chat_id,
            sender_id=chat_id,
            sender_name="Test User",
            text_content="Let's count together to 10, I'll start. 1",
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            message_type="text"
        )
        
        request1 = ai_handler.create_request(message1, chat_id=chat_id, user_role='client')
        response1 = ai_handler.get_response(
            request1,
            chat_id=chat_id,
            user_role='client',
            sender="whatsapp_tester1", recipient="AI_test"
        )
        
        # Verify first response contains "2"
        assert "2" in response1.response_text, f"First response should contain '2', got: {response1.response_text}"
        
        # Second message: Continue counting
        message2 = WhatsAppMessage(
            message_id="test_msg_2",
            chat_id=chat_id,
            sender_id=chat_id,
            sender_name="Test User",
            text_content="3",
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            message_type="text"
        )
        
        request2 = ai_handler.create_request(message2, chat_id=chat_id, user_role='client')
        response2 = ai_handler.get_response(
            request2,
            chat_id=chat_id,
            user_role='client',
            sender="whatsapp_tester1", recipient="AI_test"
        )
        
        # Verify second response contains "4" (maintaining context)
        assert "4" in response2.response_text, f"Second response should contain '4' (maintaining context), got: {response2.response_text}"
        
        # Verify conversation history has all 4 messages
        history = ai_handler.session_manager.get_conversation_history(whatsapp_chat=chat_id)
        assert len(history) == 4  # 2 user messages + 2 AI responses
        
        # Cleanup
        ai_handler.session_manager.stop_cleanup_thread()
