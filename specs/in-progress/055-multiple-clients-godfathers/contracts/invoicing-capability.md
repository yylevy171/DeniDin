# Integration Contracts: Invoicing Capability (morning-mcp-app, shared server)

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

---

### `AIHandler` ↔ morning-mcp-app (shared server) Contract (extension of existing MCP contract)

**`AIHandler` MUST**:
- Continue attaching the Morning MCP remote tool only for godfather/admin roles (existing RBAC
  gate, unchanged) — additionally, only when the calling tenant has an invoicing-provider
  capability configured at all (REQ-CAP-005/REQ-CAP-006).
- Pass the calling tenant's own `mcp_auth_token` (`data-model.md`'s `Tenant.mcp_auth_token`) as
  the bearer credential for every MCP call for that turn — never a shared/global token, and
  never another tenant's token.
- Discover the tunnel URL exactly as today, via the environment's single shared status file
  (`shared/mcp-status-<env>/`) — no per-tenant status file is introduced (`research.md` §4).

**morning-mcp-app (shared server) PROVIDES**:
- The same 11 tools (`create_invoice`, `list_invoices`, etc.), identical logic for every tenant
  — the tool surface itself is not tenant-specific (`research.md` §4: "the mcp as a
  functionality truly is common for all").
- `BearerTokenMiddleware` extended to a one-token-per-tenant map (was: one shared secret per
  environment) — resolves the calling tenant from the presented token, then uses that tenant's
  Morning credentials for the underlying Morning API call.
- Audit logging (`audit.py`) attributed to the correct tenant — every audit line MUST record
  which tenant the call was for, in addition to the existing resolved-client/payload/response
  fields, so cross-tenant audit trails stay distinguishable in one shared log.

**morning-mcp-app (shared server) EXPECTS**:
- Exactly one valid bearer token per tenant, provisioned into the server's config alongside that
  tenant's Morning credentials (manual onboarding, per spec.md Assumptions) — an unrecognized
  token is rejected the same way an invalid shared secret is rejected today, not silently mapped
  to a default tenant.
- One shared ngrok tunnel per environment (2 total, per `research.md` §3) — not a
  tunnel-per-tenant assumption anywhere in server startup/discovery.

---

### `BearerTokenMiddleware` ↔ Tenant Config Contract

**`BearerTokenMiddleware` MUST**:
- Reject any request whose bearer token doesn't match exactly one configured tenant's
  `mcp_auth_token` — no partial matching, no fallback to a "default" tenant.
- Make the resolved `tenant_id` available to the tool-call handler (`server.py`'s
  `_call_with_error_boundary`) for the rest of that call's lifetime, so the correct Morning
  credentials and audit attribution are used without a second lookup.

**Tenant Config PROVIDES**:
- One `mcp_auth_token` per tenant, unique across all tenants in that environment (system MUST
  enforce this at config-load time — two tenants sharing a token is a config error, not a valid
  state, since it would silently merge their invoicing access).
