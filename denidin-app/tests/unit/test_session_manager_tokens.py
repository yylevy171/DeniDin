"""Unit tests for SessionManager token limit enforcement."""

import pytest
from unittest.mock import Mock, patch
from src.managers.session_manager import SessionManager
from src.models.user import Role


class TestSessionManagerTokenCounting:
    """Test token counting functionality."""
    
    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temporary storage."""
        return SessionManager(
            storage_dir=str(tmp_path / "sessions"),
            session_timeout_hours=24
        )
    
    def test_add_message_tracks_token_count(self, session_manager):
        """Test that adding messages increments token count."""
        # Mock token counter
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
            mock_tiktoken.return_value = mock_encoder
            
            message_id = session_manager.add_message_with_tokens(
                chat_id="test_chat",
                role="user",
                content="Test message",
                user_role=Role.CLIENT
            )
            
            session = session_manager.get_session("test_chat")
            assert session.total_tokens == 5
    
    def test_add_multiple_messages_accumulates_tokens(self, session_manager):
        """Test that multiple messages accumulate token count."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.side_effect = [
                [1, 2, 3],  # 3 tokens
                [1, 2, 3, 4, 5],  # 5 tokens
                [1, 2]  # 2 tokens
            ]
            mock_tiktoken.return_value = mock_encoder
            
            session_manager.add_message_with_tokens(
                chat_id="test_chat",
                role="user",
                content="First",
                user_role=Role.CLIENT
            )
            session_manager.add_message_with_tokens(
                chat_id="test_chat",
                role="assistant",
                content="Second",
                user_role=Role.CLIENT
            )
            session_manager.add_message_with_tokens(
                chat_id="test_chat",
                role="user",
                content="Third",
                user_role=Role.CLIENT
            )
            
            session = session_manager.get_session("test_chat")
            assert session.total_tokens == 10  # 3 + 5 + 2


class TestSessionManagerTokenLimitEnforcement:
    """Test token limit enforcement and pruning."""
    
    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temporary storage."""
        return SessionManager(
            storage_dir=str(tmp_path / "sessions"),
            session_timeout_hours=24
        )
    
    def test_prune_messages_when_client_limit_exceeded(self, session_manager):
        """Test that oldest messages are pruned when CLIENT hits 4K limit."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            # Each message is 2000 tokens
            mock_encoder.encode.return_value = [1] * 2000
            mock_tiktoken.return_value = mock_encoder
            
            # Add 3 messages (6000 tokens total, exceeds 4K limit)
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="user",
                content="Message 1",
                user_role=Role.CLIENT,
                token_limit=4000
            )
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="assistant",
                content="Message 2",
                user_role=Role.CLIENT,
                token_limit=4000
            )
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="user",
                content="Message 3",
                user_role=Role.CLIENT,
                token_limit=4000
            )
            
            session = session_manager.get_session("test_chat")
            # Should have pruned oldest message, leaving 2 messages (4000 tokens)
            assert len(session.message_ids) == 2
            assert session.total_tokens == 4000
    
    def test_godfather_can_exceed_client_limit(self, session_manager):
        """Test that GODFATHER can exceed 4K CLIENT limit."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1] * 3000  # 3K each
            mock_tiktoken.return_value = mock_encoder
            
            # Add 2 messages as GODFATHER (6K total, would exceed CLIENT limit)
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="user",
                content="Message 1",
                user_role=Role.GODFATHER,
                token_limit=100_000
            )
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="assistant",
                content="Message 2",
                user_role=Role.GODFATHER,
                token_limit=100_000
            )
            
            session = session_manager.get_session("test_chat")
            # Should keep both messages (under 100K limit)
            assert len(session.message_ids) == 2
            assert session.total_tokens == 6000
    
    def test_prune_keeps_most_recent_messages(self, session_manager):
        """Test that pruning keeps most recent messages, removes oldest."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1] * 1500  # 1.5K each
            mock_tiktoken.return_value = mock_encoder
            
            # Add 4 messages (6K total, exceeds 4K limit)
            for i in range(4):
                session_manager.add_message_with_token_limit(
                    chat_id="test_chat",
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i+1}",
                    user_role=Role.CLIENT,
                    token_limit=4000
                )
            
            session = session_manager.get_session("test_chat")
            history = session_manager.get_conversation_history("test_chat")
            
            # Should have pruned 2 oldest, kept 2 newest
            assert len(history) == 2
            assert "Message 3" in history[0]['content']
            assert "Message 4" in history[1]['content']
    
    def test_blocked_user_cannot_add_messages(self, session_manager):
        """Test that BLOCKED user cannot add messages (0 token limit)."""
        with pytest.raises(ValueError, match="Token limit exceeded"):
            session_manager.add_message_with_token_limit(
                chat_id="test_chat",
                role="user",
                content="Blocked user message",
                user_role=Role.BLOCKED,
                token_limit=0
            )


class TestSessionManagerTokenHelpers:
    """Test helper methods for token management."""
    
    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temporary storage."""
        return SessionManager(
            storage_dir=str(tmp_path / "sessions"),
            session_timeout_hours=24
        )
    
    def test_count_tokens_uses_tiktoken(self, session_manager):
        """Test that count_tokens uses tiktoken for accurate counting."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.return_value = mock_encoder
            
            count = session_manager.count_tokens("Test message")
            assert count == 5
            mock_tiktoken.assert_called_once_with('gpt-4o-mini')
    
    def test_calculate_total_tokens_sums_all_messages(self, session_manager):
        """Test that total tokens calculation sums all message tokens."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.side_effect = [
                [1, 2, 3],  # 3 tokens
                [1, 2, 3, 4, 5],  # 5 tokens
                [1, 2]  # 2 tokens
            ]
            mock_tiktoken.return_value = mock_encoder
            
            # Add messages using regular method (no token enforcement)
            session_manager.add_message("test_chat", "user", "First", Role.CLIENT)
            session_manager.add_message("test_chat", "assistant", "Second", Role.CLIENT)
            session_manager.add_message("test_chat", "user", "Third", Role.CLIENT)
            
            total = session_manager.calculate_session_tokens("test_chat")
            assert total == 10
    
    def test_prune_to_limit_removes_oldest_first(self, session_manager):
        """Test that prune_to_limit removes oldest messages first."""
        # Create session with messages
        session_manager.add_message("test_chat", "user", "Message 1", Role.CLIENT)
        session_manager.add_message("test_chat", "assistant", "Message 2", Role.CLIENT)
        session_manager.add_message("test_chat", "user", "Message 3", Role.CLIENT)
        session_manager.add_message("test_chat", "assistant", "Message 4", Role.CLIENT)
        
        session = session_manager.get_session("test_chat")
        original_count = len(session.message_ids)
        
        # Prune to keep only 2 messages
        session_manager.prune_to_limit("test_chat", keep_count=2)
        
        session = session_manager.get_session("test_chat")
        assert len(session.message_ids) == 2
        assert original_count == 4
        
        # Verify we kept the newest messages
        history = session_manager.get_conversation_history("test_chat")
        assert "Message 3" in history[0]['content']
        assert "Message 4" in history[1]['content']
    
    def test_get_session_token_count(self, session_manager):
        """Test getting current token count for a session."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1] * 100  # 100 tokens each
            mock_tiktoken.return_value = mock_encoder
            
            session_manager.add_message_with_tokens("test_chat", "user", "Test", Role.CLIENT)
            session_manager.add_message_with_tokens("test_chat", "assistant", "Reply", Role.CLIENT)
            
            count = session_manager.get_session_token_count("test_chat")
            assert count == 200
