"""Unit tests (rewritten 2026-09-16 for the capability-resolution-loop.md
stateless-approval redesign): Backbone.single_turn sets
AIResponse.offer_approval_buttons whenever the model called the stateless,
domain-agnostic `approval_with_yes_no_buttons` resolution tool this turn -
the backbone's own equivalent of AIHandler's `new_pending_approval_created`
(Feature 047 parity), now driven by `self._turn_offered_approval` rather than
any pending-approval manager lookup."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.backbone_test_support import make_backbone, make_session_manager
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _backbone(prompts_root, client):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return make_backbone(client, config, session_manager=make_session_manager())


def _request():
    return AIRequest(
        user_prompt="תזכיר לי בעוד שעה לשלוח חשבונית", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1",
    )


def _function_call_response(name: str, arguments: dict, call_id="call1"):
    item = SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)
    return SimpleNamespace(output=[item], output_text="", id="resp1", usage=None)


def test_offer_approval_buttons_true_when_the_model_calls_the_approval_tool(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _function_call_response(
        "approval_with_yes_no_buttons", {"text": "📋 לאישור — תזכורת חדשה..."},
    )
    backbone = _backbone(prompts_root, client)

    response = backbone.single_turn(_request(), chat_id="chat1", user_role="godfather")

    assert response.offer_approval_buttons is True
    assert response.response_text == "📋 לאישור — תזכורת חדשה..."


def test_offer_approval_buttons_false_when_only_send_to_user_is_called(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _function_call_response("send_to_user", {"text": "בוקר טוב!"})
    backbone = _backbone(prompts_root, client)

    response = backbone.single_turn(_request(), chat_id="chat1", user_role="godfather")

    assert response.offer_approval_buttons is False


def test_offer_approval_buttons_resets_between_turns(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _function_call_response("approval_with_yes_no_buttons", {"text": "לאשר?"}),
        _function_call_response("send_to_user", {"text": "בוקר טוב!"}),
    ]
    backbone = _backbone(prompts_root, client)

    first = backbone.single_turn(_request(), chat_id="chat1", user_role="godfather")
    second = backbone.single_turn(_request(), chat_id="chat1", user_role="godfather")

    assert first.offer_approval_buttons is True
    assert second.offer_approval_buttons is False
