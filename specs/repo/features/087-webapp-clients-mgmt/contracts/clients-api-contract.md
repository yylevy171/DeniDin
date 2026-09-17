# Integration Contract: Clients API (`apps/webapp/backend` ↔ frontend, and ↔ `morning-mcp-app`)

## 1. Frontend ↔ webapp-backend

### `GET /api/clients`
- Auth: same `SessionAuthMiddleware` bearer-token gate as every other `/api/*` route — no new auth code.
- Behavior: on each call, `ClientsReader.get_report_data()`:
  1. Fetches the live official client list from `morning-mcp-app` (see §2 below).
  2. Loads ledger events from `{data_root}/events` via the existing `LedgerEventManager`-loader pattern (`ledger_reader.py`'s `_load_ledger_event_manager_class()`), read-fresh per call (this feature does not depend on bugfix-064's fix, but benefits from it — Events tab and Clients tab should both see current data once 064 lands).
  3. Loads `{data_root}/clients/{client_mapping,client_comments,mapping_notes}.json`.
  4. Runs the ported aggregation/matching/status logic (`generate_client_status.py`'s behavior, unchanged).
  5. Overwrites `{data_root}/clients/{removed_clients,new_morning_clients}.json` (preserved side effect, per Clarifications).
  6. Returns `{ clients: ClientRow[], unmatched: UnmatchedEntry[] }` (data-model.md).
- Errors: if the Morning fetch fails (tunnel down, MCP unavailable), respond `503` with a friendly message — do NOT silently return ledger-only data with clients missing, since that would misrepresent debt/status. Frontend surfaces this as a retryable banner, not a partial table.

### `POST /api/clients/{client_id}/comments`
- Body/response: data-model.md.
- Persists to `{data_root}/clients/client_comments.json` (read-modify-write of the whole dict, matching current behavior).
- No re-run of the full aggregation — the frontend updates just that row's comment locally (per UAT-2's "immediately reflected... without page reload").

### `POST /api/clients/mapping`
- Body/response: data-model.md.
- Persists to `{data_root}/clients/client_mapping.json`.
- Per UAT-3 ("subsequent ledger queries reflect the resolved client profile"), the *next* `GET /api/clients` call picks up the new mapping — no separate re-aggregation trigger needed since GET always recomputes fresh.

## 2. webapp-backend ↔ morning-mcp-app (new cross-app call)

- Discovery: read the environment's `shared/mcp-status-<env>/` status file (same file `denidin-app` reads) to get the live ngrok tunnel URL — reuse `denidin-app`'s bounded-retry-with-backoff pattern for this read, not a one-shot check (Constitution Check §XVIII gate).
- Call: a minimal MCP client invocation of `morning-mcp-app`'s `list_clients` tool over its streamable-HTTP MCP endpoint, bearer-authed with the same shared secret `denidin-app` uses (`config.mcp.auth_token`-equivalent, added to `apps/webapp/backend`'s own config).
- No code import of `denidin_mcp_morning` — HTTP/MCP-protocol only, consistent with every other cross-app boundary in this repo.
- Failure handling: any failure (tunnel down, timeout, malformed response) propagates to `GET /api/clients`'s `503` path above — never a silent empty client list.

## 3. Frontend tab contract

- `App.tsx` owns a single `activeTab: "events" | "clients"` state (persisted to `localStorage`, same pattern as today's `settings.theme`).
- `EventsView` (today's Ledger UI, extracted verbatim) and `ClientsView` (new) are siblings, both receiving `theme` as a prop exactly as `App.tsx`'s current body does.
- `ClientsView` imports `clientsTheme.ts` for the preserved status-text color constants; it must never introduce its own background-color tints per the user's explicit UX direction.
