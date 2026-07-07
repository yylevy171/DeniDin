"""
Integration tests for WhatsAppHandler message-type validation (Phase 5: US3).
NO API calls, NO MOCKING - pure local validation logic.

Real-API-call tests (exception handling, message-length validation via
create_request()) moved to tests/expensive/test_ai_handler_real_api.py.
"""
import pytest
from src.handlers.whatsapp_handler import WhatsAppHandler


@pytest.fixture
def real_whatsapp_handler():
    """Create real WhatsAppHandler instance"""
    return WhatsAppHandler()


class TestWhatsAppValidation:
    """Test WhatsAppHandler validation - NO API calls"""

    def test_rejects_image_messages(self, real_whatsapp_handler):
        """Test handler rejects imageMessage"""
        # Create real notification-like structure
        notification_event = {'messageData': {'typeMessage': 'imageMessage'}}

        # Create a simple object with event attribute
        class FakeNotification:
            def __init__(self, event):
                self.event = event

        fake_notif = FakeNotification(notification_event)
        assert real_whatsapp_handler.validate_message_type(fake_notif) is False

    def test_rejects_audio_messages(self, real_whatsapp_handler):
        """Test handler rejects audioMessage"""
        class FakeNotification:
            def __init__(self, event):
                self.event = event

        fake_notif = FakeNotification({'messageData': {'typeMessage': 'audioMessage'}})
        assert real_whatsapp_handler.validate_message_type(fake_notif) is False

    def test_rejects_video_messages(self, real_whatsapp_handler):
        """Test handler rejects videoMessage"""
        class FakeNotification:
            def __init__(self, event):
                self.event = event

        fake_notif = FakeNotification({'messageData': {'typeMessage': 'videoMessage'}})
        assert real_whatsapp_handler.validate_message_type(fake_notif) is False

    def test_accepts_text_messages(self, real_whatsapp_handler):
        """Test handler accepts textMessage"""
        class FakeNotification:
            def __init__(self, event):
                self.event = event

        fake_notif = FakeNotification({'messageData': {'typeMessage': 'textMessage'}})
        assert real_whatsapp_handler.validate_message_type(fake_notif) is True
