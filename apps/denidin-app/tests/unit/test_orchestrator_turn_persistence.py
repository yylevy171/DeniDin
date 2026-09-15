"""Unit tests (Feature 063, 2026-09-15 gap fix): BackboneOrchestrator persists every
flag-on turn to the shared SessionManager via `_persist_turn`, so the rolling window,
post-turn ledger recognition, and the nightly daily-summary roll all see flag-on
turns exactly as they'd see a flag-off turn - closing a real gap where flag-on turns
never wrote anything to the session at all."""
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
    (base / "prompts" / "capabilities" / "intent_identification.md").write_text("INTENT", encoding="utf-8")
    (base / "prompts" / "capabilities" / "planning.md").write_text("PLAN", encoding="utf-8")
    return base


def _orchestrator(prompts_root, client, **kwargs):
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(prompts_root)},
    )
    return BackboneOrchestrator(client, config, **kwargs)


def _request(timestamp=None):
    return AIRequest(
        user_prompt="שלום", constitution="", max_tokens=1000,
        model="gpt-5.6-luna", chat_id="chat1", message_id="msg1", timestamp=timestamp,
    )


def _run_turn(orchestrator, **get_response_kwargs):
    response = MagicMock()
    response.output = []
    response.output_text = "תשובה"
    orchestrator.client.responses.create.return_value = response
    with patch("src.backbone.orchestrator.identify_intent", return_value="intent"), \
         patch("src.backbone.orchestrator.build_plan") as mock_build_plan:
        from src.backbone.planning import Plan
        mock_build_plan.return_value = Plan(steps=[])
        return orchestrator.get_response(_request(), chat_id="chat1", **get_response_kwargs)


def test_get_response_persists_user_and_assistant_messages(prompts_root):
    session_manager = MagicMock()
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager,
                                  own_whatsapp_number="972500000000")

    _run_turn(orchestrator, sender="Yaron", user_phone="972501234567", sender_phone="972501234567")

    assert session_manager.add_message_with_tokens.call_count == 2
    user_call, assistant_call = session_manager.add_message_with_tokens.call_args_list
    assert user_call.kwargs["role"] == "user"
    assert user_call.kwargs["content"] == "שלום"
    assert user_call.kwargs["chat_id"] == "chat1"
    assert assistant_call.kwargs["role"] == "assistant"
    # empty plan => final_text is Intent Identification's own output (per
    # contracts/orchestration-loop.md step 4), not the mocked response text.
    assert assistant_call.kwargs["content"] == "intent"
    assert assistant_call.kwargs["sender"] == "972500000000@c.us"
    assert assistant_call.kwargs["sender_name"] == "DeniDin"


def test_get_response_skips_assistant_persistence_on_no_reply(prompts_root):
    session_manager = MagicMock()
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager)
    response = MagicMock()
    response.output = []
    response.output_text = "[[NO_REPLY]]"
    orchestrator.client.responses.create.return_value = response

    with patch("src.backbone.orchestrator.identify_intent", return_value="[[NO_REPLY]]"), \
         patch("src.backbone.orchestrator.build_plan") as mock_build_plan:
        from src.backbone.planning import Plan
        mock_build_plan.return_value = Plan(steps=[])
        orchestrator.get_response(_request(), chat_id="chat1")

    # Only the user message is persisted - no assistant message for a no-reply turn.
    assert session_manager.add_message_with_tokens.call_count == 1
    assert session_manager.add_message_with_tokens.call_args.kwargs["role"] == "user"


def test_get_response_persistence_is_a_noop_without_session_manager(prompts_root):
    """session_manager=None (default) must never raise - a turn with no
    persistence configured is a degraded turn, not a crashed one."""
    orchestrator = _orchestrator(prompts_root, MagicMock())
    result = _run_turn(orchestrator)
    assert result.response_text == "intent"


def test_persist_turn_never_raises_on_session_manager_failure(prompts_root):
    session_manager = MagicMock()
    session_manager.add_message_with_tokens.side_effect = RuntimeError("disk full")
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager)

    result = _run_turn(orchestrator)  # must not raise
    assert result.response_text == "intent"


def test_persist_turn_drops_implausible_source_timestamp(prompts_root):
    """A request.timestamp below _MIN_PLAUSIBLE_SOURCE_EPOCH (2020-01-01 UTC) must
    fall back to None (processing time) rather than persisting a bogus 1970 date."""
    session_manager = MagicMock()
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager)
    response = MagicMock()
    response.output = []
    response.output_text = "תשובה"
    orchestrator.client.responses.create.return_value = response

    request = AIRequest(user_prompt="שלום", constitution="", max_tokens=1000,
                         model="gpt-5.6-luna", chat_id="chat1", message_id="msg1", timestamp=5)
    with patch("src.backbone.orchestrator.identify_intent", return_value="intent"), \
         patch("src.backbone.orchestrator.build_plan") as mock_build_plan:
        from src.backbone.planning import Plan
        mock_build_plan.return_value = Plan(steps=[])
        orchestrator.get_response(request, chat_id="chat1")

    user_call = session_manager.add_message_with_tokens.call_args_list[0]
    assert user_call.kwargs["timestamp"] is None


def test_persist_turn_group_chat_uses_chat_id_as_recipient(prompts_root):
    session_manager = MagicMock()
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager)

    _run_turn(orchestrator, is_group=True, chat_name="Team Chat", sender="Yaron")

    user_call, assistant_call = session_manager.add_message_with_tokens.call_args_list
    assert user_call.kwargs["recipient"] == "chat1"
    assert assistant_call.kwargs["recipient"] == "chat1"


def test_get_response_threads_mcp_calls_into_persisted_assistant_message(prompts_root):
    session_manager = MagicMock()
    orchestrator = _orchestrator(prompts_root, MagicMock(), session_manager=session_manager)
    orchestrator._turn_mcp_calls = []  # reset explicitly before the call sets it fresh

    mcp_item = MagicMock()
    mcp_item.type = "mcp_call"
    mcp_item.name = "list_invoices"
    mcp_item.error = None
    mcp_item.arguments = "{}"
    mcp_item.output = "[]"
    response = MagicMock()
    response.output = [mcp_item]
    response.output_text = "תשובה"
    orchestrator.client.responses.create.return_value = response

    with patch("src.backbone.orchestrator.identify_intent", return_value="intent"), \
         patch("src.backbone.orchestrator.build_plan") as mock_build_plan:
        from src.backbone.planning import PlanStep, Plan
        from src.backbone.capability_tags import CapabilityTag
        mock_build_plan.return_value = Plan(steps=[PlanStep(capability=CapabilityTag.INVOICING_READ, note="")])
        with patch.object(BackboneOrchestrator, "_resolve_capability_handler") as mock_resolve:
            def fake_handler(orch, request, accumulated_context, note, turn_context):
                return orch.call_capability_step(tag=CapabilityTag.INVOICING_READ, request=request)
            mock_resolve.return_value = fake_handler
            result = orchestrator.get_response(_request(), chat_id="chat1")

    assert result.mcp_calls == [
        {"name": "list_invoices", "error": None, "arguments": "{}", "output": "[]"}
    ]
    assistant_call = session_manager.add_message_with_tokens.call_args_list[1]
    assert assistant_call.kwargs["mcp_calls"] == [
        {"name": "list_invoices", "error": None, "arguments": "{}", "output": "[]"}
    ]
