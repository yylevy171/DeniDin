"""
Component-Integration Test: an approval that leads straight into a second approval
(Feature 098 - "save the client's ID, then issue the document").

Above the allocation threshold, a client with no ID gets two separate approvals:
first `update_client` (save the ID), then the document itself. The second one is
born inside the RESOLUTION of the first: the approved `update_client` runs, and in
that same OpenAI response the model proposes `create_combo_document`, which comes
back as a fresh `mcp_approval_request`.

This drives that chain through the real router (`handle_text_message` /
`handle_button_tap`), real `AIHandler`, real `PendingApprovalManager` and real
`WhatsAppHandler` send path (CONSTITUTION §V). The only stand-in is OpenAI's
`responses.create` - both the normal client and the `with_options(max_retries=0)`
client `_call_openai_approval_api` resolves approvals with - scripted per call via
`_ledger_069_harness.ScriptedOpenAI`. Whether the real model actually asks for the
ID and chains the approvals is `tests/billed/test_allocation_tax_id_billed.py`.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.managers.pending_approval_manager import BUTTON_ID_APPROVE
from src.models.config import AppConfiguration

from tests.e2e_helpers import wipe_chat_messages_on_disk
from tests.integration import _ledger_069_harness as h
from tests.integration._ledger_069_harness import (
    ScriptedOpenAI, GODFATHER_CHAT_ID, GODFATHER_SENDER,
)

CLIENT_NAME = "דנה כהן"
TAX_ID = "308253681"
SERVER_LABEL = "morning-invoices"

UPDATE_CLIENT_ARGS = {"name": CLIENT_NAME, "tax_id": TAX_ID, "name_resolved": True}
COMBO_ARGS = {
    "client_name": CLIENT_NAME, "amount": 12000, "description": "ייעוץ משפטי",
    "vat_included": True, "payment_date": "2026-10-06", "payment_type": 4,
    "name_resolved": True,
}


def _approval_request(name: str, arguments: dict, request_id: str):
    return SimpleNamespace(
        type="mcp_approval_request", id=request_id, name=name,
        arguments=json.dumps(arguments, ensure_ascii=False), server_label=SERVER_LABEL,
    )


def _mcp_call(name: str, arguments: dict, output: dict):
    return SimpleNamespace(
        type="mcp_call", name=name, error=None,
        arguments=json.dumps(arguments, ensure_ascii=False),
        output=json.dumps(output, ensure_ascii=False),
    )


def _response(resp_id: str, text: str, output: list):
    return SimpleNamespace(id=resp_id, output=output, output_text=text,
                           model="gpt-5.6-luna", usage=h._usage())


def _ask_for_id():
    """Turn 1: the client has no ID - DeniDin asks for it in plain text."""
    return _response("resp_ask_id", f"ל{CLIENT_NAME} אין ת.ז / ח.פ במערכת. מה המספר (9 ספרות)?", [
        _mcp_call("get_client_details", {"name": CLIENT_NAME, "name_resolved": True},
                  {"name": CLIENT_NAME, "tax_id": None}),
    ])


def _propose_update_client():
    """Turn 2: the ID arrives - `update_client` comes back as an approval request."""
    return _response("resp_update_proposed", "אעדכן את ת.ז של הלקוח.", [
        _approval_request("update_client", UPDATE_CLIENT_ARGS, "apr_update"),
    ])


def _update_done_and_propose_document():
    """Resolution of the first approval: `update_client` RAN, and the same response
    proposes the document - a second, separate approval request."""
    return _response("resp_update_done", "עדכנתי את ת.ז. עכשיו - החשבונית:", [
        _mcp_call("update_client", UPDATE_CLIENT_ARGS, {
            "status": "updated",
            "client": {"name": CLIENT_NAME, "email": None, "phone": None, "tax_id": TAX_ID},
        }),
        _approval_request("create_combo_document", COMBO_ARGS, "apr_combo"),
    ])


def _document_done():
    """Resolution of the second approval: the document is created."""
    return _response("resp_combo_done", "הופקה חשבונית מס/קבלה מספר 70001.", [
        _mcp_call("create_combo_document", COMBO_ARGS, {
            "display_number": "70001", "internal_morning_id": "mid-70001", "type": 320,
            "type_name": "חשבונית מס/קבלה", "client_name": CLIENT_NAME, "amount": 12000,
        }),
    ])


@pytest.mark.integration
class TestAllocationTaxIdApprovalChain:

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
                # Legacy (flag-off) path: 098's constitution rule and its pending-approval chain.
                'feature_flags': {**(config.feature_flags or {}), 'enable_capability_backbone': False},
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
            wipe_chat_messages_on_disk(denidin_app.ai_manager.session_manager.storage_dir, GODFATHER_CHAT_ID)
            denidin_app.ai_manager.pending_approval_manager.clear(GODFATHER_CHAT_ID)
            denidin_app.ai_manager.pending_local_tool_approval_manager.clear(GODFATHER_CHAT_ID)
        _wipe()
        yield
        _wipe()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _install(denidin_app, monkeypatch, script: ScriptedOpenAI) -> ScriptedOpenAI:
        """Stand in for OpenAI on both paths: the normal client, and the
        no-retry client approvals are resolved through."""
        client = denidin_app.ai_manager.client
        monkeypatch.setattr(client.responses, 'create', script)
        no_retry_client = SimpleNamespace(responses=SimpleNamespace(create=script))
        monkeypatch.setattr(client, 'with_options', lambda **_kwargs: no_retry_client)
        return script

    @staticmethod
    def _notification(message_data: dict, msg_id: str):
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
            'messageData': message_data,
        }
        notification._test_sent_messages = []
        notification._test_button_sends = []

        def track_answer_with_interactive_buttons(body, buttons, header=None, footer=None):
            id_message = f"TEST_BUTTONS_{msg_id}"
            notification._test_button_sends.append({'body': body, 'idMessage': id_message})
            notification._test_sent_messages.append(body)
            return SimpleNamespace(code=200, data={'idMessage': id_message}, error=None)

        notification.answer = notification._test_sent_messages.append
        notification.answer_with_interactive_buttons = track_answer_with_interactive_buttons
        return notification

    def _send_text(self, text: str, msg_id: str):
        from denidin import handle_text_message

        notification = self._notification(
            {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}}, msg_id)
        handle_text_message(notification)
        return notification

    def _tap_approve(self, denidin_app, msg_id: str):
        from denidin import handle_button_tap

        pending = denidin_app.ai_manager.pending_approval_manager.get(GODFATHER_CHAT_ID)
        notification = self._notification({
            'typeMessage': 'interactiveButtonsResponse',
            'interactiveButtonsResponse': {
                'stanzaId': pending.sent_message_id, 'selectedIndex': 0,
                'selectedId': BUTTON_ID_APPROVE, 'selectedDisplayText': 'כן',
            },
        }, msg_id)
        handle_button_tap(notification)
        return notification

    def _pending(self, denidin_app):
        return denidin_app.ai_manager.pending_approval_manager.get(GODFATHER_CHAT_ID)

    @staticmethod
    def _approval_calls(script: ScriptedOpenAI):
        return [c for c in script.main_calls
                if any(isinstance(i, dict) and i.get("type") == "mcp_approval_response"
                       for i in (c.get("input") or []))]

    def _reach_update_client_approval(self, denidin_app, monkeypatch) -> ScriptedOpenAI:
        """Turns 1-2: ask for the ID, then the ID arrives -> update_client pending."""
        script = ScriptedOpenAI()
        script.queue_turn(_ask_for_id())
        script.queue_turn(_propose_update_client())
        script.queue_turn(_update_done_and_propose_document())
        self._install(denidin_app, monkeypatch, script)

        first = self._send_text(f"תפיק חשבונית מס קבלה ל{CLIENT_NAME} על 12,000 ₪ כולל מע\"מ", "u1")
        assert first._test_button_sends == [], "asking for the ID is a plain question, not an approval"
        assert self._pending(denidin_app) is None

        second = self._send_text(TAX_ID, "u2")
        pending = self._pending(denidin_app)
        assert pending is not None and pending.tool_name == "update_client"
        assert json.loads(pending.arguments)["tax_id"] == TAX_ID
        assert len(second._test_button_sends) == 1, "the ID save must be offered as approval buttons"
        assert pending.sent_message_id == second._test_button_sends[0]['idMessage']
        return script

    def _assert_document_approval_is_pending(self, denidin_app, script, reply_notification):
        """After the ID save is approved: update_client was resolved, and a NEW,
        separate approval for the document is pending and offered as buttons."""
        approval_calls = self._approval_calls(script)
        assert len(approval_calls) == 1
        assert approval_calls[0]["previous_response_id"] == "resp_update_proposed"
        assert approval_calls[0]["input"] == [{
            "type": "mcp_approval_response", "approval_request_id": "apr_update", "approve": True,
        }]

        pending = self._pending(denidin_app)
        assert pending is not None, "the document's own approval must be pending"
        assert pending.tool_name == "create_combo_document"
        assert pending.approval_request_id == "apr_combo"
        assert pending.response_id == "resp_update_done"

        assert len(reply_notification._test_button_sends) == 1, (
            "the document approval must be offered as buttons; got plain text: "
            f"{reply_notification._test_sent_messages!r}"
        )
        assert pending.sent_message_id == reply_notification._test_button_sends[0]['idMessage']

    # ------------------------------------------------------------------ #
    # tests
    # ------------------------------------------------------------------ #

    def test_typed_yes_on_id_save_chains_into_a_pending_document_approval(self, denidin_app, monkeypatch):
        script = self._reach_update_client_approval(denidin_app, monkeypatch)

        third = self._send_text("כן", "u3")
        self._assert_document_approval_is_pending(denidin_app, script, third)

        # Second approval, typed: the document is created and nothing stays pending.
        script.queue_turn(_document_done())
        fourth = self._send_text("כן", "u4")
        approval_calls = self._approval_calls(script)
        assert len(approval_calls) == 2
        assert approval_calls[1]["previous_response_id"] == "resp_update_done"
        assert approval_calls[1]["input"][0]["approval_request_id"] == "apr_combo"
        assert self._pending(denidin_app) is None
        assert fourth._test_button_sends == []
        assert any("70001" in m for m in fourth._test_sent_messages)

    def test_button_tap_on_id_save_chains_into_a_pending_document_approval(self, denidin_app, monkeypatch):
        script = self._reach_update_client_approval(denidin_app, monkeypatch)

        third = self._tap_approve(denidin_app, "u3")
        self._assert_document_approval_is_pending(denidin_app, script, third)

        # Second approval, tapped on the NEW message's buttons.
        script.queue_turn(_document_done())
        fourth = self._tap_approve(denidin_app, "u4")
        approval_calls = self._approval_calls(script)
        assert len(approval_calls) == 2
        assert approval_calls[1]["input"][0]["approval_request_id"] == "apr_combo"
        assert self._pending(denidin_app) is None
        assert any("70001" in m for m in fourth._test_sent_messages)

    def test_declining_the_document_after_saving_the_id_creates_nothing(self, denidin_app, monkeypatch):
        """Edge case "ID saved, document declined": the ID save stands, the
        document's own approval is declined, nothing stays pending."""
        script = self._reach_update_client_approval(denidin_app, monkeypatch)
        third = self._send_text("כן", "u3")
        self._assert_document_approval_is_pending(denidin_app, script, third)

        # The decline is reported to OpenAI, then "לא" is processed as a fresh turn.
        script.queue_turn(_response("resp_combo_declined", "", []))
        script.queue_turn(h.reply("בסדר, לא הפקתי את החשבונית. ת.ז של הלקוח נשמרה."))
        self._send_text("לא", "u4")

        approval_calls = self._approval_calls(script)
        assert len(approval_calls) == 2
        assert approval_calls[1]["input"] == [{
            "type": "mcp_approval_response", "approval_request_id": "apr_combo", "approve": False,
        }]
        assert self._pending(denidin_app) is None
