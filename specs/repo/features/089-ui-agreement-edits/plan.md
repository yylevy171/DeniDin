# Implementation Plan: Edit Agreements from UI & WhatsApp (089)

**Branch**: `feature/089-ui-agreement-edits` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)
**Input**: `spec.md`, `user-stories.md` (acceptance scenarios approved 2026-10-09)

**Gate 0 (METHODOLOGY section VI.a)**: PASSED. The `billed`/`expensive`/UI acceptance scenarios in
`user-stories.md` were approved by the human on 2026-10-09 (see its Approval block).

## Summary

Add an **Agreements DB** (SQLite, owned by denidin-app) as the living source of truth for fee
agreements: an agreement container with fee components, four-state lifecycle, a chronological
revision log. Every write, from the webapp or the WhatsApp bot, goes to that DB first; the DB
write then produces the matching ledger events. denidin-app gains a small bearer-authenticated
HTTP API; the webapp backend proxies it behind its existing session gate; the Clients tab gets a
"הסכמים" section with create/edit/delete/lifecycle/history dialogs and its agreed total switches to
the DB. The WhatsApp bot reads from the DB through two new capabilities and writes through the
same manager; agreement capture from documents is rewired to write the DB instead of the ledger.
A one-time, two-step migration moves existing ledger agreements into the DB and rewrites those
events to ledger schema v4.

## Technical Context

**Language/Version**: Python 3.11 (denidin-app, webapp backend), TypeScript/React Native Web (frontend)  
**Primary Dependencies**: SQLite (stdlib); **new in denidin-app: `starlette`, `uvicorn`** (approved 2026-10-09, R3); existing `rapidfuzz`, OpenAI Responses API via the backbone  
**Storage**: `{data_root}/agreements/agreements.db`; ledger events stay JSON files; migration marker file  
**Testing**: pytest via `scripts/run_unit_integration_tests.sh`; `billed` via `scripts/run_single_test.sh`; Playwright in `apps/webapp/e2e`  
**Target Platform**: Docker containers (dev local, prod on the Windows box); no new container  
**Project Type**: multi-app (denidin-app + webapp backend + webapp frontend + e2e)  
**Performance Goals**: API p95 under 200 ms for a client with 50 components; the Clients report must not do N API calls (one bulk `totals` call)  
**Constraints**: no env vars; Israel local time (`now_local()`); `pathlib`; no monkey-patching; no feature flag (REQ-089-17); webapp mount of denidin-app data stays read-only; ledger writes only through `LedgerEventManager`  
**Scale/Scope**: low hundreds of agreements, a handful of components each, single operator  

## Constitution Check

| Rule | Status |
|---|---|
| No environment variables (config only) | OK: API port/token in `config.agreements_api`, webapp URL/token in its config; both example files updated |
| Israel local time, `now_local()` | OK: all DB/revision timestamps |
| `pathlib.Path` | OK |
| No monkey-patching; DI | OK: `AgreementsManager(denidin)` per REQ-063-08; API gets the manager injected |
| Feature flag | None, by human decision REQ-089-17; rollback = previous release |
| Zero mocking; integration tests via a real entry point | OK: API tests use Starlette `TestClient` against a real manager + real `LedgerEventManager` on a tmp data root; no `unittest.mock` in `tests/integration/` |
| Config is baked or mounted correctly (bugfix-066) | OK: prompts and `runtime_constitution.md` baked, only `config.<env>.json` mounted |
| Tool-bearing feature needs constitution boundaries | PLANNED (Phase E, T030-T032): new section + two-way cross-references |
| Ledger schema bump is human-only | APPROVED 2026-10-09: bump to v4 with the full field list (R5) |
| Startup handshakes must retry (section XVIII) | N/A for denidin-app (API is a server, not a client). Webapp -> API is request-time, fails closed with an explicit error |
| No bare `pytest` | OK: wrappers only |
| Test sound-off per test | OK: `conftest.py` default |
| Other apps in scope (checked 2026-10-09) | `morning-mcp-app`: no change. Feature 025 reconciliation: writes `חשבונית` events only, unaffected (verified by the T050 regression run). WhatsApp-export player: goes through `initialize_app` and the shared recognizer, so it inherits the capture rewiring. `apps/prod-ledger-backfill` and `apps/rolling-memory-backfill`: write no `הסכם` events; only a smoke check that v4 stays compatible |
| Migration against prod | Gated: its own explicit human go-ahead, never during development |

**Human decisions taken (2026-10-09)**, all three resolved:

1. **Ledger schema bumps to v4** (skipping 3, which a reverted change once stamped), with the full field list: `original_client_name`, `component_status`, `agreement_status`, and `split_partner`/`split_percent` populated (R5).
2. **A web server is added to denidin-app**: `starlette` + `uvicorn` (R3).
3. **The Agreements API must be reachable by the webapp backend only**, never by the frontend. In Docker the backend uses the compose service name, so nothing is published; `dev` additionally publishes on `127.0.0.1` for the non-Docker `run_webapp.sh host` mode (R3).

Re-check after Phase 1 design: no new violations; the open gates above are unchanged.

## Integration Contracts (METHODOLOGY section VII)

### Webapp frontend <-> Webapp backend
**Frontend MUST**: call only `/api/agreements/...` and `/api/clients/{id}/agreements` with its
session token; treat `locked: true` as authoritative for disabled controls; show the API error text on `4xx`.
**Backend PROVIDES**: the JSON shapes in `contracts/agreements-api.md` unchanged; `401` without a session; `502 agreements_unavailable` when denidin-app is unreachable; never exposes the denidin-app token.
**Backend EXPECTS**: well-formed JSON bodies; it does not validate business rules (the API does) beyond shape.

### Webapp backend <-> Agreements API
**Backend MUST**: send the bearer token and `"actor": "webapp"` on every write; use `GET /agreements/totals` once per Clients report build; treat any non-2xx or timeout (5 s) as "unavailable" for the affected section, not as zero.
**API PROVIDES**: the routes and error codes in `contracts/agreements-api.md`; each write is atomic (DB + cascade) and returns the new state and `ledger_event_ids`; `locked` computed server-side; identical request twice yields one revision (idempotent no-op).
**API EXPECTS**: `client_name` equal to the official Morning name; amounts as integers; whitelisted `PATCH` fields only.

### Agreements API / Bot tools <-> AgreementsManager
**Callers MUST**: pass `actor` (`webapp` or `whatsapp`) and never touch SQLite or ledger files directly.
**AgreementsManager PROVIDES**: `create_agreement`, `create_from_capture`, `edit_agreement`, `add_component`, `edit_component`, `set_component_status`, `set_agreement_status`, `delete_component`, `get_agreement`, `find_agreements`, `totals`, `revisions`. Every mutating call: validates, applies state rules and the cascade, commits DB + revision in one transaction, then writes the ledger events under the same lock, returns `(agreement, ledger_event_ids)`.
**AgreementsManager EXPECTS**: a resolved official `client_name`; a `DeniDin` object exposing `ledger_event_manager` and `config`.

### AgreementsManager <-> LedgerEventManager
**AgreementsManager MUST**: call only the existing public persist API extended for v4 (new optional kwargs); hold the manager write lock across all events of one write; pass `reference_override=<origin_event_id>` for deletes.
**LedgerEventManager PROVIDES**: one persisted v4 `הסכם` event per call, returning its `event_id`; unchanged behaviour for every other `source_type` and for hours-worked lines.
**LedgerEventManager EXPECTS**: `source_type=הסכם` events from this path carry `hours=None`; the three new fields plus `split_*` are optional and null elsewhere.

### LedgerEventRecognizer <-> AgreementsManager
**Recognizer MUST**: route a complete agreement verdict (non-hours) to `create_from_capture` and leave bank, invoice, hours-worked and incomplete-capture handling exactly as today.
**AgreementsManager PROVIDES**: the same dedup guarantee the ledger path gave (a re-recognized document does not create a second agreement; keyed by content fingerprint of client + label + amount/percent + date).
**EXPECTS**: the verdict's `components` array as produced today.

### Backbone <-> Agreements capabilities
**Backbone MUST**: load `cap_agreements_read`/`cap_agreements_write` only when the model asks; route every write through `approval_with_yes_no_buttons`; never attach these tools to a non-godfather/admin role.
**Capability PROVIDES**: tool results as JSON strings; errors as `error: <reason>` strings the model can relay (including `locked`).
**Capability EXPECTS**: `client_name` already resolved via `cap_client_read`; ambiguity (multiple agreements) is returned to the model, which asks the user (no auto-pick).

### Migration scripts <-> operator
**Export script PROVIDES**: `name_resolution.json` (data-model.md), read-only on webapp and denidin data.
**Migration script MUST**: take a backup of every event file before rewriting, be a no-op on a second run (marker), refuse to run without `--resolution`, print counts on `--dry-run` and write nothing.
**Operator MUST**: rehearse on a copy first; run on prod only with an explicit go-ahead.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/089-ui-agreement-edits/
├── spec.md  user-stories.md  README.md
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/agreements-api.md
└── tasks.md            # next: /speckit.tasks (not created here)
```

### Source Code

```text
apps/denidin-app/
├── src/managers/agreements_manager.py          # NEW: DB, state rules, cascade, ledger mapping
├── src/managers/ledger_event_manager.py        # v4 fields, SCHEMA_VERSION_HISTORY entry
├── src/managers/ledger_event_recognizer.py     # route agreement verdicts to AgreementsManager
├── src/services/agreements_api.py              # NEW: Starlette app + standalone entry point
├── src/capabilities/agreements/{tools,handler}.py   # NEW: cap_agreements_read/write
├── src/capabilities/toolsets.py                # register tools
├── src/backbone/capability_tags.py             # tags + catalog text
├── config/prompts/capabilities/cap_agreements_{read,write}.md   # NEW
├── config/prompts/flows/flow_agreement_management.md            # NEW
├── config/runtime_constitution.md              # new section + cross-references
├── config/prompts/capabilities/cap_ledger_query.md  # points to agreements tools
├── denidin.py                                  # build AgreementsManager, start API
├── scripts/migrate_agreements_089.py           # NEW
└── tests/{unit,integration,billed}/test_agreements_*.py

apps/webapp/
├── backend/src/webapp_backend/{agreements_client.py (NEW), server.py, clients_reader.py, config.py}
├── backend/scripts/export_name_resolution.py   # NEW
├── frontend/src/{AgreementsSection.tsx (NEW), ClientsView.tsx, api.ts}
└── e2e/tests/agreements.spec.ts  + playwright.config.ts (webServer for the API)
docker/docker-compose.{dev,prod}.yml            # API port (dev: 127.0.0.1 publish only)
```

**Structure Decision**: no new app or container. Business rules live once, in
`AgreementsManager`; the API, the bot capabilities, the recognizer and the migration are thin
callers of it.

## Phases

- **Phase A, foundations (denidin-app)**: ledger v4 fields + history entry; `AgreementsManager` with state machine, cascade, revisions, ledger mapping, locking. Unit tests first (RED, human-approved, then GREEN) per section VI.b.
- **Phase B, Agreements API**: Starlette routes, auth, error mapping, standalone entry point, config; integration tests through `TestClient`.
- **Phase C, webapp**: `agreements_client`, proxy routes, `clients_reader` agreed-total switch (R8), config fields; backend integration tests.
- **Phase D, UI**: `AgreementsSection` and dialogs; `npm run typecheck`.
- **Phase E, WhatsApp**: recognizer rewiring (shared code), `cap_agreements_read/write`, prompts, flow, runtime constitution section + two-way cross-references. Unit/integration first.
- **Phase F, migration**: export script, migration script, tests on a fixture ledger; rehearsal on a copy.
- **Phase G, acceptance**: write all approved UATs as `billed` / Playwright / `[MIG]` tests together, run once, per section VI.a. Playwright `webServer` starts the real API.
- **Phase H, close-out (separate human decisions)**: haleluya, then release and prod migration, each only on explicit instruction.

## Acceptance Test Map (from the approved UATs)

| UATs | Tier | Home |
|---|---|---|
| 1.1-1.4, 2.1-2.6, 3.1-3.6, 4.1, 6.1 | [UI] Playwright | `apps/webapp/e2e/tests/agreements.spec.ts` |
| 4.2, 4.3 | [UI+WA] | split in two: the UI edit and its ledger effect are asserted in Playwright (T041); the bot's answer from a DB pre-edited through the API is a billed test (T042) |
| 5.1-5.6 | [WA] billed | `apps/denidin-app/tests/billed/test_agreements_whatsapp.py` |
| 7.1-7.5 | [MIG] integration | `apps/denidin-app/tests/integration/test_migrate_agreements_089.py` |

## Risks

- **Double counting in the agreed total** (ledger mirrors DB). Mitigation: R8, UAT 6.1.
- **Ledger event-id collisions in a cascade** (per-minute sequence). Mitigation: one lock, test with a 6-component close.
- **Recognizer dedup regression** when moving creation off the ledger path. Mitigation: port its fingerprint rule into `create_from_capture`, keep its existing tests green.
- **Wrong client key**: agreements keyed by official name but the Clients tab matches via mappings. Mitigation: bulk totals keyed by official name; unresolved names flow through the existing "names to resolve".
- **Bot misrouting** between reminders / invoices / ledger query / agreements. Mitigation: constitution section and two-way cross-references; UAT 5.6.
- **Prod migration rewriting history.** Mitigation: backup, dry-run, marker, rehearsal on a copy, separate go-ahead.

## Complexity Tracking

No constitution violations. Two additions worth naming: a new Python web dependency in
denidin-app (decision 2) and a two-step file-handoff migration (forced by the rule that apps do
not import each other; the alternative, importing webapp code from denidin-app, is forbidden).
