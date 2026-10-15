"""
Unit tests for WhatsAppHandler error handling (Phase 5: US3)
Tests Green API errors and unsupported message types
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import requests
from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_denidin
import denidin as denidin_module


def _reply_unsupported(whatsapp_handler, notification, monkeypatch):
    """The unsupported-type auto-reply as denidin.py sends it (2026-10-02: moved off
    WhatsAppHandler onto denidin.py)."""
    app = whatsapp_handler.denidin
    app.whatsapp_handler = whatsapp_handler
    monkeypatch.setattr(denidin_module, "denidin_app", app)
    denidin_module._reply_unsupported(notification)
from src.constants.error_messages import UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
from src.models.message import AIResponse, WhatsAppMessage
from whatsapp_chatbot_python import Notification


@pytest.fixture
def whatsapp_handler():
    """Create WhatsAppHandler instance"""
    return WhatsAppHandler(make_denidin())


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
    """A Green API HTTP error on a send is logged with its status and never raised (send_to_chat -> None)."""

    @pytest.mark.parametrize("status", [400, 401, 429, 500])
    @patch('time.sleep')
    @patch('src.handlers.whatsapp_handler.logger')
    def test_send_to_chat_logs_the_http_error_and_returns_none(self, mock_logger, _sleep, whatsapp_handler, status):
        response = Mock()
        response.status_code = status
        whatsapp_handler.denidin.green_api_bot = Mock()
        whatsapp_handler.denidin.green_api_bot.api.sending.sendMessage.side_effect = requests.HTTPError(
            f"{status} error", response=response)

        assert whatsapp_handler.send_to_chat("1234567890@c.us", "Test response") is None

        assert mock_logger.error.called
        assert str(status) in str(mock_logger.error.call_args)


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

    def test_validate_message_type_accepts_contact_message(
        self, whatsapp_handler, mock_notification
    ):
        """Feature 030: validate_message_type accepts contactMessage (shared vCard contact
        card), reused by _process_conversational_message alongside textMessage."""
        mock_notification.event['messageData']['typeMessage'] = 'contactMessage'

        is_valid = whatsapp_handler.validate_message_type(mock_notification)

        assert is_valid is True
    
    @patch('denidin.logger')
    def test_auto_reply_sent_for_unsupported_type(
        self, mock_logger, whatsapp_handler, mock_notification, monkeypatch
    ):
        """Test auto-reply sent 'I currently only support text messages'"""
        mock_notification.event['messageData']['typeMessage'] = 'imageMessage'
        
        _reply_unsupported(whatsapp_handler, mock_notification, monkeypatch)
        
        # Should send auto-reply
        mock_notification.answer.assert_called_once()
        reply_text = mock_notification.answer.call_args[0][0]
        # Should return the exact unsupported message constant
        assert reply_text == UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES
    
    @patch('denidin.logger')
    def test_bot_continues_after_unsupported_message(
        self, mock_logger, whatsapp_handler, mock_notification, monkeypatch
    ):
        """Test bot skips processing and continues after unsupported message"""
        mock_notification.event['messageData']['typeMessage'] = 'videoMessage'
        
        # Should not raise exception
        _reply_unsupported(whatsapp_handler, mock_notification, monkeypatch)
        
        # Should log warning
        assert mock_logger.warning.called or mock_logger.info.called
