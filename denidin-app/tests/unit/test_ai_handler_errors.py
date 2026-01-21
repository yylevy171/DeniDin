"""
Unit tests for AIHandler timeout and rate limit handling (Phase 5: US3)
Tests fallback responses for API failures
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from openai import APITimeoutError, RateLimitError
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage, AIRequest


@pytest.fixture
def mock_config():
    """Create a mock AppConfiguration for testing"""
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-4o-mini"
    config.system_message = "You are a helpful assistant."
    config.max_tokens = 500
    config.temperature = 0.7
    return config


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client"""
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_openai_client):
    """Create AIHandler instance with mocked dependencies"""
    return AIHandler(mock_openai_client, mock_config)


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


class TestAIHandlerTimeoutHandling:
    """Test timeout handling with fallback responses"""
    
    @patch('src.handlers.ai_handler.logger')
    def test_get_response_catches_timeout_error(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test that get_response catches APITimeoutError after retries"""
        # Simulate persistent timeout
        mock_openai_client.chat.completions.create.side_effect = APITimeoutError(
            request=Mock()
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        # Should return fallback response
        assert "trouble connecting" in response.response_text.lower()
        assert "try again" in response.response_text.lower()
        assert response.is_truncated is False
    
    @patch('src.handlers.ai_handler.logger')
    def test_timeout_logged_with_details(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test timeout logged with timestamp and error details"""
        mock_openai_client.chat.completions.create.side_effect = APITimeoutError(
            request=Mock()
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        ai_handler.get_response(request)
        
        # Verify error was logged
        assert mock_logger.error.called
        # Check that error details were logged
        log_call_args = str(mock_logger.error.call_args)
        assert "timeout" in log_call_args.lower() or "APITimeoutError" in log_call_args
    
    @patch('src.handlers.ai_handler.logger')
    def test_fallback_response_structure(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test fallback AIResponse has correct structure"""
        mock_openai_client.chat.completions.create.side_effect = APITimeoutError(
            request=Mock()
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        # Verify response structure
        assert response.request_id == request.request_id
        assert response.response_text is not None
        assert len(response.response_text) > 0
        assert response.tokens_used == 0  # No tokens used on error
        assert response.model == "error-fallback"


class TestAIHandlerRateLimitHandling:
    """Test rate limit handling with fallback responses"""
    
    @patch('src.handlers.ai_handler.logger')
    def test_get_response_catches_rate_limit_error(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test that get_response catches RateLimitError after retries"""
        # Simulate persistent rate limit
        mock_openai_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        # Should return rate limit fallback message
        assert "capacity" in response.response_text.lower() or "rate limit" in response.response_text.lower()
        assert "try again" in response.response_text.lower()
    
    @patch('src.handlers.ai_handler.logger')
    def test_rate_limit_logged_with_timestamp(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test rate limit logged with timestamp"""
        mock_openai_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        ai_handler.get_response(request)
        
        # Verify error was logged
        assert mock_logger.error.called
        log_call_args = str(mock_logger.error.call_args)
        assert "rate" in log_call_args.lower() or "RateLimitError" in log_call_args
    
    @patch('src.handlers.ai_handler.logger')
    def test_rate_limit_fallback_message_user_friendly(
        self, mock_logger, ai_handler, mock_openai_client, sample_whatsapp_message
    ):
        """Test fallback message is user-friendly for rate limits"""
        mock_openai_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )
        
        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)
        
        # Message should be helpful and not technical
        assert "Sorry" in response.response_text or "currently" in response.response_text
        # Should suggest action
        assert "try again" in response.response_text.lower() or "minute" in response.response_text.lower()
