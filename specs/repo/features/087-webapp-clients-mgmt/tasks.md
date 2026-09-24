# Tasks: Clients Management UI in Webapp

**Input**: plan.md, data-model.md, contracts/clients-api-contract.md

**Note (2026-09-23)**: tasks below reference the original `{data_root}/clients` /
`clients_data_root: {denidin_data_root}/clients` design as it was actually implemented at
the time (kept as an accurate historical record, `[x]` entries unchanged). That design was
found wrong post-implementation — `denidin_data_root` is a read-only mount and must stay
read-only — and was corrected to a separate, webapp-owned writable `webapp_data_root`
(`clients_data_root` now defaults under `webapp_data_root`, not `denidin_data_root`); dev/prod
are also seeded once from Rapaport's real live analyst files rather than starting empty. See
the corrected REQ-087-04 in spec.md, data-model.md, plan.md, and contracts/clients-api-contract.md.

## Phase 1: Backend — Clients data service

- [x] T001: `apps/webapp/backend/src/webapp_backend/clients_reader.py` — port `generate_client_status.py` + `mapping_server.py`'s bucket-routing logic into one importable `ClientsReader` class: `get_report()` returns `{clients, unmatched}` (data-model.md `ClientRow`/`UnmatchedEntry`), reading ledger events via the existing `LedgerEventManager` loader, official clients from an injected list (from `morning_client_source.py`), and state from `{data_root}/clients/*.json`. Preserves: fuzzy matching, comment-driven status rules, merge/check/active/settle/delete directives, side-effect writes to `removed_clients.json`/`new_morning_clients.json`.
- [x] T002: `apps/webapp/backend/src/webapp_backend/morning_client_source.py` — thin wrapper importing `denidin_mcp_morning.morning_client.MorningClient`, calling `search_clients()` for the active client list, using this app's own Morning credentials.
- [x] T003: `apps/webapp/backend/src/webapp_backend/config.py` — add `clients_data_root` (default `{denidin_data_root}/clients`), `morning_api_key_id`/`morning_api_key_secret`/`morning_api_url`, `morning_src_path`.
- [x] T004: `apps/webapp/backend/src/webapp_backend/server.py` — add `GET /api/clients`, `POST /api/clients/{client_id}/comments`, `POST /api/clients/mapping` routes per contracts/clients-api-contract.md; wire `ClientsReader` in `build_app()`.
- [x] T005: `apps/webapp/backend/config/config.example.json` (+ dev/test if present) — document new fields.

## Phase 2: Frontend — Two-tab shell

- [x] T006: `apps/webapp/frontend/src/App.tsx` — introduce `activeTab` state ("events"|"clients", persisted), shared header (logo + tab buttons + settings gear), extract today's full Ledger body into `EventsView`.
- [x] T007: `apps/webapp/frontend/src/EventsView.tsx` — today's Ledger view, functionally unchanged, as its own component receiving `theme`/`settings`/`onAuthErr`.
- [x] T008: `apps/webapp/frontend/src/clientsTheme.ts` — the preserved mapping-tool status TEXT color constants (settled/debt/inferred/overridden/active-accent).
- [x] T009: `apps/webapp/frontend/src/ClientsView.tsx` — table grouped by section (active/settled/debt/missing-agreement/past/check), inline comment editor, alias-mapping UI for unmatched names, all styled with webapp theme + `clientsTheme.ts` text colors.
- [x] T010: `apps/webapp/frontend/src/api.ts` — add `fetchClients()`, `saveClientComment()`, `saveClientMapping()`.

## Phase 3: Verification

- [x] T011: `speckit.analyze` cross-artifact consistency pass. Found and fixed: `config.clients_data_root` was added to `AppConfig` but never actually threaded through to `ClientsReader` (which derived its own `{data_root}/clients` path instead) — `ClientsReader.__init__` now takes `clients_data_root` explicitly and `server.py` passes `config.clients_data_root`.
- [x] T012: Programmatic smoke test — `ClientsReader.get_report()` exercised end-to-end against synthetic events (agreements/invoices/unmatched-name fuzzy-matching/comment-driven status override all verified), full existing webapp-backend test suite re-run (82/82 passed, no regressions), frontend `npm run build` clean. Manual click-through in a real browser is still pending human verification since this session has no browser-automation access.
- [x] T013: Playwright acceptance for UAT-1/2/3 + the "served from memory, reload only on refresh" behavior — `apps/webapp/e2e/tests-clients/10-clients.spec.ts` (own config `playwright.clients.config.ts`, real backend + Morning SANDBOX, no mocking; 6/6 green). It caught a real refetch-on-tab-switch bug (unstable `onAuthErr` in `App.tsx`), fixed in the same change. Not written: a separate backend-only `tests/integration/test_clients_api.py` (the e2e suite exercises the same API end-to-end).
