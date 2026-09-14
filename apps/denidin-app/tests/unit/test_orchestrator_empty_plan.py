"""Unit test (T032, US2): an empty Plan produces a final reply built only from
Intent Identification's output, with zero domain-capability prompt content ever
loaded."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "capabilities" / "intent_identification.md").write_text("II", encoding="utf-8")
    (base / "prompts" / "capabilities" / "planning.md").write_text("PLANNING", encoding="utf-8")
    (base / "prompts" / "capabilities" / "reminders_read.md").write_text("SHOULD_NOT_LOAD", encoding="utf-8")
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


def test_small_talk_turn_never_loads_domain_capability_content(prompts_root):
    orchestrator = BackboneOrchestrator(MagicMock(), _config(prompts_root))

    call_log = []
    original_load = orchestrator.load_capability_prompt

    def tracking_load(tag):
        call_log.append(tag)
        return original_load(tag)

    orchestrator.load_capability_prompt = tracking_load

    # Intent Identification returns small talk; Planning returns empty steps.
    with patch.object(orchestrator, "call_capability_step") as mock_call:
        mock_call.side_effect = [
            "This is ordinary small talk with no action needed.",
            '{"steps": []}',
        ]
        response = orchestrator.get_response(_request(), user_role="client")

    assert response.response_text == "This is ordinary small talk with no action needed."
    # Only Intent Identification / Planning ever get their prompts loaded via
    # call_capability_step (mocked here) - load_capability_prompt itself is
    # never invoked for any domain capability in this empty-plan path.
    assert call_log == []
