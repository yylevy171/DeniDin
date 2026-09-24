# Phase 0 Research: Clients Management UI in Webapp

## Decisions (from Clarifications session 2026-09-17)

| Question | Decision | Rationale |
|---|---|---|
| Official client list source | Fetch live from Morning on each `GET /api/clients` (no CSV, no cache) | Avoids stale/missing-CSV problem found during investigation; Morning is already the source of truth `denidin-app` trusts |
| Agreement/deposit/invoice amounts source | Same environment-scoped `{data_root}/events` ledger the Events tab reads | Removes the hardcoded `~/denidin-winprod-data/events` sshfs path; makes dev environment usable for the first time |
| Comment-parsing business rules | Port as-is, unchanged | User confirmed functionality "is doing great" — behavior preservation over refactor |
| Read-side-effect (write `removed_clients.json`/`new_morning_clients.json` on every GET) | Preserve exactly | User explicitly chose to keep current behavior over making reads pure |
| State file location | Move to `{data_root}/clients/` (env-scoped) | REQ-087-04; fixes the current unscoped `reports/mapping_tool/` location that can't distinguish dev/prod |
| Tabs | "ארועים" (Events, today's Ledger UI) + "לקוחות" (Clients, new) | User's explicit framing |
| Theme | webapp chrome as base; mapping tool's status **text** colors (not backgrounds) preserved | User's explicit UX direction |
| Morning client-list fetch mechanism | Direct import of `MorningClient.search_clients()`, no MCP/AI/tunnel | User's explicit direction: "webapp backend can just use morning directly, no ai calls — all it needs is a list of all the active clients" |

## Resolved: Morning client-list fetch shape

Originally flagged as an open question (MCP-protocol client vs. a new plain-HTTP route
on `morning-mcp-app`) — resolved by the user directly: skip both. `apps/webapp/backend`
imports `denidin_mcp_morning.morning_client.MorningClient` (a plain Python class with a
`requests` session, no FastMCP/no server process involved) and calls `search_clients()`
with its own Morning API credentials. This is simpler than either original option:
- No dependency on `morning-mcp-app`'s container, ngrok tunnel, or status file being up.
- No MCP client implementation needed in webapp-backend.
- `apps/webapp/backend` needs its own `api_key_id`/`api_key_secret`/`api_url` config
  fields (same shape `morning-mcp-app`'s own config already uses) — a second set of
  credentials for the same Morning account, since each service authenticates
  independently (`MorningClient.__init__` takes credentials directly, no shared token
  cache between processes).
- This is a second precedent for "webapp imports another app's code directly" (the
  first being `denidin-app`'s managers) — `denidin_mcp_morning` is a plain importable
  package (`apps/morning-mcp-app/src/denidin_mcp_morning/`), so this follows the exact
  same mechanical pattern `ledger_reader.py` already uses, just pointed at a different
  app's `src/`.

## Remaining open technical questions for Phase 1

1. **`generate_client_status.py` porting shape**: the routing logic (green/red/yellow bucket assignment) currently lives split between `generate_client_status.py` (aggregation) and `mapping_server.py` (bucket routing + HTML rendering). Phase 1's `clients_reader.py` must merge both into one importable pure-data function (returns structured per-client dicts with a `status` field), with only the *presentation* (colors/HTML) left to the frontend.
2. **Fuzzy-matching dependency**: `fuzzy_match()` uses stdlib `difflib` — no new dependency needed for the port.
3. **`morning-mcp-app`'s `src/` on `sys.path`**: confirm `apps/webapp/backend`'s import bootstrap can add a second app's `src/` (its own for `denidin-app`, now also `morning-mcp-app`'s) without either package's modules colliding by name — quick sanity check during task implementation, not expected to be an issue (`denidin_mcp_morning` vs. denidin-app's flat `managers`/`handlers` packages don't overlap).

## Alternatives considered

- **Call `morning-mcp-app`'s MCP server directly (minimal MCP client, no AI)**: rejected by the user — adds tunnel/status-file dependency and an unnecessary protocol layer for something as simple as listing clients.
- **Add a new plain-HTTP `/clients` route to `morning-mcp-app`**: rejected — unnecessary service-surface growth when a direct `MorningClient` import does the job with less moving parts.
- **Cache the Morning client list backend-side with a TTL**: rejected by explicit user decision (fetch fresh every load/reload) — simpler, and the client roster is small enough that a live fetch's latency is acceptable.
