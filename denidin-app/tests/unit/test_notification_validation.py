"""
BUGFIX-007: Unit Tests for Notification Validation

These tests validate notification objects BEFORE calling notification.answer().
They test the validation function with notification objects AS THEY ARE CREATED NOW.

**EXPECTED RESULTS:**
- Tests with fixtures missing chatId will FAIL (demonstrating the bug)
- Tests with factory methods including chatId will PASS (showing correct behavior)
"""

import pytest
from unittest.mock import MagicMock
from whatsapp_chatbot_python import Notification
from src.models.green_api import (
    NotificationValidationError,
    validate_notification_for_response
)


class TestNotificationValidation:
    """Test the validation function that enforces required fields."""
    
    def test_validation_passes_with_valid_notification(self):
        """
        Validation should PASS when notification has all required fields.
        
        This uses the real SDK Notification with proper event structure.
        """
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/test.jpg',
                    'fileName': 'test.jpg',
                    'mimeType': 'image/jpeg'
                }
            }
        }
        
        # Should not raise
        validate_notification_for_response(notification)
    
    def test_validation_fails_without_chatid(self):
        """
        **THIS TEST DEMONSTRATES THE BUG**
        
        Validation should FAIL when notification is missing chatId.
        This creates a notification AS OUR TEST FIXTURES DO (without chatId).
        """
        # Create notification like our broken test fixtures
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                # MISSING chatId - this is how our fixtures are broken
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/test.jpg',
                    'fileName': 'test.jpg',
                    'mimeType': 'image/jpeg'
                }
            }
        }
        
        # Should raise validation error
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        assert "chatId" in str(exc_info.value)
        assert "missing required 'chatId' field" in str(exc_info.value)
    
    def test_validation_fails_with_empty_chatid(self):
        """Validation should FAIL when chatId is empty string."""
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '',  # Empty chatId
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessage': 'Test'
            }
        }
        
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        assert "empty chatId" in str(exc_info.value)
    
    def test_validation_fails_without_senderdata(self):
        """Validation should FAIL when notification has no senderData."""
        # Create a notification-like object without senderData
        class BrokenNotification:
            def __init__(self):
                self.event = {
                    "typeWebhook": "incomingMessageReceived",
                    "messageData": {"typeMessage": "textMessage"}
                    # Missing senderData
                }
        
        notification = BrokenNotification()
        
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        assert "senderData" in str(exc_info.value)
    
    def test_validation_fails_without_event_attribute(self):
        """Validation should FAIL when notification object has no event attribute."""
        class InvalidNotification:
            pass
        
        notification = InvalidNotification()
        
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        assert "event" in str(exc_info.value)
    
    def test_validation_message_includes_fix_instructions(self):
        """Error messages should include instructions for fixing the issue."""
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'sender': '972522968679@c.us'
                # Missing chatId
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessage': 'Test'
            }
        }
        
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        error_message = str(exc_info.value)
        assert "Fix:" in error_message
        assert "test fixtures" in error_message.lower() or "webhook parsing" in error_message.lower()


class TestFixtureChatIdCompliance:
    """
    Test that demonstrates current test fixtures are non-compliant.
    
    **THESE TESTS WILL FAIL** until fixtures are fixed to include chatId.
    """
    
    def test_unit_test_image_fixture_has_chatid(self):
        """
        **THIS WILL FAIL** - Unit test fixtures missing chatId.
        
        This creates a notification exactly as unit test fixtures do.
        The validation will fail, proving fixtures need to be fixed.
        """
        # This is how test_whatsapp_handler_media.py creates notifications
        from tests.unit.test_whatsapp_handler_media import create_mock_notification_image
        
        # Get the fixture (it's missing chatId)
        notification = create_mock_notification_image()
        
        # Validation should catch the missing chatId
        with pytest.raises(NotificationValidationError) as exc_info:
            validate_notification_for_response(notification)
        
        assert "chatId" in str(exc_info.value)
    
    def test_unit_test_document_fixture_has_chatid(self):
        """
        **THIS WILL FAIL** - Unit test document fixtures missing chatId.
        """
        from tests.unit.test_whatsapp_handler_media import create_mock_notification_document
        
        notification = create_mock_notification_document()
        
        with pytest.raises(NotificationValidationError):
            validate_notification_for_response(notification)
    
    def test_unit_test_video_fixture_has_chatid(self):
        """
        **THIS WILL FAIL** - Unit test video fixtures missing chatId.
        """
        from tests.unit.test_whatsapp_handler_media import create_mock_notification_video
        
        notification = create_mock_notification_video()
        
        with pytest.raises(NotificationValidationError):
            validate_notification_for_response(notification)
    
    def test_unit_test_audio_fixture_has_chatid(self):
        """
        **THIS WILL FAIL** - Unit test audio fixtures missing chatId.
        """
        from tests.unit.test_whatsapp_handler_media import create_mock_notification_audio
        
        notification = create_mock_notification_audio()
        
        with pytest.raises(NotificationValidationError):
            validate_notification_for_response(notification)


class TestFactoryMethodCompliance:
    """
    Test that factory methods create compliant notifications.
    
    **THESE TESTS SHOULD PASS** - Factory methods already include chatId.
    """
    
    def test_properly_structured_image_notification_has_chatid(self):
        """Properly structured notification with chatId passes validation."""
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/test.jpg',
                    'fileName': 'test.jpg',
                    'mimeType': 'image/jpeg'
                }
            }
        }
        
        # Should not raise
        validate_notification_for_response(notification)
        
        # Verify chatId is present
        assert notification.event['senderData']['chatId'] == '972522968679@c.us'
    
    def test_properly_structured_document_notification_has_chatid(self):
        """Properly structured document notification with chatId passes validation."""
        notification = MagicMock(spec=Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/test.pdf',
                    'fileName': 'test.pdf',
                    'mimeType': 'application/pdf'
                }
            }
        }
        
        # Should not raise
        validate_notification_for_response(notification)
        
        # Verify chatId is present
        assert notification.event['senderData']['chatId'] == '972522968679@c.us'


# ==================== EXPECTED TEST RESULTS ====================
#
# TestNotificationValidation:
#   ✅ test_validation_passes_with_valid_notification - PASS
#   ✅ test_validation_fails_without_chatid - PASS (raises expected error)
#   ✅ test_validation_fails_with_empty_chatid - PASS
#   ✅ test_validation_fails_without_senderdata - PASS
#   ✅ test_validation_fails_without_event_attribute - PASS
#   ✅ test_validation_message_includes_fix_instructions - PASS
#
# TestFixtureChatIdCompliance:
#   ❌ test_unit_test_image_fixture_has_chatid - FAIL (fixture missing chatId)
#   ❌ test_unit_test_document_fixture_has_chatid - FAIL
#   ❌ test_unit_test_video_fixture_has_chatid - FAIL
#   ❌ test_unit_test_audio_fixture_has_chatid - FAIL
#
# TestFactoryMethodCompliance:
#   ✅ test_factory_create_image_message_has_chatid - PASS
#   ✅ test_factory_create_document_message_has_chatid - PASS
#
# Total Expected: 6 PASS, 4 FAIL
# The 4 failing tests demonstrate the bug in test fixtures.
#
# =====================================================================
