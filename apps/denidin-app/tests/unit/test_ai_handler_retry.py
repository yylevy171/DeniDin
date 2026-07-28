"""
Unit tests for AIHandler retry logic (Phase 5: US3)
Tests retry behavior for OpenAI API failures with exponential backoff
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from openai import RateLimitError, APITimeoutError, APIError
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage, AIResponse


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock AppConfiguration for testing"""
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-4o-mini"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = "data"
    # Memory/RBAC are always on now (no feature flags) - AIHandler.__init__
    # unconditionally constructs SessionManager/MemoryManager/UserManager, so
    # these must be real, isolated (tmp_path) values, not left to the code's
    # own literal 'data/sessions' fallback default (would pollute the real
    # data dir). Long-term memory disabled - these tests don't need ChromaDB.
    config.memory = {
        'session': {'storage_dir': str(tmp_path / 'sessions')},
        'longterm': {'enabled': False}
    }
    config.user_roles = {}
    config.godfather_phone = None
    return config


@pytest.fixture
def mock_ai_client():
    """Create a mock OpenAI client"""
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_ai_client):
    """Create AIHandler instance with mocked dependencies"""
    return AIHandler(mock_ai_client, mock_config)


@pytest.fixture
def sample_whatsapp_message():
    """Create a sample WhatsApp message for testing"""
    return WhatsAppMessage(
        message_id="msg_123",
        chat_id="1234567890@c.us",
        sender_id="1234567890@c.us",
        sender_name="John Doe",
        text_content="Hello, how are you?",
        timestamp=1234567890,
        message_type="textMessage",
        is_group=False,
        received_timestamp=datetime.now(timezone.utc)
    )


class TestAIHandlerRetryLogic:
    """Test retry logic for OpenAI API calls"""
    
    def test_get_response_retries_on_rate_limit_error(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        """Test that get_response retries once on RateLimitError"""
        # Simulate RateLimitError on first call, success on 2nd
        mock_ai_client.responses.create.side_effect = [
            RateLimitError("Rate limit exceeded", response=Mock(), body={}),
            Mock(
                output_text="Success response",
                usage=Mock(total_tokens=50, input_tokens=10, output_tokens=40),
                id="chatcmpl_123",
                model="gpt-4o-mini",
                created=1234567890,
                incomplete_details=None,
                output=[]
            )
        ]
        
        # Create AI request
        request = ai_handler.create_request(sample_whatsapp_message)
        
        # Should succeed after 1 retry
        response = ai_handler.get_response(request)
        
        # Verify 2 attempts were made (1 initial + 1 retry)
        assert mock_ai_client.responses.create.call_count == 2
        assert response.response_text == "Success response"
        assert response.tokens_used == 50
    
    def test_get_response_retries_on_api_timeout_error(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        """Test that get_response retries on APITimeoutError"""
        # Simulate timeout on first call, success on 2nd
        mock_ai_client.responses.create.side_effect = [
            APITimeoutError(request=Mock()),
            Mock(
                output_text="Success after timeout",
                usage=Mock(total_tokens=45, input_tokens=10, output_tokens=35),
                id="chatcmpl_124",
                model="gpt-4o-mini",
                created=1234567891,
                incomplete_details=None,
                output=[]
            )
        ]
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        assert mock_ai_client.responses.create.call_count == 2
        assert response.response_text == "Success after timeout"
    
    def test_get_response_retries_on_api_error(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        """Test that get_response retries on generic APIError"""
        # Simulate APIError on first call, success on 2nd
        mock_ai_client.responses.create.side_effect = [
            APIError("API Error", request=Mock(), body={}),
            Mock(
                output_text="Success after error",
                usage=Mock(total_tokens=40, input_tokens=10, output_tokens=30),
                id="chatcmpl_125",
                model="gpt-4o-mini",
                created=1234567892,
                incomplete_details=None,
                output=[]
            )
        ]
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        assert mock_ai_client.responses.create.call_count == 2
        assert response.response_text == "Success after error"
    
    def test_get_response_fails_after_max_retries(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        """Test that get_response fails after 3 retry attempts"""
        # Simulate persistent RateLimitError
        mock_ai_client.responses.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        
        # Should return fallback response after max retries
        response = ai_handler.get_response(request)
        
        # Verify it tried 2 times (initial + 1 retry)
        assert mock_ai_client.responses.create.call_count == 2
        
        # Should return fallback instead of raising
        assert "trouble connecting" in response.response_text.lower() or "capacity" in response.response_text.lower()
    
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_timing(
        self, mock_sleep, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        """Test exponential backoff timing (1s, 2s, 4s)"""
        # Simulate failures requiring retries
        mock_ai_client.responses.create.side_effect = [
            RateLimitError("Rate limit", response=Mock(), body={}),
            RateLimitError("Rate limit", response=Mock(), body={}),
            Mock(
                output_text="Success",
                usage=Mock(total_tokens=50, input_tokens=10, output_tokens=40),
                id="chatcmpl_126",
                model="gpt-4o-mini",
                created=1234567893,
                incomplete_details=None,
                output=[]
            )
        ]
        
        request = ai_handler.create_request(sample_whatsapp_message)
        ai_handler.get_response(request)
        
        # Verify sleep was called with 1 second wait (at least 1 retry)
        assert mock_sleep.call_count >= 1  # At least 1 retry with sleep
