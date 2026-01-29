"""
Unit tests for WhatsAppHandler media message processing (Phase 6)
Tests media message detection, routing to MediaHandler, and summary sending
CHK111: Caption is WhatsApp message text from webhook
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.constants.error_messages import FAILED_TO_PROCESS_FILE_DEFAULT
from whatsapp_chatbot_python import Notification


@pytest.fixture
def whatsapp_handler():
    """Create WhatsAppHandler instance"""
    return WhatsAppHandler()


@pytest.fixture
def mock_media_handler():
    """Create a mock MediaHandler"""
    handler = MagicMock()
    handler.process_media_message = MagicMock()
    return handler


@pytest.fixture
def mock_notification_image():
    """Create a mock Green API notification for image message"""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'imageMessage',
            'downloadUrl': 'https://api.green-api.com/file/abc123',
            'caption': 'What is in this photo?',
            'fileName': 'IMG_001.jpg',
            'mimeType': 'image/jpeg',
            'fileSize': 2048000  # ~2MB
        },
        'senderData': {
            'sender': '972501234567@c.us',
            'senderName': 'David Cohen'
        }
    }
    return notification


@pytest.fixture
def mock_notification_document():
    """Create a mock Green API notification for document message"""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'documentMessage',
            'downloadUrl': 'https://api.green-api.com/file/xyz789',
            'caption': 'Please review this contract',
            'fileName': 'contract.pdf',
            'mimeType': 'application/pdf',
            'fileSize': 5120000  # ~5MB
        },
        'senderData': {
            'sender': '972501234567@c.us',
            'senderName': 'Sarah Levy'
        }
    }
    return notification


@pytest.fixture
def mock_notification_video():
    """Create a mock Green API notification for video message (unsupported)"""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'videoMessage',
            'downloadUrl': 'https://api.green-api.com/file/vid123',
            'caption': 'Check out this video',
            'fileName': 'video.mp4',
            'mimeType': 'video/mp4',
            'fileSize': 10240000  # ~10MB
        },
        'senderData': {
            'sender': '972501234567@c.us',
            'senderName': 'Mike Jones'
        }
    }
    return notification


@pytest.fixture
def mock_notification_audio():
    """Create a mock Green API notification for audio message (unsupported)"""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'audioMessage',
            'downloadUrl': 'https://api.green-api.com/file/aud456',
            'fileName': 'voice.ogg',
            'mimeType': 'audio/ogg',
            'fileSize': 512000  # ~512KB
        },
        'senderData': {
            'sender': '972501234567@c.us',
            'senderName': 'Rachel Green'
        }
    }
    return notification


class TestMediaMessageDetection:
    """Test detection of different media message types"""
    
    def test_detect_image_message(self, whatsapp_handler, mock_notification_image):
        """Test that imageMessage type is correctly identified"""
        result = whatsapp_handler.is_media_message(mock_notification_image)
        
        assert result is True
        assert whatsapp_handler.get_media_type(mock_notification_image) == 'imageMessage'
    
    def test_detect_document_message(self, whatsapp_handler, mock_notification_document):
        """Test that documentMessage type is correctly identified"""
        result = whatsapp_handler.is_media_message(mock_notification_document)
        
        assert result is True
        assert whatsapp_handler.get_media_type(mock_notification_document) == 'documentMessage'
    
    def test_ignore_video_message_future(self, whatsapp_handler, mock_notification_video):
        """Test that videoMessage is not processed (future scope)"""
        result = whatsapp_handler.is_supported_media_message(mock_notification_video)
        
        assert result is False
    
    def test_ignore_audio_message_future(self, whatsapp_handler, mock_notification_audio):
        """Test that audioMessage is not processed (future scope)"""
        result = whatsapp_handler.is_supported_media_message(mock_notification_audio)
        
        assert result is False


class TestMediaHandlerIntegration:
    """Test integration between WhatsAppHandler and MediaHandler"""
    
    def test_route_media_to_media_handler_and_send_summary(
        self, whatsapp_handler, mock_notification_image, mock_media_handler
    ):
        """Test that media messages are routed to MediaHandler and summary is sent"""
        # Mock successful processing
        mock_media_handler.process_media_message.return_value = {
            "success": True,
            "summary": "📷 Image Analysis\n\nI found a photo of a receipt from SuperMarket.\n\nKey details:\n• Merchant: SuperMarket\n• Date: 2026-01-20\n• Total: ₪150.50",
            "media_attachment": Mock(),
            "document_metadata": Mock()
        }
        
        # Inject MediaHandler into WhatsAppHandler
        whatsapp_handler.media_handler = mock_media_handler
        
        whatsapp_handler.handle_media_message(mock_notification_image)
        
        # Verify MediaHandler was called with correct parameters (CHK111: caption from webhook)
        mock_media_handler.process_media_message.assert_called_once_with(
            file_url='https://api.green-api.com/file/abc123',
            filename='IMG_001.jpg',
            mime_type='image/jpeg',
            file_size=2048000,
            caption='What is in this photo?',  # CHK111: WhatsApp message text
            sender_phone='972501234567@c.us'
        )
        
        # Verify summary was sent back to user
        mock_notification_image.answer.assert_called_once()
        sent_message = mock_notification_image.answer.call_args[0][0]
        assert "Image Analysis" in sent_message
        assert "SuperMarket" in sent_message
    
    def test_send_error_message_on_processing_failure(
        self, whatsapp_handler, mock_notification_document, mock_media_handler
    ):
        """Test that MediaHandler failures send user-friendly error messages"""
        # Mock failed processing
        mock_media_handler.process_media_message.return_value = {
            "success": False,
            "error_message": "Sorry, I couldn't process this PDF. The file may be corrupted or too large."
        }
        
        # Inject MediaHandler into WhatsAppHandler
        whatsapp_handler.media_handler = mock_media_handler
        
        whatsapp_handler.handle_media_message(mock_notification_document)
        
        # Verify error message was sent to user (exact constant)
        mock_notification_document.answer.assert_called_once_with(
            FAILED_TO_PROCESS_FILE_DEFAULT
        )


class TestCaptionHandling:
    """Test CHK111: Caption is WhatsApp message text"""
    
    def test_caption_extracted_from_webhook_not_file_metadata(
        self, whatsapp_handler, mock_media_handler
    ):
        """Test that caption comes from webhook messageData, not file embedded metadata"""
        # Create notification with caption in messageData (CHK111)
        notification = MagicMock(spec=Notification)
        notification.answer = MagicMock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'imageMessage',
                'downloadUrl': 'https://api.green-api.com/file/test',
                'caption': 'User typed this question',  # CHK111: This is what user typed
                'fileName': 'photo.jpg',
                'mimeType': 'image/jpeg',
                'fileSize': 1024000
            },
            'senderData': {
                'sender': '972501234567@c.us',
                'senderName': 'Test User'
            }
        }
        
        mock_media_handler.process_media_message.return_value = {
            "success": True,
            "summary": "Test summary",
            "media_attachment": Mock(),
            "document_metadata": Mock()
        }
        
        whatsapp_handler.media_handler = mock_media_handler
        
        whatsapp_handler.handle_media_message(notification)
        
        # Verify caption from webhook was passed to MediaHandler (CHK111)
        call_kwargs = mock_media_handler.process_media_message.call_args[1]
        assert call_kwargs['caption'] == 'User typed this question'
    
    def test_missing_caption_sends_empty_string(
        self, whatsapp_handler, mock_media_handler
    ):
        """Test that missing caption results in empty string, not None"""
        # Create notification without caption
        notification = MagicMock(spec=Notification)
        notification.answer = MagicMock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'documentMessage',
                'downloadUrl': 'https://api.green-api.com/file/test',
                # No caption field
                'fileName': 'doc.pdf',
                'mimeType': 'application/pdf',
                'fileSize': 2048000
            },
            'senderData': {
                'sender': '972501234567@c.us',
                'senderName': 'Test User'
            }
        }
        
        mock_media_handler.process_media_message.return_value = {
            "success": True,
            "summary": "Test summary",
            "media_attachment": Mock(),
            "document_metadata": Mock()
        }
        
        whatsapp_handler.media_handler = mock_media_handler
        
        whatsapp_handler.handle_media_message(notification)
        
        # Verify empty string was passed, not None
        call_kwargs = mock_media_handler.process_media_message.call_args[1]
        assert call_kwargs['caption'] == ''
        assert call_kwargs['caption'] is not None
