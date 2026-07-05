"""
Unit tests for WhatsAppHandler error handling (Phase 5: US3)
Tests Green API errors and unsupported message types
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import requests
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
from src.models.message import AIResponse, WhatsAppMessage
from whatsapp_chatbot_python import Notification


@pytest.fixture
def whatsapp_handler():
    """Create WhatsAppHandler instance"""
    return WhatsAppHandler()


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
                'textMessage': 'Hello'
            }
        },
        'senderData': {
            'sender': '1234567890@c.us',
            'senderName': 'John Doe'
        }
    }
    return notification


@pytest.fixture
def sample_ai_response():
    """Create a sample AI response"""
    return AIResponse(
        request_id="req_123",
        response_text="Test response",
        tokens_used=50,
        prompt_tokens=10,
        completion_tokens=40,
        model="gpt-4o-mini",
        finish_reason="stop",
        timestamp=1234567890,
        is_truncated=False
    )


class TestGreenAPIErrorHandling:
    """Test Green API HTTP error handling"""
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_send_response_catches_http_400_error(
        self, mock_logger, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test send_response catches 400 error and logs status code"""
        response = Mock()
        response.status_code = 400
        response.text = "Bad Request"
        
        mock_notification.answer.side_effect = requests.HTTPError(
            "400 Bad Request", response=response
        )
        
        # Should raise after retries
        with pytest.raises(requests.HTTPError):
            whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        # Verify error was logged with status code
        assert mock_logger.error.called
        log_call_args = str(mock_logger.error.call_args)
        assert "400" in log_call_args or "Bad Request" in log_call_args
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_send_response_catches_http_401_error(
        self, mock_logger, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test send_response catches 401 authentication error"""
        response = Mock()
        response.status_code = 401
        response.text = "Unauthorized"
        
        mock_notification.answer.side_effect = requests.HTTPError(
            "401 Unauthorized", response=response
        )
        
        with pytest.raises(requests.HTTPError):
            whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_logger.error.called
        log_call_args = str(mock_logger.error.call_args)
        assert "401" in log_call_args or "auth" in log_call_args.lower()
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_send_response_catches_http_429_error(
        self, mock_logger, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test send_response catches 429 rate limit error"""
        response = Mock()
        response.status_code = 429
        response.text = "Too Many Requests"
        
        mock_notification.answer.side_effect = requests.HTTPError(
            "429 Too Many Requests", response=response
        )
        
        with pytest.raises(requests.HTTPError):
            whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_logger.error.called
        log_call_args = str(mock_logger.error.call_args)
        assert "429" in log_call_args or "rate limit" in log_call_args.lower()
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_send_response_catches_http_500_error(
        self, mock_logger, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test send_response catches 500 server error"""
        response = Mock()
        response.status_code = 500
        response.text = "Internal Server Error"
        
        mock_notification.answer.side_effect = requests.HTTPError(
            "500 Internal Server Error", response=response
        )
        
        with pytest.raises(requests.HTTPError):
            whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_logger.error.called
        log_call_args = str(mock_logger.error.call_args)
        assert "500" in log_call_args or "server" in log_call_args.lower()


class TestUnsupportedMessageTypes:
    """Test handling of unsupported message types"""
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_validate_message_type_rejects_image_message(
        self, mock_logger, whatsapp_handler, mock_notification
    ):
        """Test validate_message_type rejects imageMessage"""
        mock_notification.event['messageData']['typeMessage'] = 'imageMessage'
        
        is_valid = whatsapp_handler.validate_message_type(mock_notification)
        
        assert is_valid is False
        # Should log warning
        assert mock_logger.warning.called or mock_logger.info.called
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_validate_message_type_rejects_audio_message(
        self, mock_logger, whatsapp_handler, mock_notification
    ):
        """Test validate_message_type rejects audioMessage"""
        mock_notification.event['messageData']['typeMessage'] = 'audioMessage'
        
        is_valid = whatsapp_handler.validate_message_type(mock_notification)
        
        assert is_valid is False
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_validate_message_type_rejects_video_message(
        self, mock_logger, whatsapp_handler, mock_notification
    ):
        """Test validate_message_type rejects videoMessage"""
        mock_notification.event['messageData']['typeMessage'] = 'videoMessage'
        
        is_valid = whatsapp_handler.validate_message_type(mock_notification)
        
        assert is_valid is False
    
    def test_validate_message_type_accepts_text_message(
        self, whatsapp_handler, mock_notification
    ):
        """Test validate_message_type accepts textMessage"""
        mock_notification.event['messageData']['typeMessage'] = 'textMessage'
        
        is_valid = whatsapp_handler.validate_message_type(mock_notification)
        
        assert is_valid is True
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_auto_reply_sent_for_unsupported_type(
        self, mock_logger, whatsapp_handler, mock_notification
    ):
        """Test auto-reply sent 'I currently only support text messages'"""
        mock_notification.event['messageData']['typeMessage'] = 'imageMessage'
        
        whatsapp_handler.handle_unsupported_message(mock_notification)
        
        # Should send auto-reply
        mock_notification.answer.assert_called_once()
        reply_text = mock_notification.answer.call_args[0][0]
        # Should return the exact unsupported message constant
        assert reply_text == UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
    
    @patch('src.handlers.whatsapp_handler.logger')
    def test_bot_continues_after_unsupported_message(
        self, mock_logger, whatsapp_handler, mock_notification
    ):
        """Test bot skips processing and continues after unsupported message"""
        mock_notification.event['messageData']['typeMessage'] = 'videoMessage'
        
        # Should not raise exception
        whatsapp_handler.handle_unsupported_message(mock_notification)
        
        # Should log warning
        assert mock_logger.warning.called or mock_logger.info.called
