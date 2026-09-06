# Tasks: Ledger Web UI (Feature 068, v1)

🚨 **REVISED GATE (2026-09-05, explicit user instruction): nothing in Phases 1–10 below may be
implemented until the user has approved the exact Playwright test plan** — a draft exists at
`contracts/playwright-draft.md`, still pending sign-off. This reverses the original
`billed`/`expensive`-style "describe now, write code at the end" ordering: for this feature,
the acceptance test *code* (or at minimum its exact scenario/assertion list) is approved
**first**, and only then does any Task B implementation work begin. Task A (unit/integration
tests) for Phases 1–3 may still be written and approved independently in the meantime, but no
Task B — and no frontend work at all — starts before the Playwright plan is signed off.

Per-story unit/integration tasks: **Task A = tests (written first), Task B = implementation
(blocked until Task A is human-approved, AND now also blocked on the Playwright-plan approval
above)**. Unit/integration tests keep the repo's normal RED→GREEN/approval/immutable
discipline. Jest/RTL component tests are optional scaffolding — not tracked as their own gated
tasks here, per the user's explicit "I don't care about the rest."

## Story 1 — BFF scaffolding, config, auth  ✅ DONE (2026-09-05)

Implemented under `apps/webapp/` (`VERSION` 0.5.4, `CHANGELOG.md`/`RELEASES.md` seeded) and
`apps/webapp/backend/` (`src/webapp_backend/{config,auth,server}.py`, `config/config.example.json`
+ `config.test.json`, `requirements.txt`, `pytest.ini`, `conftest.py`, `Dockerfile`,
`tests/{unit,integration}/`). 21 tests green (`venv/bin/python -m pytest`). `/health` +
`/api/auth/login` unauthenticated; `/api/auth/logout` + `/api/events` (stub) session-gated;
literal password comparison; missing/corrupt hash file → app still starts, all logins fail;
concurrent sessions independent; every login attempt audit-logged (`LOGIN success|failure`, no
secrets). `/api/events` is a placeholder returning an empty list until Story 2.


- **1A** (tests): unit tests for `auth.py` — password-hash check against a known
  `sha256("denidin-pw" + pw)` fixture hash file (correct password → success; wrong → failure);
  session-token issuance/validation/invalidation (logout); **concurrent sessions**: two tokens
  issued from two separate logins are both independently valid, and invalidating one (logout)
  does not affect the other. Real file I/O against a temp dir, no mocking. Integration tests:
  `POST /auth/login` → `POST /events` with the returned token succeeds; without a token, or
  with an invalid one, `/events` returns 401; **every login attempt (success and failure)
  appends exactly one audit log line with a timestamp and outcome, and never contains the
  plaintext password or its hash**.
  - **Explicitly not automated** (user decision, 2026-09-05): the 168-hour inactivity expiry
    itself. Recorded here as a required **manual check at real acceptance time** — log in,
    confirm the token is rejected once `expires_after_hours` has passed — not to be silently
    dropped just because it isn't in any automated suite.
  - **Route/URL guard** (user-requested, 2026-09-05): every URL the frontend serves post-login
    must independently verify a valid, non-expired session before rendering anything —
    confirmed by a dedicated integration test (backend: any authenticated route rejects an
    invalidated/expired token, never trusting client-held state) and the corresponding
    Playwright scenario below (frontend: a copied post-login URL, pasted fresh after logout,
    shows the password screen with zero stale data ever rendered).
- **1B** (impl, blocked on 1A approval): `apps/webapp/backend/` skeleton — `server.py`
  (Starlette app, `BearerTokenMiddleware`-style session-token check per `plan.md`'s Auth Flow),
  `auth.py`, `config/config.example.json` (+ `.dev`/`.prod`/`.test`, flat shape mirroring
  morning-mcp-app), `requirements.txt`, `pytest.ini` + `conftest.py` (mirrors
  `morning-mcp-app`'s layout), `/health` route (unauthenticated). `Dockerfile`.

## Story 2 — Event listing endpoint  ✅ DONE (2026-09-05)

`LedgerEventManager.list_events()` added (additive, read-only, `+1` unit test in denidin-app —
171→172 pass). `webapp_backend/ledger_reader.py`: `LedgerReader` loads `ledger_event_manager`
directly by file path (bypassing the heavy `managers/__init__.py`), maps records to `EventRow`
(6 display fields + `event_id`, `date` = `txn_date` else `event_datetime`, `DD/MM/YYYY`),
trailing-window filter (inclusive boundary, Israel-local), newest-first + `event_id`-desc
tiebreaker. Routes: `GET /api/events?days_back=`, `GET /api/events/{event_id}` (404 shape),
`GET /api/clients/search?prefix=` (2+ chars, case-insensitive prefix, deduped). webapp-backend
suite now 39 tests green.


- **2A** (tests): unit test for the additive `LedgerEventManager.list_events()` method
  (`apps/denidin-app/src/managers/ledger_event_manager.py` — flagged in `research.md` §5 as an
  in-scope change to denidin-app itself, called out for explicit review). Integration test:
  `GET /events?days_back=N` against a real fixture `data_root` with events at known dates —
  asserts correct trailing-window filtering and correct `EventRow` shape/field mapping
  (`date` = `txn_date` else `event_datetime`, `DD/MM/YYYY` formatting).
- **2B** (impl, blocked on 2A approval): `list_events()` on `LedgerEventManager`; BFF's
  `ledger_reader.py` + `GET /events` route per `contracts/api.md`.

## Story 3 — Event detail + context (session/message/media resolution)  ✅ DONE (2026-09-05)

`webapp_backend/context_reader.py`: `ContextReader` reads the session layout on disk directly
(active + `sessions/expired/<day>/`), builds the lookback window (inclusive both ends, clamped
`[0,60]`), tags each message `side` (`assistant`→left, else right), mints opaque per-file media
tokens with a `data_root`-containment check. Routes: `GET /api/events/{id}/context?lookback_minutes=`
(→ `context_unavailable` graceful shape when the session/anchor can't be resolved) and
`GET /api/media/{token}` (`FileResponse`, 404 on unknown/traversal). CORS middleware added for
the split-origin Vite dev server (tightened in Story 10). **Deviation from plan** (recorded in
`research.md` §7 spirit): reads the layout directly rather than importing `SessionManager` —
that would pull `tiktoken` + the model layer into a read-only app. webapp-backend suite: 55 green.

## Story 4–8 — Frontend (login, list, filters, expand, Σ, settings, themes)  ⏳ VIEWABLE (2026-09-05)

`apps/webapp/frontend/` — Vite + React + `react-native-web` (RN primitives → DOM, keeps the
future-native-app door open per `research.md` §... / spec Architecture). `src/`: `api.ts`
(token in `localStorage`, `fetchMediaObjectUrl` for auth'd `<img>`), `theme.ts` (light/dark
white-green-black), `ui.tsx` (`Button`/`Field`/`Chips`/`ChatPanel`/`DetailPanel`), `App.tsx`
(login screen; RTL top bar with gear/refresh/Σ/expand-all/collapse-all; always-visible wrapping
filter bar — type + subtype multi-select with live grey-out, client-name text + 300ms-debounced
typeahead dropdown, global free-text, Apply; scrollable row list with the 6 fields + "+";
row-expand into right detail panel + left WhatsApp-style chat, side-by-side desktop / stacked
`<768px`; Σ result that clears on Apply/refresh and is disabled mid-refresh; settings panel with
theme/sort/days-back/lookback + logout, persisted to `localStorage`).

**2026-09-05 feedback round applied**: RTL fixed (`<html dir="rtl">` + `I18nManager.forceRTL`
+ dropped the double-flipping `row-reverse`); type/subtype are now **multi-select dropdowns**
(`MultiSelect` in `ui.tsx`), not chip rows; list row is full-width (description on its own
second sub-line, `flex:1` spacer); detail panel is **2-per-line, `label: value` inline** (no
column alignment); expand height trimmed 320→240; title says "דני-דין · ארועים" (no "לדג'ר");
context window is now **bidirectional** (`anchor ± lookback`) so the bot's capture reply shows.
Data finding (not a UI bug): `ירין ביטון` ₪1500 shows twice because the ledger genuinely holds
two event files (`H31082617540`/`...541`) for the same Morning doc `112317` — a reconciliation
dedup gap, tracked as future Σ/dedup work.

**2026-09-05 feedback round 2 applied**: column-header row above the list; from–to date-range
picker wired (native `<input type="date">`, bounded to the days-back window, filtered
client-side over row `DD/MM/YYYY`); WhatsApp image click now opens an `ImageOverlay` sized to
the expanded-row panel area (not the chat sub-panel, not browser-fullscreen); chat bubble
sides corrected under `forceRTL` (user right / דני דין left); assistant messages labelled
"דני דין" (`context_reader.build_context`); `ClientNameInput` component — 1st suggestion
highlighted on open, ↑/↓ navigate, Enter selects like a click, no re-search of the picked
full name and list stays closed after pick; subtype dropdown now offers the full canonical
union (`SUBTYPES_BY_TYPE`: הסכם→יצירה/עדכון/ביטול/אישור-מימוש/מבוטל, בנק→הפקדה/מבוטל,
חשבונית→"חשבונית מס / קבלה"/"חשבונית מס"/"חשבונית זיכוי"/"קבלה"/"חשבון עסקה"), options invalid
for the selected type(s) shown disabled; Apply button relabelled "חפש!". Type/subtype options
are now the canonical lists, not derived from the loaded rows.
NOTE: actual stored subtype labels differ from `contracts/field-manifests.md` — real data has
"חשבונית מס / קבלה" (spaced slash) and "חשבון עסקה" (not "חשבון עיסקה"); the canonical lists
above match the real data.

**2026-09-05 feedback round 3 applied**: date-range now defaults to the actual window
(from-daysBack .. today) rather than blank; filter bar reordered right-to-left to
dates → client → type → subtype → free-text → "חפש!"; image viewer (`ImageOverlay`) lifted to
the App root so it fills the whole app viewport (was expanded-row-sized); הסכם subtypes trimmed
to יצירה/עדכון/מבוטל (dropped ביטול/אישור-מימוש); `ALL_SUBTYPES` de-duped (מבוטל was listed
twice); `MultiSelect` dropdown now scrolls properly (`ScrollView maxHeight:320`,
`overflow:"hidden"` on the menu box) so all 9 subtypes + "הכל" are reachable; dropdowns are
now single-open, coordinated by App `openMenu` state + a click-away backdrop, and close on any
other action (apply / row expand / refresh / Σ / settings); type & subtype multi-selects
default to **all selected** (== no filter) and reflect the live selection; each has a bold
"הכל" row — click toggles select-all/clear-all, and it auto-unchecks (without clearing the
others) whenever the selection is partial.

**2026-09-05 feedback round 4 applied**: sort toggle now reads "חדש ראשון" / "ישן ראשון"
(no arrow); settings labels → "ברירת מחדל בעלייה ראשונה (ימים)" and
"זמן סביב שיחת whatsapp (דקות)"; date-range inputs swapped so **from** is on the right, **to**
on the left; per-input bounds — from: [2024-01-01 … to], to: [from … today].
**Bug fixes**: (a) picking a date / typing a free-text or client-name query that reaches
outside the loaded trailing window now re-fetches a wider window from the backend before
filtering (`daysBackFor`, floor = 2024-01-01) instead of silently returning 0 rows;
(b) `ClientNameInput` rewritten with its own internal `listOpen` state (was fully dependent on
a parent round-trip that wasn't rendering the list) — coordinated with the other dropdowns via
an `active`/`onActivate` pair; (c) free-text search now matches against a server-built
`search_blob` (every string/number anywhere in the full event record, lowercased) rather than
just the six display columns, so text in agreement descriptions / component labels / references
is found. `LedgerReader._to_row` adds `search_blob`; `test_ledger_reader.py` updated (56 tests).

**2026-09-05 config/isolation fixes**:
- `config.dev.json` `denidin_data_root` was pointing at `~/denidin-winprod-data` (the read-only
  prod mount) — corrected to `/Users/yaron/Projects/DeniDin/apps/denidin-app/dev_data` (the
  dev-data singleton in the root clone; ~4170 events). **dev→dev, prod→prod, never crossed.**
  Nothing was ever written to prod (read-only mount + no write code path), but dev must not
  read prod. `config.prod.json` (when a prod webapp is deployed) is the only file that points
  at `~/denidin-winprod-data`.
- Password salt removed from config entirely — hardcoded as `webapp_backend.auth.PASSWORD_SALT`
  (`"denidin-pw"`). Dropped from `AppConfig`, `config.example/test/dev.json`, all fixtures and
  tests. `hash_password(pw)` / `PasswordVerifier(hash_file)` no longer take a salt arg.
  56 backend tests green; login still works (hash file unchanged, same salt value).

**2026-09-05 feedback round 5**:
- **Non-Morning events were silently dropped (real bug).** `_parse_event_date` only understood
  `txn_date` as ISO and `event_datetime` as `DD/MM/YYYY HH:MM`. Pre-Phase-11 הסכם/בנק events
  have neither — they carry `event_date` (`DD/MM/YYYY`) + `event_time`, and `txn_date` in
  `DD/MM/YYYY`. So all 6 `A` (הסכם) + 13 `B` (בנק) events in dev returned `None` and were
  filtered out. Fixed: `_flex_date` parses both `DD/MM/YYYY` and `YYYY-MM-DD`; precedence is
  `txn_date → event_datetime → event_date` (spec.md's txn_date-wins rule preserved). +2 unit
  tests. dev now returns 4170 events (was 4151).
- `client_name` search: the highlight used `i === active` where `active` was a **boolean**
  prop — never matched, so nothing ever highlighted; the component was also over-coupled.
  Rewrote `ClientNameInput` cleanly: `menuOpen`/`onOpenMenu`/`onCloseMenu` for App coordination,
  internal `suggests`+`cursor`, `show = menuOpen && suggests.length>0`, highlight on
  `i === cursor` (+ hover), ↑/↓/Enter/Esc, no re-search after pick.
- subtype dropdown `maxHeight` 320→440 so all 10 rows fit without scrolling.
- Sort: removed the settings toggle. A ▼/▲ control sits next to the "תאריך" column header —
  ▼ = descending (default), ▲ = ascending. Session-only state (`sortDir`), resets on
  reload/re-login, never persisted. `Settings.sort` removed.
- Top bar shows the visible record count ("<n> רשומות") next to ⚙︎; recomputes on every search.

**What's a first-cut, NOT yet the full test-plan spec** (Playwright not written/run yet):
detail panel uses a simplified always/if-exists rule, not the per-subtype
`contracts/field-manifests.md` matrix; filter matching is substring/normalized, not `fuse.js`
fuzzy; documents render as a "media unavailable"-style fallback (only images have the
thumbnail/lightbox path). These are the remaining gaps before Stories 4–8 are *done* vs
*viewable*.

Local launcher: `apps/webapp/run_webapp_dev.sh` (backend :8100 via `uvicorn --factory`,
frontend :5173 via Vite; not the containerized env — that's Story 10).

### Story 3 original task text (kept for reference)

- **3A** (tests): unit tests for the session/message lookback-window resolution logic (given a
  fixture session with messages at known timestamps, assert the correct subset is returned for
  a given `lookback_minutes`, clamped to `[0,60]`). Integration tests: `GET /events/{id}` (found
  / 404), `GET /events/{id}/context` (happy path with media, happy path text-only, and the
  `context_unavailable` graceful-degradation path for a missing/archived session). `GET
  /media/{token}` — real file served, plus the path-traversal-containment check
  (`research.md` §3) with a deliberately adversarial token asserted to fail closed.
- **3B** (impl, blocked on 3A approval): context-resolution logic in `ledger_reader.py`
  (reusing `SessionManager`'s active/archived resolution pattern), `/events/{id}`,
  `/events/{id}/context`, `/media/{token}` routes.

## Story 4 — Frontend scaffolding, login, theme

- **4A** (tests): none required (Jest/RTL optional/non-gating per the revised testing scope —
  skip a dedicated test task here; covered instead by the Acceptance phase).
- **4B** (impl): `apps/webapp/frontend/` RN-Web project scaffold, login screen (calls
  `/auth/login`, stores token in `localStorage` — survives tab/browser close, 2026-09-05
  decision), light/dark theme (white/green/black
  palette) with a settings-driven toggle, RTL layout base.

## Story 5 — Event list, filters, initial load

- **5A**: none required (see Story 4A rationale).
- **5B** (impl): top bar (logo, gear, refresh, Σ placeholder, expand-all/collapse-all), always-
  visible filter bar (date range pickers `DD/MM/YYYY`, event-type multi-select, event-subtype
  multi-select, client-name fuzzy text, global fuzzy text, **Apply** button — client-side
  filtering per `plan.md`'s Data Flow section, `fuse.js` or equivalent for fuzzy matching),
  scrollable RTL row list (6 fields per `spec.md`), refresh-data → re-calls `GET /events` with
  the settings' `days_back`.

## Story 6 — Row expand (multi, expand-all/collapse-all), two panels

- **6A**: none required (see Story 4A rationale).
- **6B** (impl): "+" toggle per row (independent expand state, multiple simultaneous), expand-
  all/collapse-all wired to the top-bar control, accordion push-down layout, right panel
  (`EventDetail` per field manifest) + left panel (`EventContext` — WhatsApp-style chat), side-
  by-side desktop / stacked-vertical mobile via responsive layout, collapse-all triggered
  internally on Apply and on refresh (see Component 5).

## Story 7 — Σ summation

- **7A**: none required.
- **7B** (impl): sum `amount` over the currently client-side-filtered row set, excluding
  null/unparseable amounts from both sum and count, display `"Σ (N events): ₪X"` next to the
  button, recomputed on every filter Apply / expand-all-unrelated state change that alters the
  visible set.

## Story 8 — Settings persistence

- **8A**: none required.
- **8B** (impl): settings panel (theme, sort order, days-back, lookback-minutes, logout),
  persisted to `localStorage`, applied on load.

## Story 9 — Versioning & release tooling

- **9A** (tests — DONE 2026-09-06): `scripts/tests/test_cut_release.py` +
  `test_deploy_release.py` extended. New `scratch_webapp_repo` fixture (two-Dockerfile layout).
  `test_webapp_bundles_two_images_into_one_artifact` (full cut: both images in one tar, manifest
  lists both, one tag, VERSION bumped), `test_webapp_recut_refuses`, `test_bad_app_exits_2`,
  `test_webapp_is_an_accepted_app` (passes arg validation, fails on missing artifact not exit 2).
  The full two-service deploy+verify path is left to a manual gate against real infra, exactly
  as morning-mcp-app's `/health` path already is (see `test_deploy_release.py` docstring).
- **9B** (impl — DONE 2026-09-06): `cut_release.sh` + `deploy_release.sh` accept `webapp`.
  - `cut_release.sh`: `webapp` builds `webapp-backend` + `webapp-frontend` (repo-root context,
    each its own Dockerfile), `docker save`s **both into the one** `webapp-v<version>.tar`,
    manifest gains an `images: [...]` array, one tag `webapp-v<version>`. VERSION/CHANGELOG/
    RELEASES at `apps/webapp/` (already seeded: VERSION `0.5.4`).
  - `deploy_release.sh`: `webapp` loads both images, retags each to its
    `<project>-webapp-{backend,frontend}-<env>:latest`, `up -d --no-build` both services
    (+ `cloudflared-<env>` **iff** `docker/cloudflared.<env>.env` exists), confirms both
    backend+frontend containers `running`, then polls `webapp-backend-<env>`'s `/health` for
    `version == <version>` (same shape as morning-mcp-app). Both local (`dev`) and remote
    Windows-box (`prod`, over SSH) paths handled.

## Story 10 — Docker/env bundling & Cloudflare Tunnel ingress

- **10A**: no automated test (infra/compose config) — verified manually per-environment at
  deploy time, same as the existing two apps' compose changes. `docker compose config` on both
  merged files (base + coder2 local override) parses clean; frontend `vite build` + backend
  pytest (62) green after the config-path changes.
- **10B** (impl — DONE 2026-09-05): `webapp-backend-<env>`/`webapp-frontend-<env>`/
  `cloudflared-<env>` services added to `docker/docker-compose.{dev,prod}.yml`;
  `apps/webapp/run_webapp.sh`/`stop_webapp.sh dev|prod` (mirror `run_morning_mcp.sh`, source
  `scripts/env_lock.sh`, `env_lock_require_local_override` + `acquire`/`release`);
  `scripts/run_all.sh`/`stop_all.sh` extended (`morning-mcp-app → denidin-app → webapp`,
  reverse on stop). Backend `Dockerfile` rewritten to **preserve** the repo tree inside the
  image (`/app/apps/webapp/backend/...` + `/app/apps/denidin-app/src`) so
  `ledger_reader`/`__init__`'s `parents[4]` and `server.read_version`'s `parents[3]` resolve
  in-container (the old flattened layout broke both). New `apps/webapp/frontend/Dockerfile`
  (multi-stage Vite build → nginx) + `nginx.conf.template` (envsubst `${BACKEND_UPSTREAM}`,
  `NGINX_ENVSUBST_FILTER` so nginx's own `$vars` survive) proxying `/api` + `/health` to the
  backend, SPA fallback. Container config: committed `config/config.{dev,prod}.container.json`
  (no secrets); `auth/password.hash` mounted read-only from host. Cloudflare Tunnel:
  `cloudflared-<env>` container, token from gitignored `docker/cloudflared.<env>.env`
  (`env_file` `required: false` — absent → container just stays down), `docker/cloudflared.env.example`
  committed, `.gitignore` updated.
  **Manual per-clone follow-up (flagged, not automatable):** every clone's gitignored
  `docker-compose.{dev,prod}.local.yml` needs a `webapp-backend-<env>` override entry for the
  `/app/denidin-data` mount — coder2's is done; documented in `quickstart.md`.

## Follow-ups (deferred — not blocking)

- **cut_release.sh build vs. colima-keepalive race** (found 2026-09-06 cutting
  `webapp-v0.0.1-webapp`): `~/bin/colima-keepalive.sh` runs every 2 min via launchd; its
  `daemon_ok()` health check (`docker info`, 15s timeout) times out while a heavy `docker build`
  is loading context / running `pip install`, so the keepalive concludes the daemon is wedged
  and does `pkill -9 limactl` + `colima start` — hard-killing the in-progress build. Every
  `cut_release.sh webapp ...` retry hit the same ~2-min guillotine (`EOF` / "Cannot connect to
  the Docker daemon"). **FIXED 2026-09-06** in `cut_release.sh`: it now `launchctl unload`s the
  keepalive (best-effort; only when `--artifacts-root` is not overridden, i.e. not in tests)
  right before the build loop and `launchctl load`s it back the moment `docker save` succeeds,
  with an `EXIT` trap as the safety net. Not a webapp-specific bug (any large build is exposed),
  but surfaced by webapp's two repo-root-context images. A keepalive-side hardening (skip the
  restart while a `docker build` is active) is still worth doing but is out of this feature's
  scope — `~/bin/colima-keepalive.sh` is not in the repo.
- **deploy_release.sh R5 retags only the first of webapp's two images over SSH** (found
  2026-09-06 deploying `webapp-v0.0.1-webapp` to the Windows box): R3's remote `docker load`
  loads both images fine (both present in `docker images` on the box afterward), but
  `LOADED_REFS` came back with only the `webapp-backend` "Loaded image:" line, so R5 retagged
  just the backend and R7 died with `No such image: denidin-prod-webapp-frontend-prod:latest`.
  Likely the `wsl_ssh_run` base64/ssh transport collapsing `docker load`'s multi-line stdout.
  Worked around by manually `docker tag`-ing the frontend on the box + `docker compose up -d
  --no-build` + verifying by hand — deploy is live and healthy. Real fix: retag from the
  manifest's authoritative `images: [...]` list instead of parsing `docker load` stdout (also
  removes a fragile grep). The local (`dev`) path may have the same latent bug.
  **FIXED 2026-09-06** in `deploy_release.sh`: retag list now comes from the manifest's
  `images: [...]` array (`MANIFEST_IMAGES`), not from parsing `docker load` stdout;
  `_verify_loaded_matches_manifest` still checks the load output but only to reject a tar
  containing an image the manifest doesn't list (swapped/corrupt bytes), and each manifest
  image's real presence is confirmed by `docker image inspect` at the retag step (both R3 and
  L1/L2). `cut_release.sh` also fixed: pauses `~/bin/colima-keepalive.sh` (launchctl
  unload/load, best-effort, skipped under `--artifacts-root`) around build+save so the
  keepalive's 2-min `docker info` probe can't hard-restart colima mid-build. 20/20
  `scripts/tests/` green.
- **context/conversation + images empty in prod (found 2026-09-06, right after the
  `webapp-v0.0.1-webapp` prod deploy)** — NOT a deploy bug and NOT caused by this feature.
  The live prod `denidin-app` is running an unreleased pre-release, **`0.5.4-70`**, which this
  morning (~10:08, before the webapp went up) **restructured prod's on-disk session store**:
  the entire old tree was moved to `{data_root}/sessions/_pre070_raw_20260906/{active,expired}/`
  (3 active + 96 expired sessions) and the new top-level `sessions/` now holds only 2
  carried-forward sessions + a new `chat_index.db`, with **no top-level `sessions/expired/`**.
  `webapp-backend`'s `context_reader.ContextReader._find_session_dir` only knows the
  pre-`-70` layout (`sessions/{sid}/` and `sessions/expired/{YYYY-MM-DD}/{sid}/`), so it
  resolves almost every ledger event's `session_id` to nothing → the endpoint returns
  `{"error":"context_unavailable"}` (HTTP 200, error body) → the UI shows no conversation, and
  since media tokens are only minted from messages found during that walk, no images either.
  **FIXED 2026-09-06** — `context_reader.py` rewritten to resolve **by `message_id`, not
  `session_id`** (via a lazily-built, miss-rebuilt `message_id → session dir` index). The
  index spans the canonical post-070 layout (`sessions/{sid}/{messages,archived}/`), the
  legacy `sessions/expired/{day}/{sid}/`, and the Feature 070 raw backup
  (`sessions/_pre070_raw_<date>/` incl. `active/` and `expired/{day}/`), canonical winning on
  collision. `/context` now also returns `event_session_id` (the stale stored value) alongside
  the resolved real `session_id`. Events with no conversation at all (accounting-reconciliation
  sweep — `message_id` null, sentinel `session_id`) return `no_conversation: true` with a
  distinct message rather than a generic "no longer available". 6 new unit tests in
  `test_context_reader.py::TestFeature070Layout`; full backend suite 68 green. Verified against
  real prod data + **live on prod** (event `A04092615200` → 4-msg window in canonical session
  `12e158e2…`; `B06092608250` → 16 msgs incl. 1 image). Still worth confirming with the team
  why an unreleased `-70` build is live in prod.
- **Deployed to prod outside the release mechanism (2026-09-06, user-directed "no release,
  just put it there")**: `webapp-backend` rebuilt locally as `webapp-backend:ctxfix2` (VERSION
  temporarily set to `0.0.1-webapp-ctxfix2` for the build, then reverted — nothing committed),
  `docker save` → scp → `docker load` on the box → retag to
  `denidin-prod-webapp-{backend,frontend}-prod:latest` → `docker compose up -d --no-build`.
  Same manual path used for the Honigman logo (frontend `webapp-frontend:logo1`). `/health`
  reports `0.0.1-webapp-ctxfix2`. This code is NOT in any cut release or git tag — a real
  release still needs a human-supplied version + `cut_release.sh`/`deploy_release.sh`.
- **Honigman Law logo (2026-09-06)**: `apps/webapp/frontend/public/honigman-law-logo.png`
  (moved from a loose drop at `apps/webapp/`). Shown top-right (rightmost in the RTL top bar,
  before "דני-דין · ארועים") as a 34×40 contained `<Image>` in `App.tsx`; also the favicon
  (`<link rel="icon">` in `index.html`). Live on prod.

## Acceptance Phase (Playwright — approved FIRST, before Phases 1–10 build; run at the end)

**Ordering note (2026-09-05)**: unlike the original plan, the scenarios/assertions below (and
the concrete draft in `contracts/playwright-draft.md`) must be reviewed and approved by the
user *before* implementation work begins — not merely described in UX terms and coded later.
The suite is still *executed* only once Phases 1–10 are built (it needs the real app running),
but its content is locked in advance so implementation is built against a known target.

**Structure (revised 2026-09-05)**: organized as **components**, each a named area of behavior
covering multiple individual test cases — not a flat numbered list of 9. Each component is
reviewed/approved as a unit; individual test cases within it are added/removed as gaps surface
(as already happened with Component 1). Original scenarios 2–9 are provisionally components
2–9 below pending the same per-case scrutiny Component 1 got; expect that list to grow, not
stay fixed, as each one is actually gone through.

### Component 1 — Session & Auth (full test enumeration, approved 2026-09-05, ~33 tests)

Token is held in **`localStorage`** (survives tab/browser close); expiry is 168h since
**last activity**, not since login (using the app resets the clock).

**1.1 Wrong/correct password** (10): empty submission shows validation error; wrong password
shows a visible error; error clears on new attempt; correct password reveals the app; no stale
error lingers after success; repeated wrong attempts each independently error (no lockout —
rate-limiting explicitly out of scope); password field is masked; garbage/special-character
input doesn't crash the request; paste-into-field works; leading/trailing whitespace is
compared **literally, no trimming** (2026-09-05 decision) — a stray space causes a genuine
mismatch, not silently corrected.

**1.7 Missing/corrupted password file at startup** (1, 2026-09-05 decision): the backend still
starts normally; every login attempt fails cleanly (not a 500/crash) until the file is fixed.

**1.2 Reload & tab-close persistence** (4): reload after login shows the app directly; reload
immediately post-login has no token-save race condition; closing and reopening the tab/browser
keeps the session (per `localStorage` decision); auth state isn't incorrectly re-fetched on
reload.

**1.3 Concurrent sessions** (6): login A succeeds; login B (same password) succeeds
independently; A still works with both active; B still works with both active; logging out A
doesn't affect B; a third/fourth concurrent login also succeeds (no artificial cap).

**1.4 Login audit logging** (6, backend-only — no Playwright case, see Story 1A): success
writes one log line with timestamp+outcome; failure writes one log line with timestamp+outcome;
never contains the plaintext password; never contains the password hash; rapid repeated
failures each get their own line; log format matches the app's standard logging format.

**1.5 Session expiry** (3, **manual-only, no automated test** — explicit user decision): after
168h of zero activity, the next request is rejected back to the password screen; activity
within the window resets the clock (using the app at hour 167 keeps it alive past the original
168h mark); no stale data renders before the redirect on expiry.

**1.6 Post-logout URL guard** (4, 1 forward-looking): copied URL pasted fresh after logout
shows the password screen; same in a private/incognito window (no bypass via a URL-embedded
token); no cached network response renders stale data before the guard resolves;
**[forward-looking, not testable in v1]** the same guard applies to any future deep-linked
per-event URL, once such URLs exist.

Draft Playwright code for cases 1.1–1.3 and 1.6 lives in `contracts/playwright-draft.md`; 1.4 is
a backend integration test (Story 1A); 1.5 is manual-only (no code, ever).

Real browser, real data, no mocking, one pass at the end of `speckit.implement`.

**Status: Component 1 (Session & Auth) is the only one gone through case-by-case so far and
approved with the additions above. Components 2–9 below are still at their original,
provisional one-line granularity — each needs the same per-case scrutiny before being
considered approved.** Do not treat their brevity below as equivalent to Component 1's
thoroughness; it isn't, yet.

### Component 2 — Initial Load (full test enumeration, approved 2026-09-05, ~21 tests)

**2.1 Default load window** (7): only last-7-days events shown; boundary event (exactly 7 days
ago) included; event 8 days ago excluded; sort is newest-first (dates non-increasing top to
bottom); date computation uses Israel local time, not UTC; total count matches fixture exactly
(no off-by-one); **two events on the identical date break ties by `event_id` descending**
(2026-09-05 decision — deterministic, testable exactly).

**2.2 Empty result** (3): zero events in window shows an explicit empty state; no stuck
spinner; no unindicated blank area. **The same generic empty state covers both "nothing in the
window" and "filters narrowed to zero"** (2026-09-05 decision — no distinct wording needed).

**2.3 Changing days-back reloads immediately** (5): increasing the value immediately reloads
wider; decreasing immediately reloads narrower; newly-revealed events sort correctly into the
existing list (respecting the same-date tiebreaker above), not just appended; setting the same
value again is a safe no-op; rapid consecutive changes don't race (stale-response guard, same
concern as the typeahead in 3.4).

**2.4 Refresh button** (5): re-fetches from backend, not a re-render of cached data; new
server-side data appears after refresh; hypothetically-removed data disappears after refresh;
visual feedback while refreshing; **refresh re-applies whatever on-screen filters were already
active** (2026-09-05 decision) rather than resetting to the full loaded set.

Draft Playwright code for these cases lives in `contracts/playwright-draft.md`.

### Component 3 — Filters (full test enumeration, approved 2026-09-05, ~85 tests)

Mental model: **all filters are always active** — an unset/empty filter passes everything
through; there is no "clear filters" button, and the date range can never be fully unset (it
always holds a real range, defaulting to/tracking the load window). Resetting a filter means
manually unsetting it per-field, then pressing Apply. Full per-case test enumeration (this is
the approved granularity going forward for every component, not a one-off for this one):

**3.1 Apply gating** (10 tests): no-op until Apply for each filter type individually (type,
client-name text, global-search text, date range, subtype); Enter key in client-name field
does not apply; Enter key in global-search field does not apply; multiple filters set
simultaneously still unapplied until Apply; Apply with nothing actually changed is a safe
no-op; repeated identical Applies don't duplicate/corrupt results.

**3.2 Event type filter** (7 tests): single selection narrows correctly; two selections OR
together; selecting all types equals no type filter; deselecting one of several narrows
correctly next Apply; deselecting back to none returns to passthrough; dropdown lists exactly
the distinct `source_type` values present in the **full loaded window**, computed from the
unfiltered load and NOT shrinking as other filters narrow the visible rows (2026-09-05
decision), no phantom/missing entries; a
selected type with zero matches shows the Component-2-style empty state, not an error.

**3.3 Event subtype filter (dynamic scoping)** (8 tests): no type selected → all subtypes
selectable; one type selected → invalid subtypes grayed out; second type added → union of
valid subtypes un-grayed; all types deselected → all subtypes selectable again; **a selected
subtype that becomes invalid after type selection changes is auto-deselected** (2026-09-05);
grayed-out options are genuinely unclickable; type+valid-subtype together AND-narrow correctly;
subtype dropdown's grayed/enabled state updates live without reopening.

**3.4 Client-name typeahead + fuzzy filter** (22 tests): trigger behavior (2+ characters fires
after a **~300ms debounce**, 2026-09-05 decision — waits for a pause in typing rather than
firing per keystroke; 1 character does not fire it; clearing the field closes the dropdown;
several keystrokes within the debounce window fire only one request); dropdown interaction
(prefix-only matching, mid-string match never suggested; selecting a suggestion fills the field
and closes the dropdown; suggestion list scrolls/truncates sanely for many matches); reliability/
race conditions (typing further before a suggestion response returns discards the stale
response — same stale-response guard as 2.3; rapid clear-then-retype doesn't leave a stale
dropdown open); Apply-time fuzzy filtering (typed name need not exactly match a suggestion to
Apply; fuzzy near-miss still narrows correctly at Apply; empty field is passthrough at Apply).
**Suggestions are drawn from the FULL client list, all of history — never limited to clients
present in the currently-loaded window** (clarified 2026-09-05: `GET /clients/search` scans the
entire event index). Applying a client-name filter is still purely client-side over the loaded
rows — a 0-result client match is a valid outcome, and the user widens "from" themselves (3.6)
if they want to reach that client's older events; the applied filter never auto-fetches.
On a stale-token 401 the typeahead surfaces the auth error (kicks to login), never fails
silently.

**3.5 Global free-text search** (9 tests): matches in `description`; matches in `amount`
(numeric-as-text); matches in a date field; matches in a field not shown anywhere in the
detail/collapsed views (e.g. `bank_account`); typo/near-miss still fuzzy-matches; no-match
returns zero cleanly; broad/common-term match doesn't error or hang; combines as AND with
another filter; empty field is passthrough.

**3.6 Date range** (8 tests): initial range = the load window (`today - daysBack` … `today`);
"from" picker floor is a **fixed absolute `2024-01-01`**, NOT the window start (amended
2026-09-05, explicit user correction — "FROM is definitely NOT clamped to the window start and
can be anything the user wants after 1/1/24. BUT THE USER NEEDS TO CHANGE IT, NOT ANYTHING
ELSE"); "to" picker clamped at today; narrowing inward filters client-side; invalid
to-before-from prevented/auto-corrected; changing "days back" in settings reloads and resets
"from" to the new window start; **the user moving "from" earlier than what's currently loaded
is the ONLY thing that triggers a wider backend fetch** — type/subtype/client-name/free-text
filters, and pressing "חפש!" with an unchanged "from", never trigger a fetch; nothing but a
direct user edit of the "from" field ever changes its value (no auto-jump on search).

**3.7 Combined filters (AND across, OR within)** (6 tests): type(OR)+client-name AND; triple
combination (type+subtype+client-name); date-range-narrowed+type; all five categories set to
match exactly one known row; all five set so no row satisfies all → zero rows; removing one
category from a multi-filter combination correctly widens the result.

**3.8 No clear button, manual reset** (4 tests): full manual reset across all filters restores
the full loaded set; partial reset leaves remaining filters still active; a "clear all" control
genuinely does not exist anywhere in the UI (absence check); resetting a multi-select
per-value/chip works the same as reopening the dropdown and unchecking each one.

**Opens resolved 2026-09-05**: `GET /clients/search` exists (Story 2); 3.6's "clamping" →
fixed `2024-01-01` floor + user-only "from" edits + fetch-on-earlier-from (above). Still open:
3.3's P1 (auto-deselect of a now-invalid selected subtype).

Draft Playwright code for these ~85 cases to be added to `contracts/playwright-draft.md`.

**Coverage mandate (2026-09-05, user)**: the Playwright suite must cover *all* functionality
that already exists in the VIEWABLE frontend (Stories 4–8) — not only net-new work. When the
suite is written is the implementer's call for now, but existing behavior is in scope, not
grandfathered out.

### Component 0 — Layout (resolved + full test enumeration, 2026-09-05, 11 tests)

Decisions: filter bar is **always visible, single row that wraps** at narrow widths (never a
collapsible/toggled panel); top bar keeps the **same fixed control set** (logo, gear, refresh,
Σ, expand-all/collapse-all) in the same RTL order at every viewport, shrinking/wrapping rather
than moving anything into an overflow menu.

1. Desktop: all filter controls in one horizontal row above the list.
2. Mobile: same controls wrap onto multiple lines, never hidden behind a toggle.
3. No filter control is ever hidden behind a collapsed/closed panel at any viewport size.
4. Filter bar's RTL control order is consistent between desktop and mobile (only wrapping
   changes).
5. Apply button stays visible/reachable at every viewport size.
6. Desktop top bar shows all 5 control groups simultaneously in consistent RTL order.
7. Mobile top bar keeps all controls visible (shrunk/wrapped), never an overflow "..." menu.
8. No top-bar control disappears entirely at any tested viewport width.
9. Mobile icon/touch targets remain large enough to tap accurately (usability floor, not just
   presence).
10. Live browser resize (desktop→narrow) reflows correctly with no leftover artifacts from the
    wider layout.
11. RTL is consistent everywhere in this chrome — no accidental LTR-ordered element.

**0b. General responsiveness (moved here from a draft Component 6.4, 2026-09-05)** — this is a
cross-cutting Layout concern, not mobile-specific: the app must adapt to screen
orientation/direction (mobile), resolution (both desktop and mobile), font-size/zoom scaling
(both), and available view area (both), not just a single mobile/desktop breakpoint switch.
(6 tests): rotating a mobile device (portrait↔landscape) reflows correctly live; increasing
browser zoom/OS font-size scaling doesn't overflow containers or break control usability;
progressively resizing a desktop browser window narrower reflows smoothly through intermediate
widths, not just jumping cleanly between two fixed breakpoints; reducing available viewport
area (e.g. DevTools panel open, split-screen on a tablet) reflows correctly; an extremely
narrow width doesn't crash the layout (best-effort, not a supported-width guarantee); an
extremely wide desktop monitor doesn't leave the layout looking broken or absurdly stretched.

### Component 4 — Row Expand (single) (full test enumeration, approved 2026-09-05, ~58 tests)

Right panel uses the per-type field manifest in `contracts/field-manifests.md` (ALWAYS/
IF-EXISTS/NEVER per field, subtype-conditional overrides). Left panel is a WhatsApp-style chat:
human ("user") on the right, bot ("assistant") on the left, image attachments as clickable
thumbnails opening a larger view dismissed with "OK". Lookback window boundary is **inclusive**
(consistent with Component 2).

**4.1 Pressing "+" opens both panels correctly** (8): right panel shows the correct event's
data; left panel shows the correct session/messages for that event; row expands in place (no
navigation/modal); rows below visibly shift down; toggle icon changes state; right panel sits
right of left panel on desktop; identical behavior regardless of which row; no flash of
wrong/blank content before real data appears.

**4.2 Collapsing back** (5): toggle again closes both panels; row/icon revert to collapsed;
rows below shift back up; collapsing one row doesn't affect another independently-expanded row;
re-expanding shows fresh correct data, not stale content.

**4.3 Right panel field manifest correctness** (22, per `contracts/field-manifests.md`):
הסכם — common fields always shown; manifest fields shown when populated; same fields absent
when empty; reference/reference_hint ALWAYS shown when subtype ≠ "יצירה"; same fields
IF-EXISTS-only when subtype = "יצירה"; `event_id`/`agreement_id`/`component_id` never appear.
בנק — subtype "הפקדה" → bank fields + vat_status shown even null; other subtypes → same fields
IF-EXISTS only; payer_name always IF-EXISTS; split fields never shown, any subtype/value.
חשבונית — display_number/status_label/vat_status always shown; status/status_code never shown;
payment_method IF-EXISTS; subtype 320/400 + "העברה בנקאית" → bank fields shown even empty;
subtype 320/400 + other payment method → bank fields completely absent; subtype 305/300 → bank
fields completely absent regardless; subtype 330 → reference/reference_hint shown even empty;
other subtypes → IF-EXISTS only. Cross-cutting: Hebrew labels render correctly (spot-check);
internal/bookkeeping fields never appear for any type. **A record with a `source_type` outside
the three known types shows an explicit "unrecognized event type" message instead of any
fields** (2026-09-05 decision, defensive — 1 additional test).

**4.4/4.5 Left panel — WhatsApp-style chat** (17): user messages on the right; assistant
messages on the left; chronological order; only messages within the lookback window shown; the
anchor message always included; image attachment renders as a thumbnail, not inline full-size;
clicking a thumbnail opens a larger view; larger view has an "OK" to dismiss; dismissing
returns to the chat view without leaving the expanded row; text-only message shows just its
bubble, no broken-image placeholder; sender name renders correctly; timestamp shown/orderable;
multiple images each have independent thumbnail/lightbox behavior; a message just outside the
window is excluded; **a message exactly at the boundary (N minutes before) is included**
(2026-09-05 decision, inclusive); **a video or audio message in the window shows a generic
media-attachment placeholder or its extracted text, not a playable control** (2026-09-05
decision — video/audio playback out of scope for v1); **a document attachment (PDF/DOCX)
renders as a clickable thumbnail exactly like an image, and clicking opens it in the same larger
view relying on the browser's native PDF/doc rendering, dismissed with "OK"** (2026-09-05
decision).

**4.6 Graceful degradation** (5): missing/unresolvable session shows a clear "unavailable"
message in the left panel; right panel stays fully correct even when the left panel fails; no
crash/infinite spinner on unresolvable context; same graceful handling when the session
resolves but the specific message doesn't; same graceful handling when a message's
`image_path` points to a file no longer on disk (broken-media indicator, not a broken app).

**4.7 Layout/positioning** (3): right panel positioned right of left panel on desktop (real
bounding-box check); both panels sit directly below the expanded row; expanding one row doesn't
visually corrupt/overlap unrelated rows. (Mobile stacking is Component 6's responsibility, not
duplicated here.)
Pressing "+" on a row opens both panels with the correct data (right panel matches the event's
full detail; left panel shows the linked message plus the configured lookback window, image or
text as appropriate); the row below is visibly pushed down (real layout assertion, not just
presence).

### Component 5 — Row Expand (multi / expand-all / collapse-all) (full enumeration, ~19 tests)

**Any Apply or "refresh data" collapses every expanded row** (2026-09-05 decision) — expand
state never survives either action. **A full page reload also resets every row to collapsed**
(2026-09-05 decision) — expand state is never persisted.

**5.1 Multiple independent expansions** (5): expanding row 2 doesn't close row 1; both show
correct, non-bleeding data; rows below shift down by the combined expansion height; a 3rd row
also stays independent; collapsing one of several open rows doesn't affect the others.

**5.2 Collapse-all** (4): closes every expanded row regardless of count; works on a mix of
individually- and expand-all-expanded rows; all return to collapsed height; no-op with zero
expanded.

**5.3 Expand-all** (5): opens every currently-loaded (post-filter) row, including untouched
ones; already-open rows aren't double-expanded/glitched; each shows correct data; scales to a
long list (no hardcoded cap); no-op with all already expanded.

**5.4 Apply collapses everything** (3): pressing Apply (even with no real value change)
collapses all expanded rows, regardless of how many/how they got expanded; the newly-filtered
list starts fully collapsed.

**5.5 Refresh collapses everything** (2): pressing "refresh data" collapses all expanded rows;
the refreshed list starts fully collapsed.

**5.6 Reload resets expand state** (1, 2026-09-05 decision): a full page reload with rows
expanded shows the list fully collapsed after reload — expand state is never persisted.

### Component 6 — Mobile Viewport Layout (full enumeration, approved 2026-09-05, 14 tests)

**Breakpoint (2026-09-05 decision)**: standard responsive CSS on the browser's actual viewport
width — below **768px** is mobile (stacked), at/above is desktop (side-by-side); live-reactive
to resize, not a device-type detection.

Chat/left panel is a **fixed height with its own internal scroll** on both desktop and mobile
(same constant, TBD exact value, same across every expansion) — see spec.md. General
cross-viewport responsiveness (resolution/zoom/available-area, not just a mobile/desktop
switch) is covered under Component 0's "0b" rather than duplicated here.

**6.1 Single expanded row stacks vertically** (2): right (detail) panel appears above the left
(chat) panel on mobile, not side-by-side; both panels are full/near-full width, not squeezed
into half-width columns.

**6.2 Multiple expanded rows on mobile** (2): each independently expanded row shows its own
correctly-stacked pair of panels; stacking applies uniformly, not as a one-row special case.

**6.3 Row list at mobile width** (4): description wraps onto a second sub-row when needed; the
other five fields stay on the first line under normal circumstances; no row ever requires
horizontal scrolling at any supported width; amount and date stay fully visible/un-truncated
(highest-priority fields) even under tight width. (No firm field-removal policy exists yet —
not tested as a rule, only as "nothing breaks/scrolls sideways.")

**6.5 WhatsApp chat panel usability + fixed height** (6): chat bubbles remain legible at mobile
width; tapping a thumbnail opens the larger view correctly sized for the smaller screen with
"OK" reachable/tappable; the chat panel occupies its fixed height on mobile, not the full
remaining page height; the panel has its own internal scrollbar independent of the outer page
scroll; scrolling inside the chat panel never scrolls the outer row list, and vice versa;
scrolling within the panel correctly reveals every message in the lookback window, top to
bottom.

**Desktop note (2026-09-05 decision)**: the same fixed-height + internal-scroll rule for the
chat panel applies on desktop too, not just mobile — one consistent behavior, tested once and
verified on both.

### Component 7 — Σ Summation (full enumeration, approved 2026-09-05, ~17 tests)

🚨 **v1 is a deliberately naive placeholder — real summation semantics are TBD, not solved
here.** Known real nuances NOT implemented in v1 (tracked as future work, not tested now):
sign-correcting `חשבון זיכוי` (positive-stored but financially negative); deduplicating the
same underlying payment when it appears as both a bank deposit and a Morning document;
per-client netting of agreement amounts (owed/plus) against payments (received/minus). None of
these are in scope for this component's tests — v1 sums raw `amount` values exactly as stored,
nothing more, and is explicitly documented as not-yet-real financial math.

**7.1 Basic sum/count display** (4): correct total matching the sum of every visible row's
`amount`; displayed count matches events actually contributing; repeat press with nothing
changed is deterministic; single-row view shows that row's amount with count 1.

**7.6 Σ disabled during refresh** (1, 2026-09-05 decision): the Σ button is disabled/unpressable
while a "refresh data" call is in flight, re-enabled once it completes.

**7.2 Sum disappears on view change** (4, **revised 2026-09-05** — no longer "stale-marked,"
now fully cleared): applying a filter change clears the previously-shown sum entirely, not
just marking it stale; pressing refresh also clears it; the sum only reappears by pressing Σ
again for the new view; merely expanding/collapsing rows does **not** clear an already-shown
sum, since it doesn't change the underlying filtered set.

**7.3 Excluding null/unparseable amounts** (3): an event with a null amount is excluded from
the sum; also excluded from the displayed count; a view where every event has a null amount
shows a sum of ₪0 with a count of 0, not an error.

**7.4 Independence from expand/collapse state** (2): sum is identical whether computed with
zero or all rows expanded; expanding/collapsing does not itself clear or recompute the sum.

**7.5 Sign/decimal/currency correctness** (4, raw-value only — no semantic sign correction per
the TBD note above): a genuinely negative stored `amount` correctly reduces the total (not
treated as absolute value); a view netting to a negative raw total displays that correctly, not
floored at zero; non-integer amounts sum without visible rounding distortion; currency
formatting stays consistent regardless of sign.

### Component 8 — Settings (full enumeration, approved 2026-09-05, 23 tests)

Same-date tiebreaker mirrors sort direction (`event_id` descending under newest-first,
ascending under oldest-first — 2026-09-05 decision). No maximum on "days back" in v1.

**8.1 Theme switching** (4): dark theme changes colors app-wide; switching back restores
light; applies immediately, no reload; an open expanded row's panels also restyle correctly.

**8.2 Sort order toggle** (4): oldest-first re-sorts immediately; newest-first restores
original order; tiebreaker flips direction to match; the change is a client-side re-sort, no
new backend load.

**8.3 Days-back validation** (4, no max): valid value reloads immediately and persists; zero/
negative input rejected/clamped, never sent as-is; non-numeric input rejected; clearing the
field falls back to a defined default, not sent as invalid.

**8.4 Lookback-minutes validation** (5): valid value (0–60) takes effect on next expansion;
above-60 clamped/rejected client-side; negative rejected; non-numeric rejected; backend
independently clamps to [0,60] regardless (defense in depth).

**8.5 Persistence** (2): all four settings preserved exactly after reload; settings persist
across tab/browser close too (`localStorage`).

**8.6 Settings panel open/close** (3): opening shows current values pre-filled; closing without
changes leaves everything unchanged; reopening shows consistent values.

**8.7 Logout reachable from settings** (1): the logout control triggers the flow already fully
tested in Component 1 (entry-point reachability only, not re-testing logout mechanics).

### Component 9 — Visual Regression (full enumeration, approved 2026-09-05, 8 tests + 1 rule)

**9.1 Collapsed list baseline** (1): desktop, default light theme, seeded fixture — matches
baseline within a small anti-aliasing tolerance.

**9.2 Expanded row baseline** (2): a single expanded row (both panels, desktop) matches its
baseline; an expanded row whose chat panel includes an image thumbnail matches its baseline
(covers real image content, not just text/layout).

**9.3 Mobile baselines** (2): collapsed list at mobile width matches its baseline; expanded row
at mobile width (stacked panels) matches its baseline.

**9.4 Dark theme baseline** (2): collapsed list in dark theme matches its baseline; expanded
row in dark theme matches its baseline.

**9.5 Baseline governance** (1 process rule, not an automated test): a baseline image is only
ever updated through deliberate human review/approval — never auto-accepted just because a run
produced a new screenshot.

Human approval gate: each component above is reviewed/approved **as a unit, case-by-case**
(same treatment Component 1 got) before its actual Playwright test code is written — same gate
shape as `billed`/`expensive` tests being described in `tasks.md` before being coded.
