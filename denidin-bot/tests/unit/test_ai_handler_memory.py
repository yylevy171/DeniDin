"""
Unit tests for AIHandler memory system integration.
Tests session storage, memory recall, and conversation history.

Per TDD workflow: Write tests FIRST, then implement features.

Note: These tests assume memory system is ENABLED (feature_flags.enable_memory_system = True).
To run without memory, set the flag to False in config and these tests should fail/skip.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from openai import OpenAI
from src.handlers.ai_handler import AIHandler
from src.models.config import BotConfiguration
from src.models.message import WhatsAppMessage


@pytest.fixture
def memory_enabled_config():
    """Config fixture with memory system enabled for testing."""
    return BotConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        openai_api_key="test-key",
        ai_model="gpt-4o-mini",
        system_message="You are a helpful assistant.",
        max_tokens=100,
        temperature=0.7,
        log_level="INFO",
        poll_interval_seconds=5,
        max_retries=3,
        feature_flags={"enable_memory_system": True},
        memory={
            "session": {
                "storage_dir": "test_data/sessions",
                "max_tokens_by_role": {"client": 4000, "godfather": 100000},
                "session_timeout_hours": 24
            },
            "longterm": {
                "storage_dir": "test_data/memory",
                "embedding_model": "text-embedding-3-small",
                "top_k_results": 5,
                "min_similarity": 0.7
            }
        }
    )


class TestAIHandlerMemoryInitialization:
    """Test memory manager initialization."""
    
    def test_initialize_with_memory_managers(self, memory_enabled_config):
        """Verify memory managers are initialized correctly."""
        client = MagicMock()
        handler = AIHandler(client, memory_enabled_config)
        
        # Memory managers should be initialized
        assert handler.session_manager is not None
        assert handler.memory_manager is not None


class TestAIHandlerCreateRequestWithMemory:
    """Test create_request with memory recall."""
    
    def test_create_request_includes_recalled_memories(self, memory_enabled_config):
        """Verify recalled memories are added to system prompt."""
        client = MagicMock()
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock memory manager recall
        mock_memories = [
            {"content": "User prefers Python", "similarity": 0.85},
            {"content": "User works at TechCorp", "similarity": 0.78}
        ]
        handler.memory_manager.recall = Mock(return_value=mock_memories)
        
        message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="chat_456",
            sender_name="Alice",
            sender_id="1234567890@c.us",
            text_content="What do you know about me?",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message, chat_id="chat_456", user_role="client")
        
        # Should include recalled memories in system message
        assert "RECALLED MEMORIES" in request.system_message
        assert "User prefers Python" in request.system_message
        assert "User works at TechCorp" in request.system_message
        assert "0.85" in request.system_message
        
        # Verify recall was called with correct parameters
        handler.memory_manager.recall.assert_called_once()
        call_args = handler.memory_manager.recall.call_args[1]
        assert call_args["query"] == "What do you know about me?"
        assert "memory_chat_456" in call_args["collection_names"]
        assert call_args["top_k"] == 5
        assert call_args["min_similarity"] == 0.7


class TestAIHandlerGetResponseWithMemory:
    """Test get_response with session storage."""
    
    def test_get_response_stores_messages_in_session(self, memory_enabled_config):
        """Verify user and AI messages are stored in session."""
        # Mock OpenAI client
        client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello! How can I help you?"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.total_tokens = 50
        mock_completion.usage.prompt_tokens = 20
        mock_completion.usage.completion_tokens = 30
        mock_completion.model = "gpt-4o-mini"
        client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock session manager
        handler.session_manager.add_message = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])
        
        # Create request
        from src.models.message import AIRequest
        request = AIRequest(
            user_prompt="Hello",
            system_message="Test",
            max_tokens=100,
            temperature=0.7,
            model="gpt-4o-mini",
            chat_id="chat_123",
            message_id="msg_456"
        )
        
        # Get response
        response = handler.get_response(
            request,
            chat_id="chat_123",
            user_role="client",
            sender="whatsapp_tester1",
            recipient="AI_test"
        )
        
        # Verify both messages were stored
        assert handler.session_manager.add_message.call_count == 2
        
        # First call: user message
        first_call = handler.session_manager.add_message.call_args_list[0]
        assert first_call[1]["chat_id"] == "chat_123"
        assert first_call[1]["role"] == "user"
        assert first_call[1]["content"] == "Hello"
        assert first_call[1]["sender"] == "whatsapp_tester1"
        assert first_call[1]["recipient"] == "AI_test"
        
        # Second call: assistant message
        # AI messages have sender=recipient (AI_test) and recipient=original sender (whatsapp_tester1)
        second_call = handler.session_manager.add_message.call_args_list[1]
        assert second_call[1]["role"] == "assistant"
        assert second_call[1]["content"] == "Hello! How can I help you?"
        assert second_call[1]["sender"] == "AI_test"  # recipient becomes sender for AI
        assert second_call[1]["recipient"] == "whatsapp_tester1"  # sender becomes recipient for AI


class TestAIHandlerConversationHistory:
    """Test conversation history in API calls."""
    
    def test_api_call_includes_conversation_history(self, memory_enabled_config):
        """Verify conversation history is included in OpenAI API calls."""
        client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Response"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.total_tokens = 50
        mock_completion.usage.prompt_tokens = 20
        mock_completion.usage.completion_tokens = 30
        mock_completion.model = "gpt-4o-mini"
        client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock conversation history
        mock_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        handler.session_manager.get_conversation_history = Mock(return_value=mock_history)
        handler.session_manager.add_message = Mock()
        
        from src.models.message import AIRequest
        request = AIRequest(
            user_prompt="Current question",
            system_message="Test system",
            max_tokens=100,
            temperature=0.7,
            model="gpt-4o-mini",
            chat_id="chat_123",
            message_id="msg_456"
        )
        
        # Call get_response with user_role to trigger history fetching
        response = handler.get_response(
            request,
            user_role="client",
            chat_id="chat_123",
            sender="user_123",
            recipient="bot_456"
        )
        
        # Verify conversation history was retrieved
        handler.session_manager.get_conversation_history.assert_called_once_with(
            whatsapp_chat="chat_123",
            max_tokens=4000  # client role default
        )
        
        # Verify API was called with conversation history
        client.chat.completions.create.assert_called_once()
        call_args = client.chat.completions.create.call_args[1]
        messages = call_args["messages"]
        
        # Should have: system + history (2 msgs) + current user msg = 4 messages
        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": "Test system"}
        assert messages[1] == {"role": "user", "content": "Previous question"}
        assert messages[2] == {"role": "assistant", "content": "Previous answer"}
        assert messages[3] == {"role": "user", "content": "Current question"}
        
        # Verify response was returned
        assert response.response_text == "Response"
        assert response.tokens_used == 50


class TestAIHandlerHybridMemory:
    """Test using BOTH conversation history AND long-term memory together."""
    
    def test_hybrid_memory_recall_with_conversation_context(self, memory_enabled_config):
        """
        Verify that a single request uses BOTH:
        1. Long-term memory (semantic recall from ChromaDB)
        2. Conversation history (recent messages from session)
        
        Scenario: User had a previous conversation about invoicing, then stored
        a long-term fact about a client, and now asks a follow-up question.
        The AI should have access to BOTH the conversation and the stored fact.
        """
        client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Based on our earlier discussion and your stored info, I can help."
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.total_tokens = 100
        mock_completion.usage.prompt_tokens = 60
        mock_completion.usage.completion_tokens = 40
        mock_completion.model = "gpt-4o-mini"
        client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock conversation history (recent session messages)
        mock_conversation_history = [
            {"role": "user", "content": "I need to create an invoice"},
            {"role": "assistant", "content": "Sure, for which client?"},
            {"role": "user", "content": "For TestCorp"}
        ]
        handler.session_manager.get_conversation_history = Mock(return_value=mock_conversation_history)
        handler.session_manager.add_message = Mock()
        
        # Mock long-term memory recall (facts stored in ChromaDB)
        mock_recalled_memories = [
            {"content": "TestCorp payment terms: NET30", "similarity": 0.82},
            {"content": "TestCorp contact: john@testcorp.com", "similarity": 0.75}
        ]
        handler.memory_manager.recall = Mock(return_value=mock_recalled_memories)
        
        # User asks a follow-up question
        message = WhatsAppMessage(
            message_id="msg_789",
            chat_id="chat_456",
            sender_name="Alice",
            sender_id="1234567890@c.us",
            text_content="What are their payment terms?",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Create request (should include recalled memories in system message)
        request = handler.create_request(message, chat_id="chat_456", user_role="client")
        
        # Get response (should include conversation history in API call)
        response = handler.get_response(
            request,
            chat_id="chat_456",
            user_role="client",
            sender="user@c.us",
            recipient="bot@c.us"
        )
        
        # VERIFY LONG-TERM MEMORY: Recalled facts in system message
        assert "RECALLED MEMORIES" in request.system_message
        assert "TestCorp payment terms: NET30" in request.system_message
        assert "TestCorp contact: john@testcorp.com" in request.system_message
        
        # VERIFY CONVERSATION HISTORY: API call includes recent messages
        client.chat.completions.create.assert_called_once()
        api_call_args = client.chat.completions.create.call_args[1]
        api_messages = api_call_args["messages"]
        
        # Should have: system (with recalled memories) + 3 history msgs + current msg = 5 total
        assert len(api_messages) == 5
        assert api_messages[0]["role"] == "system"
        assert "RECALLED MEMORIES" in api_messages[0]["content"]  # Long-term memory
        assert api_messages[1] == {"role": "user", "content": "I need to create an invoice"}  # History
        assert api_messages[2] == {"role": "assistant", "content": "Sure, for which client?"}  # History
        assert api_messages[3] == {"role": "user", "content": "For TestCorp"}  # History
        assert api_messages[4] == {"role": "user", "content": "What are their payment terms?"}  # Current
        
        # VERIFY BOTH MEMORIES WERE QUERIED
        handler.memory_manager.recall.assert_called_once()  # Long-term lookup
        handler.session_manager.get_conversation_history.assert_called_once()  # Session lookup
        
        # VERIFY NEW MESSAGES STORED (conversation continues)
        assert handler.session_manager.add_message.call_count == 2  # User msg + AI response


class TestAIHandlerSessionToLongTermMemory:
    """Test transferring session conversations to long-term memory."""
    
    def test_transfer_session_to_long_term_memory_on_session_end(self, memory_enabled_config):
        """
        Verify that when a session ends (expires/closes), its conversation
        is summarized and stored in long-term memory for future recall.
        
        Scenario: User has a conversation about a client project. When the
        session expires (after 24h of inactivity), the system should:
        1. Summarize the key facts from the conversation
        2. Store the summary in ChromaDB for long-term recall
        3. Tag it with metadata (session_id, date, participants)
        
        This enables future conversations to benefit from past discussions.
        """
        client = MagicMock()
        
        # Mock OpenAI for summarization
        mock_summary_completion = MagicMock()
        mock_summary_completion.choices = [MagicMock()]
        mock_summary_completion.choices[0].message.content = (
            "Key facts from conversation:\n"
            "- TestCorp needs invoice for Q4 consulting work\n"
            "- Amount: $50,000 USD\n"
            "- Payment terms: NET30\n"
            "- Due date: January 31, 2026"
        )
        mock_summary_completion.choices[0].finish_reason = "stop"
        mock_summary_completion.usage.total_tokens = 150
        mock_summary_completion.usage.prompt_tokens = 100
        mock_summary_completion.usage.completion_tokens = 50
        mock_summary_completion.model = "gpt-4o-mini"
        client.chat.completions.create.return_value = mock_summary_completion
        
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock session manager with conversation history
        mock_session = Mock()
        mock_session.session_id = "session_uuid_123"
        mock_session.whatsapp_chat = "1234567890@c.us"
        mock_session.created_at = "2026-01-17T10:00:00Z"
        mock_session.last_active = "2026-01-17T15:30:00Z"
        mock_session.message_ids = ["msg1", "msg2", "msg3", "msg4"]
        
        mock_conversation = [
            {"role": "user", "content": "I need to invoice TestCorp for Q4 consulting"},
            {"role": "assistant", "content": "Sure! What's the amount?"},
            {"role": "user", "content": "$50,000 USD, NET30 terms"},
            {"role": "assistant", "content": "Got it. I'll help you create that invoice."}
        ]
        
        handler.session_manager.get_session = Mock(return_value=mock_session)
        handler.session_manager.get_conversation_history = Mock(return_value=mock_conversation)
        handler.memory_manager.remember = Mock(return_value="memory_uuid_456")
        
        # Call the session-to-memory transfer method
        result = handler.transfer_session_to_long_term_memory(
            chat_id="1234567890@c.us",
            session_id="session_uuid_123"
        )
        
        # VERIFY CONVERSATION WAS SUMMARIZED
        # Should call OpenAI to create summary
        client.chat.completions.create.assert_called_once()
        api_call = client.chat.completions.create.call_args[1]
        messages = api_call["messages"]
        
        # Should have system prompt + conversation history for summarization
        assert len(messages) >= 2  # At least system + conversation
        assert any("summarize" in msg.get("content", "").lower() for msg in messages if msg["role"] == "system")
        
        # VERIFY SUMMARY STORED IN LONG-TERM MEMORY
        handler.memory_manager.remember.assert_called_once()
        remember_call = handler.memory_manager.remember.call_args[1]
        
        # Summary content
        assert "TestCorp" in remember_call["content"]
        assert "$50,000" in remember_call["content"]
        assert "NET30" in remember_call["content"]
        
        # Collection name (chat-specific or global)
        assert "memory_" in remember_call["collection_name"]
        
        # Metadata includes session tracking
        metadata = remember_call["metadata"]
        assert metadata["type"] == "session_summary"
        assert metadata["session_id"] == "session_uuid_123"
        assert metadata["whatsapp_chat"] == "1234567890@c.us"
        assert "session_start" in metadata
        assert "session_end" in metadata
        assert metadata["message_count"] == 4
        
        # VERIFY RETURN VALUE
        assert result["success"] is True
        assert result["memory_id"] == "memory_uuid_456"
        assert result["summary_length"] > 0
    
    def test_handle_summarization_failure_gracefully(self, memory_enabled_config):
        """
        CRITICAL: If AI summarization fails, ALWAYS store the raw conversation.
        Errors are logged separately - the conversation itself MUST be preserved.
        
        No data loss, ever.
        """
        client = MagicMock()
        
        # Mock OpenAI failure
        client.chat.completions.create.side_effect = Exception("API timeout")
        
        handler = AIHandler(client, memory_enabled_config)
        
        mock_session = Mock()
        mock_session.session_id = "session_fail_001"
        mock_session.whatsapp_chat = "test@c.us"
        mock_session.created_at = "2026-01-17T10:00:00Z"
        mock_session.last_active = "2026-01-17T11:00:00Z"
        mock_session.message_ids = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        
        mock_conversation = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"}
        ]
        
        handler.session_manager.get_session = Mock(return_value=mock_session)
        handler.session_manager.get_conversation_history = Mock(return_value=mock_conversation)
        handler.memory_manager.remember = Mock(return_value="fallback_memory_001")
        
        result = handler.transfer_session_to_long_term_memory(
            chat_id="test@c.us",
            session_id="session_fail_001"
        )
        
        # MUST ALWAYS SUCCEED - conversation stored even if summarization failed
        assert result["success"] is True
        assert result["used_fallback"] is True
        assert result["memory_id"] == "fallback_memory_001"
        
        # Verify conversation stored in ChromaDB
        handler.memory_manager.remember.assert_called_once()
        remember_call = handler.memory_manager.remember.call_args[1]
        
        # Should contain FULL raw conversation text
        content = remember_call["content"]
        assert "Message 1" in content
        assert "Message 2" in content
        assert "Message 3" in content
        assert "Response 1" in content
        assert "Response 2" in content
        
        # Metadata indicates fallback (for monitoring/debugging)
        metadata = remember_call["metadata"]
        assert metadata["type"] == "session_summary_fallback"
        assert metadata["session_id"] == "session_fail_001"
        assert metadata["whatsapp_chat"] == "test@c.us"
        assert metadata["message_count"] == 5
        assert metadata["summarization_failed"] is True
        assert "session_start" in metadata
        assert "session_end" in metadata


class TestAIHandlerStartupRecovery:
    """
    Test startup recovery procedure for orphaned sessions.
    
    On bot startup, check for sessions that weren't properly transferred to
    long-term memory (e.g., due to crashes, unexpected shutdowns).
    """
    
    def test_startup_recovery_expired_sessions(self, memory_enabled_config):
        """
        CRITICAL STARTUP BEHAVIOR:
        
        On bot startup, scan for "active" sessions from past 24 hours that
        should have been transferred but weren't (orphaned sessions).
        
        Decision logic:
        - If session expired (>24h inactive) → transfer to long-term memory
        - If session still active (<24h inactive) → load to short-term memory
        
        Ensures NO data loss from crashes/restarts.
        """
        client = MagicMock()
        client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Summary of recovered session"))]
        )
        
        handler = AIHandler(client, memory_enabled_config)
        
        # Mock 3 orphaned sessions
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        # Session 1: Expired (30 hours old) - should go to long-term
        expired_session = Mock()
        expired_session.session_id = "expired_001"
        expired_session.whatsapp_chat = "user1@c.us"
        expired_session.last_active = (now - timedelta(hours=30)).isoformat() + "Z"
        expired_session.created_at = (now - timedelta(hours=31)).isoformat() + "Z"
        expired_session.message_ids = ["m1", "m2", "m3"]
        
        # Session 2: Still active (12 hours old) - should load to short-term
        active_session = Mock()
        active_session.session_id = "active_001"
        active_session.whatsapp_chat = "user2@c.us"
        active_session.last_active = (now - timedelta(hours=12)).isoformat() + "Z"
        active_session.created_at = (now - timedelta(hours=12)).isoformat() + "Z"
        active_session.message_ids = ["m4", "m5"]
        
        # Session 3: Just expired (25 hours) - should go to long-term
        barely_expired = Mock()
        barely_expired.session_id = "expired_002"
        barely_expired.whatsapp_chat = "user3@c.us"
        barely_expired.last_active = (now - timedelta(hours=25)).isoformat() + "Z"
        barely_expired.created_at = (now - timedelta(hours=26)).isoformat() + "Z"
        barely_expired.message_ids = ["m6"]
        
        # Mock session manager to return these orphaned sessions
        handler.session_manager.find_orphaned_sessions = Mock(return_value=[
            expired_session,
            active_session,
            barely_expired
        ])
        
        handler.session_manager.is_session_expired = Mock(side_effect=[
            True,   # expired_001
            False,  # active_001
            True    # expired_002
        ])
        
        # Mock get_session to return the appropriate session for each chat_id
        def get_session_side_effect(chat_id):
            if chat_id == "user1@c.us":
                return expired_session
            elif chat_id == "user2@c.us":
                return active_session
            elif chat_id == "user3@c.us":
                return barely_expired
            return None
        
        handler.session_manager.get_session = Mock(side_effect=get_session_side_effect)
        
        handler.session_manager.get_conversation_history = Mock(return_value=[
            {"role": "user", "content": "Test message"}
        ])
        
        handler.memory_manager.remember = Mock(side_effect=[
            "memory_001",  # For expired_001
            "memory_002"   # For expired_002
        ])
        
        # Call startup recovery
        result = handler.recover_orphaned_sessions()
        
        # VERIFY RESULTS
        assert result["total_found"] == 3
        assert result["transferred_to_long_term"] == 2  # expired_001, expired_002
        assert result["loaded_to_short_term"] == 1      # active_001
        
        # Verify expired sessions transferred to long-term memory
        assert handler.memory_manager.remember.call_count == 2
        
        # Verify sessions categorized correctly
        assert "expired_001" in result["long_term_sessions"]
        assert "expired_002" in result["long_term_sessions"]
        assert "active_001" in result["short_term_sessions"]
    
    def test_startup_recovery_no_orphaned_sessions(self, memory_enabled_config):
        """
        Verify clean startup when no orphaned sessions exist.
        """
        client = MagicMock()
        handler = AIHandler(client, memory_enabled_config)
        
        handler.session_manager.find_orphaned_sessions = Mock(return_value=[])
        
        result = handler.recover_orphaned_sessions()
        
        assert result["total_found"] == 0
        assert result["transferred_to_long_term"] == 0
        assert result["loaded_to_short_term"] == 0
    
    def test_startup_recovery_handles_errors_gracefully(self, memory_enabled_config):
        """
        Verify that startup recovery continues even if individual sessions fail.
        
        If one session fails to transfer, others should still be processed.
        """
        client = MagicMock()
        handler = AIHandler(client, memory_enabled_config)
        
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        session1 = Mock()
        session1.session_id = "fail_session"
        session1.whatsapp_chat = "user1@c.us"
        session1.last_active = (now - timedelta(hours=30)).isoformat() + "Z"
        session1.created_at = (now - timedelta(hours=31)).isoformat() + "Z"
        session1.message_ids = ["m1"]
        
        session2 = Mock()
        session2.session_id = "good_session"
        session2.whatsapp_chat = "user2@c.us"
        session2.last_active = (now - timedelta(hours=30)).isoformat() + "Z"
        session2.created_at = (now - timedelta(hours=31)).isoformat() + "Z"
        session2.message_ids = ["m2"]
        
        handler.session_manager.find_orphaned_sessions = Mock(return_value=[session1, session2])
        handler.session_manager.is_session_expired = Mock(return_value=True)
        
        # Mock get_session to return appropriate session
        def get_session_side_effect(chat_id):
            if chat_id == "user1@c.us":
                return session1
            elif chat_id == "user2@c.us":
                return session2
            return None
        
        handler.session_manager.get_session = Mock(side_effect=get_session_side_effect)
        
        handler.session_manager.get_conversation_history = Mock(return_value=[
            {"role": "user", "content": "Test"}
        ])
        
        # First transfer fails, second succeeds
        handler.memory_manager.remember = Mock(side_effect=[
            Exception("ChromaDB connection failed"),
            "memory_002"
        ])
        
        client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Summary"))]
        )
        
        result = handler.recover_orphaned_sessions()
        
        # Should continue despite failure
        assert result["total_found"] == 2
        assert result["transferred_to_long_term"] == 1  # Only session2 succeeded
        assert result["failed"] == 1
        assert "fail_session" in result["failed_sessions"]
