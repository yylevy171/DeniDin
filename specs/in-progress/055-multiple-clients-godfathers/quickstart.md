# Quickstart: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Feature**: `055-multiple-clients-godfathers` · Phase 1 output of `speckit.plan`

**Note**: this describes the *intended* operator workflow once this feature is implemented.
Exact CLI/config file names are `speckit.tasks`/`speckit.implement` decisions — this is the
shape, not the final interface.

**Scope note (2026-08-17)**: everything below describes the fully-live, two-real-tenant
version of each scenario. Under this feature's actual current scope (no real second tenant
available — see `spec.md`'s Clarifications), these are exercised via automated tests against a
*synthetic* second tenant instead; see `tasks.md`'s "now" vs "deferred" task splits (T014a/b,
T020a/b, T025a/c, T026a/b, T030a/b). This document stays the target/deferred version, run for
real whenever a second client exists.

## Example configuration shape

Tenant **identity** (environment-agnostic) and tenant **credentials** (per-environment) are
split into separate files (`data-model.md`'s "Config file structure", REQ-TENANT-004/005) —
not one combined per-environment tenant list.

**`apps/denidin-app/config/tenants.json`** (new, shared by dev and prod):

```json
{
  "tenants": [
    {
      "tenant_id": "b6f1c2a4-...-uuid",
      "account_name": "denidin",
      "bot_name": "DeniDin",
      "godfathers": ["+972501111111"],
      "admins": ["+972509999999"],
      "constitution_supplement_file": "config/tenants/denidin/constitution_supplement.md",
      "capability_selection": {
        "messaging_provider": "green_api",
        "invoicing_provider": "morning"
      }
    },
    {
      "tenant_id": "a92c7e10-...-uuid",
      "account_name": "jabaloola-inc",
      "bot_name": "Jabaloola",
      "godfathers": ["+972502222222", "+972502222223"],
      "admins": ["+972509999999"],
      "constitution_supplement_file": "config/tenants/jabaloola-inc/constitution_supplement.md",
      "capability_selection": {
        "messaging_provider": "green_api",
        "invoicing_provider": "morning"
      }
    }
  ]
}
```

`config/tenants/jabaloola-inc/constitution_supplement.md` is a plain markdown file — as long
(or short) as that tenant needs, edited like any other doc, not squeezed into a JSON string.

**`apps/denidin-app/config/config.dev.json`** (existing file, extended — everything else in it,
`data_root`/`ai_embedding_model`/`feature_flags`/etc., is unchanged; only the new
`tenant_credentials` map is shown):

```json
{
  "tenant_credentials": {
    "b6f1c2a4-...-uuid": {
      "green_api": {
        "instance_id": "1101...",
        "api_token": "d0d5...",
        "whatsapp_number": "+972501234567"
      },
      "openai": { "api_key": "sk-..." },
      "mcp_auth_token": "denidin-tenant-bearer-token-dev"
    },
    "a92c7e10-...-uuid": {
      "green_api": {
        "instance_id": "1102...",
        "api_token": "9fae...",
        "whatsapp_number": "+972502345678"
      },
      "openai": { "api_key": "sk-..." },
      "mcp_auth_token": "jabaloola-tenant-bearer-token-dev"
    }
  }
}
```

`config.prod.json` has the same shape, same `tenant_id` keys, but its own (different)
credentials and `mcp_auth_token` values per tenant — dev and prod never share a Green API
instance/OpenAI key/MCP token even for the same tenant (`data-model.md`).

Notes:
- No `morning` credential block anywhere in `denidin-app`'s config — Morning credentials live
  only in `morning-mcp-app`'s own config (below). `denidin-app` only needs each tenant's
  `mcp_auth_token` to call the shared MCP server as that tenant.
- ylevy's admin number (`+972509999999` above) is repeated in every tenant's `admins` list in
  `tenants.json` — deliberate, per the "config is sole source of truth, no break-glass"
  decision.
- `mcp_auth_token` values must be unique across all tenants *within one environment*
  (`contracts/invoicing-capability.md`).

**`apps/morning-mcp-app/config/config.dev.json`** (its own `mcp.ngrok_authtoken`/`status_file`
stay environment-level, shared by all tenants per `research.md` §4 — only the new
`tenant_credentials` map is shown):

```json
{
  "tenant_credentials": {
    "b6f1c2a4-...-uuid": {
      "mcp_auth_token": "denidin-tenant-bearer-token-dev",
      "api_key_id": "...",
      "api_key_secret": "...",
      "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1"
    },
    "a92c7e10-...-uuid": {
      "mcp_auth_token": "jabaloola-tenant-bearer-token-dev",
      "api_key_id": "...",
      "api_key_secret": "...",
      "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1"
    }
  }
}
```

`tenant_id` is the join key across all three files (`tenants.json`, and both apps'
`config.<env>.json`) — `speckit.tasks` should decide whether config-load validation enforces
agreement across them (recommended: e.g. every `tenant_credentials` key in `config.dev.json`
must exist in `tenants.json`), a task-level detail not decided here. `morning-mcp-app` also
needs `bot_name` for its own tenant-scoped log lines (REQ-LOG-001) — either it reads
`denidin-app`'s `tenants.json` directly (both apps already share a filesystem in this repo
layout) or keeps its own minimal `tenant_id → bot_name` copy; `speckit.tasks` decision.

---

## Onboarding a new tenant (manual, no tooling — per spec.md Assumptions)

1. Provision the tenant's own paid infrastructure outside the app: a Green API instance +
   WhatsApp Business number, a Morning account, an OpenAI API key.
2. Generate a `tenant_id` (UUID) and choose an `account_name` (slug) for this tenant.
3. Add an entry for this tenant to the **dev environment's** tenant list (`data-model.md`'s
   `Tenant` shape) — credentials, `godfathers`/`admins` phone numbers (ylevy's number MUST be
   included in `admins`), an empty or minimal `constitution_supplement`, and
   `capability_selection` (defaults: `green_api` / `morning`).
4. Restart the dev environment's shared services (`denidin-app-dev`, `morning-mcp-app-dev`) to
   pick up the new tenant.
5. Verify end-to-end in dev: message the tenant's WhatsApp number as a configured godfather,
   confirm a reply, confirm session/memory data lands under
   `{dev_data_root}/{tenant_id}/sessions/...` and nowhere else.
6. Once verified, add the same tenant entry to the **prod environment's** tenant list and
   restart prod's shared services (separate, explicit, human-approved deploy action — unchanged
   from every other environment-start rule in this repo).

## Verifying tenant isolation (SC-002)

1. With at least two tenants configured (A, B) in the same environment, message tenant A's
   WhatsApp number.
2. Confirm the reply came from tenant A's constitution/business rules (its
   `constitution_supplement` content, if distinctive).
3. Confirm no new file appeared under tenant B's data root
   (`{data_root}/{tenant_id_B}/...`) as a result of tenant A's message.
4. Ask tenant A's godfather to create a test invoice; confirm it lands in tenant A's Morning
   account only, using tenant A's `mcp_auth_token` — check `audit.py`'s log line records the
   correct `tenant_id`.

## Verifying super-admin access (SC-004)

1. From ylevy's phone number, message tenant A's WhatsApp number, then tenant B's.
2. Confirm `Role.ADMIN` resolution in both (e.g. ask "what version are you running?" in each —
   REQ-ROLE-004).

## Verifying capability degraded-start (REQ-CAP-005)

1. Configure a new tenant with `morning` credentials omitted from `capability_selection`.
2. Confirm the tenant's shared-service listener still starts and responds to plain messaging.
3. Confirm that tenant's godfather does NOT get the Morning MCP tool attached (no invoicing
   capability available), while messaging otherwise works normally.
