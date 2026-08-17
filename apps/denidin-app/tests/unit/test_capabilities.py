"""
Unit tests for the capability interface + registry (Feature 055: Multi-Tenancy),
tasks.md Phase 6/T021a (REQ-CAP-001/002/003/004/005).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI).

`CapabilityRegistry.resolve(tenant, capability_name)` takes the tenant OBJECT (not
a bare `tenant_id` string) - matching every other Phase 3+ factory in this codebase
(`TenantAIHandlerFactory.build(tenant, base_config)`, `GroupMembershipResolver`,
etc.), all of which operate on the already-resolved `Tenant` rather than doing a
second `tenant_id -> Tenant` lookup of their own. tasks.md's "(tenant_id,
'invoicing_provider')" phrasing is descriptive shorthand for "the tenant this call
concerns", not a literal signature requirement.

research.md §5: resolution is PER-CALL (a plain registry dict lookup keyed by the
implementation name in `tenant.capability_selection`), never a startup-only cached/
memoized binding - `CapabilityRegistry` carries no per-tenant state at all, so a
config change between calls (not expected mid-process today, but not precluded by
this design either) would be picked up on the very next resolve().
"""

import pytest

from src.capabilities.registry import CapabilityRegistry
from src.capabilities.messaging_provider import MessagingProvider
from src.capabilities.invoicing_provider import InvoicingProvider
from src.capabilities.impl.green_api_messaging import GreenAPIMessagingProvider
from src.capabilities.impl.morning_invoicing import MorningInvoicingProvider
from src.models.tenant import Tenant


def _tenant(tmp_path, **overrides):
    kwargs = {
        "tenant_id": "tenant-a",
        "account_name": "a",
        "bot_name": "DeniDin",
        "godfathers": ["+972501111111"],
        "admins": [],
        "constitution_supplement_file": "config/tenants/a/constitution_supplement.md",
        "capability_selection": {
            "messaging_provider": "green_api",
            "invoicing_provider": "morning",
        },
        "environment_data_root": str(tmp_path),
        "green_api": {"instance_id": "instance-a", "api_token": "token-a"},
        "openai": {"api_key": "sk-tenant-a"},
        "mcp_auth_token": "token-a-mcp",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


class TestCapabilityInterfacesExist:
    """REQ-CAP-001/002: messaging/invoicing are defined capability interfaces, with
    Green API/Morning as their existing implementations."""

    def test_green_api_messaging_provider_implements_the_messaging_interface(self):
        assert isinstance(GreenAPIMessagingProvider(), MessagingProvider)

    def test_morning_invoicing_provider_implements_the_invoicing_interface(self):
        assert isinstance(MorningInvoicingProvider(), InvoicingProvider)


class TestCapabilityRegistryResolvesConfiguredImplementation:
    """REQ-CAP-001/002: resolving a tenant's configured capability returns that
    tenant's own selected implementation, via configuration/DI - not a hardcoded
    choice."""

    def test_resolve_messaging_provider_returns_green_api_implementation(self, tmp_path):
        tenant = _tenant(tmp_path, capability_selection={"messaging_provider": "green_api"})
        provider = CapabilityRegistry.resolve(tenant, "messaging_provider")
        assert isinstance(provider, GreenAPIMessagingProvider)

    def test_resolve_invoicing_provider_returns_morning_implementation(self, tmp_path):
        tenant = _tenant(tmp_path)
        provider = CapabilityRegistry.resolve(tenant, "invoicing_provider")
        assert isinstance(provider, MorningInvoicingProvider)

    def test_resolve_returns_the_same_registered_instance_every_call(self, tmp_path):
        """Per-call registry lookup, not a fresh construction per call - the
        registered implementation instances are shared, stateless singletons
        (no per-tenant mutable state lives on them)."""
        tenant = _tenant(tmp_path)
        first = CapabilityRegistry.resolve(tenant, "invoicing_provider")
        second = CapabilityRegistry.resolve(tenant, "invoicing_provider")
        assert first is second


class TestCapabilityRegistryDegradedStart:
    """REQ-CAP-005: a tenant with no (working) invoicing provider resolves to None,
    not an exception - messaging_provider stays required (REQ-CAP-005 explicitly
    excludes it from the degraded-start allowance)."""

    def test_tenant_with_no_invoicing_provider_selected_resolves_none(self, tmp_path):
        tenant = _tenant(
            tmp_path,
            capability_selection={"messaging_provider": "green_api"},
            mcp_auth_token=None,
        )
        assert CapabilityRegistry.resolve(tenant, "invoicing_provider") is None

    def test_tenant_with_invoicing_provider_selected_but_no_mcp_auth_token_resolves_none(self, tmp_path):
        """A dangling capability_selection entry with no working credential is not
        a functioning capability (Tenant.has_invoicing_provider's own rule) -
        the registry must agree, not attach a tool with no token to send."""
        tenant = _tenant(
            tmp_path,
            capability_selection={"messaging_provider": "green_api", "invoicing_provider": "morning"},
            mcp_auth_token=None,
        )
        assert CapabilityRegistry.resolve(tenant, "invoicing_provider") is None

    def test_missing_invoicing_provider_never_raises(self, tmp_path):
        tenant = _tenant(
            tmp_path, capability_selection={"messaging_provider": "green_api"}, mcp_auth_token=None,
        )
        # Must not raise - this is the whole point of REQ-CAP-005.
        CapabilityRegistry.resolve(tenant, "invoicing_provider")

    def test_missing_messaging_provider_selection_raises(self, tmp_path):
        """messaging_provider is NOT eligible for degraded-start (REQ-CAP-005 only
        names non-messaging capabilities) - Tenant.__post_init__ already refuses to
        construct a tenant missing this key at all, so simulate it by resolving
        against a capability_selection with the key deleted post-construction."""
        tenant = _tenant(tmp_path)
        del tenant.capability_selection["messaging_provider"]
        with pytest.raises(ValueError):
            CapabilityRegistry.resolve(tenant, "messaging_provider")


class TestCapabilityRegistryUnknownImplementation:
    """An implementation name that isn't registered is a real config error (a typo
    in capability_selection, or a not-yet-implemented provider referenced too
    early) - distinct from REQ-CAP-005's legitimate "not configured at all" case."""

    def test_unknown_invoicing_implementation_name_raises_value_error(self, tmp_path):
        tenant = _tenant(
            tmp_path,
            capability_selection={"messaging_provider": "green_api", "invoicing_provider": "ypay"},
        )
        with pytest.raises(ValueError):
            CapabilityRegistry.resolve(tenant, "invoicing_provider")

    def test_unknown_messaging_implementation_name_raises_value_error(self, tmp_path):
        tenant = _tenant(tmp_path, capability_selection={"messaging_provider": "whatsapp_cloud_api"})
        with pytest.raises(ValueError):
            CapabilityRegistry.resolve(tenant, "messaging_provider")

    def test_unknown_capability_name_raises_value_error(self, tmp_path):
        tenant = _tenant(tmp_path)
        with pytest.raises(ValueError):
            CapabilityRegistry.resolve(tenant, "sms_provider")


class TestGreenAPIMessagingProviderBuildsBot:
    """REQ-CAP-001: the messaging provider owns the Green-API-specific mechanics of
    turning a tenant's credentials into a running bot instance - Tenant.start()
    delegates here rather than constructing DeniDinGreenAPIBot inline."""

    def test_build_bot_calls_bot_factory_with_tenant_credentials(self, tmp_path):
        tenant = _tenant(
            tmp_path, green_api={"instance_id": "unique-id", "api_token": "unique-token"},
        )
        calls = []

        def fake_bot_factory(instance_id, api_token, **_kwargs):
            calls.append((instance_id, api_token))
            return "a-fake-bot"

        provider = GreenAPIMessagingProvider()
        bot = provider.build_bot(tenant, fake_bot_factory)

        assert bot == "a-fake-bot"
        assert calls == [("unique-id", "unique-token")]


class TestMorningInvoicingProviderMcpConfigOverrides:
    """REQ-CAP-006/contracts/invoicing-capability.md: the invoicing provider
    supplies the tenant-scoped mcp config overrides (the tenant's OWN bearer
    token) that get merged into that tenant's AIHandler config - never a shared/
    global token."""

    def test_mcp_config_overrides_includes_tenant_own_auth_token(self, tmp_path):
        tenant = _tenant(tmp_path, mcp_auth_token="tenant-a-own-token")
        provider = MorningInvoicingProvider()
        overrides = provider.mcp_config_overrides(tenant)
        assert overrides["morning_auth_token"] == "tenant-a-own-token"

    def test_two_tenants_get_different_auth_token_overrides(self, tmp_path):
        tenant_a = _tenant(tmp_path, tenant_id="tenant-a", mcp_auth_token="token-a")
        tenant_b = _tenant(tmp_path, tenant_id="tenant-b", mcp_auth_token="token-b")
        provider = MorningInvoicingProvider()

        assert provider.mcp_config_overrides(tenant_a)["morning_auth_token"] == "token-a"
        assert provider.mcp_config_overrides(tenant_b)["morning_auth_token"] == "token-b"
