"""
Unit tests for Tenant runtime (Feature 055: Multi-Tenancy).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers the
"each tenant is a fully self-contained messaging endpoint" design confirmed with the
user 2026-08-17: Tenant.start() constructs its own Bot + AIHandler + WhatsAppHandler +
MediaHandler + GroupMembershipResolver, registers its own 9 message-type handlers as
BOUND METHODS on its own bot.router (never a module global, never a parameter-threaded
tenant_id), and runs its own listener thread. Outbound routing is automatically correct
by construction (Green API's Notification.answer() is tied to whichever bot received
it) - no separate gateway/dispatch layer.

Explicit focus per user request: "make sure to have tests with multiple tenants and
make sure the code uses the correct instances" - TestTenantMultiTenantIsolation is the
core of that; the rest verifies start()'s wiring and each handler's dispatch shape.

See specs/in-progress/055-multiple-clients-godfathers/contracts/
tenant-scoped-data-managers.md and messaging-gateway.md (superseded, historical) for
the design this implements.

Note: deep business-logic coverage of AIHandler's own behavior (typing indicators,
retry, RBAC internals, etc.) is NOT re-tested here - that's already covered by
AIHandler's own extensive existing test suite (untouched, per REQ-PARITY-001). These
tests mock ai_handler/whatsapp_handler at the boundary to isolate and verify DISPATCH
correctness (the right method gets called, on the right instance), not re-verify their
internals.
"""

import logging
import threading
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from whatsapp_chatbot_python.manager.router import Router

from src.models.tenant import Tenant
from src.models.config import AppConfiguration


def _base_config(**overrides):
    kwargs = {
        "green_api_instance_id": "base-instance-unused",
        "green_api_token": "base-token-unused",
        "ai_api_key": "sk-base-unused",
    }
    kwargs.update(overrides)
    return AppConfiguration(**kwargs)


def _tenant(tmp_path, **overrides):
    kwargs = {
        "tenant_id": "b6f1c2a4-0000-0000-0000-000000000001",
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
            "instance_id": "1101000001",
            "api_token": "d0d5deadbeef",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-tenant-key"},
        "mcp_auth_token": "denidin-tenant-bearer-token-dev",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


class _FakeGreenAPI:
    """Stand-in for whatsapp_chatbot_python's GreenAPI client - no real HTTP calls."""

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
    fake API, so handler registration works exactly like production, but run_forever()
    is a harmless no-op instead of a real blocking network loop."""

    def __init__(self, instance_id: str, api_token: str, **_kwargs: Any):
        self.id_instance = instance_id
        self.api_token_instance = api_token
        self.api = _FakeGreenAPI()
        self.logger = logging.getLogger(f"fake-bot-{instance_id}")
        self.router = Router(self.api, self.logger)
        self.on_notification_received = None
        self.run_forever_called = False

    def run_forever(self) -> None:
        self.run_forever_called = True  # returns immediately - no real loop


def _registered_type_messages(tenant):
    """All type_message filters registered on this tenant's own bot.router.message."""
    return [h.filters.get("type_message") for h in tenant.bot.router.message.handlers]


def _handler_for(tenant, type_message):
    """The registered bound method for a given type_message filter."""
    for h in tenant.bot.router.message.handlers:
        if h.filters.get("type_message") == type_message:
            return h.handler
    return None


class TestTenantStartWiring:
    """Test that start() builds a complete, correctly-scoped runtime."""

    def test_start_builds_ai_handler(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.ai_handler is not None

    def test_start_builds_whatsapp_handler(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.whatsapp_handler is not None

    def test_start_wires_media_handler_onto_whatsapp_handler(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.whatsapp_handler.media_handler is not None
        assert tenant.whatsapp_handler.media_handler.denidin is tenant

    def test_start_builds_group_membership_resolver_with_own_bot_groups_client(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.group_membership_resolver is not None

    def test_start_constructs_bot_with_tenant_own_credentials(self, tmp_path):
        tenant = _tenant(
            tmp_path,
            green_api={
                "instance_id": "unique-instance-id",
                "api_token": "unique-token",
                "whatsapp_number": "+972501234567",
            },
        )
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.bot.id_instance == "unique-instance-id"
        assert tenant.bot.api_token_instance == "unique-token"

    def test_start_registers_all_nine_message_types(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        registered = _registered_type_messages(tenant)

        assert ["textMessage", "extendedTextMessage"] in registered
        assert "contactMessage" in registered
        assert "contactsArrayMessage" in registered
        assert "imageMessage" in registered
        assert "documentMessage" in registered
        assert "videoMessage" in registered
        assert "audioMessage" in registered
        assert "interactiveButtonsResponse" in registered
        # Catch-all default has no type_message filter at all
        assert None in registered

    def test_start_launches_a_listener_thread(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert isinstance(tenant._listener_thread, threading.Thread)
        tenant._listener_thread.join(timeout=2)
        assert tenant.bot.run_forever_called is True

    def test_start_sets_own_whatsapp_number_from_own_bot(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.ai_handler.own_whatsapp_number == "972500000000"

    def test_start_own_whatsapp_number_fails_open_on_error(self, tmp_path):
        class _FailingGetWaSettingsBot(_FakeBot):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.api.account.getWaSettings = Mock(side_effect=RuntimeError("boom"))

        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FailingGetWaSettingsBot)
        assert tenant.ai_handler.own_whatsapp_number == ""

    def test_start_wires_read_receipt_hook(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        assert tenant.bot.on_notification_received is not None


class TestTenantMultiTenantIsolation:
    """The core ask: multiple tenants started together must never share state, and
    each handler must operate on its OWN tenant's instances only."""

    def _two_started_tenants(self, tmp_path):
        tenant_a = _tenant(
            tmp_path,
            tenant_id="tenant-a",
            account_name="a",
            bot_name="DeniDin",
            green_api={
                "instance_id": "instance-a",
                "api_token": "token-a",
                "whatsapp_number": "+972501111111",
            },
            openai={"api_key": "sk-tenant-a"},
            mcp_auth_token="token-a-mcp",
        )
        tenant_b = _tenant(
            tmp_path,
            tenant_id="tenant-b",
            account_name="b",
            bot_name="Jabaloola",
            green_api={
                "instance_id": "instance-b",
                "api_token": "token-b",
                "whatsapp_number": "+972502222222",
            },
            openai={"api_key": "sk-tenant-b"},
            mcp_auth_token="token-b-mcp",
        )
        tenant_a.start(_base_config(), bot_factory=_FakeBot)
        tenant_b.start(_base_config(), bot_factory=_FakeBot)
        return tenant_a, tenant_b

    def test_two_tenants_get_two_independent_bot_instances(self, tmp_path):
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        assert tenant_a.bot is not tenant_b.bot
        assert tenant_a.bot.id_instance == "instance-a"
        assert tenant_b.bot.id_instance == "instance-b"

    def test_two_tenants_get_two_independent_ai_handlers(self, tmp_path):
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        assert tenant_a.ai_handler is not tenant_b.ai_handler
        assert tenant_a.ai_handler.client.api_key == "sk-tenant-a"
        assert tenant_b.ai_handler.client.api_key == "sk-tenant-b"

    def test_two_tenants_get_two_independent_whatsapp_handlers(self, tmp_path):
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        assert tenant_a.whatsapp_handler is not tenant_b.whatsapp_handler

    def test_registered_handlers_are_bound_to_the_correct_tenant_instance(self, tmp_path):
        """The registered callback for tenant A's router is a bound method whose
        __self__ IS tenant A, never tenant B - this is the actual mechanism that
        guarantees correct-instance dispatch (no global, no parameter to get wrong)."""
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)

        handler_a = _handler_for(tenant_a, ["textMessage", "extendedTextMessage"])
        handler_b = _handler_for(tenant_b, ["textMessage", "extendedTextMessage"])

        assert handler_a.__self__ is tenant_a
        assert handler_b.__self__ is tenant_b
        assert handler_a.__self__ is not tenant_b
        assert handler_b.__self__ is not tenant_a

    def test_invoking_tenant_a_handler_never_touches_tenant_b_ai_handler(self, tmp_path):
        """Behavioral proof, not just identity: actually invoke tenant A's registered
        text handler and confirm tenant B's ai_handler.create_request was never called."""
        tenant_a, tenant_b = self._two_started_tenants(tmp_path)
        tenant_a.ai_handler = MagicMock()
        tenant_a.whatsapp_handler = MagicMock()
        tenant_a.whatsapp_handler.validate_message_type.return_value = True
        tenant_a.ai_handler.create_request.return_value = Mock(request_id="req-1")
        tenant_a.ai_handler.get_response.return_value = Mock(
            should_reply=True, tokens_used=10, response_text="ok"
        )
        tenant_a.ai_handler.user_manager.get_user.return_value = Mock(is_blocked=False)
        tenant_a.group_membership_resolver = None
        tenant_b.ai_handler = MagicMock()

        fake_message = Mock(
            message_id="m1",
            received_timestamp=Mock(isoformat=lambda: "2026-08-17T00:00:00"),
            sender_name="Test",
            sender_id="+972501111111",
            text_content="hi",
            is_group=False,
            sender_display_name="Test",
            chat_id="+972501111111@c.us",
        )
        tenant_a.whatsapp_handler.process_notification.return_value = fake_message
        notification = Mock()

        tenant_a._handle_text_message(notification)

        tenant_a.ai_handler.create_request.assert_called_once()
        tenant_b.ai_handler.create_request.assert_not_called()


class TestTenantHandlerDispatch:
    """Test that each of the 9 handlers delegates to the correct internal method."""

    def _started_tenant_with_mocked_deps(self, tmp_path):
        tenant = _tenant(tmp_path)
        tenant.start(_base_config(), bot_factory=_FakeBot)
        tenant.ai_handler = MagicMock()
        tenant.whatsapp_handler = MagicMock()
        return tenant

    def test_handle_contacts_array_message_declines_without_any_ai_call(self, tmp_path):
        """Per spec.md Clarifications: declines outright, no AIHandler/OpenAI call."""
        tenant = self._started_tenant_with_mocked_deps(tmp_path)
        notification = Mock()

        tenant._handle_contacts_array_message(notification)

        notification.answer.assert_called_once()
        tenant.ai_handler.create_request.assert_not_called()

    def test_handle_unsupported_message_default_delegates_to_whatsapp_handler(self, tmp_path):
        tenant = self._started_tenant_with_mocked_deps(tmp_path)
        notification = Mock()

        tenant._handle_unsupported_message_default(notification)

        tenant.whatsapp_handler.handle_unsupported_message.assert_called_once_with(notification)

    def test_handle_image_message_delegates_to_media_processing(self, tmp_path):
        tenant = self._started_tenant_with_mocked_deps(tmp_path)
        tenant.ai_handler.user_manager.get_user.return_value = Mock(is_blocked=False)
        notification = Mock()
        notification.event = {"senderData": {}}

        tenant._handle_image_message(notification)

        tenant.whatsapp_handler.handle_media_message.assert_called_once_with(notification)

    def test_handle_button_tap_delegates_to_resolve_button_tap(self, tmp_path):
        tenant = self._started_tenant_with_mocked_deps(tmp_path)
        tenant.ai_handler.resolve_button_tap.return_value = None
        notification = Mock()
        notification.event = {
            "messageData": {
                "interactiveButtonsResponse": {
                    "selectedId": "denidin_approve",
                    "stanzaId": "abc123",
                }
            }
        }

        tenant._handle_button_tap(notification)

        tenant.ai_handler.resolve_button_tap.assert_called_once()
