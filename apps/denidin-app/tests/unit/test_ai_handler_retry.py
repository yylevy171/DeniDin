"""
Unit tests for AIHandler's behavior when an OpenAI call ultimately fails
(Phase 5: US3).

Rewritten 2026-08-19 (see AppConfiguration.max_retries' own docstring for the
full incident): retries themselves are no longer this app's own concern.
_call_openai_api used to carry its own tenacity `@retry` decorator, which
silently doubled up with the OpenAI SDK's own (previously unconfigured, so
defaulted) internal retry-with-backoff - up to 6 real HTTP attempts for one
logical call, several of which could each sleep a real server-suggested
Retry-After delay. The fix removed the app-level decorators entirely and
made the SDK's own max_retries=config.max_retries (denidin.py's OpenAI(...)
construction) the single retry mechanism.

What that means for this file: a MagicMock client doesn't implement the
SDK's own internal retry/backoff machinery at all (that logic lives deep in
openai._base_client, which a bare mock bypasses), so "does the app retry N
times" is no longer something a unit test against a mocked client can
meaningfully assert - that behavior is now entirely the SDK's own, already
tested by OpenAI itself. What's still genuinely ours to test, and still
covered here: _call_openai_api makes exactly ONE call per get_response
attempt (no leftover app-level retry loop), and get_response's own
exception-handling/fallback-response behavior is unchanged when the
(single) call ultimately raises.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

import pytest
from openai import RateLimitError, APITimeoutError, APIError

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


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


class TestAIHandlerCallsOpenAIExactlyOnce:
    """No leftover app-level retry loop - _call_openai_api must never call
    the client more than once per get_response attempt now that retries are
    the SDK's own responsibility (config.max_retries, wired into the real
    OpenAI(...) client construction in denidin.py - not exercised here,
    since a MagicMock doesn't implement it)."""

    def test_successful_call_is_made_exactly_once(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        mock_ai_client.responses.create.return_value = Mock(
            output_text="Success response",
            usage=Mock(total_tokens=50, input_tokens=10, output_tokens=40),
            id="chatcmpl_123",
            model="gpt-4o-mini",
            created=1234567890,
            incomplete_details=None,
            output=[]
        )

        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)

        assert mock_ai_client.responses.create.call_count == 1
        assert response.response_text == "Success response"
        assert response.tokens_used == 50

    @pytest.mark.parametrize("exception_factory", [
        lambda: RateLimitError("Rate limit exceeded", response=Mock(), body={}),
        lambda: APITimeoutError(request=Mock()),
        lambda: APIError("API Error", request=Mock(), body={}),
    ])
    def test_a_single_raised_exception_is_not_retried_by_our_own_code(
        self, ai_handler, mock_ai_client, sample_whatsapp_message, exception_factory
    ):
        """A mocked client that raises once (never recovers, since a
        MagicMock has no real backoff/retry of its own) must still only be
        called once - proves _call_openai_api itself doesn't loop, whether
        or not the real SDK would have retried underneath it in production."""
        mock_ai_client.responses.create.side_effect = exception_factory()

        request = ai_handler.create_request(sample_whatsapp_message)
        ai_handler.get_response(request)

        assert mock_ai_client.responses.create.call_count == 1


class TestAIHandlerFallbackOnFailure:
    """get_response's own exception-handling/fallback-response behavior -
    unchanged by the retry-layer removal, since this logic was never part of
    the tenacity decorator to begin with (it's the except block AROUND
    _call_openai_api, in get_response itself)."""

    def test_rate_limit_error_returns_capacity_fallback(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        mock_ai_client.responses.create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )

        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)

        assert "capacity" in response.response_text.lower()

    def test_api_timeout_error_returns_connection_fallback(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        mock_ai_client.responses.create.side_effect = APITimeoutError(request=Mock())

        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)

        assert "trouble connecting" in response.response_text.lower()

    def test_generic_api_error_returns_generic_fallback(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        mock_ai_client.responses.create.side_effect = APIError("API Error", request=Mock(), body={})

        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)

        assert "encountered an error" in response.response_text.lower()

    def test_unexpected_exception_returns_generic_fallback_not_a_crash(
        self, ai_handler, mock_ai_client, sample_whatsapp_message
    ):
        mock_ai_client.responses.create.side_effect = RuntimeError("something else entirely")

        request = ai_handler.create_request(sample_whatsapp_message)
        response = ai_handler.get_response(request)

        assert "unexpected error" in response.response_text.lower()
