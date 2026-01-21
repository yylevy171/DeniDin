"""
Integration tests for bot exception handling (Phase 5: US3)
Tests global exception handler with REAL API calls - NO MOCKING
Limited to 1 real API call to minimize cost
"""
import pytest
import json
from pathlib import Path
from openai import OpenAI
from src.handlers.ai_handler import AIHandler
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


@pytest.fixture
def real_config():
    """Load real configuration for testing"""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    return config


@pytest.fixture
def real_openai_client(real_config):
    """Create real OpenAI client"""
    return OpenAI(api_key=real_config.openai_api_key, timeout=30.0)


@pytest.fixture
def real_ai_handler(real_openai_client, real_config):
    """Create real AIHandler instance"""
    return AIHandler(real_openai_client, real_config)


@pytest.fixture
def real_whatsapp_handler():
    """Create real WhatsAppHandler instance"""
    return WhatsAppHandler()


class TestBotExceptionHandlingWithRealAPI:
    """Test exception handling with 1 REAL API call to prove end-to-end functionality"""
    
    def test_openai_error_handling_real_api(self, real_ai_handler):
        """Test AIHandler catches REAL OpenAI API error - 1 REAL API CALL"""
        # Create a real message
        from datetime import datetime, timezone
        message = WhatsAppMessage(
            message_id='msg_real_test',
            chat_id='test@c.us',
            sender_id='test@c.us',
            sender_name='Test User',
            text_content='Trigger an error',
            timestamp=1234567890,
            message_type='textMessage',
            is_group=False,
            received_timestamp=datetime.now(timezone.utc)
        )
        
        # Force an error by using invalid model
        original_model = real_ai_handler.config.ai_model
        real_ai_handler.config.ai_model = "invalid-model-xyz-12345"
        
        try:
            # Create request
            request = real_ai_handler.create_request(message)
            
            # This makes 1 REAL API call that will fail
            response = real_ai_handler.get_response(request)
            
            # Should return error response (retry logic will have run)
            assert response.response_text is not None
            assert "error" in response.response_text.lower() or "unable" in response.response_text.lower()
        finally:
            # Restore original model
            real_ai_handler.config.ai_model = original_model


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


class TestMessageLengthValidation:
    """Test AIHandler message length validation - NO API calls"""
    
    def test_long_prompt_truncated_to_10000(self, real_ai_handler):
        """Test long prompt truncated to 10000 chars"""
        from datetime import datetime, timezone
        long_message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="123@c.us",
            sender_id="123@c.us",
            sender_name="User",
            text_content="a" * 10001,
            timestamp=1234567890,
            message_type="textMessage",
            is_group=False,
            received_timestamp=datetime.now(timezone.utc)
        )
        
        request = real_ai_handler.create_request(long_message)
        assert len(request.user_prompt) <= 10000
    
    def test_short_messages_pass_through(self, real_ai_handler):
        """Test short messages (<10000) pass through unchanged"""
        from datetime import datetime, timezone
        short_text = "Hello, this is a normal message."
        short_message = WhatsAppMessage(
            message_id="msg_123",
            chat_id="123@c.us",
            sender_id="123@c.us",
            sender_name="User",
            text_content=short_text,
            timestamp=1234567890,
            message_type="textMessage",
            is_group=False,
            received_timestamp=datetime.now(timezone.utc)
        )
        
        request = real_ai_handler.create_request(short_message)
        assert request.user_prompt == short_text

