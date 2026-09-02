"""
Component-Integration Test: post-turn ledger recognition through the real router
(Feature 069, T007a — mechanism move).

A real `textMessage`-shaped Green API notification for an exact-match `הסכם` →
`bot.router` → `handle_text_message` → `_process_conversational_message` →
`AIHandler.get_response` (normal reply) → **the post-turn recognition call** →
the zero-AI ledgerer → exactly one `LedgerEvent` file on disk, back-linked from
the completing `Message`.

All real internal objects and real router dispatch (CONSTITUTION §V); only the
OpenAI client's `responses.create` is stood in for — call 1 returns the operator
reply, call 2 returns the `complete` recognition verdict.

This is the redesign's integration proof that:
  - ledger capture is now a post-turn step, not an inline `capture_ledger_event`
    function tool on the main turn,
  - `_call_openai_ledger_followup_api` (the old second round-trip) is gone,
  - the new `event_id` lands on the **completing** message, not the trigger.

It does NOT exercise real model judgment (whether the model actually recognizes a
complete event) — that is `tests/billed/` (US1).
"""
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration

GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"
TRIGGER_MSG_ID = "integration_069_recognition_msg_1"

RECOGNITION_TOOL_NAME = "report_ledger_recognition"
OPERATOR_REPLY = "רשמתי את הסכם שכר הטרחה עם דנה כהן."


@pytest.mark.integration
class TestLedgerClientResolutionRouting:

    @pytest.fixture
    def denidin_app(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

        import denidin as denidin_module
        if denidin_module.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                'ai_vision_model': config.ai_vision_model,
                'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles,
                'reminders': {'max_active_reminders': 20},
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)
        return denidin_module.denidin_app

    @pytest.fixture(autouse=True)
    def _clean_state(self, denidin_app):
        def _wipe():
            manager = denidin_app.ai_handler.ledger_event_manager
            manager._index = []
            for path in manager.storage_dir.glob("*.json"):
                path.unlink()
            sessions_dir = Path(denidin_app.ai_handler.session_manager.storage_dir)
            chat_session = denidin_app.ai_handler.session_manager.get_session(GODFATHER_CHAT_ID)
            for path in (sessions_dir / chat_session.session_id).glob("messages/*.json"):
                path.unlink()
            chat_session.message_ids = []
        _wipe()
        yield
        _wipe()

    def _create_notification(self, text: str, msg_id: str):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1755331200,
            'senderData': {
                'chatId': GODFATHER_CHAT_ID,
                'sender': GODFATHER_SENDER,
                'senderName': 'Test Godfather',
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': text},
            },
        }
        notification._test_sent_messages = []
        notification.answer = notification._test_sent_messages.append
        return notification

    def _complete_agreement_verdict(self):
        return {
            "verdict": "complete",
            "trigger_message_id": TRIGGER_MSG_ID,
            "event": {
                "source_type": "הסכם",
                "event_subtype": "יצירה",
                "client_name": "דנה כהן",
                "description": "הסכם שכר טרחה",
                "vat_status": None,
                "payer_name": None,
                "amount": None,
                "txn_date": None,
                "components": [
                    {"amount": "4000", "percent": None, "percent_base": None,
                     "trigger_condition": None, "hours": None, "hourly_rate": None,
                     "description": "ריטיינר חודשי"},
                ],
                "component_count": 1,
                "bank_number": None, "bank_branch": None, "bank_account": None,
                "accounting_document_display_number": None,
                "reference": None, "reference_hint": None,
            },
        }

    def _stub_openai(self, denidin_app, monkeypatch):
        calls = {"n": 0}

        def fake_create(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return SimpleNamespace(
                    id="resp_069_main_1", output=[], output_text=OPERATOR_REPLY,
                    model="gpt-5.6-luna",
                    usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
                )
            return SimpleNamespace(
                id="resp_069_recognition_1",
                output=[SimpleNamespace(
                    type="function_call", name=RECOGNITION_TOOL_NAME,
                    arguments=json.dumps(self._complete_agreement_verdict(), ensure_ascii=False),
                    call_id="call_069_recognition_1",
                )],
                output_text="", model="gpt-5.6-luna",
                usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
            )

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', fake_create)
        return calls

    # ------------------------------------------------------------------ #

    def test_followup_api_is_gone(self):
        assert not hasattr(AIHandler, "_call_openai_ledger_followup_api")

    def test_exact_match_agreement_captured_post_turn_and_back_linked(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        self._stub_openai(denidin_app, monkeypatch)

        notification = self._create_notification(
            "חתמנו הסכם שכר טרחה עם דנה כהן, ריטיינר 4000 בחודש", TRIGGER_MSG_ID)

        from denidin import handle_text_message
        handle_text_message(notification)

        # operator got their normal reply, unchanged
        assert notification._test_sent_messages == [OPERATOR_REPLY]

        # exactly one ledger event persisted
        manager = denidin_app.ai_handler.ledger_event_manager
        event_files = sorted(manager.storage_dir.glob("*.json"))
        assert len(event_files) == 1
        record = json.loads(event_files[0].read_text(encoding="utf-8"))
        assert record["source_type"] == "הסכם"
        assert record["client_name"] == "דנה כהן"
        event_id = record["event_id"]

        # back-link lands on the completing (assistant) message, not the trigger
        sm = denidin_app.ai_handler.session_manager
        session = sm.get_session(GODFATHER_CHAT_ID)
        messages_dir = Path(sm.storage_dir) / session.session_id / "messages"
        by_role = {}
        for mid in session.message_ids:
            data = json.loads((messages_dir / f"{mid}.json").read_text(encoding="utf-8"))
            by_role.setdefault(data["role"], []).append(data)
        assistant_msg = by_role["assistant"][-1]
        trigger_msg = json.loads(
            (messages_dir / f"{TRIGGER_MSG_ID}.json").read_text(encoding="utf-8"))
        assert assistant_msg["ledger_event_ids"] == [event_id]
        assert trigger_msg["ledger_event_ids"] == []

        # C6 lifecycle breadcrumbs
        crumbs = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[069]")]
        assert any(c.startswith("[069] ledger capture recognized:") for c in crumbs)
        assert any(c.startswith("[069] ledger event written:") and event_id in c for c in crumbs)
