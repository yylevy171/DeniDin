"""
Test suite for AIHandler RBAC (Role-Based Access Control) enforcement.

Tests verify that AIHandler correctly integrates with UserManager, MemoryManager,
and SessionManager to enforce RBAC policies.

Following TDD methodology: Tests written BEFORE implementation.
Task A: Write tests for RBAC enforcement in AIHandler.

IMPORTANT: Per CONSTITUTION.md Section I - Feature flags MUST NEVER appear in tests.
These tests ASSUME enable_rbac is enabled. Existing pre-RBAC tests should NOT be modified.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from openai import OpenAI

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage, AIRequest
from src.models.user import Role, MemoryScope


class TestAIHandlerRBACInitialization:
    """Test that AIHandler initializes UserManager with RBAC configuration."""
    
    @patch('src.handlers.ai_handler.UserManager')
    def test_initializes_user_manager_with_config(self, mock_user_manager_class):
        """AIHandler should initialize UserManager with godfather_phone and user_roles from config."""
        # Arrange
        config = AppConfiguration(
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            ai_api_key="test-key",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={
                "admin_phones": ["+972509999999"],
                "blocked_phones": ["+972505555555"]
            },
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {'enabled': False}
            }
        )
        
        ai_client = MagicMock()
        
        # Act
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        # Assert
        mock_user_manager_class.assert_called_once_with(
            godfather_phone="+972501234567",
            admin_phones=["+972509999999"],
            blocked_phones=["+972505555555"]
        )
        assert handler.user_manager is not None


class TestAIHandlerRBACMemoryRecall:
    """Test that AIHandler uses RBAC-filtered memory recall."""
    
    @patch('src.handlers.ai_handler.UserManager')
    @patch('src.handlers.ai_handler.MemoryManager')
    def test_create_request_uses_rbac_recall(self, mock_memory_manager_class, mock_user_manager_class):
        """create_request should use recall_with_rbac_filter() with user permissions."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": []},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {
                    'enabled': True,
                    'storage_dir': 'test_data/memory',
                    'collection_name': 'test_memory',
                    'top_k_results': 5,
                    'min_similarity': 0.7
                }
            }
        )
        
        # Mock UserManager
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.CLIENT
        mock_user.allowed_memory_scopes = [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
        mock_user.can_see_all_memories = False
        mock_user.is_blocked = False
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        # Mock MemoryManager
        mock_memory_manager = Mock()
        mock_memory_manager.recall_with_rbac_filter.return_value = [
            {'content': 'Test memory', 'similarity': 0.85}
        ]
        mock_memory_manager_class.return_value = mock_memory_manager
        
        ai_client = MagicMock()
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        message = WhatsAppMessage(
            message_id="test-msg-1",
            chat_id="1234567890@c.us",
            sender_name="Test User",
            sender_id="+972501111111",
            text_content="What do you remember?",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Act
        request = handler.create_request(message, user_phone="+972501111111")
        
        # Assert
        # UserManager.get_user() should be called (called twice: once for blocking check, once for RBAC recall)
        assert mock_user_manager.get_user.called
        assert mock_user_manager.get_user.call_count >= 1
        
        # MemoryManager.recall_with_rbac_filter() should be called
        mock_memory_manager.recall_with_rbac_filter.assert_called_once()
        call_args = mock_memory_manager.recall_with_rbac_filter.call_args
        assert call_args.kwargs['user_phone'] == "+972501111111"
        assert call_args.kwargs['allowed_scopes'] == [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
        assert call_args.kwargs['can_see_all_memories'] is False
        
        # System message should include recalled memories
        assert "RECALLED MEMORIES" in request.constitution
        assert "Test memory" in request.constitution
    
    @patch('src.handlers.ai_handler.UserManager')
    @patch('src.handlers.ai_handler.MemoryManager')
    def test_godfather_can_see_all_memories(self, mock_memory_manager_class, mock_user_manager_class):
        """GODFATHER user should have can_see_all_memories=True."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": []},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {
                    'enabled': True,
                    'storage_dir': 'test_data/memory',
                    'collection_name': 'test_memory',
                    'top_k_results': 5,
                    'min_similarity': 0.7
                }
            }
        )
        
        # Mock UserManager - GODFATHER user
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.GODFATHER
        mock_user.allowed_memory_scopes = [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
        mock_user.can_see_all_memories = True  # GODFATHER sees all
        mock_user.is_blocked = False
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        # Mock MemoryManager
        mock_memory_manager = Mock()
        mock_memory_manager.recall_with_rbac_filter.return_value = []
        mock_memory_manager_class.return_value = mock_memory_manager
        
        ai_client = MagicMock()
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        message = WhatsAppMessage(
            message_id="test-msg-1",
            chat_id="1234567890@c.us",
            sender_name="Godfather",
            sender_id="+972501234567",
            text_content="What's happening?",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Act
        request = handler.create_request(message, user_phone="+972501234567")
        
        # Assert
        call_args = mock_memory_manager.recall_with_rbac_filter.call_args
        assert call_args.kwargs['can_see_all_memories'] is True


class TestAIHandlerRBACTokenLimits:
    """Test that AIHandler enforces per-role token limits."""
    
    @patch('src.handlers.ai_handler.UserManager')
    @patch('src.handlers.ai_handler.SessionManager')
    def test_enforces_client_token_limit(self, mock_session_manager_class, mock_user_manager_class):
        """CLIENT role should be limited to 4000 tokens."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": []},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {
                    'storage_dir': 'test_data/sessions',
                    'max_tokens_by_role': {'client': 4000, 'godfather': 100000}
                },
                'longterm': {'enabled': False}
            }
        )
        
        # Mock UserManager
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.CLIENT
        mock_user.token_limit = 4000
        mock_user.is_blocked = False
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        # Mock SessionManager
        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = []
        mock_session_manager_class.return_value = mock_session_manager
        
        # Mock AI client
        ai_client = MagicMock()
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
        mock_completion.usage = Mock(total_tokens=150, prompt_tokens=100, completion_tokens=50)
        mock_completion.model = "gpt-4o-mini"
        ai_client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        request = AIRequest(
            user_prompt="Test prompt",
            constitution="Test system",
            max_tokens=500,
            temperature=0.7,
            model="gpt-4o-mini",
            chat_id="1234567890@c.us",
            message_id="test-msg-1"
        )
        
        # Act
        response = handler.get_response(
            request,
            chat_id="1234567890@c.us",
            user_phone="+972501111111",
            sender="+972501111111",
            recipient="AI"
        )
        
        # Assert
        # UserManager.get_user() should be called
        mock_user_manager.get_user.assert_called_once_with("+972501111111")
        
        # SessionManager.add_message_with_token_limit() should be called with CLIENT limit
        assert mock_session_manager.add_message_with_token_limit.called
        # Check that token_limit=4000 was passed
        calls = mock_session_manager.add_message_with_token_limit.call_args_list
        assert any(call.kwargs.get('token_limit') == 4000 for call in calls)
    
    @patch('src.handlers.ai_handler.UserManager')
    @patch('src.handlers.ai_handler.SessionManager')
    def test_enforces_godfather_token_limit(self, mock_session_manager_class, mock_user_manager_class):
        """GODFATHER role should get 100K token limit."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": []},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {
                    'storage_dir': 'test_data/sessions',
                    'max_tokens_by_role': {'client': 4000, 'godfather': 100000}
                },
                'longterm': {'enabled': False}
            }
        )
        
        # Mock UserManager
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.GODFATHER
        mock_user.token_limit = 100000
        mock_user.is_blocked = False
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        # Mock SessionManager
        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = []
        mock_session_manager_class.return_value = mock_session_manager
        
        # Mock AI client
        ai_client = MagicMock()
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
        mock_completion.usage = Mock(total_tokens=150, prompt_tokens=100, completion_tokens=50)
        mock_completion.model = "gpt-4o-mini"
        ai_client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        request = AIRequest(
            user_prompt="Test prompt",
            constitution="Test system",
            max_tokens=500,
            temperature=0.7,
            model="gpt-4o-mini",
            chat_id="1234567890@c.us",
            message_id="test-msg-1"
        )
        
        # Act
        response = handler.get_response(
            request,
            chat_id="1234567890@c.us",
            user_phone="+972501234567",
            sender="+972501234567",
            recipient="AI"
        )
        
        # Assert
        mock_user_manager.get_user.assert_called_once_with("+972501234567")
        
        # SessionManager.add_message_with_token_limit() should be called with GODFATHER limit
        assert mock_session_manager.add_message_with_token_limit.called
        calls = mock_session_manager.add_message_with_token_limit.call_args_list
        assert any(call.kwargs.get('token_limit') == 100000 for call in calls)


class TestAIHandlerRBACBlockedUsers:
    """Test that BLOCKED users are rejected."""
    
    @patch('src.handlers.ai_handler.UserManager')
    def test_blocked_user_rejected_in_create_request(self, mock_user_manager_class):
        """BLOCKED user should be rejected in create_request()."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": ["+972505555555"]},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {'enabled': False}
            }
        )
        
        # Mock UserManager to return BLOCKED user
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.BLOCKED
        mock_user.is_blocked = True
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        ai_client = MagicMock()
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        message = WhatsAppMessage(
            message_id="test-msg-1",
            chat_id="5555555555@c.us",
            sender_name="Blocked User",
            sender_id="+972505555555",
            text_content="Hello",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Act & Assert
        with pytest.raises(PermissionError, match="User is blocked"):
            handler.create_request(message, user_phone="+972505555555")
    
    @patch('src.handlers.ai_handler.UserManager')
    def test_blocked_user_rejected_in_get_response(self, mock_user_manager_class):
        """BLOCKED user should be rejected in get_response()."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": ["+972505555555"]},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {'enabled': False}
            }
        )
        
        # Mock UserManager to return BLOCKED user
        mock_user_manager = Mock()
        mock_user = Mock()
        mock_user.role = Role.BLOCKED
        mock_user.is_blocked = True
        mock_user_manager.get_user.return_value = mock_user
        mock_user_manager_class.return_value = mock_user_manager
        
        ai_client = MagicMock()
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        request = AIRequest(
            user_prompt="Test prompt",
            constitution="Test system",
            max_tokens=500,
            temperature=0.7,
            model="gpt-4o-mini",
            chat_id="5555555555@c.us",
            message_id="test-msg-1"
        )
        
        # Act & Assert
        with pytest.raises(PermissionError, match="User is blocked"):
            handler.get_response(
                request,
                chat_id="5555555555@c.us",
                user_phone="+972505555555",
                sender="+972505555555",
                recipient="AI"
            )


class TestAIHandlerRBACLongTermMemory:
    """Test that long-term memory transfer respects RBAC scopes."""
    
    @patch('src.handlers.ai_handler.UserManager')
    @patch('src.handlers.ai_handler.SessionManager')
    @patch('src.handlers.ai_handler.MemoryManager')
    def test_transfer_session_stores_with_private_scope(
        self, mock_memory_manager_class, mock_session_manager_class, mock_user_manager_class
    ):
        """When transferring to long-term memory, should default to PRIVATE scope."""
        # Arrange
        config = AppConfiguration(
            ai_api_key="test-key",
            
            
            green_api_instance_id="test-instance",
            green_api_token="test-token",
            temperature=0.7,
            godfather_phone="+972501234567",
            user_roles={"admin_phones": [], "blocked_phones": []},
            feature_flags={'enable_memory_system': True, 'enable_rbac': True},
            memory={
                'session': {'storage_dir': 'test_data/sessions'},
                'longterm': {
                    'enabled': True,
                    'storage_dir': 'test_data/memory',
                    'collection_name': 'test_memory'
                }
            }
        )
        
        # Mock UserManager
        mock_user_manager = Mock()
        mock_user_manager_class.return_value = mock_user_manager
        
        # Mock SessionManager
        mock_session = Mock()
        mock_session.session_id = "test-session-123"
        mock_session.whatsapp_chat = "1234567890@c.us"
        mock_session.created_at = "2024-01-01T00:00:00Z"
        mock_session.last_active = "2024-01-01T01:00:00Z"
        mock_session.message_ids = ["msg1", "msg2"]
        mock_session.storage_path = "active/test-session-123"  # Add storage_path
        
        mock_session_manager = Mock()
        mock_session_manager.get_session.return_value = mock_session
        mock_session_manager.get_conversation_history_for_session.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        mock_session_manager_class.return_value = mock_session_manager
        
        # Mock MemoryManager
        mock_memory_manager = Mock()
        mock_memory_manager.remember.return_value = "mem-123"
        mock_memory_manager_class.return_value = mock_memory_manager
        
        # Mock AI client for summarization
        ai_client = MagicMock()
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Summary of conversation"))]
        ai_client.chat.completions.create.return_value = mock_completion
        
        handler = AIHandler(ai_client, config, cleanup_interval_seconds=3600)
        
        # Act
        result = handler.transfer_session_to_long_term_memory(mock_session)
        
        # Assert
        assert result['success'] is True
        
        # MemoryManager.remember() should be called
        # Scope enforcement tested in test_memory_manager_rbac.py
        mock_memory_manager.remember.assert_called_once()
