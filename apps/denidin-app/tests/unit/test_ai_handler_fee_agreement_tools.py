"""
Unit tests for Feature 083's fee-agreement tool wiring (2026-09-13 redesign:
minimal code, maximal AI - no approval gate anywhere in this feature any
more). Covers tool attachment (RBAC + feature flag) and the four
immediate-dispatch handlers: _handle_get_fee_agreement_template,
_handle_render_fee_agreement_document, _handle_verify_fee_agreement_document,
_handle_send_fee_agreement_document.

Same discipline as test_ai_handler_reminders.py: only the OpenAI client is a
stand-in (external service, per CONSTITUTION SS I) - DocTemplateEngine runs for
real against the real committed templates, never mocked.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler
from src.handlers.fee_agreement_tools import (
    GET_FEE_AGREEMENT_TEMPLATE_TOOL, RENDER_FEE_AGREEMENT_DOCUMENT_TOOL,
    VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL, SEND_FEE_AGREEMENT_DOCUMENT_TOOL,
    FEE_AGREEMENT_AUTHORIZED_ROLES,
)
from src.models.config import AppConfiguration
from src.models.message import AIRequest

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "config" / "fee_agreement_templates"

GODFATHER_PHONE = '972500000002'
ADMIN_PHONE = '972500000001'
CLIENT_PHONE = '972500000003'

SAMPLE_BODY_TEXT = "הסכם שכר טרחה\nלקוח: ישראל ישראלי\nשכר הטרחה: 15,000 ש\"ח כולל מע\"מ"


def _function_call_item(name, arguments, call_id="call_fee_1"):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def _response(output, resp_id="resp_1", text=""):
    return SimpleNamespace(
        id=resp_id, output=output, output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
    )


def _followup_response(text="הנה ההסכם", resp_id="resp_followup_1"):
    return SimpleNamespace(
        id=resp_id, output=[], output_text=text, model="gpt-5.6-luna",
        usage=SimpleNamespace(total_tokens=10, input_tokens=6, output_tokens=4),
    )


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
        'longterm': {'enabled': False},
    }
    config.user_roles = {
        'admin_phones': ['972500000001'],
        'blocked_phones': ['972500000099'],
    }
    config.godfather_phone = '972500000002'
    config.reminders = {'max_active_reminders': 20}
    config.fee_agreements = {'templates_dir': str(TEMPLATES_DIR), 'tmp_dir': 'tmp/fee_agreements'}
    config.feature_flags = {'fee_agreement_docs': True}
    return config


@pytest.fixture
def mock_ai_client():
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_ai_client):
    return AIHandler(mock_ai_client, mock_config)


def _request(prompt="שכר טרחה"):
    return AIRequest(
        request_id="req_1", user_prompt=prompt, model="gpt-5.6-luna",
        constitution="constitution text", max_tokens=500,
        chat_id="chat1", message_id="msg_1",
    )


class TestToolAttachment:
    def test_godfather_gets_all_four_tools_when_flag_enabled(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler.fee_agreement_tools.build_tools(user_obj, ai_handler.fee_agreement_docs_enabled)
        names = {t["name"] for t in tools}
        assert names == {
            GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"],
            RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
            VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
            SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
        }

    def test_client_gets_no_fee_agreement_tools(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(CLIENT_PHONE)
        tools = ai_handler.fee_agreement_tools.build_tools(user_obj, ai_handler.fee_agreement_docs_enabled)
        assert tools == []

    def test_disabled_flag_excludes_tools_even_for_godfather(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler.fee_agreement_tools.build_tools(user_obj, feature_enabled=False)
        assert tools == []

    def test_assemble_tools_includes_fee_agreement_tools_for_godfather(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler._assemble_tools(user_obj, "corr-1")
        names = {t.get("name") for t in (tools or [])}
        assert GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"] in names
        assert RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"] in names
        assert VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"] in names
        assert SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"] in names


class TestGetTemplateImmediateDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        result = ai_handler._handle_get_fee_agreement_template(_request(), response, tools=None)
        assert result is None

    def test_valid_variant_returns_followup_with_reference_body(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response(text="קיבלתי את התבנית")
        response = _response(output=[
            _function_call_item(
                GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"],
                {"variant_id": "hourly_consultation"},
                call_id="call_get_1",
            )
        ], resp_id="resp_get_1")

        followup = ai_handler._handle_get_fee_agreement_template(_request(), response, tools=None)

        assert followup is not None
        assert followup.output_text == "קיבלתי את התבנית"

    def test_unknown_variant_is_a_tool_call_error_not_a_crash(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response(text="תבנית לא קיימת")
        response = _response(output=[
            _function_call_item(
                GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"],
                {"variant_id": "no_such_variant"},
                call_id="call_get_2",
            )
        ], resp_id="resp_get_2")

        followup = ai_handler._handle_get_fee_agreement_template(_request(), response, tools=None)

        assert followup is not None


class TestRenderImmediateDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        result = ai_handler._handle_render_fee_agreement_document(_request(), response, tools=None)
        assert result is None

    def test_valid_render_creates_document_and_returns_followup(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response(text="ההסכם מוכן")
        response = _response(output=[
            _function_call_item(
                RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"variant_id": "hourly_consultation", "client_name": "ישראל ישראלי", "body_text": SAMPLE_BODY_TEXT},
                call_id="call_render_1",
            )
        ], resp_id="resp_render_1")

        followup = ai_handler._handle_render_fee_agreement_document(_request(), response, tools=None)

        assert followup is not None
        assert followup.output_text == "ההסכם מוכן"
        assert len(ai_handler.fee_agreement_tools._documents) == 1
        (generated,) = ai_handler.fee_agreement_tools._documents.values()
        assert generated.body_text == SAMPLE_BODY_TEXT
        assert generated.temp_path.exists()

    def test_missing_body_text_is_a_tool_call_error_not_a_crash(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response(text="חסר תוכן")
        response = _response(output=[
            _function_call_item(
                RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"variant_id": "hourly_consultation", "client_name": "ישראל ישראלי", "body_text": ""},
                call_id="call_render_2",
            )
        ], resp_id="resp_render_2")

        followup = ai_handler._handle_render_fee_agreement_document(_request(), response, tools=None)

        assert followup is not None
        assert ai_handler.fee_agreement_tools._documents == {}


class TestVerifyImmediateDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        result = ai_handler._handle_verify_fee_agreement_document(_request(), response, tools=None)
        assert result is None

    def test_verify_clean_document_marks_verified_and_returns_followup(self, ai_handler, mock_ai_client):
        generated = ai_handler.doc_template_engine.render_free_text("hourly_consultation", "ישראל ישראלי", SAMPLE_BODY_TEXT)
        ai_handler.fee_agreement_tools._documents[generated.document_id] = generated
        mock_ai_client.responses.create.return_value = _followup_response(text="נבדק, תקין")

        response = _response(output=[
            _function_call_item(
                VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"document_id": generated.document_id},
                call_id="call_verify_1",
            )
        ], resp_id="resp_verify_1")

        followup = ai_handler._handle_verify_fee_agreement_document(_request(), response, tools=None)

        assert followup is not None
        assert followup.output_text == "נבדק, תקין"
        assert generated.verified is True

    def test_stale_document_id_is_a_tool_call_error_not_a_crash(self, ai_handler, mock_ai_client):
        mock_ai_client.responses.create.return_value = _followup_response(text="לא נמצא מסמך")
        response = _response(output=[
            _function_call_item(
                VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"document_id": "does-not-exist"},
                call_id="call_verify_2",
            )
        ], resp_id="resp_verify_2")

        followup = ai_handler._handle_verify_fee_agreement_document(_request(), response, tools=None)

        assert followup is not None
        # No exception raised - the "error" key travels back to the model
        # via the function_call_output payload (asserted at the unit level
        # in test_fee_agreement_tools.py; here we only assert no crash).


class TestSendImmediateDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        result = ai_handler._handle_send_fee_agreement_document(
            _request(), response, tools=None, effective_chat_id="chat1"
        )
        assert result is None

    def test_send_refused_when_not_verified(self, ai_handler, mock_ai_client):
        generated = ai_handler.doc_template_engine.render_free_text("hourly_consultation", "ישראל ישראלי", SAMPLE_BODY_TEXT)
        ai_handler.fee_agreement_tools._documents[generated.document_id] = generated
        assert generated.verified is False

        captured = {}

        def fake_create(**kwargs):
            captured["input"] = kwargs["input"]
            return _followup_response(text="לא ניתן לשלוח")

        mock_ai_client.responses.create.side_effect = fake_create
        response = _response(output=[
            _function_call_item(
                SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"document_id": generated.document_id, "caption": "הנה ההסכם"},
                call_id="call_send_1",
            )
        ], resp_id="resp_send_1")

        followup = ai_handler._handle_send_fee_agreement_document(
            _request(), response, tools=None, effective_chat_id="chat1"
        )

        assert followup is not None
        payload = json.loads(captured["input"][0]["output"])
        assert "error" in payload
        # Refused before any WhatsApp send was attempted - document is still
        # tracked (not cleaned up), since handle_send never reaches its
        # finally-cleanup branch on this early-return path.
        assert generated.document_id in ai_handler.fee_agreement_tools._documents

    def test_send_success_cleans_up_document_and_temp_file(self, ai_handler, mock_ai_client):
        generated = ai_handler.doc_template_engine.render_free_text("hourly_consultation", "ישראל ישראלי", SAMPLE_BODY_TEXT)
        generated.verified = True
        ai_handler.fee_agreement_tools._documents[generated.document_id] = generated
        temp_path = generated.temp_path
        assert temp_path.exists()

        fake_whatsapp_handler = Mock()
        fake_whatsapp_handler.send_document_response.return_value = True
        ai_handler.whatsapp_handler = fake_whatsapp_handler
        mock_ai_client.responses.create.return_value = _followup_response(text="נשלח בהצלחה")

        response = _response(output=[
            _function_call_item(
                SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"document_id": generated.document_id, "caption": "הנה ההסכם"},
                call_id="call_send_2",
            )
        ], resp_id="resp_send_2")

        followup = ai_handler._handle_send_fee_agreement_document(
            _request(), response, tools=None, effective_chat_id="chat1"
        )

        assert followup is not None
        assert followup.output_text == "נשלח בהצלחה"
        fake_whatsapp_handler.send_document_response.assert_called_once()
        assert generated.document_id not in ai_handler.fee_agreement_tools._documents
        assert not temp_path.exists()

    def test_send_with_no_chat_id_or_no_whatsapp_handler_is_a_tool_call_error(self, ai_handler, mock_ai_client):
        generated = ai_handler.doc_template_engine.render_free_text("hourly_consultation", "ישראל ישראלי", SAMPLE_BODY_TEXT)
        generated.verified = True
        ai_handler.fee_agreement_tools._documents[generated.document_id] = generated
        ai_handler.whatsapp_handler = None  # not injected (e.g. test harness)

        captured = {}

        def fake_create(**kwargs):
            captured["input"] = kwargs["input"]
            return _followup_response(text="שגיאה")

        mock_ai_client.responses.create.side_effect = fake_create
        response = _response(output=[
            _function_call_item(
                SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
                {"document_id": generated.document_id, "caption": "x"},
                call_id="call_send_3",
            )
        ], resp_id="resp_send_3")

        followup = ai_handler._handle_send_fee_agreement_document(
            _request(), response, tools=None, effective_chat_id=None
        )

        assert followup is not None
        payload = json.loads(captured["input"][0]["output"])
        assert "error" in payload


def test_fee_agreement_authorized_roles_matches_reminder_gating():
    from src.handlers.ai_handler import REMINDER_AUTHORIZED_ROLES
    assert set(FEE_AGREEMENT_AUTHORIZED_ROLES) == set(REMINDER_AUTHORIZED_ROLES)
