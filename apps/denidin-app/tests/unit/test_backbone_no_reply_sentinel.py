"""Unit test (T033, US2; updated 2026-09-16 for the capability-resolution-loop.md
redesign): the [[NO_REPLY]] sentinel, sent via the model's own send_to_user tool
call, suppresses the reply exactly as before."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone
from tests.backbone_test_support import make_session_manager
from src.models.config import AppConfiguration
from src.models.message import AIRequest, NO_REPLY_SENTINEL


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _backbone(prompts_root, client=None):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return Backbone(client or MagicMock(), config, session_manager=make_session_manager())


def _request():
    return AIRequest(
        user_prompt="hey Yossi, did you finish that?", constitution="",
        max_tokens=1000, model="gpt-5.6-luna", chat_id="group1", message_id="msg1",
    )


def _send_to_user_response(text: str):
    item = SimpleNamespace(
        type="function_call", name="send_to_user",
        arguments=json.dumps({"text": text}), call_id="call1",
    )
    return SimpleNamespace(output=[item], output_text="", id="resp1", usage=None)


def test_no_reply_sentinel_suppresses_reply(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _send_to_user_response(NO_REPLY_SENTINEL)
    backbone = _backbone(prompts_root, client)

    response = backbone.turn_with_rounds(_request(), user_role="client")

    assert response.should_reply is False
    assert response.response_text == NO_REPLY_SENTINEL


def test_ordinary_reply_is_sent(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _send_to_user_response("בוקר טוב!")
    backbone = _backbone(prompts_root, client)

    response = backbone.turn_with_rounds(_request(), user_role="client")

    assert response.should_reply is True
    assert response.response_text == "בוקר טוב!"
