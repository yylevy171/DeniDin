"""TenantManager: loads and joins tenant identity + per-environment credentials.

See specs/in-progress/055-multiple-clients-godfathers/data-model.md's "Config file
structure" section for the two-file split this implements: tenants.json holds
environment-agnostic identity, shared by dev and prod; each environment's own
config.<env>.json holds that environment's credentials, keyed by tenant_id.

REQ-TENANT-004/005: identity lives in tenants.json, credentials live per-environment.
A tenants.json identity with no matching tenant_credentials entry in the active
environment simply isn't active there yet (phased onboarding — quickstart.md) — not an
error. A tenant_credentials entry with no matching tenants.json identity IS an error
(stale/typo'd tenant_id).
"""

import json
from pathlib import Path
from typing import Dict, List

from src.models.tenant import Tenant


class TenantManager:
    """Holds every tenant active in the current environment, keyed by tenant_id."""

    def __init__(self, tenants: List[Tenant]):
        self._tenants_by_id: Dict[str, Tenant] = {}
        account_names_seen: Dict[str, str] = {}
        mcp_tokens_seen: Dict[str, str] = {}

        for tenant in tenants:
            if tenant.account_name in account_names_seen:
                raise ValueError(
                    f"Duplicate tenant account_name '{tenant.account_name}' "
                    f"(tenant_ids '{account_names_seen[tenant.account_name]}' and "
                    f"'{tenant.tenant_id}') — account_name must be unique within one "
                    "environment's tenant list"
                )
            account_names_seen[tenant.account_name] = tenant.tenant_id

            if tenant.mcp_auth_token:
                if tenant.mcp_auth_token in mcp_tokens_seen:
                    raise ValueError(
                        f"Duplicate mcp_auth_token '{tenant.mcp_auth_token}' "
                        f"(tenant_ids '{mcp_tokens_seen[tenant.mcp_auth_token]}' and "
                        f"'{tenant.tenant_id}') — mcp_auth_token must be unique within "
                        "one environment"
                    )
                mcp_tokens_seen[tenant.mcp_auth_token] = tenant.tenant_id

            self._tenants_by_id[tenant.tenant_id] = tenant

    @classmethod
    def load(
        cls,
        tenants_json_path: str,
        config_json_path: str,
        environment_data_root: str,
    ) -> "TenantManager":
        """Load tenants.json + this environment's tenant_credentials, join by tenant_id."""
        identities = json.loads(Path(tenants_json_path).read_text(encoding="utf-8")).get(
            "tenants", []
        )
        credentials = json.loads(Path(config_json_path).read_text(encoding="utf-8")).get(
            "tenant_credentials", {}
        )

        identity_ids = {identity["tenant_id"] for identity in identities}
        for tenant_id in credentials:
            if tenant_id not in identity_ids:
                raise ValueError(
                    f"{config_json_path} has tenant_credentials for tenant_id "
                    f"'{tenant_id}' but no matching entry in {tenants_json_path} — "
                    "stale or mistyped tenant_id"
                )

        tenants = []
        for identity in identities:
            tenant_credentials = credentials.get(identity["tenant_id"])
            if tenant_credentials is None:
                # Onboarded in tenants.json but not yet credentialed in this
                # environment — not active here yet, not an error.
                continue
            tenants.append(
                Tenant(
                    tenant_id=identity["tenant_id"],
                    account_name=identity["account_name"],
                    bot_name=identity["bot_name"],
                    godfathers=identity.get("godfathers", []),
                    admins=identity.get("admins", []),
                    constitution_supplement_file=identity.get(
                        "constitution_supplement_file", ""
                    ),
                    capability_selection=identity.get("capability_selection", {}),
                    environment_data_root=environment_data_root,
                    green_api=tenant_credentials.get("green_api"),
                    openai=tenant_credentials.get("openai"),
                    mcp_auth_token=tenant_credentials.get("mcp_auth_token"),
                )
            )

        return cls(tenants)

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Look up a tenant by id. Raises KeyError — never a silent wrong-tenant fallback."""
        try:
            return self._tenants_by_id[tenant_id]
        except KeyError:
            raise KeyError(f"Unknown tenant_id: '{tenant_id}'") from None

    def all_tenants(self) -> List[Tenant]:
        """Every tenant active in this environment."""
        return list(self._tenants_by_id.values())
