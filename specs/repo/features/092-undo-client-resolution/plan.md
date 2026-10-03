# Implementation Plan: Feature 092 — Clients Tab: Resolution Corrections & Explicit Line Status

**Branch**: `feature/092-undo-client-resolution-bugfix-068` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: `specs/repo/features/092-undo-client-resolution/spec.md` (acceptance scenarios approved 2026-10-03)

## Summary

This feature has three parts:
- It replaces the three comment keywords that route a Clients-tab line (`לסגור`, `לבדוק`,
  `לקוח פעיל`) with a persisted per-line status driven by four buttons.
- It deletes the `לסגור` amount-rewriting hack (bugfix-068).
- It fixes three gaps in the names-to-resolve table: per-event `Unknown-<event_id>` names, undo
  for explicit name mappings, and a "הסר מהרשימה" button. It also adds ESC to close the client
  dropdown.

The core idea is to change only **where `_row_status`'s flags come from**, never the routing
itself. A one-shot, idempotent migration converts today's comment keywords into statuses, so
no line moves on deploy.

## Technical Context

**Language/Version**: Python 3 (webapp backend, Starlette); TypeScript (Vite + react-native-web frontend)  
**Primary Dependencies**: existing only (Starlette, difflib). No new packages.  
**Storage**: JSON files in `clients_data_root`. 3 new files, see `data-model.md`.  
**Testing**:
- backend `pytest`, both unit and integration via Starlette `TestClient`, with real files in
  `tmp_path` and no mocks;
- Playwright acceptance in `apps/webapp/e2e/tests-clients/`, against the real backend and the
  Morning sandbox.

**Target Platform**: webapp backend/frontend containers (dev on the Mac, prod on the Windows box)  
**Project Type**: web (backend + frontend)  
**Performance Goals**: no regression. A button press costs one write plus one cached-report recompute, with no Morning call.  
**Constraints**:
- the ledger (`denidin_data_root`) stays read-only;
- no `denidin-app` / `morning-mcp-app` change;
- no env vars;
- Israel-local timestamps (`now_local`).

**Scale/Scope**: hundreds of client lines and tens of unmatched names. 4 backend files touched, plus `ClientsView.tsx` / `api.ts` / `clientsTheme.ts`.

## Constitution Check

| Rule | Status | Note |
|---|---|---|
| Zero mocking / §V integration tests | ✅ | Unit tests use real files in `tmp_path`. Integration tests go through `TestClient` → the real routes. Playwright uses the real backend and the Morning sandbox. |
| No unverified third-party assumptions | ✅ | The sandbox client count was verified live (research R-10). Nothing new is assumed about Morning. |
| §I No env vars / config via `AppConfig` | ✅ | No new config keys needed. |
| §II Israel local time | ✅ | The migration marker uses `now_local()`. |
| §III Git workflow | ✅ | Feature branch, single PR. |
| §VI Feature flags | ⚠️ **Deviation proposed** | See Complexity Tracking / research R-9. **Needs user approval.** |
| §VIII Test immutability | ✅ | Existing `10-clients.spec.ts` and `test_caching.py` are untouched. New tests are added in new files. |
| §IX Logging | ✅ | INFO for each status change, unlink and hide (client, action, result). WARNING for an unknown stored status or an event with no `event_id`. |
| §X Error format | ✅ | Existing `_error()` shape, with Hebrew user-facing messages. |
| §XIV `pathlib` | ✅ | Same as the existing `_paths()`. |
| §XVII No monkey-patching | ✅ | New functions plus constructor-injected readers only. |
| §XIX No bare pytest (agents) | ✅ | Tests run via the wrapper (see quickstart §1). |
| METHODOLOGY §XXI constitution boundaries | N/A | No new bot tools. This is webapp only. |

## Design

### Backend — `clients_reader.py`

1. **`_aggregate_events`** — `Unknown-<event_id>` naming (research R-5).
2. **New `_apply_line_status(stats, client_status)`** — sets
   `is_check` / `is_active_client` / `is_manually_settled` from `client_status.json`.
3. **`_apply_status_directives`** —
   - remove the `לקוח פעיל`, `לבדוק` and `לסגור` branches, including the whole amount hack
     (lines 338–339 and 353–375 at `f096e06`);
   - keep the delete branch and `removed_clients` exactly as they are.
4. **New `_legacy_comment_status(comment)`** — a frozen copy of the old detection, used only by
   the migration (R-4).
5. **`ClientsReader`** —
   - `_paths()` gains `status`, `hidden` and `migrations`;
   - `_compute_report()` runs `_migrate_comment_status_once()` first, then wires
     `_apply_line_status`;
   - `_split_unmatched` skips hidden names;
   - `_build_client_rows` adds `line_status` and `mapped_aliases`;
   - new methods `set_line_status(client_id, action)`, `unlink_mapping(raw_name)` and
     `hide_unmatched(raw_name)`, all invalidating the report cache.
6. **`reopen`** — computes the line with its status cleared, reusing the same pure functions
   (R-3).

### Backend — `server.py`

Three routes per `contracts/clients-api.md`, following the shape of the existing
`client_comment`/`client_mapping` handlers: `run_in_threadpool` and `_error`.

### Frontend

- **`api.ts`** —
  - `ClientRow` gains `line_status` and `mapped_aliases`;
  - new functions `setClientLineStatus`, `unlinkClientMapping` and `hideUnmatched`.
- **`ClientsView.tsx`** — `ClientRowCard` header gets a button group (hidden for `past`):
  - green **לסגור** / gray **לפתוח**;
  - blue **לבדוק**;
  - light-blue **לקוח פעיל**;
  - hide a button whose target is the current section;
  - presses must not toggle row expansion;
  - after each action, re-fetch `GET /api/clients`.
- **`ClientsView.tsx`, other changes** —
  - each alias in `mapped_aliases` gets an unlink "×" in the expanded row;
  - `UnmatchedRowCard` gets a **הסר מהרשימה** button;
  - `ClientPicker` gets the ESC `keydown` effect (R-8).
- **`clientsTheme.ts`** — button shades are derived from the existing `CLIENT_STATUS_COLORS`.
  No new palette.

## Integration Contracts (METHODOLOGY §VII)

| From → To | Contract |
|---|---|
| Frontend → backend | `contracts/clients-api.md` (3 new POSTs; additive `GET /api/clients` fields) |
| Backend → files | `data-model.md` (3 new JSON files; `client_mapping.json` gains delete) |
| Backend → ledger | Unchanged and read-only. It only reads `event_id`, which is already in every event record. |
| Old version ↔ new files | The old version ignores `client_status.json` / `hidden_unmatched.json` / `migrations.json`, which makes rollback safe (quickstart §4). |

## Phasing (for `speckit.tasks`)

| Phase | Stories | Content |
|---|---|---|
| 1 | US1, US2, US3 (P1) | Line status file, `_apply_line_status`, hack removal, migration and parity tests, status endpoint, buttons |
| 2 | US4, US5 (P2) | `Unknown-<event_id>`, `mapped_aliases`, unlink endpoint and UI |
| 3 | US6, US7 (P3) | Hide endpoint and button, ESC |
| 4 | Acceptance | Extend `seed_clients_fixture.py` (several sandbox clients, Unknown events, pre-seeded keyword comments); new `tests-clients/11-line-status-and-resolution.spec.ts` covering UAT 1–9; `preview_092_migration.py` (quickstart §3) |

Each phase follows Task A (tests, RED, human approval) before Task B (implementation, GREEN),
per METHODOLOGY §VI.b.

## Project Structure

```text
specs/repo/features/092-undo-client-resolution/
├── spec.md  user-stories.md  plan.md  research.md  data-model.md  quickstart.md
└── contracts/clients-api.md

apps/webapp/backend/
├── src/webapp_backend/clients_reader.py      # bulk of the change
├── src/webapp_backend/server.py              # 3 routes
├── scripts/preview_092_migration.py          # new, read-only
└── tests/
    ├── unit/test_clients_line_status.py      # new: routing, hack removal, migration parity
    ├── unit/test_clients_resolution.py       # new: Unknown naming, unlink, hide, mapped_aliases
    └── integration/test_clients_endpoints.py # new: the 3 routes end-to-end via TestClient
apps/webapp/frontend/src/{ClientsView.tsx, api.ts, clientsTheme.ts}
apps/webapp/e2e/
├── seed_clients_fixture.py                   # extended (additive; existing manifest keys kept)
└── tests-clients/11-line-status-and-resolution.spec.ts   # new
```

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **No feature flag (§VI)** — pending user approval | Part of this is a data-corruption bug fix, and the migration writes a new source of truth. | A flag-off path keeps the hack live by default. Toggling would let `client_status.json` and comment routing diverge and silently move lines. The versioned release rollback already restores the old behavior exactly (quickstart §4). Same call as Feature 087's plan. Research R-9. |
