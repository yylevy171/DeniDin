"""
Unit tests for the Tenant model (Feature 055: Multi-Tenancy).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 2, T003a: construction from a tenants.json identity entry joined
with a matching per-environment tenant_credentials entry, required vs. optional
fields, and the derived (never directly settable) data_root property.

See specs/in-progress/055-multiple-clients-godfathers/data-model.md for the full
field list ("Tenant Identity" / "Tenant Credentials" tables) and spec.md's
REQ-TENANT-001..005/REQ-CAP-005/REQ-PARITY-001 for the requirements this
behavior derives from.
"""

from pathlib import Path

import pytest

from src.models.tenant import Tenant


def _base_kwargs(**overrides):
    """A minimal, valid set of constructor kwargs for Tenant, with overrides."""
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
        "environment_data_root": "dev_data",
        "green_api": {
            "instance_id": "1101000001",
            "api_token": "d0d5deadbeef",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-test-key"},
        "mcp_auth_token": "denidin-tenant-bearer-token-dev",
    }
    kwargs.update(overrides)
    return kwargs


class TestTenantConstruction:
    """Test constructing a Tenant from a full (identity + credentials) field set."""

    def test_create_tenant_with_all_fields(self):
        """A fully-populated Tenant constructs successfully with all fields set."""
        tenant = Tenant(**_base_kwargs())
        assert tenant.tenant_id == "b6f1c2a4-0000-0000-0000-000000000001"
        assert tenant.account_name == "denidin"
        assert tenant.bot_name == "DeniDin"
        assert tenant.godfathers == ["+972501111111"]
        assert tenant.admins == ["+972509999999"]
        assert tenant.mcp_auth_token == "denidin-tenant-bearer-token-dev"

    def test_create_tenant_with_multiple_godfathers(self):
        """A tenant may have more than one godfather (REQ-ROLE-001)."""
        tenant = Tenant(**_base_kwargs(godfathers=["+972501111111", "+972502222222"]))
        assert len(tenant.godfathers) == 2


class TestTenantRequiredFields:
    """Test that required identity/credential fields raise clear errors when missing."""

    def test_missing_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id"):
            Tenant(**_base_kwargs(tenant_id=""))

    def test_missing_account_name_raises(self):
        with pytest.raises(ValueError, match="account_name"):
            Tenant(**_base_kwargs(account_name=""))

    def test_missing_bot_name_raises(self):
        with pytest.raises(ValueError, match="bot_name"):
            Tenant(**_base_kwargs(bot_name=""))

    def test_missing_openai_credential_raises(self):
        """REQ-TENANT-003: OpenAI credential is a firm, required-per-tenant decision."""
        with pytest.raises(ValueError, match="openai"):
            Tenant(**_base_kwargs(openai=None))

    def test_missing_green_api_credential_raises(self):
        """Messaging provider is required to start at all (REQ-CAP-005)."""
        with pytest.raises(ValueError, match="green_api"):
            Tenant(**_base_kwargs(green_api=None))

    def test_missing_messaging_provider_capability_selection_raises(self):
        """capability_selection MUST name a messaging_provider (REQ-CAP-001/005)."""
        with pytest.raises(ValueError, match="messaging_provider"):
            Tenant(**_base_kwargs(capability_selection={"invoicing_provider": "morning"}))


class TestTenantOptionalInvoicingCapability:
    """REQ-CAP-005: a tenant may legitimately have no invoicing provider configured."""

    def test_tenant_without_invoicing_provider_constructs_successfully(self):
        """Omitting invoicing_provider entirely is a valid, non-error, degraded state."""
        tenant = Tenant(
            **_base_kwargs(
                capability_selection={"messaging_provider": "green_api"},
                mcp_auth_token=None,
            )
        )
        assert tenant.has_invoicing_provider is False

    def test_tenant_with_invoicing_provider_reports_true(self):
        tenant = Tenant(**_base_kwargs())
        assert tenant.has_invoicing_provider is True

    def test_invoicing_provider_selected_but_no_mcp_token_is_not_fully_configured(self):
        """A dangling capability_selection entry with no token isn't a working capability."""
        tenant = Tenant(
            **_base_kwargs(
                capability_selection={
                    "messaging_provider": "green_api",
                    "invoicing_provider": "morning",
                },
                mcp_auth_token=None,
            )
        )
        assert tenant.has_invoicing_provider is False


class TestTenantDataRoot:
    """data_root is always derived, never a settable field (data-model.md)."""

    def test_data_root_is_derived_from_environment_and_tenant_id(self):
        tenant = Tenant(**_base_kwargs(environment_data_root="dev_data"))
        assert tenant.data_root == Path("dev_data") / "b6f1c2a4-0000-0000-0000-000000000001"

    def test_data_root_is_a_path_instance(self):
        """Per CONSTITUTION: pathlib.Path, not string concatenation."""
        tenant = Tenant(**_base_kwargs())
        assert isinstance(tenant.data_root, Path)

    def test_data_root_differs_per_environment(self):
        dev_tenant = Tenant(**_base_kwargs(environment_data_root="dev_data"))
        prod_tenant = Tenant(**_base_kwargs(environment_data_root="data"))
        assert dev_tenant.data_root != prod_tenant.data_root

    def test_data_root_is_not_a_constructor_keyword(self):
        """data_root itself is never directly settable — passing it MUST fail construction."""
        kwargs = _base_kwargs()
        kwargs["data_root"] = "some/other/path"
        with pytest.raises(TypeError):
            Tenant(**kwargs)

    def test_data_root_cannot_be_reassigned_after_construction(self):
        """data_root is a read-only derived property, not a plain mutable attribute."""
        tenant = Tenant(**_base_kwargs())
        with pytest.raises(AttributeError):
            tenant.data_root = Path("something/else")
