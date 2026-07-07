"""
Expensive tests for AIHandler behavior with REAL API calls (Phase 5: US3).
Tests exception handling and message-length validation - NO MOCKING.

Moved out of tests/integration/test_bot_exception_handling.py: these all
make real OpenAI API calls (chat completion or embeddings via memory
recall), so they belong under tests/expensive/ with the other
@pytest.mark.expensive tests, not tests/integration/.

Run with: pytest tests/expensive/test_ai_handler_real_api.py -m expensive -v
"""
import pytest
from pathlib import Path
from openai import OpenAI
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


@pytest.fixture
def real_config():
    """Load real configuration for testing"""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    # Isolate session/memory storage from production data (data/) so these
    # tests' real API calls don't write into real production state.
    # SessionManager/MemoryManager read storage paths from
    # config.memory[...]['storage_dir'], not config.data_root.
    test_data_root = Path(__file__).parent.parent.parent / "test_data"
    config.data_root = str(test_data_root)
    if 'session' in config.memory:
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    if 'longterm' in config.memory:
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
    return config


@pytest.fixture
def real_openai_client(real_config):
    """Create real OpenAI client"""
    return OpenAI(api_key=real_config.ai_api_key, timeout=30.0)


@pytest.fixture
def real_ai_handler(real_openai_client, real_config):
    """Create real AIHandler instance"""
    return AIHandler(real_openai_client, real_config)


class TestBotExceptionHandlingWithRealAPI:
    """Test exception handling with 1 REAL API call to prove end-to-end functionality"""

    @pytest.mark.expensive
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


class TestMessageLengthValidation:
    """Test AIHandler message length validation via create_request().

    NOTE: create_request() triggers a real OpenAI embeddings API call via
    memory recall (real_config's production config.json has
    enable_memory_system=True), so these are NOT free despite only
    asserting on truncation logic. Marked expensive accordingly.
    """

    @pytest.mark.expensive
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

    @pytest.mark.expensive
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
