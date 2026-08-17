"""
Integration test for Feature 055 (Multi-Tenancy), tasks.md T014a: SC-002's actual
acceptance test under this feature's current scope.

"Now (synthetic second tenant)" per tasks.md/spec.md Clarifications (2026-08-17 scope
note): no real second Green API/Morning/OpenAI account exists for this feature yet, so
isolation is proven with a SYNTHETIC second tenant (fabricated green_api credentials, a
second OpenAI api_key string) rather than live infrastructure - T014b (real two-tenant
verification) is a separate, deferred, manual-approval-gated task.

Dispatches a real Green API webhook JSON through each tenant's OWN bot.router.route_event
(the actual production entry point - Router -> Observer -> Handler -> the tenant's bound
handler method, exactly as denidin.py's real bot would), per this repo's "real entry
point, not a direct method call" integration-test convention (CONSTITUTION SS V). Only the
two genuine external network boundaries are stood in for - Green API's own HTTP client
(_FakeGreenAPI, the same real-Router/fake-API-client pattern established in
tests/unit/test_tenant_runtime.py) and OpenAI's Responses API (`client.responses.create`,
stubbed per this repo's existing `_mock_response`-shaped fixture convention, see e.g.
tests/unit/test_ai_handler_no_reply.py) - so this test makes NO real network calls and
incurs no OpenAI cost, honoring this session's explicit constraint that billed/expensive
tests stay untouched and nothing new here should require that tier. Long-term (ChromaDB)
memory is disabled per tenant (`memory.longterm.enabled=False`) for the same reason -
Tier-1 SessionManager storage (what's actually being proven isolated here) does not
depend on it. Every other internal component - SessionManager, UserManager (RBAC),
LedgerEventManager, WhatsAppHandler, GroupMembershipResolver wiring - is the real,
unmodified class, per REQ-PARITY-001.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from whatsapp_chatbot_python.manager.router import Router

from src.models.config import AppConfiguration
from src.models.tenant import Tenant


def _base_config(**overrides):
    """Environment-wide config both tenants' AppConfiguration views are built from.
    Long-term memory disabled so no embedding call is ever attempted (see module
    docstring) - only Tier-1 SessionManager storage is exercised."""
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
        "tenant_id": "tenant-a",
        "account_name": "denidin",
        "bot_name": "DeniDin",
        "godfathers": ["+972501111111"],
        "admins": ["+972509999999"],
        "constitution_supplement_file": "config/tenants/denidin/constitution_supplement.md",
        "capability_selection": {
            "messaging_provider": "green_api",
            "invoicing_provider": "morning",
        },
        "environment_data_root": str(tmp_path),
        "green_api": {
            "instance_id": "instance-a",
            "api_token": "token-a",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-tenant-a-key"},
        "mcp_auth_token": "token-a-mcp",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


class _FakeGreenAPI:
    """Stand-in for whatsapp_chatbot_python's GreenAPI client - no real HTTP calls.
    Same shape as tests/unit/test_tenant_runtime.py's fixture (kept local to this file
    per this repo's existing per-file-fakes integration-test convention, see e.g.
    tests/integration/test_group_conversation_routing.py)."""

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
    """Stand-in for DeniDinGreenAPIBot - a REAL Router (no I/O of its own) wired to a
    fake API, so real dispatch (route_event -> Observer -> Handler -> the tenant's bound
    method) works exactly as it does in production."""

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
    """Same minimal fixture shape as tests/unit/test_ai_handler_no_reply.py's
    _mock_response - the only fields AIHandler._finalize_response actually reads."""
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
    """A real incomingMessageReceived/textMessage Green API webhook payload shape."""
    return {
        "typeWebhook": "incomingMessageReceived",
        "idMessage": msg_id,
        "timestamp": 1755400000,
        "senderData": {
            "chatId": chat_id,
            "sender": sender,
            "senderName": sender_name,
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": text},
        },
    }


@pytest.mark.integration
class TestTenantMessageIsolation:
    """SC-002: a message sent to one tenant's WhatsApp number never appears in, or
    affects, any other tenant's session/memory/ledger/credential-selection."""

    def _two_started_tenants(self, tmp_path):
        tenant_a = _tenant(
            tmp_path,
            tenant_id="tenant-a",
            account_name="a",
            bot_name="DeniDin",
            green_api={
                "instance_id": "instance-a", "api_token": "token-a",
                "whatsapp_number": "+972501234567",
            },
            openai={"api_key": "sk-tenant-a"},
            mcp_auth_token="token-a-mcp",
        )
        tenant_b = _tenant(
            tmp_path,
            tenant_id="tenant-b",
            account_name="b",
            bot_name="Jabaloola",
            admins=["+972508888888"],
            godfathers=["+972502222222"],
            green_api={
                "instance_id": "instance-b", "api_token": "token-b",
                "whatsapp_number": "+972509876543",
            },
            openai={"api_key": "sk-tenant-b"},
            mcp_auth_token="token-b-mcp",
        )
        tenant_a.start(_base_config(), bot_factory=_FakeBot)
        tenant_b.start(_base_config(), bot_factory=_FakeBot)
        return tenant_a, tenant_b

    def test_message_to_tenant_a_is_dispatched_and_answered_via_tenant_a_bot_only(self, tmp_path, monkeypatch):
        """Real dispatch through tenant A's own router (route_event, the production
        entry point) never touches tenant B's bot at all."""
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        monkeypatch.setattr(
            tenant_a.ai_handler.client.responses, "create",
            Mock(return_value=_mock_openai_response("Hello from DeniDin")),
        )
        monkeypatch.setattr(
            tenant_b.ai_handler.client.responses, "create",
            Mock(return_value=_mock_openai_response("Should never be called")),
        )

        event = _text_webhook(
            chat_id="972501111111@c.us", sender="972501111111@c.us",
            sender_name="Client One", text="Hello tenant A", msg_id="A_MSG_001",
        )
        tenant_a.bot.router.route_event(event)

        tenant_a.ai_handler.client.responses.create.assert_called_once()
        tenant_b.ai_handler.client.responses.create.assert_not_called()

        tenant_a.bot.api.sending.sendMessage.assert_called_once()
        sent_chat_id = tenant_a.bot.api.sending.sendMessage.call_args[0][0]
        sent_text = tenant_a.bot.api.sending.sendMessage.call_args[0][1]
        assert sent_chat_id == "972501111111@c.us"
        assert sent_text == "Hello from DeniDin"
        tenant_b.bot.api.sending.sendMessage.assert_not_called()

    def test_session_data_lands_only_under_the_receiving_tenants_own_data_root(self, tmp_path, monkeypatch):
        """Tier-1 SessionManager storage (data-model.md's tenant-scoped data-root
        layout) is per-tenant by construction - a message to tenant A must create a
        session file under tenant_a.data_root/sessions and create NOTHING at all
        under tenant_b.data_root."""
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        monkeypatch.setattr(
            tenant_a.ai_handler.client.responses, "create",
            Mock(return_value=_mock_openai_response("Reply to A")),
        )

        event = _text_webhook(
            chat_id="972501111111@c.us", sender="972501111111@c.us",
            sender_name="Client One", text="Remember this", msg_id="A_MSG_002",
        )
        tenant_a.bot.router.route_event(event)

        tenant_a_sessions = tenant_a.ai_handler.session_manager.storage_dir
        tenant_b_sessions = tenant_b.ai_handler.session_manager.storage_dir
        assert tenant_a_sessions == Path(tmp_path) / "tenant-a" / "sessions"
        assert tenant_b_sessions == Path(tmp_path) / "tenant-b" / "sessions"
        assert any(tenant_a_sessions.iterdir()), "Expected tenant A's session dir to gain a session"
        # Both storage_dirs are created eagerly at SessionManager construction time
        # (Tenant.start(), for both tenants) - existence alone proves nothing about
        # isolation. What must hold is that tenant B's dir stays EMPTY: no session
        # was ever written into it as a side effect of tenant A's turn.
        assert tenant_b_sessions.exists()
        assert not any(tenant_b_sessions.iterdir()), (
            "Tenant B's session dir must stay empty - untouched by a message sent to tenant A"
        )

    def test_two_tenants_receiving_messages_independently_never_cross_contaminate(self, tmp_path, monkeypatch):
        """Both tenants active at once, each receiving its own message - the
        strongest form of SC-002's proof: simultaneous, fully independent turns."""
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        monkeypatch.setattr(
            tenant_a.ai_handler.client.responses, "create",
            Mock(return_value=_mock_openai_response("A's reply")),
        )
        monkeypatch.setattr(
            tenant_b.ai_handler.client.responses, "create",
            Mock(return_value=_mock_openai_response("B's reply")),
        )

        tenant_a.bot.router.route_event(_text_webhook(
            chat_id="972501111111@c.us", sender="972501111111@c.us",
            sender_name="Client One", text="Hi A", msg_id="A_MSG_003",
        ))
        tenant_b.bot.router.route_event(_text_webhook(
            chat_id="972502222222@c.us", sender="972502222222@c.us",
            sender_name="Client Two", text="Hi B", msg_id="B_MSG_003",
        ))

        tenant_a.ai_handler.client.responses.create.assert_called_once()
        tenant_b.ai_handler.client.responses.create.assert_called_once()

        a_sent = tenant_a.bot.api.sending.sendMessage.call_args[0]
        b_sent = tenant_b.bot.api.sending.sendMessage.call_args[0]
        assert a_sent[0] == "972501111111@c.us" and a_sent[1] == "A's reply"
        assert b_sent[0] == "972502222222@c.us" and b_sent[1] == "B's reply"

        assert any((Path(tmp_path) / "tenant-a" / "sessions").iterdir())
        assert any((Path(tmp_path) / "tenant-b" / "sessions").iterdir())


@pytest.mark.integration
class TestTenantLedgerEventIsolation:
    """SC-002 also names ledger events explicitly: each tenant's real
    LedgerEventManager (constructed by TenantAIHandlerFactory, REQ-PARITY-001 -
    unmodified class) writes under that tenant's own events/ directory only."""

    SAMPLE_EVENT = {
        "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "לקוח בדיקה",
        "payer_name": None, "description": "בדיקת בידוד בין דיירים", "amount": "1,000₪",
        "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
        "txn_date": None, "vat_status": "לא צוין", "replaces_hint": None,
        "reference_hint": None, "notes": None, "raw_message_excerpt": "1,000₪",
        "agreement_label": "בדיקה", "component_label": "בסיס",
    }

    def test_ledger_events_written_per_tenant_stay_under_that_tenants_own_events_dir(self, tmp_path):
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a",
            green_api={"instance_id": "instance-a", "api_token": "token-a"},
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b",
            green_api={"instance_id": "instance-b", "api_token": "token-b"},
        )
        tenant_a.start(_base_config(), bot_factory=_FakeBot)
        tenant_b.start(_base_config(), bot_factory=_FakeBot)

        event_id_a = tenant_a.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="sess-a", whatsapp_chat="972501111111@c.us",
            event=dict(self.SAMPLE_EVENT), message_id="msg-a",
            message_timestamp=1755400000, sender="972501111111@c.us",
        )

        assert event_id_a is not None
        assert (Path(tmp_path) / "tenant-a" / "events" / f"{event_id_a}.json").exists()
        # LedgerEventManager creates storage_dir eagerly at construction time (both
        # tenants, via Tenant.start()) - existence alone proves nothing; the isolation
        # guarantee under test is that tenant B's events dir stays EMPTY.
        tenant_b_events = Path(tmp_path) / "tenant-b" / "events"
        assert tenant_b_events.exists()
        assert not any(tenant_b_events.iterdir()), (
            "Tenant B's events dir must stay empty - untouched by tenant A's ledger event"
        )
