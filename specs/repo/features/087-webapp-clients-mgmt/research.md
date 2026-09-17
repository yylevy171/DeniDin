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

## Open technical questions for Phase 1 (to resolve during data-model/contract design, not blocking)

1. **Morning client-list fetch shape**: `apps/morning-mcp-app` already exposes `list_clients` as an MCP tool consumed via the Responses-API remote-MCP mechanism inside `denidin-app`'s `AIHandler` — that mechanism is OpenAI-Responses-API-shaped (tool-call protocol), not a plain HTTP endpoint a non-AI backend can call directly. `apps/webapp/backend` has no OpenAI client and no reason to add one just to list clients. Two options for Phase 1:
   - (a) Call `morning-mcp-app`'s FastMCP server directly over its streamable-HTTP MCP protocol (bearer-auth, same tunnel/status-file discovery denidin-app uses) using a minimal MCP client — no OpenAI involved, this is a direct tool invocation.
   - (b) Ask `morning-mcp-app` to expose a small additional plain-HTTP `/clients` read route alongside its MCP surface, specifically for non-AI callers like the webapp.
   Recommendation for data-model.md/contract: (a), since it requires no change to `morning-mcp-app` and matches "webapp reaches other apps only over HTTP" without inventing a new plain-REST surface on an MCP-only service. Confirm feasibility (a minimal MCP client call from Starlette) during Phase 1 before locking the contract.
2. **`generate_client_status.py` porting shape**: the routing logic (green/red/yellow bucket assignment) currently lives split between `generate_client_status.py` (aggregation) and `mapping_server.py` (bucket routing + HTML rendering). Phase 1's `clients_reader.py` must merge both into one importable pure-data function (returns structured per-client dicts with a `status` field), with only the *presentation* (colors/HTML) left to the frontend.
3. **Fuzzy-matching dependency**: `fuzzy_match()` uses stdlib `difflib` — no new dependency needed for the port.
4. **Retry/backoff for Morning-MCP status-file discovery**: per Constitution Check gate on §XVIII, reuse `denidin-app`'s existing bounded-retry pattern (see `ai_handler.py`'s MCP status-file read) rather than a fresh one-shot implementation in webapp-backend.

## Alternatives considered

- **Import `morning-mcp-app`'s Python client library directly** (like the webapp already does for `denidin-app`'s managers): rejected — CLAUDE.md's cross-app-import exception is scoped specifically to `webapp` reading `denidin-app`'s *data*, not to importing another *service's* code; `morning-mcp-app` is reached only over HTTP by every other app, and this feature should not be the first exception to that.
- **Cache the Morning client list backend-side with a TTL**: rejected by explicit user decision (fetch fresh every load/reload) — simpler, and the client roster is small enough that a live fetch's latency is acceptable.
