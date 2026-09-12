"""
Unit tests for Feature 083's fee-agreement tool wiring: tool attachment
(RBAC + feature flag), the generate_fee_agreement proposal path
(_handle_fee_agreement_generation_proposal), the approval-resolution path
(_resolve_pending_local_tool_approval's new branch), and the immediate-dispatch
verify/send handlers (_handle_verify_fee_agreement_document /
_handle_send_fee_agreement_document).

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
    GENERATE_FEE_AGREEMENT_TOOL, VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL,
    SEND_FEE_AGREEMENT_DOCUMENT_TOOL, FEE_AGREEMENT_AUTHORIZED_ROLES,
)
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.models.config import AppConfiguration
from src.models.message import AIRequest
from src.utils.time_utils import now_local

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "config" / "fee_agreement_templates"

GODFATHER_PHONE = '972500000002'
ADMIN_PHONE = '972500000001'
CLIENT_PHONE = '972500000003'

HOURLY_VALUES = {
    "FIRM_NAME": "אילה הוניגמן עריכת דין",
    "DATE": "12.9.2026",
    "CLIENT_NAME": "ישראל ישראלי",
    "SCOPE_OF_WORK": "בתביעה נגד מדינת ישראל",
    "HOURLY_RATE": "600",
    "FEE_AMOUNT": "15,000",
}


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
    def test_godfather_gets_all_three_tools_when_flag_enabled(self, ai_handler):
        user_obj = ai_handler.user_manager.get_user(GODFATHER_PHONE)
        tools = ai_handler.fee_agreement_tools.build_tools(user_obj, ai_handler.fee_agreement_docs_enabled)
        names = {t["name"] for t in tools}
        assert names == {
            GENERATE_FEE_AGREEMENT_TOOL["name"],
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
        assert GENERATE_FEE_AGREEMENT_TOOL["name"] in names
        assert VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"] in names
        assert SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"] in names


class TestGenerationProposal:
    def test_no_call_returns_none_false(self, ai_handler):
        response = _response(output=[], text="hello")
        details, created = ai_handler._handle_fee_agreement_generation_proposal(
            _request(), response, "chat1"
        )
        assert details is None
        assert created is False

    def test_valid_proposal_creates_pending_approval(self, ai_handler):
        args = {"variant_id": "hourly_consultation", "values": HOURLY_VALUES}
        response = _response(output=[
            _function_call_item(GENERATE_FEE_AGREEMENT_TOOL["name"], args)
        ], resp_id="resp_gen_1")

        details, created = ai_handler._handle_fee_agreement_generation_proposal(
            _request(), response, "chat1"
        )

        assert created is True
        assert details is not None
        assert "hourly_consultation" in details
        pending = ai_handler.pending_local_tool_approval_manager.get("chat1")
        assert pending is not None
        assert pending.tool_name == GENERATE_FEE_AGREEMENT_TOOL["name"]
        assert pending.arguments["variant_id"] == "hourly_consultation"

    def test_missing_values_rejected_with_no_pending(self, ai_handler):
        args = {"variant_id": "hourly_consultation", "values": {"FIRM_NAME": "X"}}
        response = _response(output=[
            _function_call_item(GENERATE_FEE_AGREEMENT_TOOL["name"], args)
        ])

        details, created = ai_handler._handle_fee_agreement_generation_proposal(
            _request(), response, "chat1"
        )

        assert created is False
        assert details is not None
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None

    def test_unknown_variant_rejected(self, ai_handler):
        args = {"variant_id": "no_such_variant", "values": {}}
        response = _response(output=[
            _function_call_item(GENERATE_FEE_AGREEMENT_TOOL["name"], args)
        ])

        details, created = ai_handler._handle_fee_agreement_generation_proposal(
            _request(), response, "chat1"
        )
        assert created is False
        assert details is not None


class TestResolvePendingLocalToolApproval:
    def _pending(self, args, call_id="call_fee_1", resp_id="resp_gen_1"):
        return PendingLocalToolApproval(
            tool_name=GENERATE_FEE_AGREEMENT_TOOL["name"],
            response_id=resp_id, call_id=call_id, arguments=args,
            created_at=now_local().isoformat(),
        )

    def test_approve_generates_document_and_returns_followup_text(self, ai_handler, mock_ai_client):
        args = {"variant_id": "hourly_consultation", "values": HOURLY_VALUES}
        pending = self._pending(args)
        ai_handler.pending_local_tool_approval_manager.set("chat1", pending)
        mock_ai_client.responses.create.return_value = _followup_response()

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, _request("כן"), "chat1", user_obj=None, user_role="GODFATHER",
            sender=None, recipient=None,
        )

        assert result is not None
        assert result.response_text == "הנה ההסכם"
        # The pending approval is cleared after resolution.
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None
        # A real GeneratedDocument now exists, keyed by the document_id the
        # OpenAI followup call's output arguments referenced.
        assert len(ai_handler.fee_agreement_tools._documents) == 1
        (generated,) = ai_handler.fee_agreement_tools._documents.values()
        assert generated.temp_path.exists()

    def test_decline_clears_pending_and_returns_none(self, ai_handler):
        args = {"variant_id": "hourly_consultation", "values": HOURLY_VALUES}
        pending = self._pending(args)
        ai_handler.pending_local_tool_approval_manager.set("chat1", pending)

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, _request("לא"), "chat1", user_obj=None, user_role="GODFATHER",
            sender=None, recipient=None,
        )

        assert result is None
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None
        assert ai_handler.fee_agreement_tools._documents == {}

    def test_toctou_invalid_values_at_approval_time_returns_fallback(self, ai_handler):
        # Simulates a value having become invalid between proposal and
        # approval (TOCTOU-closing re-validation, same discipline as
        # reminders' cap/date re-check).
        args = {"variant_id": "hourly_consultation", "values": {"FIRM_NAME": "X"}}
        pending = self._pending(args)
        ai_handler.pending_local_tool_approval_manager.set("chat1", pending)

        result = ai_handler._resolve_pending_local_tool_approval(
            pending, _request("כן"), "chat1", user_obj=None, user_role="GODFATHER",
            sender=None, recipient=None,
        )

        assert result is not None
        assert ai_handler.pending_local_tool_approval_manager.get("chat1") is None
        assert ai_handler.fee_agreement_tools._documents == {}


class TestVerifyImmediateDispatch:
    def test_no_call_returns_none(self, ai_handler):
        response = _response(output=[], text="hello")
        result = ai_handler._handle_verify_fee_agreement_document(_request(), response, tools=None)
        assert result is None

    def test_verify_clean_document_marks_verified_and_returns_followup(self, ai_handler, mock_ai_client):
        generated = ai_handler.doc_template_engine.generate("hourly_consultation", HOURLY_VALUES)
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
        generated = ai_handler.doc_template_engine.generate("hourly_consultation", HOURLY_VALUES)
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
        generated = ai_handler.doc_template_engine.generate("hourly_consultation", HOURLY_VALUES)
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
        generated = ai_handler.doc_template_engine.generate("hourly_consultation", HOURLY_VALUES)
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
