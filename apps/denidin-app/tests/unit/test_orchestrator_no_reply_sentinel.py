"""Unit test (T033, US2): the [[NO_REPLY]] sentinel on the final step suppresses
the reply exactly as AIHandler's does."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration
from src.models.message import AIRequest, NO_REPLY_SENTINEL


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _orchestrator(prompts_root):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(MagicMock(), config)


def _request():
    return AIRequest(
        user_prompt="hey Yossi, did you finish that?", constitution="",
        max_tokens=1000, model="gpt-5.6-luna", chat_id="group1", message_id="msg1",
    )


def test_no_reply_sentinel_suppresses_reply(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    with patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = [NO_REPLY_SENTINEL, '{"steps": []}']
        response = orchestrator.get_response(_request(), user_role="client")

    assert response.should_reply is False
    assert response.response_text == NO_REPLY_SENTINEL


def test_ordinary_reply_is_sent(prompts_root):
    orchestrator = _orchestrator(prompts_root)
    with patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = ["בוקר טוב!", '{"steps": []}']
        response = orchestrator.get_response(_request(), user_role="client")

    assert response.should_reply is True
    assert response.response_text == "בוקר טוב!"
