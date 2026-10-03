"""Unit tests (2026-10-01): the shared turn-result helpers (core/turn_result.py), used
identically by the legacy AIHandler and the backbone - Item8 (MCP error normalized to a
string), Item9 (WhatsApp length cut), Item12 (real token totals / model / finish reason),
Item13 (possible fabricated confirmation logged), and Item10 (the backbone treats a
missing/unknown role as godfather)."""
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone
from src.core.ai_manager import AIManager
extract_mcp_call_items = AIManager.extract_mcp_call_items
finish_reason_of = AIManager.finish_reason_of
fit_for_whatsapp = AIManager.fit_for_whatsapp
log_possible_hallucinated_confirmation = AIManager.log_possible_hallucinated_confirmation
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse
from src.models.user import Role
from tests.backbone_test_support import make_backbone, make_session_manager


def _mcp_item(name, error=None):
    return SimpleNamespace(type="mcp_call", name=name, arguments="{}", output="ok", error=error)


def test_mcp_error_object_is_normalized_to_a_string():
    response = SimpleNamespace(output=[_mcp_item("list_invoices", error=ConnectionError("503 tunnel"))])
    [call] = extract_mcp_call_items(response)
    assert call["error"] == "503 tunnel"
    json.dumps(call)  # storable - the 2026-09-15 crash was json.dump on a raw error object


def test_finish_reason_is_stop_or_the_incomplete_reason():
    assert finish_reason_of(SimpleNamespace(incomplete_details=None)) == "stop"
    assert finish_reason_of(SimpleNamespace(
        incomplete_details=SimpleNamespace(reason="max_output_tokens"))) == "max_output_tokens"


def _ai_response(text):
    return AIResponse(request_id="r", response_text=text, tokens_used=0, prompt_tokens=0,
                      completion_tokens=0, model="m", finish_reason="stop", timestamp=1)


def test_fit_for_whatsapp_cuts_only_long_replies():
    assert fit_for_whatsapp(_ai_response("קצר")).response_text == "קצר"
    cut = fit_for_whatsapp(_ai_response("א" * 5000))
    assert cut.is_truncated and len(cut.response_text) == 4003


def test_confirmation_without_mcp_call_is_logged(caplog):
    caplog.set_level(logging.WARNING)
    log_possible_hallucinated_confirmation("r1", "החשבונית הוצאה בהצלחה", True, [])
    assert "Possible hallucinated invoicing confirmation" in caplog.text


def test_confirmation_backed_by_an_mcp_call_is_not_logged(caplog):
    caplog.set_level(logging.WARNING)
    log_possible_hallucinated_confirmation("r1", "החשבונית הוצאה בהצלחה", True, [{"name": "create_invoice"}])
    assert "Possible hallucinated" not in caplog.text


# --- the backbone uses the same helpers --------------------------------------

@pytest.fixture
def prompts_root(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    return base


def _response(items, response_id, *, total, inp, out):
    return SimpleNamespace(output=items, output_text="", id=response_id, model="gpt-real-model",
                           incomplete_details=None,
                           usage=SimpleNamespace(total_tokens=total, input_tokens=inp, output_tokens=out))


def _call(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _backbone(prompts_root, client):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z",
                              backbone_config={"base_dir": str(prompts_root)})
    return make_backbone(client, config, session_manager=make_session_manager())


def _request():
    return AIRequest(user_prompt="שלום", constitution="", max_tokens=1000, model="requested-model",
                     chat_id="chat1", message_id="msg1")


def test_backbone_reports_the_turns_real_tokens_model_and_mcp_errors_as_strings(prompts_root):
    client = MagicMock()
    client.responses.create.side_effect = [
        _response([_mcp_item("list_invoices", error=ConnectionError("503")),
                   _call("record_planning_status", {"status": "x"}, "c1")], "r1", total=15, inp=10, out=5),
        _response([_call("send_to_user", {"text": "שלום"}, "c2")], "r2", total=30, inp=20, out=10),
    ]
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")

    assert (response.tokens_used, response.prompt_tokens, response.completion_tokens) == (45, 30, 15)
    assert response.model == "gpt-real-model"
    assert response.finish_reason == "stop"
    assert response.mcp_calls[0]["error"] == "503"


def test_backbone_cuts_a_long_reply_for_whatsapp(prompts_root):
    client = MagicMock()
    client.responses.create.return_value = _response(
        [_call("send_to_user", {"text": "א" * 5000}, "c1")], "r1", total=1, inp=1, out=0)
    response = _backbone(prompts_root, client).single_turn(_request(), chat_id="chat1")
    assert response.is_truncated and len(response.response_text) == 4003


def test_backbone_treats_a_missing_or_unknown_role_as_godfather():
    assert Backbone._resolve_role("") == Role.GODFATHER
    assert Backbone._resolve_role("nonsense") == Role.GODFATHER
    assert Backbone._resolve_role("client") == Role.CLIENT
