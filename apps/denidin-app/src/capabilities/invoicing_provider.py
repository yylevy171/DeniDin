"""Invoicing provider capability interface (Feature 055: Multi-Tenancy, REQ-CAP-002).

See specs/in-progress/055-multiple-clients-godfathers/spec.md REQ-CAP-002/003/004/006
and contracts/invoicing-capability.md: invoicing runs as one shared morning-mcp-app
server/tunnel per environment (never one per tenant), distinguishing tenants by
bearer token - so from `apps/denidin-app`'s side, "selecting a tenant's invoicing
provider" means resolving the `config.mcp`-shaped overrides (tenant-scoped auth
token, etc.) that `AIHandler`'s Morning MCP tool-attachment needs for THIS tenant,
never a shared/global token.

Unlike messaging, invoicing IS eligible for degraded start (REQ-CAP-005): a tenant
with no invoicing provider configured still starts and serves messaging; the
registry (`registry.py`) resolves such a tenant's invoicing_provider to None rather
than raising, and callers gracefully treat None as "no invoicing capability this
turn" (mirroring the pre-existing "server unavailable" graceful-degradation path
`AIHandler._build_morning_mcp_tools` already had before this feature).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class InvoicingProvider(ABC):
    """Supplies the tenant-scoped `config.mcp` overrides needed to attach this
    provider's remote MCP tool for one tenant's AIHandler."""

    @abstractmethod
    def mcp_config_overrides(self, tenant: Any) -> Dict[str, Any]:
        """Return the `config.mcp`-shaped dict overrides for `tenant` (e.g. its own
        bearer auth token) - merged over the environment-wide `base_config.mcp`
        dict by `TenantAIHandlerFactory`, never a shared/global credential."""
