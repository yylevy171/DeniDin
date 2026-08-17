"""Morning invoicing provider implementation (Feature 055, REQ-CAP-002/006).

The existing (and, as of this feature, only) invoicing_provider implementation.
Per contracts/invoicing-capability.md: the shared morning-mcp-app server/tunnel
serves every tenant identically (tool surface, server URL, server label - all
environment-wide, unchanged by this feature); only the bearer auth token is
tenant-scoped, since that's the mechanism the server uses to resolve which
tenant's Morning credentials/audit trail a given call belongs to.
"""

from typing import Any, Dict

from src.capabilities.invoicing_provider import InvoicingProvider


class MorningInvoicingProvider(InvoicingProvider):
    """Supplies this tenant's own Morning MCP bearer token as a `config.mcp`
    override - never a shared/global token."""

    def mcp_config_overrides(self, tenant: Any) -> Dict[str, Any]:
        return {"morning_auth_token": tenant.mcp_auth_token}
