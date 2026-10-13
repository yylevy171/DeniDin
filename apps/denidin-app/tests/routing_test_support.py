"""Shared setup for the routing integration tests: the real app (`initialize_app` on a throwaway
data root, the real router entry points) with only the two genuine external boundaries faked -
the OpenAI client (scripted responses) and the Green API bot (records what it was told to send).
"""
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from src.models.config import AppConfiguration
from tests.backbone_test_support import FakeBot


def build_routing_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, longterm_enabled: bool = False,
                      extra: Optional[Dict[str, Any]] = None) -> Any:
    """The real app, made the module-global `denidin_app` for the test's duration, with a
    MagicMock OpenAI client (`app.ai_client`) and a FakeBot (`app.green_api_bot`)."""
    import denidin as denidin_module
    config_path = Path(__file__).parent.parent / "config" / "config.test.json"
    if not config_path.exists():
        pytest.skip("config.test.json not found")
    config = AppConfiguration.from_file(str(config_path))
    config_dict = {
        'green_api_instance_id': config.green_api_instance_id, 'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key, 'ai_model': config.ai_model,
        'ai_vision_model': config.ai_vision_model, 'ai_embedding_model': config.ai_embedding_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens, 'log_level': config.log_level,
        'data_root': str(tmp_path / "data"), 'godfather_phone': config.godfather_phone,
        'memory': {**config.memory, 'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
                   'longterm': {'storage_dir': str(tmp_path / "data" / "memory"), 'enabled': longterm_enabled}},
        'backbone_config': config.backbone_config, 'user_roles': config.user_roles, 'mcp': config.mcp,
        'reminders': {'max_active_reminders': 20},
    }
    config_dict.update(extra or {})
    app = denidin_module.initialize_app(config_dict)
    monkeypatch.setattr(denidin_module, "denidin_app", app)
    app.green_api_bot = FakeBot()
    app.ai_client = MagicMock()
    return app


def function_call(name: str, args: Optional[dict] = None, call_id: str = "c", rid: str = "r") -> Any:
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args or {}), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id=rid, usage=None, model="m")


def send_to_user(text: str, rid: str = "r-send") -> Any:
    return function_call("send_to_user", {"text": text}, call_id="c-send", rid=rid)


def nothing_more(rid: str = "r-end") -> Any:
    """A model response with no tool call: the app pauses."""
    return SimpleNamespace(output=[], output_text="", id=rid, usage=None, model="m")


def text_notification(chat_id: str, sender: str, sender_name: str, text: str, msg_id: str) -> Any:
    """A real textMessage-shaped Green API notification (`answer` records what the old
    reply-by-answer path would have sent - normally unused now)."""
    from whatsapp_chatbot_python import Notification
    notification = Notification.__new__(Notification)
    notification.event = {
        'typeWebhook': 'incomingMessageReceived', 'idMessage': msg_id, 'timestamp': 1755331200,
        'senderData': {'chatId': chat_id, 'sender': sender, 'senderName': sender_name},
        'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
    }
    notification._test_sent_messages = []
    notification.answer = lambda message: notification._test_sent_messages.append(message)
    return notification
