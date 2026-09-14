"""Feature 080 — telemetry instrumentation wiring inside AIHandler.get_response().

The feature flag that used to gate this has been removed (2026-09-12, explicit operator
instruction - never gated by request); telemetry is now always active whenever a
telemetry_manager is supplied (initialize_app() always supplies one). This is a UNIT test:
constructs AIHandler directly with a real TelemetryManager and a stubbed (not real) OpenAI
client, per CONSTITUTION §I/§V (mock only third-party network services - the stub here
stands in for the real OpenAI API, the only external dependency in this call path).
telemetry_manager itself stays Optional on AIHandler (tests that construct it directly
without one still get a clean no-op path).
"""
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler
from src.managers.telemetry_manager import TelemetryManager
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-4o-mini"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        'session': {'storage_dir': str(tmp_path / 'sessions')},
        'longterm': {'enabled': False}
    }
    config.user_roles = {}
    config.godfather_phone = None
    config.feature_flags = {}
    return config


@pytest.fixture
def mock_ai_client():
    return MagicMock()


@pytest.fixture
def telemetry_manager(tmp_path):
    return TelemetryManager(str(tmp_path / "data"))


@pytest.fixture
def ai_handler(mock_config, mock_ai_client, telemetry_manager):
    return AIHandler(mock_ai_client, mock_config, telemetry_manager=telemetry_manager)


@pytest.fixture
def sample_whatsapp_message():
    return WhatsAppMessage(
        message_id="msg_telemetry_1",
        chat_id="1234567890@c.us",
        sender_id="1234567890@c.us",
        sender_name="John Doe",
        text_content="Hello, how are you?",
        timestamp=1234567890,
        message_type="textMessage",
        is_group=False,
        received_timestamp=datetime.now(timezone.utc)
    )


class TestTelemetryWiring:
    def test_produces_exactly_one_telemetry_row(
        self, ai_handler, mock_ai_client, telemetry_manager, sample_whatsapp_message
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
        ai_handler.get_response(request)

        row = telemetry_manager.get(request.request_id)
        assert row is not None
        assert row["llm_turns_count"] == 1
        assert row["llm_total_inference_time_ms"] >= 0
        assert row["input_tokens_count"] == 10
        assert row["output_tokens_count"] == 40
        assert row["total_duration_ms"] >= 0

    def test_no_telemetry_manager_records_nothing(self, mock_config, mock_ai_client, telemetry_manager, sample_whatsapp_message):
        # Pins AIHandler's own no-op path when telemetry_manager=None (a test constructing
        # AIHandler directly without one, e.g. many pre-080 unit tests still do this) - not
        # a feature-flag concern any more, just an ordinary Optional-dependency no-op.
        handler = AIHandler(mock_ai_client, mock_config, telemetry_manager=None)
        mock_ai_client.responses.create.return_value = Mock(
            output_text="Success response",
            usage=Mock(total_tokens=50, input_tokens=10, output_tokens=40),
            id="chatcmpl_123", model="gpt-4o-mini", created=1234567890,
            incomplete_details=None, output=[]
        )

        request = handler.create_request(sample_whatsapp_message)
        handler.get_response(request)

        assert telemetry_manager.get(request.request_id) is None

    def test_exception_during_turn_still_records_a_row(
        self, ai_handler, mock_ai_client, telemetry_manager, sample_whatsapp_message
    ):
        """The finally-block guarantee (contracts/telemetry-recorder.md) - even a turn that
        ultimately raises still produces a telemetry row, since the call itself consumed real
        wall-clock time and the record()/reset() must always run."""
        mock_ai_client.responses.create.side_effect = RuntimeError("simulated failure")

        request = ai_handler.create_request(sample_whatsapp_message)
        ai_handler.get_response(request)  # AIHandler's own error handling returns a fallback,
                                           # never raises out to the caller - see test_ai_handler_retry.py

        row = telemetry_manager.get(request.request_id)
        assert row is not None
        assert row["llm_turns_count"] == 1  # the one failed call still counted
