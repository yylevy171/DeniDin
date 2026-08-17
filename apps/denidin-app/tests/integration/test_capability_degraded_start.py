"""
Integration test for Feature 055 (Multi-Tenancy), tasks.md Phase 6/T022a
(REQ-CAP-005/006): a tenant with no working invoicing provider still starts and
serves messaging - that capability's tools simply aren't attached for that turn.

Also the actual regression this wiring closes (found while writing this test, not
assumed): BEFORE `TenantAIHandlerFactory` set a tenant-scoped `mcp` override,
`AIHandler._build_morning_mcp_tools` read `morning_auth_token` straight from
`base_config.mcp` (the OLD, pre-multi-tenancy single-shared-token config shape) -
meaning EVERY tenant sharing one process would have received the SAME Morning
bearer token if the environment config still carried one, a real cross-tenant
credential leak, not merely a missing-degraded-start gap. `TestNoSharedTokenLeakage`
below is the test that would have caught it.

Uses `TenantAIHandlerFactory.build` directly (real, unmodified `AIHandler`/
`UserManager`/`CapabilityRegistry`) - the same real-internal-components convention
as `test_tenant_ai_handler_factory.py`/`test_multi_tenant_admin.py`. The Morning MCP
server's reachability check (`morning_mcp_locator.current_server_url()`) is stubbed
to always report a URL, isolating these tests to the ONE thing under test here
(auth-token selection), rather than also depending on a real/fake status file on
disk.
"""

from pathlib import Path

import pytest

from src.managers.tenant_ai_handler_factory import TenantAIHandlerFactory
from src.models.config import AppConfiguration
from src.models.tenant import Tenant

ADMIN_PHONE = "+972509999999"


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
        "tenant_id": "tenant-a",
        "account_name": "a",
        "bot_name": "DeniDin",
        "godfathers": [],
        "admins": [ADMIN_PHONE],
        "constitution_supplement_file": "config/tenants/a/constitution_supplement.md",
        "capability_selection": {"messaging_provider": "green_api"},
        "environment_data_root": str(tmp_path),
        "green_api": {"instance_id": "instance-a", "api_token": "token-a"},
        "openai": {"api_key": "sk-tenant-a"},
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


def _attached_morning_tool(tools):
    if not tools:
        return None
    for tool in tools:
        if tool.get("type") == "mcp":
            return tool
    return None


@pytest.mark.integration
class TestDegradedStartWithoutInvoicingProvider:
    """REQ-CAP-005: omitting the invoicing provider is a supported, non-fatal
    configuration - the tenant still starts and serves messaging normally."""

    def test_tenant_without_invoicing_provider_still_builds_a_working_ai_handler(self, tmp_path):
        tenant = _tenant(tmp_path, capability_selection={"messaging_provider": "green_api"})
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert handler is not None
        assert handler.session_manager is not None
        assert handler.user_manager is not None

    def test_admin_of_a_tenant_without_invoicing_provider_gets_no_morning_tool(self, tmp_path, monkeypatch):
        tenant = _tenant(tmp_path, capability_selection={"messaging_provider": "green_api"})
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        monkeypatch.setattr(
            handler.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        admin_user = handler.user_manager.get_user(ADMIN_PHONE)

        tools = handler._assemble_tools(admin_user, "req-degraded")  # pylint: disable=protected-access

        assert _attached_morning_tool(tools) is None
        # The always-on ledger-event tool is still attached - degraded start
        # means "no invoicing tool", never "no tools at all".
        assert tools is not None and len(tools) == 1

    def test_tenant_without_invoicing_provider_selected_at_all_also_degrades_gracefully(self, tmp_path, monkeypatch):
        """Same as above, but capability_selection never even mentions
        invoicing_provider (vs. selecting it with no working token) - both
        shapes of "not configured" degrade identically."""
        tenant = _tenant(
            tmp_path, capability_selection={"messaging_provider": "green_api"}, mcp_auth_token=None,
        )
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        monkeypatch.setattr(
            handler.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        admin_user = handler.user_manager.get_user(ADMIN_PHONE)

        tools = handler._assemble_tools(admin_user, "req-degraded-2")  # pylint: disable=protected-access
        assert _attached_morning_tool(tools) is None


@pytest.mark.integration
class TestNoSharedTokenLeakage:
    """The actual regression this feature's wiring closes: a tenant with no
    invoicing provider of its own must NEVER receive a base/shared/global
    morning_auth_token, even if one happens to be present in the environment-wide
    config.mcp (a leftover from the old single-tenant config shape, or another
    tenant's onboarding leaving a stray shared value)."""

    def test_shared_base_config_token_never_leaks_to_a_tenant_without_its_own(self, tmp_path, monkeypatch):
        base_config = _base_config(
            mcp={
                "morning_auth_token": "SHARED-LEAKY-TOKEN-should-never-be-used",
                "morning_server_label": "morning-invoices",
            }
        )
        tenant = _tenant(
            tmp_path, capability_selection={"messaging_provider": "green_api"}, mcp_auth_token=None,
        )
        handler = TenantAIHandlerFactory.build(tenant, base_config)
        monkeypatch.setattr(
            handler.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        admin_user = handler.user_manager.get_user(ADMIN_PHONE)

        tools = handler._assemble_tools(admin_user, "req-leak-check")  # pylint: disable=protected-access

        assert _attached_morning_tool(tools) is None, (
            "A tenant with no invoicing provider of its own must never inherit a "
            "shared/global morning_auth_token from base_config.mcp"
        )

    def test_tenant_with_its_own_invoicing_provider_gets_its_own_token_not_the_shared_one(self, tmp_path, monkeypatch):
        base_config = _base_config(mcp={"morning_auth_token": "SHARED-BASE-TOKEN"})
        tenant = _tenant(
            tmp_path,
            capability_selection={"messaging_provider": "green_api", "invoicing_provider": "morning"},
            mcp_auth_token="tenant-a-own-token",
        )
        handler = TenantAIHandlerFactory.build(tenant, base_config)
        monkeypatch.setattr(
            handler.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        admin_user = handler.user_manager.get_user(ADMIN_PHONE)

        tools = handler._assemble_tools(admin_user, "req-own-token")  # pylint: disable=protected-access
        morning_tool = _attached_morning_tool(tools)

        assert morning_tool is not None
        assert morning_tool["headers"]["Authorization"] == "Bearer tenant-a-own-token"

    def test_two_tenants_with_their_own_invoicing_providers_get_different_tokens(self, tmp_path, monkeypatch):
        base_config = _base_config()
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a",
            capability_selection={"messaging_provider": "green_api", "invoicing_provider": "morning"},
            mcp_auth_token="token-a",
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b",
            capability_selection={"messaging_provider": "green_api", "invoicing_provider": "morning"},
            mcp_auth_token="token-b",
        )
        handler_a = TenantAIHandlerFactory.build(tenant_a, base_config)
        handler_b = TenantAIHandlerFactory.build(tenant_b, base_config)
        monkeypatch.setattr(
            handler_a.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        monkeypatch.setattr(
            handler_b.morning_mcp_locator, "current_server_url", lambda: "https://fake.ngrok.example"
        )
        admin_a = handler_a.user_manager.get_user(ADMIN_PHONE)
        admin_b = handler_b.user_manager.get_user(ADMIN_PHONE)

        tool_a = _attached_morning_tool(handler_a._assemble_tools(admin_a, "req-a"))  # pylint: disable=protected-access
        tool_b = _attached_morning_tool(handler_b._assemble_tools(admin_b, "req-b"))  # pylint: disable=protected-access

        assert tool_a["headers"]["Authorization"] == "Bearer token-a"
        assert tool_b["headers"]["Authorization"] == "Bearer token-b"
