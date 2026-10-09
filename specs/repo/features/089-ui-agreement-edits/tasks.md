# Tasks: Edit Agreements from UI & WhatsApp (089)

**Input**: `plan.md`, `spec.md`, `user-stories.md` (UATs approved 2026-10-09), `research.md`, `data-model.md`, `contracts/agreements-api.md`
**Branch**: `feature/089-ui-agreement-edits`

**Rules that apply to every task** (CONSTITUTION / METHODOLOGY section VI):
- Unit and integration tests follow Task A (tests, RED) -> **human approval gate** -> Task B (implementation, tests frozen). Once approved, a test is immutable without fresh sign-off.
- `billed`, Playwright and `[MIG]` acceptance tests are NOT written per story. The approved UATs are coded and run together once, in the final Acceptance phase.
- Tests run only through the wrapper scripts (`scripts/run_unit_integration_tests.sh`, `scripts/run_single_test.sh`); never bare `pytest`. Sound off every result as it lands.
- No `unittest.mock` in `tests/integration/`; real `TestClient`, real managers, real tmp data roots.
- No test asserts on `schema_version`'s value.
- Config files are frozen once a test run starts. No env vars. `now_local()` for all timestamps. `pathlib.Path` only.
- Never start a dev/prod environment, cut a release or run the prod migration without that action's own explicit approval.

**Format**: `- [ ] T### [P] [US#] Description with path`. `[P]` = parallelizable. **A** = write tests, **B** = implement.

---

## Phase 1: Setup

- [ ] T001 Add `starlette` and `uvicorn` to `apps/denidin-app/requirements.txt` (approved 2026-10-09) and pin like the webapp backend does
- [ ] T002 [P] Add `agreements_api` block (`port`, `auth_token`) to `apps/denidin-app/config/config.example.json` and the `AppConfiguration` dataclass in `apps/denidin-app/src/models/config.py` (port 0 = off); extend `config.test.json` locally with a port and token (gitignored)
- [ ] T003 [P] Add `denidin_agreements_url` and `denidin_agreements_token` to `apps/webapp/backend/src/webapp_backend/config.py` (`_APP_FIELDS`) and `apps/webapp/backend/config/config.example.json`
- [ ] T004 [P] Compose: add the Agreements API port to `docker/docker-compose.dev.yml` (published on `127.0.0.1` only, for `run_webapp.sh host`) and `docker/docker-compose.prod.yml` (not published; reached by service name); webapp backend config examples point at `http://denidin-app-<env>:<port>`

---

## Phase 2: Foundational (blocks every story)

### Ledger schema v4 (human-approved 2026-10-09: bump to 4, full field list)

- [ ] T005 **A** Unit tests in `apps/denidin-app/tests/unit/test_ledger_event_manager.py` (new test class, existing tests untouched): a persisted `הסכם` event carries `original_client_name`, `component_status`, `agreement_status`, populated `split_partner` / `split_percent`; the new keys are null for bank and invoice events; `LEDGER_EVENT_FIELDS` matches the persisted record; no assertion on the `schema_version` value
- [ ] T006 **B** (blocked on T005 approval) In `apps/denidin-app/src/managers/ledger_event_manager.py`: add the three fields to `LEDGER_EVENT_FIELDS` and the record, accept them as optional kwargs on `add_ledger_event`, populate `split_*`, set `CURRENT_SCHEMA_VERSION = 4` and add the matching `SCHEMA_VERSION_HISTORY` entry (version 4, 2026-10-09, feature 089, decision text) **in the same commit**; update the stale comment block above the constant

### AgreementsManager core

- [ ] T007 **A** Unit tests `apps/denidin-app/tests/unit/test_agreements_manager.py`, part 1 (schema + CRUD + defaults): DB created under `{data_root}/agreements/`; create agreement with components; UAT 3.1 defaulting (trigger -> Pending, none -> Active); component must have amount or percent; client name required; hours-worked capture refused; `find_agreements` / `get_agreement` / `totals` (non-Cancelled sums, keyed by official name)
- [ ] T008 **A** Unit tests, part 2 (state machine + cascade): every legal and illegal component transition; `locked` computation; agreement Completed cascade (Active -> Completed, Pending -> Cancelled, closed ones unchanged); agreement Cancelled cascade (Pending/Active -> Cancelled, Completed/Cancelled unchanged); reopen agreement leaves components alone; reopen component refused while agreement closed; no-op save creates no revision and no ledger event
- [ ] T009 **A** Unit/integration tests, part 3 (revisions + ledger mapping, real `LedgerEventManager` on a tmp root): each mutation writes one revision with actor, action, snapshot, changed fields, event ids; ledger events per data-model.md table (component create/edit/status = 1; wording-only = 1; agreement edit / close / reopen = N, one per component carrying agreement-level values and status; delete = 1 `ביטול` with `reference` = `origin_event_id`); a 6-component close yields 6 distinct event ids; concurrent writes serialize (last write wins)
- [ ] T010 **B** (blocked on T007-T009 approval) Implement `apps/denidin-app/src/managers/agreements_manager.py`: `AgreementsManager(denidin)`, SQLite schema from data-model.md, process-wide write lock held across DB commit and ledger writes, state machine, cascade, revisions, ledger mapping, `create_from_capture`, `totals`, `revisions`; ledger failure after a committed DB write is logged at ERROR with the revision id and nothing more (out of scope per spec)
- [ ] T011 Wire `AgreementsManager` into `build_denidin_objects` in `apps/denidin-app/denidin.py` (built on `DeniDin`, `None`-guarded reads; no callbacks)

### Agreements API

- [ ] T012 **A** Integration tests `apps/denidin-app/tests/integration/test_agreements_api.py` through Starlette `TestClient` with a real manager and ledger on a tmp root: auth (401 without/with wrong token, `/is_alive` open); every route in `contracts/agreements-api.md`; error codes (`not_found`, `locked`, `illegal_transition`, `validation` with `fields`, `invalid_actor`); `PATCH` whitelist; idempotent no-op returns `ledger_event_ids: []`; response carries `locked`
- [ ] T013 **B** (blocked on T012 approval) Implement `apps/denidin-app/src/services/agreements_api.py`: Starlette app (thin: validation + error mapping only), bearer middleware, `python -m src.services.agreements_api --config <file> --port <n>` standalone entry, daemon-thread uvicorn start from `initialize_app` when `port != 0`; logs per request with the `[v<version>]` convention

---

## Phase 3: US1 - View client agreements and components (P1)

**Goal**: a client's "הסכמים" section lists agreements with nested components. **Independent test**: expand a seeded client in the Clients tab (UAT 1.1-1.4).

- [ ] T014 **A** [US1] Backend integration tests `apps/webapp/backend/tests/integration/test_agreements_proxy.py`: `GET /api/clients/{id}/agreements` behind the session gate (401 without), proxies to a real Agreements API fixture, maps connection failure to `502 agreements_unavailable`, never leaks the denidin-app token
- [ ] T015 **B** [US1] (blocked on T014 approval) `apps/webapp/backend/src/webapp_backend/agreements_client.py` (HTTP client, 5 s timeout, bearer, `actor`) and the read routes in `server.py`
- [ ] T016 [P] [US1] Frontend: `agreementsApi` in `apps/webapp/frontend/src/api.ts`; new `apps/webapp/frontend/src/AgreementsSection.tsx` (agreement header with ID, payer, partner, partner %, status; nested component rows with label, amount/percent, trigger, status; empty state; error state; hours-worked lines not shown as components); mount it in `ClientsView.tsx` below comments and aliases; `npm run typecheck` clean

---

## Phase 4: US2 - Create, edit, add, delete (P1)

**Goal**: UAT 2.1-2.6. **Independent test**: edit one component, verify siblings unchanged and one ledger event.

- [ ] T017 **A** [US2] Backend integration tests (same file family): proxy routes for `POST /api/agreements`, `PATCH` agreement, add / edit / delete component; validation errors pass through with `fields`; actor stamped `webapp`
- [ ] T018 **B** [US2] (blocked on T017 approval) Proxy write routes in `server.py`
- [ ] T019 [P] [US2] Frontend dialogs in `AgreementsSection.tsx`: "Edit Agreement" (payer, partner, partner %), component edit (8 fields from UAT 2.2), "+ Add Component", "+ New Agreement" (top-level + at least one component, zero components refused), delete with confirm (cancel does nothing), disabled controls when `locked`; show API error text

---

## Phase 5: US3 - Lifecycle (P2)

**Goal**: UAT 3.1-3.6. **Independent test**: add components, move them through every state, close the agreement, check cascade.

- [ ] T020 **A** [US3] Backend integration tests: `POST .../status` and `POST .../components/{id}/status` proxies, `409 locked` / `illegal_transition` pass-through
- [ ] T021 **B** [US3] (blocked on T020 approval) Proxy status routes in `server.py`
- [ ] T022 [P] [US3] Frontend: per-component buttons (Mark Active / Mark Completed / Cancel / Reopen) and agreement-header buttons (Mark Completed / Cancel / Reopen) shown only when legal; locked rows grayed; agreement reopen leaves cascaded components as they are

---

## Phase 6: US4 - Revision history and cross-platform consistency (P2)

- [ ] T023 **A** [US4] Backend integration tests: `GET /api/agreements/{id}/revisions` proxy, chronological order, actor shown
- [ ] T024 **B** [US4] (blocked on T023 approval) Proxy route in `server.py`
- [ ] T025 [P] [US4] Frontend: "Revision History" timeline in the expanded agreement (date, actor, changed values)

---

## Phase 7: US5 - WhatsApp (P1)

**Goal**: UAT 5.1-5.6 and the bot half of 4.2 / 4.3. Backbone-only for the new tools; capture rewiring is shared code.

### Capture rewiring (shared by the legacy and backbone paths)

- [ ] T026 **A** [US5] Integration tests `apps/denidin-app/tests/integration/test_agreement_capture_via_db.py`: a complete agreement verdict creates the agreement in the Agreements DB and produces ledger events; a re-recognized document does not duplicate (content-fingerprint dedup ported from the ledger path); hours-worked lines, bank and invoice events behave exactly as before (existing ledger-recognizer tests stay green and untouched)
- [ ] T027 **B** [US5] (blocked on T026 approval) `apps/denidin-app/src/managers/ledger_event_recognizer.py` routes agreement verdicts to `AgreementsManager.create_from_capture`; incomplete-capture handling unchanged

### New capabilities

- [ ] T028 **A** [US5] Unit tests `apps/denidin-app/tests/unit/test_agreements_capability.py`: tool schemas; `find_agreements`, `get_agreement` read results; each write tool maps to the right manager call with `actor="whatsapp"`; ambiguity (several agreements) is returned, never auto-picked; `locked` and not-found come back as `error: ...` strings; role gating (godfather/admin only)
- [ ] T029 **B** [US5] (blocked on T028 approval) `apps/denidin-app/src/capabilities/agreements/{tools,handler}.py` with `list/get` and `update_agreement`, `update_component`, `add_component`, `set_component_status`, `set_agreement_status`; register in `src/capabilities/toolsets.py` (local tools, `WRITE_TOOL_NAMES`, `WRITE_TOOLS_BY_TAG`), add `AGREEMENTS_READ` / `AGREEMENTS_WRITE` tags and catalog text in `src/backbone/capability_tags.py`
- [ ] T030 [US5] Prompts: `config/prompts/capabilities/cap_agreements_read.md`, `cap_agreements_write.md` (write lists the details an approval must state), `config/prompts/flows/flow_agreement_management.md`; update `cap_ledger_query.md` (current agreement terms come from agreements tools, the ledger is history); update `backbone.md` routing line
- [ ] T031 [US5] `config/runtime_constitution.md`: new "Agreement Management" section (when it applies, when it does NOT, ambiguity is resolved by asking, short replies answer the pending question in the same context) **plus explicit two-way cross-references** in the Reminder Management, Invoice Management, Client Management and Ledger Event Recognition / Ledger Query sections (CLAUDE.md "every new tool-bearing feature" rule). Wording edits only, so no pytest run for this task
- [ ] T032 [US5] Prompt-level unit test `apps/denidin-app/tests/unit/test_agreements_prompts.py`: every new capability tag has its prompt file, a catalog entry, and appears in the constitution cross-reference list

---

## Phase 8: US6 - Clients-tab agreed total (P2)

- [ ] T033 **A** [US6] Backend integration tests `apps/webapp/backend/tests/integration/test_clients_agreed_total.py`: agreed = non-Cancelled component sum from the API (one bulk `totals` call per report build) + hours-worked ledger amounts; non-hours `הסכם` ledger events are NOT added (no double counting); the `הסכם <amount>` comment override still wins; API down -> explicit error state, not zeros; UAT 6.1 numbers (9,000 then 6,000)
- [ ] T034 **B** [US6] (blocked on T033 approval) `apps/webapp/backend/src/webapp_backend/clients_reader.py`: `_aggregate_events` skips non-hours `הסכם` amounts and adds the bulk totals; handle unresolved names via the existing "names to resolve" flow

---

## Phase 9: US7 - One-time migration (P1)

- [ ] T035 **A** [US7] Tests `apps/webapp/backend/tests/integration/test_export_name_resolution.py`: the export writes `name_resolution.json` (data-model.md shape) read-only, includes line-closed, agreed, paid; unresolvable names -> `official_name: null`
- [ ] T036 **B** [US7] (blocked on T035 approval) `apps/webapp/backend/scripts/export_name_resolution.py`
- [ ] T037 **A** [US7] Integration tests `apps/denidin-app/tests/integration/test_migrate_agreements_089.py` on a fixture ledger with fee components, hours lines, bank and invoice events, legacy `מבוטל`/`ביטול` events: components created and hours lines skipped (7.1); events rewritten to v4 with clean `client_name` / dirty `original_client_name`, other events untouched (7.2); status inference for closed-paid, closed-unpaid, open clients (7.3); legacy cancellations mark components Cancelled (7.4); second run is a no-op, backup exists before any rewrite, `--dry-run` writes nothing (7.5)
- [ ] T038 **B** [US7] (blocked on T037 approval) `apps/denidin-app/scripts/migrate_agreements_089.py` (`--data-root`, `--resolution`, `--dry-run`, marker `agreements/migration_089.json`, backup folder, counts report)
- [ ] T039 [US7] Rehearsal on a COPY of the prod data (via the existing read-only mount, into the scratchpad), `--dry-run` first; report counts and a sample diff to the human. **No prod run without its own explicit go-ahead**

---

## Phase 10: Acceptance (approved UATs, written and run together, once)

Per METHODOLOGY section VI.a: code is written now, from the approved scenarios in `user-stories.md`, then run together. Every UI test asserts the DB state, the revision, and the exact ledger events named in its UAT, and that nothing else was written.

- [ ] T040 Playwright: `apps/webapp/e2e/playwright.config.ts` `webServer` starts the real Agreements API on a seeded throwaway data root plus the webapp; fixture seeder for agreements and an hours-worked line
- [ ] T041 [P] Playwright `apps/webapp/e2e/tests/agreements.spec.ts`: UAT 1.1-1.4, 2.1-2.6, 3.1-3.6, 4.1, 6.1 (4.2 / 4.3 UI halves)
- [ ] T042 [P] `billed` `apps/denidin-app/tests/billed/test_agreements_whatsapp.py`: UAT 5.1-5.6 and the bot halves of 4.2 / 4.3 (a DB pre-edited through the API, then a real webhook through the router with real OpenAI)
- [ ] T043 [P] `[MIG]` UAT 7.1-7.5 covered by T037 (confirm the mapping table in plan.md is fully satisfied)
- [ ] T044 Run the whole acceptance set once with per-test sound-off: Playwright (`cd apps/webapp/e2e && npx playwright test agreements`), the billed file via `scripts/run_multiple_billed_tests.sh`; stop on the first failure and report before doing anything else
- [ ] T045 Update the `plan.md` acceptance map with the real test node ids

---

## Phase 11: Polish and close-out

- [ ] T046 [P] `npm run typecheck` (frontend) and `backend/scripts/lint.sh` (webapp) and `make lint` (denidin-app) clean
- [ ] T047 [P] Update `.github/ARCHITECTURE.md` and CLAUDE.md sections that now change (Agreements DB, API, new capabilities, schema v4, the apps-reach-each-other exception for the Agreements API); `apps/denidin-app/RELEASES` entries are written only by the release script, never by hand
- [ ] T048 `speckit.analyze` cross-artifact consistency check
- [ ] T049 (human, separate decisions, never inferred) `/haleluya`; then release (exact version supplied by the human); then deploy; then the prod migration run

---

## Dependencies

```
Phase 1 -> Phase 2 (T005-T006, T007-T011, T012-T013)
Phase 2 blocks every story.
US1 (T014-T016) -> US2 (T017-T019) -> US3 (T020-T022) -> US4 (T023-T025)   [same UI section, built up in order]
US5 (T026-T032) depends only on Phase 2; can run in parallel with US1-US4
US6 (T033-T034) depends on Phase 2 and T015 (the HTTP client)
US7 (T035-T039) depends on Phase 2 (T006, T010); needs no UI
Phase 10 needs every story done; Phase 11 after Phase 10.
```

## Parallel examples

- After Phase 2: US5 (bot), US7 (migration scripts) and US1 (webapp read path) are independent.
- Within a story, frontend tasks marked [P] only need the API contract, not the backend proxy being finished.
- T041 / T042 / T043 are independent files.

## Implementation strategy

- **MVP**: Phase 1-2 + US1 + US2 (view and edit from the UI, with ledger events). Shippable as a slice only together with US6 (the agreed total), otherwise the Clients tab total would disagree with the section.
- **Then** US3, US4 (lifecycle and history), US5 (bot), US7 (migration, last, because it depends on a stable schema and is the only step that touches history).
- Each story ends with its unit/integration tests green; the approved UATs are run once at Phase 10.

## Totals

49 tasks: Setup 4, Foundational 9, US1 3, US2 3, US3 3, US4 3, US5 7, US6 2, US7 5, Acceptance 6, Polish 4.

## Addendum (analysis 2026-10-09)

- [ ] T050 Regression sweep for the other apps in scope: run the Feature 025 reconciliation unit/integration tests, the player's tests, and `apps/prod-ledger-backfill` and `apps/rolling-memory-backfill` tests through their wrapper scripts, to prove the v4 ledger fields and the recognizer rewiring broke nothing. `apps/morning-mcp-app` is out of scope (no change).
