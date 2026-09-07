# Phase 1 Data Model: Dev/Prod Environment Separation

No new persisted domain entities are introduced — this feature is a configuration/deployment topology change. The "entities" below are files/config shapes, not application data models.

## Environment Config (per app, per environment)

Same schema as today's `config.json` for each app (`AppConfiguration` for denidin-app, the flat `MorningConfig`-equivalent for morning-mcp-app) — only field *values* differ by environment. No schema/dataclass changes required.

| Field (denidin-app) | dev value | prod value |
|---|---|---|
| `data_root` | `dev_data` | `data` |
| `ai_api_key` / `ai_model` / `ai_vision_model` / `ai_embedding_model` | same as prod (shared OpenAI key) | production OpenAI key |
| `mcp.morning_status_file` | path inside dev's shared status volume | path inside prod's shared status volume |
| `mcp.morning_auth_token` | must match `config.dev.json`'s `mcp.auth_token` on morning-mcp-app side | must match prod's `mcp.auth_token` |
| `green_api_instance_id` / `green_api_token` | **identical to prod** — one real Green API instance shared by both environments (FR-014); only one of dev/prod denidin-app may actively poll at a time | identical to dev |
| `godfather_phone` | `972522968679` (ylevy) **or** unset — operator-switchable, mutually exclusive with `admin_phones` below (FR-015) | `972506205541` (AH), fixed |
| `admin_phones` | `["972522968679"]` (ylevy) **or** `[]` — operator-switchable, mutually exclusive with `godfather_phone` above | `["972522968679"]` (ylevy), fixed |

| Field (morning-mcp-app) | dev value | prod value |
|---|---|---|
| `api_key_id` / `api_key_secret` | Morning **sandbox** credentials | Morning **production** credentials |
| `api_url` | `https://sandbox.d.greeninvoice.co.il/api/v1/` | production Green Invoice API URL |
| `mcp.auth_token` | dev shared secret (matches denidin-app dev config) | prod shared secret |
| `mcp.ngrok_authtoken` | dev ngrok account's authtoken | prod ngrok account's authtoken (separate account) |
| `mcp.status_file` | path inside dev's shared status volume | path inside prod's shared status volume |

**Validation rules**: unchanged from today's `AppConfiguration.validate()` / morning-mcp-app's config loader — no new required fields, only new *files* holding existing fields.

## Status File (per environment)

```json
{
  "status": "running" | "not running",
  "server_url": "https://<tunnel>.ngrok-free.app/mcp" | null,
  "updated_at": "<UTC ISO8601>"
}
```

- **Producer**: `morning-mcp-app-<env>` container.
- **Consumer**: `denidin-app-<env>` container (same env only).
- **Lifecycle**: Overwritten on every tunnel start/stop/restart; no history retained (matches today's behavior, just relocated).
- **State transitions**: `not running` (default/safe state, written before any tunnel attempt) → `running` (once ngrok confirms a live HTTPS tunnel). No other states.

## Shared Status Volume (per environment)

- **Identity**: A host directory (`./shared/mcp-status-dev/`, `./shared/mcp-status-prod/`) bind-mounted into exactly 2 containers each.
- **Membership rule**: `mcp-status-dev` → {`denidin-app-dev`, `morning-mcp-app-dev`} only. `mcp-status-prod` → {`denidin-app-prod`, `morning-mcp-app-prod`} only. No container is ever a member of the other environment's volume — this is what makes cross-environment MCP resolution structurally impossible (FR-010), not merely a config convention.

## PID File — removed, not replaced

Per research.md's decision, the host-level PID-file entity from the current implementation is deleted, not carried forward. Docker Compose's own container-identity tracking is the sole "is this already running" mechanism going forward.
