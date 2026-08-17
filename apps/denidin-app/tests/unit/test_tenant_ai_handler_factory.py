"""
Unit tests for TenantAIHandlerFactory (Feature 055: Multi-Tenancy).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 3, T009a (corrected 2026-08-17 design — research.md §8): builds one
full AIHandler stack per tenant by sourcing values from a Tenant object into a
tenant-scoped AppConfiguration view, then calling the UNMODIFIED AIHandler
constructor — exactly as denidin.py's initialize_app already does for the single
migrated tenant.

REQ-PARITY-001: this task requires zero changes to AIHandler/SessionManager/
MemoryManager/LedgerEventManager/UserManager themselves — verified implicitly by
this file never touching test_ai_handler.py/test_session_manager.py/
test_memory_manager.py/test_ledger_event_manager.py/test_user_manager.py.

Note: full multi-godfather support (more than one godfather per tenant) is Phase
4/US2's concern (tasks.md T015) — this factory currently wires only the first
configured godfather through today's existing singular `godfather_phone` config
field, by design, so Phase 3 needs zero AppConfiguration/AIHandler/UserManager
changes at all. T015 will extend this factory once UserManager supports a list.
"""

from pathlib import Path

import pytest
from openai import OpenAI

from src.handlers.ai_handler import AIHandler
from src.managers.tenant_ai_handler_factory import TenantAIHandlerFactory
from src.models.config import AppConfiguration
from src.models.tenant import Tenant


def _base_config(**overrides):
    """A minimal, valid environment-wide AppConfiguration (the pre-multi-tenancy
    single-tenant config shape) — represents values TenantAIHandlerFactory should
    carry over unchanged (e.g. ai_embedding_model, feature_flags), never override."""
    kwargs = {
        "green_api_instance_id": "base-instance-unused",
        "green_api_token": "base-token-unused",
        "ai_api_key": "sk-base-unused",
        "ai_embedding_model": "text-embedding-3-large",
        "feature_flags": {"enable_memory_system": True, "enable_rbac": True},
        "data_root": "base_data_root_unused",
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
        "openai": {"api_key": "sk-tenant-a-key"},
        "mcp_auth_token": "denidin-tenant-bearer-token-dev",
    }
    kwargs.update(overrides)
    return Tenant(**kwargs)


class TestTenantAIHandlerFactoryDataIsolation:
    """Test that each tenant's AIHandler gets its own, separate data paths."""

    def test_builds_a_real_ai_handler_instance(self, tmp_path):
        tenant = _tenant(tmp_path)
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert isinstance(handler, AIHandler)

    def test_session_manager_storage_dir_is_tenant_scoped(self, tmp_path):
        tenant = _tenant(tmp_path)
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert handler.session_manager.storage_dir == tenant.data_root / "sessions"

    def test_ledger_event_manager_storage_dir_is_tenant_scoped(self, tmp_path):
        tenant = _tenant(tmp_path)
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert handler.ledger_event_manager.storage_dir == tenant.data_root / "events"

    def test_memory_manager_storage_dir_is_tenant_scoped(self, tmp_path):
        tenant = _tenant(tmp_path)
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert handler.memory_manager.storage_dir == tenant.data_root / "memory"

    def test_two_tenants_get_fully_separate_data_paths(self, tmp_path):
        tenant_a = _tenant(tmp_path, tenant_id="tenant-a", account_name="a")
        tenant_b = _tenant(tmp_path, tenant_id="tenant-b", account_name="b")

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.session_manager.storage_dir != handler_b.session_manager.storage_dir
        assert handler_a.memory_manager.storage_dir != handler_b.memory_manager.storage_dir
        assert (
            handler_a.ledger_event_manager.storage_dir
            != handler_b.ledger_event_manager.storage_dir
        )


class TestTenantAIHandlerFactoryCredentialIsolation:
    """Test that each tenant's AIHandler uses its own OpenAI credential."""

    def test_openai_client_uses_tenant_own_api_key(self, tmp_path):
        tenant = _tenant(tmp_path, openai={"api_key": "sk-tenant-specific-key"})
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        assert handler.client.api_key == "sk-tenant-specific-key"

    def test_two_tenants_get_different_openai_credentials(self, tmp_path):
        tenant_a = _tenant(
            tmp_path,
            tenant_id="tenant-a",
            account_name="a",
            openai={"api_key": "sk-tenant-a"},
        )
        tenant_b = _tenant(
            tmp_path,
            tenant_id="tenant-b",
            account_name="b",
            openai={"api_key": "sk-tenant-b"},
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.client.api_key != handler_b.client.api_key


class TestTenantAIHandlerFactoryRBAC:
    """Test that each tenant's AIHandler resolves RBAC from that tenant's own lists."""

    def test_admin_phone_resolves_within_tenant(self, tmp_path):
        tenant = _tenant(tmp_path, admins=["+972509999999"])
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        user = handler.user_manager.get_user("+972509999999")
        assert user.role.value == "ADMIN"

    def test_godfather_phone_resolves_within_tenant(self, tmp_path):
        tenant = _tenant(tmp_path, godfathers=["+972501111111"])
        handler = TenantAIHandlerFactory.build(tenant, _base_config())
        user = handler.user_manager.get_user("+972501111111")
        assert user.role.value == "GODFATHER"

    def test_two_tenants_admins_are_independent(self, tmp_path):
        """The same number that's admin in tenant A resolves as an unrecognized
        (default CLIENT) role in tenant B, which doesn't list it at all."""
        tenant_a = _tenant(
            tmp_path, tenant_id="tenant-a", account_name="a", admins=["+972509999999"]
        )
        tenant_b = _tenant(
            tmp_path, tenant_id="tenant-b", account_name="b", admins=["+972508888888"]
        )

        handler_a = TenantAIHandlerFactory.build(tenant_a, _base_config())
        handler_b = TenantAIHandlerFactory.build(tenant_b, _base_config())

        assert handler_a.user_manager.get_user("+972509999999").role.value == "ADMIN"
        assert handler_b.user_manager.get_user("+972509999999").role.value == "CLIENT"


class TestTenantAIHandlerFactoryEnvironmentWideValuesPreserved:
    """Test that non-tenant-specific config values pass through from base_config unchanged."""

    def test_ai_embedding_model_comes_from_base_config(self, tmp_path):
        tenant = _tenant(tmp_path)
        base = _base_config(ai_embedding_model="text-embedding-3-small")
        handler = TenantAIHandlerFactory.build(tenant, base)
        assert handler.memory_manager.embedding_model == "text-embedding-3-small"
