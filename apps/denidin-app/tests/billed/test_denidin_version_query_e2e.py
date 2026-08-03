"""
E2E Test (Feature 034, US4): denidin-app answers "what version are you running?" over
WhatsApp, ungated by RBAC - real webhook, real OpenAI Responses API, no mocking.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated handle_text_message - CONSTITUTION SS V):

    Green API textMessage webhook (any role)
      -> handle_text_message (real router handler)
      -> AIHandler.get_response -> client.responses.create (real OpenAI Responses API call)
           `instructions` includes the current version (research.md Decision 4 - same per-call
           injection mechanism already used for today's date, ai_handler.py:363-368 area)
      -> bot replies stating the exact version

**Test tier (Feature 029)**: real, text-only OpenAI call -> `billed`, NOT `expensive`. Runs
freely, no per-run approval needed, no one-at-a-time restriction - see CLAUDE.md.

NO MOCKING anywhere.
"""
import logging
import time
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import assert_response_exists, create_real_notification, get_response

logger = logging.getLogger(__name__)

GODFATHER_CHAT_ID = "972500000034@c.us"  # Feature 034 E2E test godfather identity
CLIENT_CHAT_ID = "972500000035@c.us"  # not in godfather_phone/admin_phones -> defaults to client


def _current_version() -> str:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    return version_file.read_text(encoding="utf-8").strip()


@pytest.fixture
def config():
    config_path = Path(__file__).resolve().parents[2] / "config" / "config.json"
    if not config_path.exists():
        pytest.skip("config.json not found")

    cfg = AppConfiguration.from_file(str(config_path))
    cfg.validate()
    cfg.godfather_phone = GODFATHER_CHAT_ID

    test_data_root = Path(__file__).resolve().parents[2] / "test_data"
    cfg.data_root = str(test_data_root)
    cfg.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    cfg.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
    return cfg


@pytest.fixture
def denidin_app(config):
    import denidin

    config_dict = {
        'green_api_instance_id': config.green_api_instance_id,
        'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key,
        'ai_model': config.ai_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens,
        'log_level': config.log_level,
        'data_root': config.data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
    }
    denidin.denidin_app = denidin.initialize_app(config_dict)
    return denidin.denidin_app


def _build_text_webhook(chat_id: str, message_id: str) -> dict:
    return {
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': int(time.time()),
        'idMessage': message_id,
        'instanceData': {
            'idInstance': 7103000000,
            'wid': '972501234567@c.us',
            'typeInstance': 'whatsapp',
        },
        'senderData': {
            'chatId': chat_id,
            'sender': chat_id,
            'senderName': 'Test User',
        },
        'messageData': {
            'typeMessage': 'textMessage',
            'textMessageData': {
                'textMessage': 'what version are you running?',
            },
        },
    }


@pytest.mark.billed
def test_client_role_gets_accurate_version_answer(denidin_app):
    from denidin import handle_text_message

    version = _current_version()
    notification = create_real_notification(
        _build_text_webhook(CLIENT_CHAT_ID, 'E2E_TEST_VERSION_QUERY_CLIENT_001')
    )

    handle_text_message(notification)
    response = get_response(notification)

    assert_response_exists(response)
    assert version in response, f"Expected version '{version}' in reply, got: {response}"


@pytest.mark.billed
def test_godfather_role_gets_accurate_version_answer(denidin_app):
    from denidin import handle_text_message

    version = _current_version()
    notification = create_real_notification(
        _build_text_webhook(GODFATHER_CHAT_ID, 'E2E_TEST_VERSION_QUERY_GODFATHER_001')
    )

    handle_text_message(notification)
    response = get_response(notification)

    assert_response_exists(response)
    assert version in response, f"Expected version '{version}' in reply, got: {response}"
