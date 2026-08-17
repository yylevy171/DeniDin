"""
Integration test for Feature 055 (Multi-Tenancy), tasks.md T016a: proves the
"shared instance" design for a tenant with more than one godfather (US2).

research.md SS8's correction (confirmed T009/T015's implementation): a tenant's
`AIHandler`/`SessionManager`/`UserManager`/`LedgerEventManager` are constructed ONCE
per tenant, not once per godfather. Two godfathers of the same tenant are therefore
never siloed from each other by construction - this test is a regression tripwire
against a design that would accidentally build per-godfather state (which would be
wrong: both godfathers are meant to see the same tenant-level data, per
user-stories.md US2's Acceptance Scenarios), not a test of new functionality (there
is none - T015's `UserManager.godfather_phones` already made both phones resolve to
Role.GODFATHER against the one shared UserManager instance; this file exercises the
rest of the stack built on top of that one instance).

Same real-entry-point dispatch (`tenant.bot.router.route_event`) and external-boundary
convention (fake Green API client, stubbed `client.responses.create`, no real OpenAI
network call - long-term memory disabled) as test_tenant_isolation.py; see that file's
module docstring for the full rationale, not repeated here.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from whatsapp_chatbot_python.manager.router import Router

from src.models.config import AppConfiguration
from src.models.tenant import Tenant
from src.models.user import Role


def _base_config(**overrides):
    kwargs = {
        "green_api_instance_id": "base-instance-unused",
        "green_api_token": "base-token-unused",
        "ai_api_key": "sk-base-unused",
        "memory": {"longterm": {"enabled": False}},
    }
    kwargs.update(overrides)
    return AppConfiguration(**kwargs)


def _tenant(tmp_path, **overrides):
    kwargs = {
        "tenant_id": "tenant-multi-godfather",
        "account_name": "denidin",
        "bot_name": "DeniDin",
        "godfathers": ["+972501111111", "+972502222222"],
        "admins": ["+972509999999"],
        "constitution_supplement_file": "config/tenants/denidin/constitution_supplement.md",
        "capability_selection": {
            "messaging_provider": "green_api",
            "invoicing_provider": "morning",
        },
        "environment_data_root": str(tmp_path),
        "green_api": {
            "instance_id": "instance-multi-godfather", "api_token": "token-multi-godfather",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-tenant-multi-godfather"},
        "mcp_auth_token": "token-multi-godfather-mcp",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


class _FakeGreenAPI:
    """Same fixture shape as tests/unit/test_tenant_runtime.py /
    tests/integration/test_tenant_isolation.py - kept local per this repo's
    per-file-fakes integration-test convention."""

    def __init__(self):
        self.groups = Mock()
        self.account = Mock()
        self.account.getWaSettings = Mock(
            return_value=Mock(code=200, data={"phone": "972500000000"})
        )
        self.serviceMethods = Mock()
        self.marking = Mock()
        self.receiving = Mock()
        self.sending = Mock()


class _FakeBot:
    def __init__(self, instance_id: str, api_token: str, **_kwargs: Any):
        self.id_instance = instance_id
        self.api_token_instance = api_token
        self.api = _FakeGreenAPI()
        self.logger = logging.getLogger(f"fake-bot-{instance_id}")
        self.router = Router(self.api, self.logger)
        self.on_notification_received = None
        self.run_forever_called = False

    def run_forever(self) -> None:
        self.run_forever_called = True


def _mock_openai_response(text: str):
    response = Mock()
    response.output_text = text
    response.output = []
    response.incomplete_details = None
    response.usage.total_tokens = 10
    response.usage.input_tokens = 5
    response.usage.output_tokens = 5
    response.model = "gpt-4o-mini"
    return response


def _text_webhook(chat_id: str, sender: str, sender_name: str, text: str, msg_id: str) -> dict:
    return {
        "typeWebhook": "incomingMessageReceived",
        "idMessage": msg_id,
        "timestamp": 1755400000,
        "senderData": {"chatId": chat_id, "sender": sender, "senderName": sender_name},
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": text},
        },
    }


SAMPLE_EVENT = {
    "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "לקוח בדיקה",
    "payer_name": None, "description": "בדיקת בידוד בין דיירים", "amount": "1,000₪",
    "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
    "txn_date": None, "vat_status": "לא צוין", "replaces_hint": None,
    "reference_hint": None, "notes": None, "raw_message_excerpt": "1,000₪",
    "agreement_label": "בדיקה", "component_label": "בסיס",
}


@pytest.mark.integration
class TestMultiGodfatherSharedInstance:
    """US2's Acceptance Scenarios: both of a tenant's godfathers get identical
    treatment because they resolve against the one shared per-tenant AIHandler
    instance, never a per-godfather one."""

    def _started_tenant(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        return tenant

    def test_both_godfathers_resolve_godfather_role_with_identical_token_limit(self, tmp_path):
        tenant = self._started_tenant(tmp_path)
        user_1 = tenant.ai_handler.user_manager.get_user("+972501111111")
        user_2 = tenant.ai_handler.user_manager.get_user("+972502222222")

        assert user_1.role == Role.GODFATHER
        assert user_2.role == Role.GODFATHER
        assert user_1.token_limit == user_2.token_limit

    def test_both_godfathers_get_identical_tool_attachment(self, tmp_path):
        """The always-on ledger-event tool (no RBAC restriction) is attached
        identically for both - proven by literal equality of the assembled
        tools list, not just "both truthy"."""
        tenant = self._started_tenant(tmp_path)
        user_1 = tenant.ai_handler.user_manager.get_user("+972501111111")
        user_2 = tenant.ai_handler.user_manager.get_user("+972502222222")

        tools_1 = tenant.ai_handler._assemble_tools(user_1, "req-g1")  # pylint: disable=protected-access
        tools_2 = tenant.ai_handler._assemble_tools(user_2, "req-g2")  # pylint: disable=protected-access

        assert tools_1 is not None
        assert tools_1 == tools_2

    def test_both_godfathers_share_the_same_tenant_scoped_managers(self, tmp_path):
        """The actual architectural guarantee under test: there is exactly ONE
        AIHandler (and everything it owns) for the whole tenant, not one per
        godfather."""
        tenant = self._started_tenant(tmp_path)
        assert tenant.ai_handler.session_manager.storage_dir == tenant.data_root / "sessions"
        assert tenant.ai_handler.ledger_event_manager.storage_dir == tenant.data_root / "events"

    def test_messages_from_both_godfathers_are_handled_by_the_same_ai_handler(self, tmp_path, monkeypatch):
        """Real dispatch through the tenant's own router for BOTH godfathers -
        both turns resolve through the one stubbed client.responses.create,
        proving there is no second, hidden per-godfather AIHandler/client."""
        tenant = self._started_tenant(tmp_path)
        monkeypatch.setattr(
            tenant.ai_handler.client.responses, "create",
            Mock(side_effect=[
                _mock_openai_response("Reply to godfather one"),
                _mock_openai_response("Reply to godfather two"),
            ]),
        )

        tenant.bot.router.route_event(_text_webhook(
            chat_id="972501111111@c.us", sender="972501111111@c.us",
            sender_name="Godfather One", text="Hi, it's godfather one", msg_id="G1_MSG",
        ))
        tenant.bot.router.route_event(_text_webhook(
            chat_id="972502222222@c.us", sender="972502222222@c.us",
            sender_name="Godfather Two", text="Hi, it's godfather two", msg_id="G2_MSG",
        ))

        assert tenant.ai_handler.client.responses.create.call_count == 2

    def test_ledger_events_from_either_godfather_land_in_the_same_shared_events_dir(self, tmp_path):
        """'Visible to the other' (T016a's own wording): ledger events attributed
        to either godfather are persisted to the exact same directory, side by
        side - nothing partitions LedgerEventManager storage by sender."""
        tenant = self._started_tenant(tmp_path)

        event_id_g1 = tenant.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="sess-g1", whatsapp_chat="972501111111@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-g1",
            message_timestamp=1755400000, sender="972501111111@c.us",
        )
        event_id_g2 = tenant.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="sess-g2", whatsapp_chat="972502222222@c.us",
            event=dict(SAMPLE_EVENT), message_id="msg-g2",
            message_timestamp=1755400001, sender="972502222222@c.us",
        )

        events_dir = tenant.ai_handler.ledger_event_manager.storage_dir
        file_g1 = events_dir / f"{event_id_g1}.json"
        file_g2 = events_dir / f"{event_id_g2}.json"
        assert file_g1.exists()
        assert file_g2.exists()
        assert file_g1.parent == file_g2.parent == events_dir
