"""
Unit tests for the no-reply sentinel mechanism (Feature 039, US4a).
"""
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler, NO_REPLY_SENTINEL
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def memory_enabled_config():
    return AppConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        ai_api_key="test-key",
        ai_model="gpt-4o-mini",
        ai_reply_max_tokens=100,
        log_level="INFO",
        feature_flags={"enable_memory_system": True},
        memory={
            "session": {
                "storage_dir": "test_data/sessions",
                "max_tokens_by_role": {"client": 4000, "godfather": 100000},
                "session_timeout_hours": 24
            },
            "longterm": {
                "storage_dir": "test_data/memory",
                "embedding_model": "text-embedding-3-small",
                "top_k_results": 5,
                "min_similarity": 0.7
            }
        }
    )


def _mock_response(text):
    mock_response = MagicMock()
    mock_response.output_text = text
    mock_response.output = []
    mock_response.incomplete_details = None
    mock_response.usage.total_tokens = 10
    mock_response.usage.input_tokens = 5
    mock_response.usage.output_tokens = 5
    mock_response.model = "gpt-4o-mini"
    return mock_response


def _make_request():
    return AIRequest(
        user_prompt="Hello",
        constitution="Test assistant",
        max_tokens=100,
        model="gpt-4o-mini",
        chat_id="chat_123",
        message_id="msg_456"
    )


class TestNoReplySentinelDetection:
    def test_sentinel_response_sets_should_reply_false(self, memory_enabled_config):
        client = MagicMock()
        client.responses.create.return_value = _mock_response(NO_REPLY_SENTINEL)
        handler = AIHandler(client, memory_enabled_config)
        handler.session_manager.add_message_with_token_limit = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])

        response = handler.get_response(_make_request(), chat_id="chat_123", sender="Godfather")

        assert response.should_reply is False
        assert response.response_text == NO_REPLY_SENTINEL

    def test_sentinel_response_does_not_persist_assistant_message(self, memory_enabled_config):
        client = MagicMock()
        client.responses.create.return_value = _mock_response(NO_REPLY_SENTINEL)
        handler = AIHandler(client, memory_enabled_config)
        handler.session_manager.add_message_with_token_limit = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])

        handler.get_response(_make_request(), chat_id="chat_123", sender="Godfather")

        # Only the user message is persisted - one call, not two.
        assert handler.session_manager.add_message_with_token_limit.call_count == 1
        call = handler.session_manager.add_message_with_token_limit.call_args_list[0]
        assert call[1]["role"] == "user"

    def test_sentinel_with_extra_whitespace_still_detected(self, memory_enabled_config):
        """Trailing/leading whitespace around the sentinel is trimmed before comparison."""
        client = MagicMock()
        client.responses.create.return_value = _mock_response(f"  {NO_REPLY_SENTINEL}  ")
        handler = AIHandler(client, memory_enabled_config)
        handler.session_manager.add_message_with_token_limit = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])

        response = handler.get_response(_make_request(), chat_id="chat_123", sender="Godfather")

        assert response.should_reply is False

    def test_sentinel_with_trailing_content_is_not_treated_as_no_reply(self, memory_enabled_config):
        """A near-miss (sentinel plus extra text) is treated as a normal reply and
        sent as-is - never silently drop a real reply on a partial match."""
        client = MagicMock()
        client.responses.create.return_value = _mock_response(f"{NO_REPLY_SENTINEL} extra text")
        handler = AIHandler(client, memory_enabled_config)
        handler.session_manager.add_message_with_token_limit = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])

        response = handler.get_response(_make_request(), chat_id="chat_123", sender="Godfather")

        assert response.should_reply is True
        assert handler.session_manager.add_message_with_token_limit.call_count == 2

    def test_normal_response_sets_should_reply_true(self, memory_enabled_config):
        client = MagicMock()
        client.responses.create.return_value = _mock_response("Hello! How can I help?")
        handler = AIHandler(client, memory_enabled_config)
        handler.session_manager.add_message_with_token_limit = Mock()
        handler.session_manager.get_conversation_history = Mock(return_value=[])

        response = handler.get_response(_make_request(), chat_id="chat_123", sender="Godfather")

        assert response.should_reply is True
        assert handler.session_manager.add_message_with_token_limit.call_count == 2
