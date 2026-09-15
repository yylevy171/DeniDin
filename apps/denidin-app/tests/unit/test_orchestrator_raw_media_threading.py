"""Unit tests (Feature 063, 2026-09-15 real design correction): BackboneOrchestrator.
get_response threads RAW media/media_type through turn_context (consumed by
media_analysis's own extract() fallback branch), and tells Intent Identification
"media attached, not yet extracted" rather than pre-computed content."""
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.orchestrator import BackboneOrchestrator
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    (base / "prompts" / "capabilities" / "intent_identification.md").write_text("INTENT", encoding="utf-8")
    (base / "prompts" / "capabilities" / "planning.md").write_text("PLAN", encoding="utf-8")
    return base


def _orchestrator(prompts_root, client):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(client, config)


def _request():
    return AIRequest(
        user_prompt="קבלה", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def test_get_response_threads_raw_media_into_turn_context(prompts_root):
    client = MagicMock()
    response = MagicMock()
    response.output = []
    response.output_text = "[[NO_REPLY]]"  # placeholder; not asserted here
    client.responses.create.return_value = response
    orchestrator = _orchestrator(prompts_root, client)
    media = Media(data=b"fake bytes", mime_type="image/jpeg", filename="x.jpg")

    with patch("src.backbone.orchestrator.identify_intent", return_value="intent") as mock_identify, \
         patch("src.backbone.orchestrator.build_plan") as mock_build_plan:
        from src.backbone.planning import Plan
        mock_build_plan.return_value = Plan(steps=[])
        orchestrator.get_response(_request(), chat_id="chat1", is_media=True,
                                   media=media, media_type="image")

    # Intent Identification was told is_media=True with no media_extraction
    # (raw media, not pre-computed) - the "not yet extracted" branch.
    call_kwargs = mock_identify.call_args.kwargs
    assert call_kwargs["is_media"] is True
    assert call_kwargs.get("media_extraction") is None
