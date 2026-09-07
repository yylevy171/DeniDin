# Contract: Per-Environment MCP Status File

**Producer**: `morning-mcp-app-<env>` container
**Consumer**: `denidin-app-<env>` container (same `<env>` only — never the other one)
**Transport**: JSON file on a per-environment shared bind-mounted directory

## Schema

```json
{
  "status": "running",
  "server_url": "https://abc123.ngrok-free.app/mcp",
  "updated_at": "2026-07-20T12:00:00+00:00"
}
```

| Field | Type | Values | Notes |
|---|---|---|---|
| `status` | string | `"running"` \| `"not running"` | `"not running"` is the safe default, written before any tunnel attempt |
| `server_url` | string \| null | full MCP endpoint URL (`<tunnel>/mcp`), or `null` when not running | Consumer must not attempt to use a stale URL when `status != "running"` |
| `updated_at` | string | UTC ISO 8601 | Per CONSTITUTION §II — UTC always |

## Isolation guarantee

- `morning-mcp-app-dev` writes only to the dev shared volume; `morning-mcp-app-prod` writes only to the prod shared volume — these are distinct host directories, never the same one, never both mounted into the same container.
- `denidin-app-dev` has the dev shared volume mounted; it has **no mount at all** granting visibility into the prod shared volume (not read-only, not otherwise — entirely absent from its container spec). Same for `denidin-app-prod` in reverse.
- This means cross-environment resolution is impossible at the infrastructure level (no code path can be misconfigured into pointing at the wrong file, since the wrong file's directory tree isn't present in the container's filesystem at all).

## Failure behavior (unchanged from current single-environment implementation)

- Missing file, `status: "not running"`, or stale `updated_at` beyond `mcp.url_max_age_seconds` (denidin-app config) → consumer treats Morning MCP tool as unavailable for that turn and degrades gracefully (no crash, no retry storm).
