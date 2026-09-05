# Implementation Plan: Ledger Web UI (Feature 068, v1)

**Spec**: `spec.md` (same directory) | **Status**: post speckit.plan, pre speckit.tasks

## Architecture

```
Browser (React Native Web SPA, apps/webapp/frontend)
   │  HTTPS via Cloudflare Tunnel (per-env: dev/prod) — the ONLY internet-reachable service
   │  denidin-app / morning-mcp-app are never tunneled/exposed
   ▼
webapp-backend (Python + Starlette BFF, apps/webapp/backend)
   │  Authorization: Bearer <session-token>  (issued at POST /auth/login)
   │  imports apps/denidin-app/src directly (PYTHONPATH) — no network hop, no live-process
   │  dependency on a running denidin-app container
   ▼
denidin-app's data_root (read-only)
   ├── events/*.json        — via LedgerEventManager (reused as-is)
   ├── sessions/**/*.json   — via SessionManager (reused as-is)
   └── media/*              — via MediaFileManager path convention (reused as-is)
```

- **Third app**: `apps/webapp/` — `backend/` (Python) + `frontend/` (React Native Web), each
  with its own `requirements.txt`/`package.json`, mirroring the existing two-app isolation
  pattern (own Dockerfile per side, own config).
- **No writes, ever**: webapp-backend opens denidin-app's data files read-only; it never
  imports or touches `SessionManager.add_message`, `LedgerEventManager.add_ledger_event`, or
  any mutating method — read-only Python-level discipline enforced by code review, since the
  managers themselves are general-purpose (not split into read/write classes).
- **Versioning**: `apps/webapp/VERSION` = `0.5.4` at cut time (starting alignment with
  denidin-app's current version, per user decision — independent going forward).
  `apps/webapp/CHANGELOG.md`/`RELEASES.md`, git tag `webapp-v<version>`, exactly like the other
  two apps. `scripts/cut_release.sh`/`scripts/deploy_release.sh` gain `webapp` as a valid
  `<app>` value.
- **Docker/env bundling**: new services `webapp-backend-<env>`, `webapp-frontend-<env>` added
  to `docker/docker-compose.{dev,prod}.yml`; new `apps/webapp/run_webapp.sh dev|prod` /
  `stop_webapp.sh dev|prod` (source `scripts/env_lock.sh` identically to the existing per-app
  scripts); `scripts/run_all.sh`/`stop_all.sh` extended with the confirmed order
  `morning-mcp-app → denidin-app → webapp` (stop reverses it). Every clone's
  `docker-compose.<env>.local.yml` needs a new override entry for `webapp-backend-<env>`'s data
  volume mount (pointing at the shared root-clone `dev_data`/`data`, same pattern as the other
  two services) — a **manual, per-clone follow-up step**, flagged explicitly in `tasks.md` so it
  isn't silently skipped (mirrors the exact 2026-07-30 incident class documented in CLAUDE.md).
- **Ingress**: one Cloudflare Tunnel per environment, each routed only to that environment's
  `webapp-frontend`/`webapp-backend` ports. Domain/subdomain naming is a deployment-time detail
  (settle with the user when wiring DNS — not blocking this plan).

## Auth Flow

1. `POST /auth/login {password}` → backend hashes with `sha256(salt="denidin-pw" + password)`
   (see `research.md` for why sha256+fixed-salt is judged sufficient here), compares to the
   stored hash file, on match mints an opaque session token (random, server-held in-memory
   set/dict with issue time — no persistence needed, a restart simply logs everyone out) and
   returns it.
2. Every other endpoint requires `Authorization: Bearer <token>`; `BearerTokenMiddleware`-style
   check (modeled on `morning-mcp-app`'s), except the token is dynamic (issued at login) rather
   than a static config value — so the middleware checks token membership in the server-held
   active-session set, not a single fixed comparison.
3. `POST /auth/logout` invalidates that token server-side; frontend also drops it client-side.
4. `/health` remains unauthenticated (liveness only, no data).

## Data Flow / Filtering Split (resolves spec's ambiguity, see research.md)

- **Load / reload** (`GET /events?days_back=N`): server-side filter by trailing window only
  (default from settings, 7 days). This is the only query param that triggers a new read of
  the underlying data source.
- **On-screen filters** (date range within the loaded set, event type/subtype multi-select,
  client name fuzzy, global fuzzy search): applied **client-side** in the frontend, in memory,
  over the already-loaded batch — matches the spec's "apply button re-filters the loaded list"
  behavior and avoids a network round-trip per filter tweak. Fuzzy matching client-side reuses
  a JS fuzzy-search library (e.g. `fuse.js`) rather than re-implementing `rapidfuzz`'s Python
  logic in JS — see `research.md`. **One exception (2026-09-05)**: the client-name field's
  autocomplete/typeahead suggestions ARE a real backend round-trip per keystroke
  (`GET /clients/search?prefix=`, over full ledger history, not just the loaded window) — this
  is suggestion-only, distinct from the actual client-name filter applied on Apply, which
  remains client-side fuzzy matching over the loaded batch exactly like the other filters.

## Files/areas touched (representative, not exhaustive — full list in tasks.md)

- `apps/webapp/backend/` — new Starlette app, `server.py` (routes + `BearerTokenMiddleware`
  variant), `auth.py` (password hash check + session token store), `ledger_reader.py` (thin
  wrapper composing `LedgerEventManager`/`SessionManager`/media-path resolution into the
  response shapes in `data-model.md`), `config/` (config.example/dev/prod/test.json, mirroring
  morning-mcp-app's flat shape), `requirements.txt`, `Dockerfile`, `pytest.ini`, `conftest.py`,
  `tests/{unit,integration}/`.
- `apps/webapp/frontend/` — React Native Web app (`package.json`, `App.tsx`, components for
  the filter bar, row list, expand panel, settings, login screen). `e2e/` holds the
  **Playwright suite — this feature's real acceptance tier** (see `research.md` §4);
  `jest.config.js` + React Native Testing Library is optional, non-gating dev-loop scaffolding
  only, not the deliverable.
- `apps/webapp/VERSION`, `CHANGELOG.md`, `RELEASES.md`.
- `apps/webapp/run_webapp.sh`, `stop_webapp.sh`.
- `docker/docker-compose.dev.yml`, `docker/docker-compose.prod.yml` — two new services each
  (`webapp-backend-<env>`, `webapp-frontend-<env>`), plus a third, `cloudflared-<env>`
  (containerized, per "Both apps run exclusively as Docker containers" precedent — see
  `research.md` §6), routed only to the webapp services, never to `denidin-app-<env>`/
  `morning-mcp-app-<env>`.
- `docker/docker-compose.{dev,prod}.local.yml` (every clone, manual) — new override lines.
- `scripts/run_all.sh`, `scripts/stop_all.sh` — extended ordering.
- `scripts/cut_release.sh`, `scripts/deploy_release.sh` — `webapp` as a valid `<app>`.
- Possibly `apps/denidin-app/src/managers/ledger_event_manager.py` — one small additive public
  method (`list_events()` or similar) if `research.md`'s recommendation is accepted, instead of
  the BFF reaching into `_index` directly.

## Verification

**Playwright is this feature's real acceptance tier — the UI equivalent of `billed`/
`expensive`, per explicit user direction (2026-09-04).** 🚨 **Ordering revised 2026-09-05:
unlike `billed`/`expensive`'s "describe now, write later" pattern, the exact Playwright
scenarios/assertions must be approved by the user BEFORE any implementation (Phases 1–10 in
`tasks.md`) begins — not merely described in prose first. A concrete draft awaiting approval
lives at `contracts/playwright-draft.md`.** Execution still happens once, at the end, against a
real running frontend+backend with real data (see `research.md` §4 for full detail):
- Real-browser interaction (press "+", panels appear with correct data), real CSS layout
  assertions (`getBoundingClientRect` — right/left panel positions per viewport), viewport-driven
  desktop-side-by-side vs. mobile-stacked behavior, and visual-regression screenshots.
- Location: `apps/webapp/frontend/e2e/`, run via `npx playwright test` — separate from `npm test`.

Everything else below is optional developer-loop scaffolding, **not gating and not part of
acceptance**, per the user's explicit "all the rest I don't care about" instruction — kept
lightweight in `tasks.md`, not over-invested:
- Unit/integration tests for the BFF (pytest, mirroring morning-mcp-app's layout) — real
  `LedgerEventManager`/`SessionManager` against real fixture data (zero-mocking-internals rule;
  no third-party calls exist in this feature, so there is nothing to fake).
- Jest + React Native Testing Library component tests for the frontend, if written at all —
  fast structural/behavioral sanity during implementation only.

No `billed`/`expensive` (Python/OpenAI) tier applies — no OpenAI calls anywhere in this
feature; Playwright is this feature's own equivalent, not an omission.
