"""
Unit tests for WhatsAppHandler retry logic (Phase 5: US3)
Tests retry behavior for Green API failures with exponential backoff
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import requests
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.models.message import AIResponse


@pytest.fixture
def whatsapp_handler():
    """Create WhatsAppHandler instance"""
    return WhatsAppHandler()


@pytest.fixture
def mock_notification():
    """Create a mock Green API notification"""
    notification = MagicMock()
    notification.answer = MagicMock()
    return notification


@pytest.fixture
def sample_ai_response():
    """Create a sample AI response"""
    return AIResponse(
        request_id="req_123",
        response_text="This is a test response",
        tokens_used=50,
        prompt_tokens=10,
        completion_tokens=40,
        model="gpt-4o-mini",
        finish_reason="stop",
        timestamp=1234567890,
        is_truncated=False
    )


class TestWhatsAppHandlerRetryLogic:
    """Test retry logic for Green API calls"""
    
    def test_send_response_retries_on_request_exception(
        self, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test that send_response retries on network errors"""
        # Simulate network timeout on first call, success on 2nd
        mock_notification.answer.side_effect = [
            requests.Timeout("Network timeout"),
            None  # Success
        ]
        
        # Should succeed after 1 retry
        whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        # Verify it tried 2 times (initial + 1 retry)
        assert mock_notification.answer.call_count == 2
        mock_notification.answer.assert_called_with("This is a test response")
    
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_for_green_api(
        self, mock_sleep, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test fixed 1-second wait for Green API sendMessage"""
        # Simulate failure then success
        mock_notification.answer.side_effect = [
            requests.Timeout("Connection timeout"),
            None  # Success on 2nd attempt
        ]
        
        whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        # Verify retry occurred
        assert mock_notification.answer.call_count == 2
        
        # Verify 1 second wait was used
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1)
    
    def test_send_response_fails_after_max_retries(
        self, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test that send_response fails after 2 attempts (1 retry) with clear error"""
        # Simulate persistent network error
        mock_notification.answer.side_effect = requests.Timeout("Persistent error")
        
        # Should raise exception after max retries
        with pytest.raises(requests.Timeout):
            whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        # Verify it tried 2 times (initial + 1 retry)
        assert mock_notification.answer.call_count == 2
    
    def test_send_response_retries_on_http_error(
        self, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test retry on HTTPError (subclass of RequestException)"""
        # Simulate HTTP error on first call, success on 2nd
        response = Mock()
        response.status_code = 500
        mock_notification.answer.side_effect = [
            requests.HTTPError("500 Server Error", response=response),
            None  # Success
        ]
        
        whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_notification.answer.call_count == 2
    
    def test_send_response_retries_on_connection_error(
        self, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test retry on ConnectionError"""
        mock_notification.answer.side_effect = [
            requests.ConnectionError("Failed to connect"),
            None  # Success
        ]
        
        whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_notification.answer.call_count == 2
    
    def test_send_response_retries_on_timeout(
        self, whatsapp_handler, mock_notification, sample_ai_response
    ):
        """Test retry on Timeout error"""
        mock_notification.answer.side_effect = [
            requests.Timeout("Request timeout"),
            None  # Success
        ]
        
        whatsapp_handler.send_response(mock_notification, sample_ai_response)
        
        assert mock_notification.answer.call_count == 2
