"""
Unit tests for TenantManager (Feature 055: Multi-Tenancy).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md Phase 2, T004a/T005a: loading + joining tenants.json (environment-agnostic
identity) with a per-environment config's tenant_credentials, validation, and
tenant_id lookup helpers.

See specs/in-progress/055-multiple-clients-godfathers/data-model.md's "Config file
structure" section and spec.md's REQ-TENANT-004/005/REQ-CAP-005 for the requirements
this behavior derives from.
"""

import json

import pytest

from src.managers.tenant_manager import TenantManager


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _tenant_identity(**overrides):
    identity = {
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
    }
    identity.update(overrides)
    return identity


def _tenant_credentials(**overrides):
    creds = {
        "green_api": {
            "instance_id": "1101000001",
            "api_token": "d0d5deadbeef",
            "whatsapp_number": "+972501234567",
        },
        "openai": {"api_key": "sk-test-key"},
        "mcp_auth_token": "denidin-tenant-bearer-token-dev",
    }
    creds.update(overrides)
    return creds


class TestTenantManagerLoad:
    """Test TenantManager.load() joining tenants.json + tenant_credentials."""

    def test_loads_and_joins_single_tenant(self, tmp_path):
        tenants_json = _write_json(
            tmp_path / "tenants.json", {"tenants": [_tenant_identity()]}
        )
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "b6f1c2a4-0000-0000-0000-000000000001": _tenant_credentials()
                }
            },
        )

        manager = TenantManager.load(
            tenants_json_path=str(tenants_json),
            config_json_path=str(config_json),
            environment_data_root="dev_data",
        )

        tenant = manager.get_tenant("b6f1c2a4-0000-0000-0000-000000000001")
        assert tenant.account_name == "denidin"
        assert tenant.bot_name == "DeniDin"
        assert tenant.green_api["instance_id"] == "1101000001"
        assert str(tenant.data_root) == "dev_data/b6f1c2a4-0000-0000-0000-000000000001"

    def test_tenant_in_registry_but_not_credentialed_in_this_env_is_simply_absent(
        self, tmp_path
    ):
        """A tenant onboarded in dev but not yet added to prod's credentials isn't an
        error — it's just not active in this environment yet (phased onboarding,
        quickstart.md)."""
        tenants_json = _write_json(
            tmp_path / "tenants.json", {"tenants": [_tenant_identity()]}
        )
        config_json = _write_json(
            tmp_path / "config.prod.json", {"tenant_credentials": {}}
        )

        manager = TenantManager.load(
            tenants_json_path=str(tenants_json),
            config_json_path=str(config_json),
            environment_data_root="data",
        )

        assert manager.all_tenants() == []

    def test_orphaned_tenant_credentials_raises(self, tmp_path):
        """A tenant_credentials entry with no matching tenants.json identity is a real
        config error (stale/typo'd tenant_id), not silently ignored."""
        tenants_json = _write_json(tmp_path / "tenants.json", {"tenants": []})
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "ghost-tenant-id": _tenant_credentials()
                }
            },
        )

        with pytest.raises(ValueError, match="ghost-tenant-id"):
            TenantManager.load(
                tenants_json_path=str(tenants_json),
                config_json_path=str(config_json),
                environment_data_root="dev_data",
            )

    def test_duplicate_account_name_raises(self, tmp_path):
        tenants_json = _write_json(
            tmp_path / "tenants.json",
            {
                "tenants": [
                    _tenant_identity(
                        tenant_id="tenant-a", account_name="same-name"
                    ),
                    _tenant_identity(
                        tenant_id="tenant-b", account_name="same-name"
                    ),
                ]
            },
        )
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "tenant-a": _tenant_credentials(mcp_auth_token="token-a"),
                    "tenant-b": _tenant_credentials(mcp_auth_token="token-b"),
                }
            },
        )

        with pytest.raises(ValueError, match="same-name"):
            TenantManager.load(
                tenants_json_path=str(tenants_json),
                config_json_path=str(config_json),
                environment_data_root="dev_data",
            )

    def test_duplicate_mcp_auth_token_raises(self, tmp_path):
        tenants_json = _write_json(
            tmp_path / "tenants.json",
            {
                "tenants": [
                    _tenant_identity(tenant_id="tenant-a", account_name="a"),
                    _tenant_identity(tenant_id="tenant-b", account_name="b"),
                ]
            },
        )
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "tenant-a": _tenant_credentials(mcp_auth_token="shared-token"),
                    "tenant-b": _tenant_credentials(mcp_auth_token="shared-token"),
                }
            },
        )

        with pytest.raises(ValueError, match="shared-token"):
            TenantManager.load(
                tenants_json_path=str(tenants_json),
                config_json_path=str(config_json),
                environment_data_root="dev_data",
            )

    def test_tenant_missing_invoicing_provider_loads_successfully(self, tmp_path):
        """REQ-CAP-005: degraded, not an error."""
        tenants_json = _write_json(
            tmp_path / "tenants.json",
            {
                "tenants": [
                    _tenant_identity(
                        capability_selection={"messaging_provider": "green_api"}
                    )
                ]
            },
        )
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "b6f1c2a4-0000-0000-0000-000000000001": _tenant_credentials(
                        mcp_auth_token=None
                    )
                }
            },
        )

        manager = TenantManager.load(
            tenants_json_path=str(tenants_json),
            config_json_path=str(config_json),
            environment_data_root="dev_data",
        )

        tenant = manager.get_tenant("b6f1c2a4-0000-0000-0000-000000000001")
        assert tenant.has_invoicing_provider is False


class TestTenantManagerLookups:
    """Test get_tenant()/all_tenants() lookup helpers."""

    def _manager_with_two_tenants(self, tmp_path):
        tenants_json = _write_json(
            tmp_path / "tenants.json",
            {
                "tenants": [
                    _tenant_identity(tenant_id="tenant-a", account_name="a"),
                    _tenant_identity(tenant_id="tenant-b", account_name="b"),
                ]
            },
        )
        config_json = _write_json(
            tmp_path / "config.dev.json",
            {
                "tenant_credentials": {
                    "tenant-a": _tenant_credentials(mcp_auth_token="token-a"),
                    "tenant-b": _tenant_credentials(mcp_auth_token="token-b"),
                }
            },
        )
        return TenantManager.load(
            tenants_json_path=str(tenants_json),
            config_json_path=str(config_json),
            environment_data_root="dev_data",
        )

    def test_get_tenant_returns_correct_tenant(self, tmp_path):
        manager = self._manager_with_two_tenants(tmp_path)
        assert manager.get_tenant("tenant-a").account_name == "a"
        assert manager.get_tenant("tenant-b").account_name == "b"

    def test_get_tenant_unknown_id_raises(self, tmp_path):
        """No silent wrong-tenant fallback (REQ-PARITY-001's sibling principle)."""
        manager = self._manager_with_two_tenants(tmp_path)
        with pytest.raises(KeyError, match="unknown-tenant"):
            manager.get_tenant("unknown-tenant")

    def test_all_tenants_returns_every_loaded_tenant(self, tmp_path):
        manager = self._manager_with_two_tenants(tmp_path)
        ids = {t.tenant_id for t in manager.all_tenants()}
        assert ids == {"tenant-a", "tenant-b"}
