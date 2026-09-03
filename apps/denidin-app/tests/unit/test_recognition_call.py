"""
Feature 069 (mechanism move) — Task A / T004a.

Pins `AIHandler.recognize_ledger_event(...)` — the ONE dedicated text-only OpenAI
call fired AFTER a godfather/admin turn's reply has been sent. It is the only place
prose → `LedgerEvent`-schema mapping happens; its output is a tri-state verdict
(`contracts/recognition-and-logging.md` C2, `data-model.md` §2) consumed immediately
by the zero-AI ledgerer and never surfaced to the operator.

Signature (pinned, keyword-only):

    recognize_ledger_event(self, *, session, reply_text, turn_mcp_calls,
                           constitution_text) -> dict

Verdicts:
  - `complete`  → {"verdict": "complete", "event": {...schema-mapped...}, "trigger_message_id": "..."}
  - `none`      → {"verdict": "none"}
  - `declined`  → {"verdict": "declined", "source_type": ..., "client_name_stated": ...,
                   "reason": "declined_by_operator"}

Only the OpenAI client is a stand-in (external service, CONSTITUTION §I); the
`AIHandler` / `SessionManager` are real.

The recognition call reports its verdict by calling a dedicated function tool named
`report_ledger_recognition` (its `event` sub-object reuses `LEDGER_EVENT_TOOL`'s
schema). Task B (`T004b`) must keep that tool name in sync with this file.
"""
import json
import inspect
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration

RECOGNITION_TOOL_NAME = "report_ledger_recognition"

GODFATHER_PHONE = "972500000002"
ADMIN_PHONE = "972500000001"


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        "session": {"storage_dir": str(tmp_path / "data" / "sessions")},
        "longterm": {"enabled": False},
    }
    config.user_roles = {"admin_phones": [ADMIN_PHONE], "blocked_phones": []}
    config.godfather_phone = GODFATHER_PHONE
    config.reminders = {"max_active_reminders": 20}
    config.ledger_recognition_context_window_hours = 1.0
    return config


@pytest.fixture
def ai_handler(mock_config):
    return AIHandler(MagicMock(), mock_config)


@pytest.fixture
def session(ai_handler):
    """A real session with a trigger user message + an assistant reply."""
    chat_id = "group-1@g.us"
    sm = ai_handler.session_manager
    trigger_id = sm.add_message(
        chat_id=chat_id, role="user", content="חתמנו היום הסכם שכר טרחה עם דנה כהן",
        user_role="godfather", sender="972500000002", sender_name="בעל הבית",
    )
    completing_id = sm.add_message(
        chat_id=chat_id, role="assistant", content="מצוין, רשמתי.", user_role="godfather",
    )
    s = sm.get_session(chat_id)
    return SimpleNamespace(session=s, chat_id=chat_id, trigger_id=trigger_id,
                           completing_id=completing_id)


def _verdict_response(payload: dict):
    """A Responses-API-shaped object carrying one report_ledger_recognition call."""
    return SimpleNamespace(
        id="resp_recog_1",
        model="gpt-5.6-luna",
        output_text="",
        output=[SimpleNamespace(
            type="function_call",
            name=RECOGNITION_TOOL_NAME,
            arguments=json.dumps(payload, ensure_ascii=False),
            call_id="call_0",
        )],
        usage=SimpleNamespace(total_tokens=5, input_tokens=4, output_tokens=1),
    )


def _no_call_response():
    return SimpleNamespace(
        id="resp_recog_none", model="gpt-5.6-luna", output_text="", output=[],
        usage=SimpleNamespace(total_tokens=3, input_tokens=3, output_tokens=0),
    )


def _garbage_response():
    return SimpleNamespace(
        id="resp_recog_bad", model="gpt-5.6-luna", output_text="", output=[SimpleNamespace(
            type="function_call", name=RECOGNITION_TOOL_NAME,
            arguments="{not valid json", call_id="call_x",
        )],
        usage=SimpleNamespace(total_tokens=3, input_tokens=3, output_tokens=0),
    )


def _agreement_event(**overrides):
    event = {
        "source_type": "הסכם",
        "event_subtype": "יצירה",
        "client_name": "דנה כהן",
        "description": "הסכם שכר טרחה",
        "amount": None,
        "txn_date": None,
        "vat_status": None,
        "components": [
            {"amount": "4000", "percent": None, "percent_base": None,
             "trigger_condition": None, "hours": None, "hourly_rate": None,
             "description": "ריטיינר חודשי"},
        ],
        "component_count": 1,
        "payer_name": "איגוד העובדים",
        "bank_number": None, "bank_branch": None, "bank_account": None,
        "accounting_document_display_number": None,
        "reference": None, "reference_hint": None,
    }
    event.update(overrides)
    return event


# --------------------------------------------------------------------------- #

class TestSignature:
    def test_method_exists(self):
        assert hasattr(AIHandler, "recognize_ledger_event")

    def test_signature_is_keyword_only(self):
        sig = inspect.signature(AIHandler.recognize_ledger_event)
        params = list(sig.parameters)
        assert params[0] == "self"
        for name in ("session", "reply_text", "turn_mcp_calls", "constitution_text"):
            assert name in sig.parameters
            assert sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


class TestVerdicts:
    def test_complete_verdict_passes_through_event_and_trigger(self, ai_handler, session):
        payload = {"verdict": "complete", "event": _agreement_event(),
                   "trigger_message_id": session.trigger_id,
                   "source_type": None, "client_name_stated": None, "reason": None}
        ai_handler.client.responses.create.return_value = _verdict_response(payload)

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="מצוין, רשמתי.",
            turn_mcp_calls=[], constitution_text="C")

        assert result["verdict"] == "complete"
        assert result["trigger_message_id"] == session.trigger_id
        assert result["event"]["source_type"] == "הסכם"
        assert result["event"]["client_name"] == "דנה כהן"
        assert result["event"]["payer_name"] == "איגוד העובדים"

    def test_none_verdict_when_model_calls_nothing(self, ai_handler, session):
        ai_handler.client.responses.create.return_value = _no_call_response()

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="בסדר גמור.",
            turn_mcp_calls=[], constitution_text="C")

        assert result == {"verdict": "none"}

    def test_none_verdict_when_model_reports_none(self, ai_handler, session):
        payload = {"verdict": "none", "event": None, "trigger_message_id": None,
                   "source_type": None, "client_name_stated": None, "reason": None}
        ai_handler.client.responses.create.return_value = _verdict_response(payload)

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="מה שלומך?",
            turn_mcp_calls=[], constitution_text="C")

        assert result == {"verdict": "none"}

    def test_declined_verdict_shape(self, ai_handler, session):
        payload = {"verdict": "declined", "event": None, "trigger_message_id": None,
                   "source_type": "בנק", "client_name_stated": "יוסי מהחנייה",
                   "reason": "declined_by_operator"}
        ai_handler.client.responses.create.return_value = _verdict_response(payload)

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="הבנתי, לא אשמור.",
            turn_mcp_calls=[], constitution_text="C")

        assert result["verdict"] == "declined"
        assert result["source_type"] == "בנק"
        assert result["client_name_stated"] == "יוסי מהחנייה"
        assert result["reason"] == "declined_by_operator"

    def test_invoice_source_type_taken_from_verdict_not_prose(self, ai_handler, session):
        """A successful create_* this turn → source_type=='חשבונית' straight from the
        recognition verdict (which the model builds off the real Morning tool result)."""
        turn_mcp_calls = [{
            "name": "create_combo_document",
            "error": None,
            "arguments": {"client_name": "דנה כהן", "amount": 4000},
            "output": json.dumps({"status": "success", "document_number": "1042",
                                  "document_type": 320, "amount": 4000,
                                  "creation_date": "2026-07-15"}, ensure_ascii=False),
        }]
        event = {"source_type": "חשבונית", "event_subtype": "חשבונית מס/קבלה",
                 "client_name": "דנה כהן", "description": "עסקה משולבת",
                 "amount": 4000, "txn_date": "2026-07-15", "vat_status": "כולל",
                 "components": [{}], "component_count": 1, "payer_name": None,
                 "bank_number": None, "bank_branch": None, "bank_account": None,
                 "accounting_document_display_number": "1042",
                 "reference": None, "reference_hint": None}
        payload = {"verdict": "complete", "event": event,
                   "trigger_message_id": session.trigger_id,
                   "source_type": None, "client_name_stated": None, "reason": None}
        ai_handler.client.responses.create.return_value = _verdict_response(payload)

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="נוצרה עסקה משולבת 1042.",
            turn_mcp_calls=turn_mcp_calls, constitution_text="C")

        assert result["verdict"] == "complete"
        assert result["event"]["source_type"] == "חשבונית"
        assert result["event"]["accounting_document_display_number"] == "1042"


class TestRetry:
    def test_one_shot_retry_on_unparseable_then_success(self, ai_handler, session):
        good = _verdict_response({"verdict": "complete", "event": _agreement_event(),
                                  "trigger_message_id": session.trigger_id,
                                  "source_type": None, "client_name_stated": None,
                                  "reason": None})
        ai_handler.client.responses.create.side_effect = [_garbage_response(), good]

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="רשמתי.",
            turn_mcp_calls=[], constitution_text="C")

        assert ai_handler.client.responses.create.call_count == 2
        assert result["verdict"] == "complete"

    def test_one_shot_retry_on_incomplete_capture(self, ai_handler, session):
        """`complete` but components empty while component_count=2 → is_incomplete_capture
        → retry once, then accept the corrected verdict."""
        incomplete = _verdict_response({
            "verdict": "complete",
            "event": _agreement_event(components=[], component_count=2),
            "trigger_message_id": session.trigger_id,
            "source_type": None, "client_name_stated": None, "reason": None})
        fixed = _verdict_response({
            "verdict": "complete",
            "event": _agreement_event(
                components=[
                    {"amount": "4000", "description": "ריטיינר"},
                    {"amount": None, "percent": "12", "description": "הצלחה"},
                ], component_count=2),
            "trigger_message_id": session.trigger_id,
            "source_type": None, "client_name_stated": None, "reason": None})
        ai_handler.client.responses.create.side_effect = [incomplete, fixed]

        result = ai_handler.recognize_ledger_event(
            session=session.session, reply_text="רשמתי.",
            turn_mcp_calls=[], constitution_text="C")

        assert ai_handler.client.responses.create.call_count == 2
        assert len(result["event"]["components"]) == 2


class TestInputAssemblyAndIsolation:
    def _stringify_call(self, create_mock):
        kwargs = create_mock.call_args.kwargs
        blob = json.dumps(kwargs.get("input"), ensure_ascii=False, default=str)
        blob += "\n" + str(kwargs.get("instructions", ""))
        return blob, kwargs

    def test_input_includes_reply_mcp_calls_and_recognition_prompt(self, ai_handler, session):
        ai_handler.client.responses.create.return_value = _no_call_response()
        turn_mcp_calls = [{
            "name": "list_invoices", "error": None, "arguments": {"client_name": "דנה כהן"},
            "output": json.dumps({"invoices": [{"number": "UNIQ-MARKER-777"}]},
                                 ensure_ascii=False),
        }]

        ai_handler.recognize_ledger_event(
            session=session.session, reply_text="REPLY-MARKER-abc",
            turn_mcp_calls=turn_mcp_calls)

        blob, kwargs = self._stringify_call(ai_handler.client.responses.create)
        assert "REPLY-MARKER-abc" in blob
        assert "UNIQ-MARKER-777" in blob          # mcp call result carried verbatim
        # Feature 069 decision #11: the dedicated recognition prompt drives this
        # call, not the full constitution.
        assert "post-turn recognition prompt" in blob
        assert RECOGNITION_TOOL_NAME in blob
        # text-only for Morning: no MCP / hosted tool wired onto this call
        # (query_ledger_events is a local read-only function tool, not an MCP one)
        assert not any(
            isinstance(t, dict) and t.get("type") == "mcp"
            for t in (kwargs.get("tools") or [])
        )
        tool_names = {t.get("name") for t in (kwargs.get("tools") or []) if isinstance(t, dict)}
        assert RECOGNITION_TOOL_NAME in tool_names
        assert "query_ledger_events" in tool_names

    def test_verdict_output_never_appended_to_session(self, ai_handler, session):
        before = list(session.session.message_ids)
        payload = {"verdict": "complete", "event": _agreement_event(),
                   "trigger_message_id": session.trigger_id,
                   "source_type": None, "client_name_stated": None, "reason": None}
        ai_handler.client.responses.create.return_value = _verdict_response(payload)

        ai_handler.recognize_ledger_event(
            session=session.session, reply_text="רשמתי.",
            turn_mcp_calls=[], constitution_text="C")

        after = list(ai_handler.session_manager.get_session(session.chat_id).message_ids)
        assert after == before
