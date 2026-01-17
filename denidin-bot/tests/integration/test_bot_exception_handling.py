"""
Integration tests for bot exception handling (Phase 5: US3)
Tests global exception handler in bot.py
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from whatsapp_chatbot_python import Notification
import importlib
import sys


@pytest.fixture
def reload_denidin():
    """Reload denidin module to ensure clean state for each test"""
    # Remove from cache if exists
    if 'denidin' in sys.modules:
        del sys.modules['denidin']
    yield
    # Clean up after test
    if 'denidin' in sys.modules:
        del sys.modules['denidin']


@pytest.fixture
def mock_notification():
    """Create a mock Green API notification"""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'textMessage',
            'textMessageData': {
                'textMessage': 'Test message'
            }
        },
        'senderData': {
            'sender': '1234567890@c.us',
            'senderName': 'Test User'
        },
        'idMessage': 'msg_123'
    }
    return notification


@pytest.fixture
def mock_whatsapp_message():
    """Create a mock WhatsAppMessage"""
    from src.models.message import WhatsAppMessage
    return WhatsAppMessage(
        message_id='msg_123',
        chat_id='123@c.us',
        sender_id='123@c.us',
        sender_name='Test',
        text_content='Hello',
        timestamp=1234567890,
        message_type='textMessage',
        is_group=False
    )


class TestBotExceptionHandling:
    """Test global exception handling in bot.py"""
    
    def test_handle_text_message_catches_any_exception(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test handle_text_message catches any Exception"""
        import denidin
        from unittest.mock import patch
        
        # Patch the handler instance methods
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'get_response', side_effect=KeyError("Unexpected error")):
                        with patch.object(denidin, 'logger'):
                            # Should not raise exception
                            denidin.handle_text_message(mock_notification)
                            
                            # Verify generic fallback sent
                            mock_notification.answer.assert_called()
                            reply = mock_notification.answer.call_args[0][0]
                            assert "error" in reply.lower() or "sorry" in reply.lower()
    
    def test_full_traceback_logged(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test full traceback logged with exc_info=True"""
        import denidin
        from unittest.mock import patch
        
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'get_response', side_effect=ValueError("Test error")):
                        with patch.object(denidin, 'logger') as mock_logger:
                            denidin.handle_text_message(mock_notification)
                            
                            # Verify error logged with traceback
                            assert mock_logger.error.called
                            # Check exc_info parameter was used
                            call_kwargs = mock_logger.error.call_args[1] if mock_logger.error.call_args else {}
                            assert call_kwargs.get('exc_info') is True
    
    def test_generic_fallback_sent_on_exception(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test generic fallback sent on any exception"""
        import denidin
        from unittest.mock import patch
        
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'get_response', side_effect=RuntimeError("Unknown error")):
                        with patch.object(denidin, 'logger'):
                            denidin.handle_text_message(mock_notification)
                            
                            mock_notification.answer.assert_called_once()
                            reply = mock_notification.answer.call_args[0][0]
                            assert "Sorry" in reply or "error" in reply.lower()
                            assert "try again" in reply.lower()
    
    def test_bot_continues_running_after_exception(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test bot continues running after exception (doesn't crash)"""
        import denidin
        from src.models.message import AIResponse
        from unittest.mock import patch
        import time
        
        # Simulate exception on first call, success on second
        success_response = AIResponse(
            request_id='req_123',
            response_text='Success',
            tokens_used=50,
            prompt_tokens=10,
            completion_tokens=40,
            model='gpt-4o-mini',
            finish_reason='stop',
            timestamp=int(time.time()),
            is_truncated=False
        )
        
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'create_request', return_value=Mock()):
                        with patch.object(denidin.ai_handler, 'get_response', side_effect=[
                            Exception("First error"),
                            success_response
                        ]):
                            with patch.object(denidin.whatsapp_handler, 'send_response'):
                                with patch.object(denidin, 'logger'):
                                    # First call with exception
                                    denidin.handle_text_message(mock_notification)
                                    
                                    # Bot should still be able to process next message
                                    denidin.handle_text_message(mock_notification)
                                    
                                    # Both calls should complete (first with fallback, second with success)
                                    assert mock_notification.answer.call_count == 1  # Only fallback on first error
    
    def test_unexpected_key_error_handled(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test unexpected KeyError is caught and logged"""
        import denidin
        from unittest.mock import patch
        
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'get_response', side_effect=KeyError("missing_key")):
                        with patch.object(denidin, 'logger') as mock_logger:
                            denidin.handle_text_message(mock_notification)
                            
                            assert mock_logger.error.called
                            mock_notification.answer.assert_called()
    
    def test_unexpected_value_error_handled(
        self, mock_notification, mock_whatsapp_message, reload_denidin
    ):
        """Test unexpected ValueError is caught and logged"""
        import denidin
        from unittest.mock import patch
        
        with patch.object(denidin.whatsapp_handler, 'validate_message_type', return_value=True):
            with patch.object(denidin.whatsapp_handler, 'process_notification', return_value=mock_whatsapp_message):
                with patch.object(denidin.whatsapp_handler, 'is_bot_mentioned_in_group', return_value=True):
                    with patch.object(denidin.ai_handler, 'get_response', side_effect=ValueError("invalid value")):
                        with patch.object(denidin, 'logger') as mock_logger:
                            denidin.handle_text_message(mock_notification)
                            
                            assert mock_logger.error.called
                            mock_notification.answer.assert_called()


class TestMessageLengthValidation:
    """Test message length validation in AIHandler"""
    
    @patch('src.handlers.ai_handler.logger')
    def test_prompt_over_10000_chars_triggers_warning(
        self, mock_logger
    ):
        """Test prompt >10000 chars triggers warning log"""
        from src.handlers.ai_handler import AIHandler
        from src.models.config import BotConfiguration
        from src.models.message import WhatsAppMessage
        
        config = Mock(spec=BotConfiguration)
        config.ai_model = "gpt-4o-mini"
        config.system_message = "You are helpful."
        config.max_tokens = 500
        config.temperature = 0.7
        
        handler = AIHandler(MagicMock(), config)
        
        # Create message with >10000 chars
        long_text = "a" * 10001
        message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="123@c.us",
            sender_id="123@c.us",
            sender_name="User",
            text_content=long_text,
            timestamp=1234567890,
            message_type="textMessage",
            is_group=False
        )
        
        request = handler.create_request(message)
        
        # Should log warning
        assert mock_logger.warning.called or mock_logger.info.called
    
    def test_long_prompt_truncated_to_10000_chars(self):
        """Test long prompt truncated to 10000 chars"""
        from src.handlers.ai_handler import AIHandler
        from src.models.config import BotConfiguration
        from src.models.message import WhatsAppMessage
        
        config = Mock(spec=BotConfiguration)
        config.ai_model = "gpt-4o-mini"
        config.system_message = "You are helpful."
        config.max_tokens = 500
        config.temperature = 0.7
        
        handler = AIHandler(MagicMock(), config)
        
        long_text = "a" * 10001
        message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="123@c.us",
            sender_id="123@c.us",
            sender_name="User",
            text_content=long_text,
            timestamp=1234567890,
            message_type="textMessage",
            is_group=False
        )
        
        request = handler.create_request(message)
        
        # Should truncate to 10000
        assert len(request.user_prompt) <= 10000
    
    def test_short_messages_pass_through_unchanged(self):
        """Test short messages (<10000) pass through unchanged"""
        from src.handlers.ai_handler import AIHandler
        from src.models.config import BotConfiguration
        from src.models.message import WhatsAppMessage
        
        config = Mock(spec=BotConfiguration)
        config.ai_model = "gpt-4o-mini"
        config.system_message = "You are helpful."
        config.max_tokens = 500
        config.temperature = 0.7
        
        handler = AIHandler(MagicMock(), config)
        
        short_text = "Hello, this is a normal message."
        message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="123@c.us",
            sender_id="123@c.us",
            sender_name="User",
            text_content=short_text,
            timestamp=1234567890,
            message_type="textMessage",
            is_group=False
        )
        
        request = handler.create_request(message)
        
        # Should remain unchanged
        assert request.user_prompt == short_text
