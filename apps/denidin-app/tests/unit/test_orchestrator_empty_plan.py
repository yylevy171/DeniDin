"""Unit test (T032, US2; updated 2026-09-16 for the resolution
redesign): a small-talk turn where the model calls send_to_user directly (no
load_capabilities at all) never loads any domain capability's
prompt content."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from tests.backbone_test_support import make_session_manager
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "capabilities" / "cap_reminders_read.md").write_text("SHOULD_NOT_LOAD", encoding="utf-8")
    return base


def _config(prompts_root):
    return AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )


def _request():
    return AIRequest(
        user_prompt="Good morning, how are you today?", constitution="",
        max_tokens=1000, model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def _send_to_user_response(text: str):
    item = SimpleNamespace(
        type="function_call", name="send_to_user",
        arguments=json.dumps({"text": text}), call_id="call1",
    )
    return SimpleNamespace(output=[item], output_text="", id="resp1", usage=None)


def test_small_talk_turn_never_loads_domain_capability_content(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _send_to_user_response(
        "This is ordinary small talk with no action needed.",
    )
    orchestrator = BackboneOrchestrator(client, _config(prompts_root), session_manager=make_session_manager())

    call_log = []
    original_load = orchestrator.load_capability_prompt

    def tracking_load(tag):
        call_log.append(tag)
        return original_load(tag)

    orchestrator.load_capability_prompt = tracking_load

    response = orchestrator.turn_with_rounds(_request(), user_role="client")

    assert response.response_text == "This is ordinary small talk with no action needed."
    # No load_capabilities tool call was made, so no domain
    # capability prompt is ever loaded.
    assert call_log == []
