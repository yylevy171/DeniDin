# Research: 089 Agreements DB, API, UI and WhatsApp write path

Phase 0 output. Every item records what the code does today (read 2026-10-09), the decision, and
the alternatives. Items marked **NEEDS HUMAN APPROVAL** are surfaced again in `plan.md`.

## R1. What exists today (facts from the code)

- **Ledger events are already per component.** `LedgerEventManager.add_ledger_event`
  (`apps/denidin-app/src/managers/ledger_event_manager.py`) persists one JSON file per event with
  `agreement_id`, `component_id`, `component_label`, `trigger_condition`, `percent`,
  `percent_base`, `hours`, `hourly_rate`, `txn_date`, `vat_status`, `payer_name`, `amount`,
  `description`, `reference`, plus two reserved, always-null fields `split_partner` and
  `split_percent`. `LEDGER_EVENT_FIELDS` is asserted equal to the persisted record's keys.
- **No component status field exists** on a ledger event, and no agreement status.
- `CURRENT_SCHEMA_VERSION = 2`; `SCHEMA_VERSION_HISTORY` must get a matching entry in the same
  commit as any bump (import-time check). CLAUDE.md: the bump is human-only (approved 2026-10-04
  for this feature) and no test may assert on the value.
- **Agreement creation today** = the post-turn `LedgerEventRecognizer`
  (`managers/ledger_event_recognizer.py`) -> `LedgerEventManager.persist_recognized_event` ->
  `add_ledger_events_from_call`. This runs for both the legacy `AIHandler` and the `Backbone`
  (shared post-turn recognition in `denidin.py`). It is the only writer of agreement `הסכם`
  events, so it is the one place the bot's "write to the DB, not the ledger" change has to land.
- **Hours-worked lines** are `הסכם` events with `hours` set; same `add_ledger_event` path.
- **denidin-app has no real HTTP API.** `services/health_server.py` is a stdlib
  `ThreadingHTTPServer` with one route (`GET /health`), bound to `0.0.0.0:<health_check_port>`
  (dev `8200:8100` in compose). Starlette/uvicorn are in the webapp backend's requirements only,
  not denidin-app's.
- **Webapp backend** (`apps/webapp/backend/src/webapp_backend/`): Starlette, `server.py` routes
  under `/api/...`, session-token gate on every post-login route, `ClientsReader` computing the
  Clients tab from ledger events (`_aggregate_events`: `agreements += amount` for every `הסכם`
  event), webapp-owned writable state under `webapp_data/clients/`. Its mount of denidin-app's
  data is read-only.
- **Frontend**: `ClientsView.tsx` (890 lines) renders the Clients tab; `api.ts` is the client.
- **Backbone capabilities** (`src/capabilities/`, `src/backbone/capability_tags.py`,
  `capabilities/toolsets.py`): a capability = a `CapabilityTag`, a prompt
  `config/prompts/capabilities/<tag>.md`, tools in `toolsets.py`, and (for local tools) a
  `dispatch_direct_tool_call` handler. Writes get approval via the on-demand
  `cap_approval_with_buttons` capability (`approval_with_yes_no_buttons`). Flows live in
  `config/prompts/flows/` (`flow_fee_agreement_provided_by_user.md` already exists).
- Compose: `webapp-backend-<env>` and `denidin-app-<env>` are in the same compose file, hence the
  same default network; the webapp backend can reach `denidin-app-<env>:<port>` by service name.

## R2. Agreements DB engine and location

- **Decision**: SQLite at `{data_root}/agreements/agreements.db`, accessed by a new
  `AgreementsManager(denidin)` in `apps/denidin-app/src/managers/agreements_manager.py`
  (REQ-063-08: DeniDin object is the only constructor arg; other managers reached through it).
- **Rationale**: same precedent as `reminders.db` and `chat_index.db`; transactional, one file,
  survives restarts, easy to back up with the data root; the API and the bot share one process, so
  one connection discipline plus a process-wide write lock gives "last write wins" without races.
- **Alternatives**: JSON files per agreement (like ledger events): rejected, a cascade touches
  many rows atomically and revision history wants queries. ChromaDB: not a fit.

## R3. Who owns the HTTP API, and which server

- **Decision**: denidin-app owns it (clarified 2026-10-05). New module
  `apps/denidin-app/src/services/agreements_api.py`, a Starlette app served by uvicorn in a daemon
  thread started from `initialize_app`, on its own port `config.agreements_api.port`
  (0 = off), bearer-token auth (`config.agreements_api.auth_token`, single shared secret, same
  shape as morning-mcp-app's `BearerTokenMiddleware`). It calls `AgreementsManager`; it contains
  no business rules.
- **Rationale**: about a dozen JSON routes with path params, auth and error mapping; Starlette is
  already the house style (webapp, FastMCP) and `TestClient` gives real, no-mock route tests.
  Extending the stdlib health server would mean hand-rolling routing, body parsing and auth.
- **Alternatives**: put routes on the stdlib health server (no new dependency, but a lot of
  hand-written plumbing and the health port is host-published, which we do not want for writes);
  let the webapp write the SQLite file directly (rejected: breaks the read-only mount rule and
  puts business rules in two apps).
- **APPROVED 2026-10-09 (human)**: add a web server (`starlette` + `uvicorn`) to
  `apps/denidin-app/requirements.txt`.
- **Exposure** (human requirement 2026-10-09: reachable by the webapp **backend**, not the
  frontend): the webapp backend reaches it by compose service name (`http://denidin-app-<env>:<port>`)
  in `dev` and `prod`, so nothing is published to the host there. Only the non-Docker mode
  `run_webapp.sh host` runs the backend as a host process; for that, `dev` also publishes the port
  on `127.0.0.1` only (not on the network). The frontend and browser never call it.

## R4. Webapp <-> denidin-app path

- **Decision**: browser -> webapp frontend -> **webapp backend** (existing session gate, new
  `/api/agreements/...` and `/api/clients/{id}/agreements` routes) -> denidin-app Agreements API
  (bearer token from the webapp backend's config: new `denidin_agreements_url`,
  `denidin_agreements_token`). The browser never talks to denidin-app and never sees its token.
  The webapp stamps `actor="webapp"` on every call.
- **If the API is unreachable**: the Agreements section and the agreed total show an explicit
  error state; the rest of the Clients tab keeps working. No silent fallback to ledger sums (a
  wrong number is worse than an error).

## R5. Ledger mapping: what a DB write pushes, and the schema fields it needs

REQ-089-07 says each event carries "the component's full new state", and the human decided
(2026-10-09) that agreement edits, close and reopen also write one event per component carrying
the agreement-level values and the agreement status. The current schema cannot carry that:

| Needed on the event | Exists today? | Proposal |
|---|---|---|
| component status (Pending/Active/Completed/Cancelled) | No | new field `component_status` |
| agreement status | No | new field `agreement_status` |
| partner name / partner % | `split_partner` / `split_percent`, reserved, always null | populate the existing reserved fields (no new field) |
| payer | `payer_name` | as is |
| original (dirty) client name | No | `original_client_name` (already in REQ-089-10) |

- **Decision**: ship all of this inside the **single v4 bump** that REQ-089-10 already has
  approved: `CURRENT_SCHEMA_VERSION` 2 -> 4, plus its `SCHEMA_VERSION_HISTORY` entry in the same
  commit, adding `original_client_name`, `component_status`, `agreement_status` to
  `LEDGER_EVENT_FIELDS` and activating `split_partner`/`split_percent`.
- **APPROVED 2026-10-09 (human)**: "bump to v4", covering this whole field list. The version
  skips 3 on purpose: a 3 was stamped once by a since-reverted change (2026-08-23 incident), so 4
  can never be confused with those. The human's decision is the only authority for the number; no
  test may assert on the `schema_version` value.
- **Delete** keeps its own shape: `הסכם`/`ביטול` with `reference` = the component's original
  event_id (stored on the component row as `origin_event_id`).
- **Idempotent edits**: a save that changes nothing still writes a revision? **Decision**: no. A
  save whose resulting state equals the current state is a no-op (no revision, no ledger event,
  returns the current state). Avoids duplicate events from double clicks.

## R6. Concurrency and failure

- **Last write wins** (REQ-089-08): every write runs in one transaction under a manager-level
  lock; no version precondition, no 409. The newest revision is the current state.
- **DB commit first, then ledger events** (REQ-089-01/07). DB-ok/ledger-failed is out of scope
  per the 2026-10-05 clarification; the manager logs it at ERROR with the revision id so it is at
  least findable, and builds nothing more.
- Event-id allocation: `LedgerEventManager._next_seq` is per-minute; a cascade writes N events in
  one request, so the manager's write lock must wrap the ledger writes too. Covered by an
  integration test that closes a 6-component agreement and asserts 6 distinct event ids.

## R7. Bot read and write paths

- **Read** (REQ-089-16): two new local function tools in a new capability `cap_agreements_read`:
  `find_agreements(client_name)` (all agreements of a client with components) and
  `get_agreement(agreement_id)`. Client-name resolution stays `cap_client_read`'s
  `resolve_client_name`, as for invoicing (reading and name resolution are separate).
- **Write**: new capability `cap_agreements_write` with local tools `update_agreement`,
  `update_component`, `add_component`, `set_component_status`, `set_agreement_status`. Each write
  is gated by the plain `approval_with_yes_no_buttons` capability like every other write. No bot
  tool for delete-component or create-agreement-by-tool: bot creation stays the existing
  capture path (below); delete is UI-only, matching the spec's flows 1-5.
- **Creation by capture**: `LedgerEventRecognizer` stops calling
  `persist_recognized_event` for agreement verdicts; it calls
  `AgreementsManager.create_from_capture(verdict, session, message_id)` which writes the DB, then
  produces the ledger events. Hours-worked lines and bank/invoice events keep today's path.
  This one change covers both the legacy `AIHandler` and the `Backbone` (shared post-turn code).
- **Legacy path scope**: the new conversational tools (`cap_agreements_*`) are backbone-only. The
  legacy `AIHandler` is not extended (memory: ai_handler is legacy; tests run with the backbone
  flag ON). The legacy path still gets the capture rewiring, because that is shared code.
- **Runtime constitution** (CLAUDE.md "every new tool-bearing feature"): a new "Agreement
  Management" section stating when it applies, when it does not, ask-don't-guess; plus explicit
  cross-references both ways in the Reminder, Invoice Management, Client Management and Ledger
  Query / Ledger Event Recognition sections. `cap_ledger_query.md` gets: current agreement terms
  come from agreements tools, the ledger is history.
- **Prompts**: `config/prompts/capabilities/cap_agreements_read.md` / `..._write.md`, catalog
  entries in `capability_tags.py`, a flow `flow_agreement_management.md`. `config/` is baked into
  the image (bugfix-066): shipping needs a release, not a mount.

## R8. Clients tab agreed total

- **Decision** (REQ-089-14): `ClientsReader._aggregate_events` stops adding every `הסכם`
  event's amount; it adds only hours-worked `הסכם` events (non-null `hours`) and the per-client
  sum of non-Cancelled components fetched from the Agreements API (one bulk call per report
  build, `GET /agreements/totals`). The `הסכם <amount>` comment override is untouched.
- **Why bulk**: the report is built for all clients and cached; N per-client calls would be slow.
- **Risk to test**: with events mirroring components, summing ledger `הסכם` events AND the DB
  would double count. UAT 6.1 pins the exact arithmetic (9,000 -> 6,000).
- **Unresolved-name clients**: the Agreements DB is keyed by the clean Morning client name; the
  report matches by the same official-name key it already uses. Clients whose agreements carry an
  unresolvable raw name appear under the existing "names to resolve" flow with their DB total.

## R9. One-time migration

- **Problem**: the clean-name source (Clients-tab confirmed mappings + automatic match to official
  Morning names) and the line status/paid totals live in the **webapp** (`ClientsReader`), while
  the ledger rewrite must be done by **denidin-app**. Apps must not import each other (webapp
  imports denidin-app's `src` read-only; the reverse is forbidden).
- **Decision**: a two-step, file-handoff migration, run by an operator, never automatically:
  1. `apps/webapp/backend/scripts/export_name_resolution.py` (read-only) writes
     `name_resolution.json`: per raw ledger client name -> `{official_name | null, line_closed,
     agreed, paid}`.
  2. `apps/denidin-app/scripts/migrate_agreements_089.py --data-root ... --resolution
     name_resolution.json [--dry-run]` reads the ledger + that file and (a) copies a timestamped
     backup of every `events/*.json` it will rewrite, (b) builds the Agreements DB from
     agreement-component `הסכם` events (`hours` unset), applying REQ-089-11 status inference and
     REQ-089-11a legacy-cancellation handling, (c) rewrites those events to v4 with
     `client_name` = official, `original_client_name` = dirty, `schema_version` v4, (d) writes a
     marker (`agreements/migration_089.json`) so a second run is a no-op.
- **`--dry-run`** prints counts and a sample diff and writes nothing. Mirrors Feature 062's
  precedent of a preview step (see also `backend/scripts/preview_092_migration.py`).
- **Never run against prod without a separate, explicit human go-ahead** (same gate as any
  prod-touching action in CLAUDE.md); rehearsal on a copy of the prod data via the existing
  read-only mount first.
- Event ids: migration does not mint new events; it rewrites existing ones in place (the
  approved one-time exception to immutability), keeping `event_id`, so `reference` links hold.

## R10. UI

- New `AgreementsSection` component rendered inside the expanded client row of `ClientsView.tsx`
  (below comments/aliases), plus dialogs: agreement edit, component edit/add, agreement create,
  delete confirm, history timeline. React Native Web primitives like the rest of the app
  (`ui.tsx`, `react-native.d.ts`); a new `agreementsApi` section in `api.ts`.
- Closed (Completed/Cancelled) components and components of a closed agreement render with
  disabled controls; the backend enforces the same rule (UI is not the only guard): a write to a
  locked component returns 409 `locked`.

## R11. Test strategy fit (METHODOLOGY section VI)

- UAT tiers already assigned in `user-stories.md`. Unit/integration tasks come with Task A/Task B
  at `speckit.tasks`. Billed and Playwright acceptance code is written last, run once, together.
- Playwright needs a real Agreements API: `playwright.config.ts` `webServer` gains an entry that
  starts denidin-app's Agreements API on a seeded throwaway data root. The API must therefore be
  startable standalone from a small entry point (`python -m src.services.agreements_api --config
  <test config>`), not only from `initialize_app`.
