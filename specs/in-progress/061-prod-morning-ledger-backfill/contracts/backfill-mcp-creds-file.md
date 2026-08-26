# Contract: `backfill_mcp_creds.local.json`

**Feature**: 061-prod-morning-ledger-backfill
**Added**: 2026-08-26, alongside `select_method.generate_method_b_manifest`'s real implementation
(see `research.md` R7's "REDESIGNED" section).
**Path**: `apps/prod-ledger-backfill/config/backfill_mcp_creds.local.json` (gitignored — same
`*.local.json` convention as `backfill_prod_creds.local.json`/`backfill_sandbox_creds.local.json`).
**Created**: once by hand, by a human, never committed, never generated or written by any script.

A separate, distinct file from `backfill_prod_creds.local.json`/`backfill_sandbox_creds.local.json`
— those two deliberately hold **zero** MCP fields (see `backfill-creds-file.md`'s "What this file
deliberately does NOT contain": "No MCP bearer token, no `mcp.*` fields of any kind — this feature
never talks to `morning-mcp-app-prod`'s MCP server"). That statement is still true for Phase 1
(`download.py`, which only ever calls Green Invoice's real API directly via `MorningClient`).
Method B's generator (Phase 2 only, a one-time sandbox experiment) is the one and only part of
this feature that does talk to a live `morning-mcp-app` server, and needs its own small,
separately-scoped credentials file rather than reusing or reaching into either app's own config.

## Shape

```json
{
  "mcp_status_file": "/absolute/path/to/shared/mcp-status-dev/status.json",
  "mcp_auth_token": "REAL_MCP_BEARER_TOKEN",
  "mcp_server_label": "morning-invoices"
}
```

- **`mcp_status_file`** (string, required): absolute path to the shared JSON status file the
  target `morning-mcp-app` environment publishes (root `CLAUDE.md`'s `shared/mcp-status-dev/` /
  `shared/mcp-status-prod/` convention) — always the **dev/sandbox** one for this feature's Phase 2
  experiment, never `-prod`. Read directly, the same sanctioned cross-app discovery pattern
  `apps/denidin-app/src/handlers/morning_mcp_locator.py`'s `MorningMcpLocator` already uses
  (reading a shared file, never importing the other app's code or pinging it directly) —
  reimplemented independently here (`select_method._discover_mcp_server_url`), not imported.
- **`mcp_auth_token`** (string, required): the same bearer token value
  `apps/morning-mcp-app/config/config.dev.json`'s `mcp.auth_token` field holds for that
  environment — copy from `creds/DeniDin Dev Creds.txt` (this project's existing single source of
  truth for pasting real secrets from), never by direct-reading either app's own config file.
- **`mcp_server_label`** (string, optional, default `"morning-invoices"`): cosmetic label passed
  through to the `type: "mcp"` tool definition — matches `ai_handler.py`'s own default.

## Validation

Before making any real OpenAI/MCP call, `generate_method_b_manifest` MUST:
1. Fail with `MethodBUnavailableError` (a clear, friendly message) if this file does not exist.
2. Fail the same way if it exists but is malformed JSON, or is missing `mcp_status_file`/
   `mcp_auth_token`.
3. Fail the same way if `mcp_status_file` doesn't exist, isn't valid JSON, or its `status` field
   isn't `"running"` — i.e. `morning-mcp-app` dev/sandbox isn't actually up.

None of these checks make a network call — same fail-closed discipline as
`download.py`'s `load_credentials`/`backfill-creds-file.md`'s Phase-1 validation.

## What this file deliberately does NOT contain

- No Green Invoice API credentials (`api_key_id`/`api_key_secret`/`auth_url`/`base_url`) — those
  stay exclusively in `backfill_prod_creds.local.json`/`backfill_sandbox_creds.local.json`, used
  only by `download.py`.
- No OpenAI API key — `generate_method_b_manifest`'s real `OpenAI()` client (when not
  test-injected) picks up its key the same way `method_b.py`'s existing `transform()` already does
  (environment-provided, unchanged by this feature).
