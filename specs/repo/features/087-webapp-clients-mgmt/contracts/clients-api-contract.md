# Integration Contract: Clients API (`apps/webapp/backend` ↔ frontend, and ↔ Morning API)

## 1. Frontend ↔ webapp-backend

### `GET /api/clients`
- Auth: same `SessionAuthMiddleware` bearer-token gate as every other `/api/*` route — no new auth code.
- Behavior: on each call, `ClientsReader.get_report_data()`:
  1. Fetches the live official client list directly from Morning via `MorningClient.search_clients()` (see §2 below) — no MCP, no AI call.
  2. Loads ledger events from `{denidin_data_root}/events` (read-only mount) via the existing `LedgerEventManager`-loader pattern (`ledger_reader.py`'s `_load_ledger_event_manager_class()`), read-fresh per call (this feature does not depend on bugfix-064's fix, but benefits from it — Events tab and Clients tab should both see current data once 064 lands).
  3. Loads `{webapp_data_root}/clients/{client_mapping,client_comments,mapping_notes}.json` — a separate, webapp-owned writable root (never `{denidin_data_root}/clients`; see data-model.md, corrected 2026-09-23). Dev/prod are seeded once from Rapaport's real live analyst files, not empty.
  4. Runs the ported aggregation/matching/status logic (`generate_client_status.py`'s behavior, unchanged).
  5. Overwrites `{webapp_data_root}/clients/{removed_clients,new_morning_clients}.json` (preserved side effect, per Clarifications).
  6. Returns `{ clients: ClientRow[], unmatched: UnmatchedEntry[] }` (data-model.md).
- Errors: if the Morning fetch fails (network error, 4xx/5xx from Morning, bad credentials), respond `503` with a friendly message — do NOT silently return ledger-only data with clients missing, since that would misrepresent debt/status. Frontend surfaces this as a retryable banner, not a partial table.

### `POST /api/clients/{client_id}/comments`
- Body/response: data-model.md.
- Persists to `{webapp_data_root}/clients/client_comments.json` (read-modify-write of the whole dict, matching current behavior).
- No re-run of the full aggregation — the frontend updates just that row's comment locally (per UAT-2's "immediately reflected... without page reload").

### `POST /api/clients/mapping`
- Body/response: data-model.md.
- Persists to `{webapp_data_root}/clients/client_mapping.json`.
- Per UAT-3 ("subsequent ledger queries reflect the resolved client profile"), the *next* `GET /api/clients` call picks up the new mapping — no separate re-aggregation trigger needed since GET always recomputes fresh.

## 2. webapp-backend ↔ Morning API (direct, via `MorningClient` import — new cross-app dependency)

- `apps/webapp/backend` imports `denidin_mcp_morning.morning_client.MorningClient` directly (code import, `apps/morning-mcp-app/src` added to `sys.path` the same way `apps/denidin-app/src` already is — see `webapp_backend/__init__.py`'s existing bootstrap pattern).
- `apps/webapp/backend` holds its **own** Morning API credentials (`api_key_id`/`api_key_secret`/`api_url`) in its own config (`config.dev.json`/`config.prod.json`) — a second, independently-configured credential set for the same Morning account, not shared/passed from `morning-mcp-app`.
- Call: `MorningClient(...).search_clients({})` (or the minimal payload needed for "all active clients") — a plain synchronous HTTPS call to Morning's real API. Retry-on-5xx/timeout is already built into `MorningClient`'s session (`_build_session`, urllib3 `Retry`) — no additional retry logic needed in webapp-backend.
- `morning-mcp-app`'s own service, container, ngrok tunnel, and MCP protocol are **entirely uninvolved** — this call works whether or not `morning-mcp-app` is running.
- Failure handling: any failure (network error, non-2xx, malformed response) propagates to `GET /api/clients`'s `503` path above — never a silent empty client list.

## 3. Frontend tab contract

- `App.tsx` owns a single `activeTab: "events" | "clients"` state (persisted to `localStorage`, same pattern as today's `settings.theme`).
- `EventsView` (today's Ledger UI, extracted verbatim) and `ClientsView` (new) are siblings, both receiving `theme` as a prop exactly as `App.tsx`'s current body does.
- `ClientsView` imports `clientsTheme.ts` for the preserved status-text color constants; it must never introduce its own background-color tints per the user's explicit UX direction.
