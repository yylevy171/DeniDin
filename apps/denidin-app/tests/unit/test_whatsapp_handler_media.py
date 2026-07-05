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
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/abc123',
                'caption': 'What is in this photo?',
                'fileName': 'IMG_001.jpg',
                'mimeType': 'image/jpeg'
            }
        },
        'senderData': {
            'chatId': '972501234567@c.us',
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
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/xyz789',
                'caption': 'Please review this contract',
                'fileName': 'contract.pdf',
                'mimeType': 'application/pdf'
            }
        },
        'senderData': {
            'chatId': '972501234567@c.us',
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
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/vid123',
                'caption': 'Check out this video',
                'fileName': 'video.mp4',
                'mimeType': 'video/mp4'
            }
        },
        'senderData': {
            'chatId': '972501234567@c.us',
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
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/aud456',
                'fileName': 'voice.ogg',
                'mimeType': 'audio/ogg'
            }
        },
        'senderData': {
            'chatId': '972501234567@c.us',
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
            file_size=0,  # Green API doesn't provide fileSize - set to 0
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
        # Create notification with caption in fileMessageData (CHK111)
        notification = MagicMock(spec=Notification)
        notification.answer = MagicMock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://api.green-api.com/file/test',
                    'caption': 'User typed this question',  # CHK111: This is what user typed
                    'fileName': 'photo.jpg',
                    'mimeType': 'image/jpeg'
                }
            },
            'senderData': {
                'chatId': '972501234567@c.us',
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
        # Create notification without caption (using correct nested structure)
        notification = MagicMock(spec=Notification)
        notification.answer = MagicMock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://api.green-api.com/file/test',
                    # No caption field
                    'fileName': 'doc.pdf',
                    'mimeType': 'application/pdf'
                }
            },
            'senderData': {
                'chatId': '972501234567@c.us',
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


class TestGreenApiWebhookStructure:
    """
    BUGFIX-007: Test that webhook notifications match Green API specification.
    These tests verify that our test fixtures and real webhooks have all required fields.
    """
    
    def test_image_notification_has_required_chatid(self, mock_notification_image):
        """
        Test that image notification senderData includes chatId (required by Green API).
        
        BUG: Current fixtures missing chatId - notification.answer() needs this to send responses.
        According to Green API docs, senderData MUST have both chatId and sender.
        """
        sender_data = mock_notification_image.event.get('senderData', {})
        
        # This test will FAIL because fixture is missing chatId
        assert 'chatId' in sender_data, (
            "senderData missing required 'chatId' field - "
            "notification.answer() needs chatId to send responses. "
            "See: https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/ImageMessage/"
        )
        assert sender_data['chatId'] is not None
        assert sender_data['chatId'] != ''
    
    def test_document_notification_has_required_chatid(self, mock_notification_document):
        """
        Test that document notification senderData includes chatId (required by Green API).
        """
        sender_data = mock_notification_document.event.get('senderData', {})
        
        # This test will FAIL because fixture is missing chatId
        assert 'chatId' in sender_data, (
            "senderData missing required 'chatId' field - "
            "notification.answer() needs chatId to send responses"
        )
        assert sender_data['chatId'] is not None
        assert sender_data['chatId'] != ''
    
    def test_chatid_matches_sender_for_personal_chat(self, mock_notification_image):
        """
        Test that for 1-on-1 chats, chatId equals sender (Green API convention).
        
        In personal chats: chatId == sender (e.g., "79001234567@c.us")
        In group chats: chatId != sender (chatId uses @g.us suffix)
        """
        sender_data = mock_notification_image.event.get('senderData', {})
        
        # For personal chats, chatId should equal sender
        if 'chatId' in sender_data and 'sender' in sender_data:
            # If sender ends with @c.us (personal chat), chatId should match
            if sender_data['sender'].endswith('@c.us'):
                assert sender_data['chatId'] == sender_data['sender'], (
                    "For personal chats, chatId should equal sender"
                )
    
    def test_all_required_senderdata_fields_present(self, mock_notification_image):
        """
        Test that senderData has all mandatory Green API fields.
        
        Required fields per Green API docs:
        - chatId (MANDATORY) - where to send the response
        - sender (MANDATORY) - who sent the message
        - chatName (OPTIONAL)
        - senderName (OPTIONAL)  
        - senderContactName (OPTIONAL)
        """
        sender_data = mock_notification_image.event.get('senderData', {})
        
        # Mandatory fields
        assert 'chatId' in sender_data, "Missing required field: chatId"
        assert 'sender' in sender_data, "Missing required field: sender"
        
        # Verify non-empty
        assert sender_data['chatId'], "chatId cannot be empty"
        assert sender_data['sender'], "sender cannot be empty"


# Helper functions for bugfix-007 validation tests
def create_mock_notification_image():
    """Create mock image notification AS CURRENT CODE DOES (missing chatId)."""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'imageMessage',
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/abc123',
                'caption': 'What is in this photo?',
                'fileName': 'IMG_001.jpg',
                'mimeType': 'image/jpeg'
            }
        },
        'senderData': {
            # MISSING chatId - this is the bug
            'sender': '972501234567@c.us',
            'senderName': 'David Cohen'
        }
    }
    return notification


def create_mock_notification_document():
    """Create mock document notification AS CURRENT CODE DOES (missing chatId)."""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'documentMessage',
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/xyz789',
                'caption': 'Please review this contract',
                'fileName': 'contract.pdf',
                'mimeType': 'application/pdf'
            }
        },
        'senderData': {
            # MISSING chatId
            'sender': '972501234567@c.us',
            'senderName': 'Sarah Levy'
        }
    }
    return notification


def create_mock_notification_video():
    """Create mock video notification AS CURRENT CODE DOES (missing chatId)."""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'videoMessage',
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/vid123',
                'caption': 'Check out this video',
                'fileName': 'video.mp4',
                'mimeType': 'video/mp4'
            }
        },
        'senderData': {
            # MISSING chatId
            'sender': '972501234567@c.us',
            'senderName': 'Mike Jones'
        }
    }
    return notification


def create_mock_notification_audio():
    """Create mock audio notification AS CURRENT CODE DOES (missing chatId)."""
    notification = MagicMock(spec=Notification)
    notification.answer = MagicMock()
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'messageData': {
            'typeMessage': 'audioMessage',
            'fileMessageData': {
                'downloadUrl': 'https://api.green-api.com/file/aud456',
                'fileName': 'voice.ogg',
                'mimeType': 'audio/ogg'
            }
        },
        'senderData': {
            # MISSING chatId
            'sender': '972501234567@c.us',
            'senderName': 'Rachel Green'
        }
    }
    return notification
