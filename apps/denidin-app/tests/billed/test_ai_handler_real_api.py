"""
Billed tests for the AI implementation's behavior with REAL API calls (Phase 5: US3) -
whichever one the backbone flag selects (REQ-063-08: AIHandler or Backbone).
Tests exception handling and message-length validation - NO MOCKING.

Moved out of tests/integration/test_bot_exception_handling.py: these all
make real OpenAI API calls (chat completion or embeddings via memory
recall), so they belong under tests/billed/ with the other
@pytest.mark.billed tests, not tests/integration/.

Run with: pytest tests/billed/test_ai_handler_real_api.py -m billed -v
"""
import dataclasses
import pytest
from pathlib import Path
from src.models.config import AppConfiguration
from tests.e2e_helpers import sanity_worker_data_root
from src.models.message import WhatsAppMessage


@pytest.fixture
def real_config():
    """Load real configuration for testing"""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    # Isolate session/memory storage from production data (data/) so these
    # tests' real API calls don't write into real production state.
    # SessionManager/MemoryManager read storage paths from
    # config.memory[...]['storage_dir'], not config.data_root.
    test_data_root = sanity_worker_data_root()  # per-xdist-worker under -n (Feature 075)
    config.data_root = str(test_data_root)
    if 'session' in config.memory:
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    if 'longterm' in config.memory:
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
    return config


@pytest.fixture
def real_ai_manager(real_config):
    """The real AI implementation, exactly as the app builds it (initialize_app) -
    the Backbone or the legacy AIHandler, per config.test.json's backbone flag."""
    import denidin
    return denidin.initialize_app(dataclasses.asdict(real_config)).ai_manager


class TestBotExceptionHandlingWithRealAPI:
    """Test exception handling with 1 REAL API call to prove end-to-end functionality"""

    @pytest.mark.billed
    @pytest.mark.sanity
    def test_openai_error_handling_real_api(self, real_ai_manager):
        """The AI implementation catches a REAL OpenAI API error - 1 REAL API CALL"""
        # Create a real message
        from datetime import datetime, timezone
        message = WhatsAppMessage(
            message_id='msg_real_test',
            chat_id='test@c.us',
            sender_id='test@c.us',
            sender_name='Test User',
            text_content='תגרום לשגיאה',
            timestamp=1234567890,
            message_type='textMessage',
            is_group=False,
            received_timestamp=datetime.now(timezone.utc)
        )

        # Force an error by using invalid model
        original_model = real_ai_manager.config.ai_model
        real_ai_manager.config.ai_model = "invalid-model-xyz-12345"

        try:
            # Create request
            request = real_ai_manager.create_request(message)

            # This makes 1 REAL API call that will fail
            response = real_ai_manager.single_turn(request)

            # Should return the error fallback (retry logic will have run) - recognized
            # by its own marker, not by wording (the backbone's is Hebrew, legacy's English).
            assert response.model == "error-fallback", response
            assert response.response_text
        finally:
            # Restore original model
            real_ai_manager.config.ai_model = original_model


class TestMessageLengthValidation:
    """Test the AI implementation's message length validation via create_request().

    NOTE: create_request() triggers a real OpenAI embeddings API call via
    memory recall (real_config's production config.json has
    enable_memory_system=True), so these are NOT free despite only
    asserting on truncation logic. Marked billed accordingly.
    """

    @pytest.mark.billed
    def test_long_prompt_truncated_to_10000(self, real_ai_manager):
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

        request = real_ai_manager.create_request(long_message)
        assert len(request.user_prompt) <= 10000

    @pytest.mark.billed
    def test_short_messages_pass_through(self, real_ai_manager):
        """Test short messages (<10000) pass through unchanged"""
        from datetime import datetime, timezone
        short_text = "שלום, זו הודעה רגילה."
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

        request = real_ai_manager.create_request(short_message)
        assert request.user_prompt == short_text
