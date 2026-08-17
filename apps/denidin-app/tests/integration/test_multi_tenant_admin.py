"""
Integration test for Feature 055 (Multi-Tenancy), tasks.md T018a/T019a: super-admin
oversight across all tenants (US3, SC-004) - and REQ-ROLE-005's "no break-glass"
counterpart.

research.md SS8 / contracts/tenant-scoped-data-managers.md: one `UserManager` instance
per tenant (via `TenantAIHandlerFactory`, unmodified since T009) already makes admin
resolution correctly per-tenant BY CONSTRUCTION - there is no special-cased global
admin check anywhere to get wrong. This file is the regression tripwire proving that,
not new functionality:
  - T018a: ylevy's number, listed in TWO different tenants' `admins`, resolves
    Role.ADMIN independently in each tenant's own AIHandler/UserManager.
  - T019a (REQ-ROLE-005): a tenant whose config OMITS that number resolves it as an
    ordinary (non-admin) role for THAT TENANT ONLY - no fallback, no break-glass, no
    cross-tenant leakage of admin status just because the same number is an admin
    somewhere else.

Also covers the "version-query admin capability (ungated by RBAC) still resolves
per-tenant version info" scope note from tasks.md T018a: `AIHandler._app_version` is
read once per AIHandler construction (from the one process-wide VERSION file, per
Feature 034 - NOT per-tenant data), so every tenant's own AIHandler independently
carries its own read of it - proven directly rather than assumed.

Uses the same real-internal-components convention as
test_tenant_ai_handler_factory.py (TenantAIHandlerFactory.build, unmodified AIHandler/
UserManager) - no webhook dispatch is needed here, since T018a/T019a are specifically
about RBAC resolution, not message routing (already covered by
test_tenant_isolation.py/test_multi_godfather.py).
"""

from pathlib import Path

import pytest

from src.managers.tenant_ai_handler_factory import TenantAIHandlerFactory
from src.models.config import AppConfiguration
from src.models.tenant import Tenant
from src.models.user import Role

YLEVY_PHONE = "+972501234567"


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
        "godfathers": ["+972501111111"],
        "admins": [],
        "constitution_supplement_file": "config/tenants/denidin/constitution_supplement.md",
        "capability_selection": {
            "messaging_provider": "green_api",
            "invoicing_provider": "morning",
        },
        "environment_data_root": str(tmp_path),
        "green_api": {
            "instance_id": "instance-a", "api_token": "token-a",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-tenant-a"},
        "mcp_auth_token": "token-a-mcp",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


@pytest.mark.integration
class TestCrossTenantAdminResolution:
    """T018a (SC-004): the same super-admin phone number, listed in more than one
    tenant, resolves Role.ADMIN independently in each - not a special-cased global
    check, just each tenant's own UserManager doing what it always does."""

    def test_ylevy_resolves_admin_in_both_tenants_that_list_the_number(self, tmp_path):
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a", admins=[YLEVY_PHONE],
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b", admins=[YLEVY_PHONE],
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.user_manager.get_user(YLEVY_PHONE).role == Role.ADMIN
        assert handler_b.user_manager.get_user(YLEVY_PHONE).role == Role.ADMIN

    def test_admin_resolution_is_via_two_fully_independent_user_manager_instances(self, tmp_path):
        """Not merely "both say ADMIN" (which a shared/global check could also
        produce) - the two AIHandlers' user_managers are genuinely separate
        objects, each independently configured from its own tenant's admins list."""
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a", admins=[YLEVY_PHONE],
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b", admins=[YLEVY_PHONE],
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.user_manager is not handler_b.user_manager
        assert handler_a.user_manager.admin_phones == [YLEVY_PHONE]
        assert handler_b.user_manager.admin_phones == [YLEVY_PHONE]

    def test_version_query_capability_resolves_independently_per_tenant_ai_handler(self, tmp_path):
        """The ungated-by-RBAC version-query capability (Feature 034) is baked into
        each AIHandler's own _app_version at construction time (one process-wide
        VERSION file, not tenant data) - both tenants' AIHandlers carry it
        independently, proven directly rather than assumed."""
        tenant_a = _tenant(tmp_path, tenant_id="tenant-a", account_name="a")
        tenant_b = _tenant(tmp_path, tenant_id="tenant-b", account_name="b")

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a._app_version  # pylint: disable=protected-access
        # Both AIHandlers in one process read the same process-wide VERSION file -
        # same value, but independently sourced (each has its own attribute, not a
        # shared global), matching REQ-VER-005's "read once at construction" rule.
        assert handler_a._app_version == handler_b._app_version  # pylint: disable=protected-access


@pytest.mark.integration
class TestNoBreakGlassAdminLeakage:
    """T019a (REQ-ROLE-005, "no break-glass"): a tenant whose config OMITS ylevy's
    admin number resolves that number as an ORDINARY role for that tenant only - no
    fallback to admin, no cross-tenant leakage just because the same number is an
    admin elsewhere."""

    def test_number_admin_in_one_tenant_is_an_ordinary_client_in_a_tenant_that_omits_it(self, tmp_path):
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a", admins=[YLEVY_PHONE],
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b", admins=[],
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.user_manager.get_user(YLEVY_PHONE).role == Role.ADMIN
        assert handler_b.user_manager.get_user(YLEVY_PHONE).role == Role.CLIENT

    def test_number_omitted_everywhere_never_resolves_admin_by_any_fallback(self, tmp_path):
        """No environment-wide/break-glass admin list exists to fall back to -
        tenant_b's UserManager was built from tenant_b's own (empty) admins list
        only."""
        tenant_b = _tenant(tmp_path, tenant_id="tenant-b", account_name="b", admins=[])
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_b.user_manager.admin_phones == []
        assert handler_b.user_manager.get_user(YLEVY_PHONE).role != Role.ADMIN

    def test_being_a_godfather_in_one_tenant_does_not_grant_admin_in_another(self, tmp_path):
        """A related leakage shape worth ruling out explicitly: a number with
        elevated (godfather) access in tenant A gets no special treatment at all
        in tenant B, where it isn't listed in any role list."""
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a",
            godfathers=[YLEVY_PHONE], admins=[],
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b",
            godfathers=["+972502222222"], admins=[],
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.user_manager.get_user(YLEVY_PHONE).role == Role.GODFATHER
        assert handler_b.user_manager.get_user(YLEVY_PHONE).role == Role.CLIENT
