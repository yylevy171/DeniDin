"""Tenant model for multi-tenancy (Feature 055).

See specs/in-progress/055-multiple-clients-godfathers/data-model.md for the full field
list ("Tenant Identity" / "Tenant Credentials" tables) and spec.md's
REQ-TENANT-001..005/REQ-CAP-005/REQ-PARITY-001 for the requirements this derives from.

A Tenant instance represents the *joined* view of a tenant's environment-agnostic identity
(from tenants.json) and its per-environment credentials (from that environment's own
config.<env>.json) — TenantManager is responsible for performing that join; this model does
not read any file itself.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Tenant:
    """Represents one tenant's identity + this-environment credentials, joined."""

    tenant_id: str
    account_name: str
    bot_name: str
    godfathers: List[str]
    admins: List[str]
    constitution_supplement_file: str
    capability_selection: Dict[str, str]
    environment_data_root: str
    green_api: Optional[Dict[str, str]] = None
    openai: Optional[Dict[str, str]] = None
    mcp_auth_token: Optional[str] = None

    def __post_init__(self):
        """Validate required identity/credential fields."""
        if not self.tenant_id:
            raise ValueError("Tenant tenant_id cannot be empty")
        if not self.account_name:
            raise ValueError("Tenant account_name cannot be empty")
        if not self.bot_name:
            raise ValueError("Tenant bot_name cannot be empty")
        if not self.openai:
            raise ValueError(
                f"Tenant '{self.account_name}' is missing its required openai credential "
                "(REQ-TENANT-003: OpenAI credential is per-tenant, not optional)"
            )
        if not self.green_api:
            raise ValueError(
                f"Tenant '{self.account_name}' is missing its required green_api credential "
                "(a tenant needs a messaging provider to start at all — REQ-CAP-005)"
            )
        if "messaging_provider" not in self.capability_selection:
            raise ValueError(
                f"Tenant '{self.account_name}' capability_selection is missing "
                "'messaging_provider' (REQ-CAP-001/REQ-CAP-005: required to start at all)"
            )

    @property
    def data_root(self) -> Path:
        """Derived, read-only: {environment_data_root}/{tenant_id}/ — never a stored field."""
        return Path(self.environment_data_root) / self.tenant_id

    @property
    def has_invoicing_provider(self) -> bool:
        """REQ-CAP-005: a tenant may legitimately have no invoicing provider configured.

        True only when both an implementation is selected AND credentials (the MCP bearer
        token) actually exist for it — a dangling capability_selection entry with no token
        is not a working capability.
        """
        return bool(self.mcp_auth_token) and "invoicing_provider" in self.capability_selection
