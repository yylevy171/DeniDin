# Tasks: Feature 092 — Clients Tab: Resolution Corrections & Explicit Line Status

**Input**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`, `contracts/clients-api.md`, `quickstart.md`
**Branch**: `feature/092-undo-client-resolution-bugfix-068`

## Ground rules (apply to every task)

- **Task A / Task B gates (METHODOLOGY §VI.b).**
  - Each story's **A** task writes tests. They must be **RED** (failing for the right reason),
    then get **human approval**.
  - **B** (implementation) is blocked until A is approved.
  - After B, the same tests are **GREEN**.
  - Approved tests are immutable (§VIII).
- **Running tests.**
  - Backend tests run **only** via `apps/webapp/backend/scripts/run_unit_integration_tests.sh`
    (T001). Never a bare `pytest`.
  - Relay each `>>> TEST [k/N]` line live.
- **No mocks.** Real JSON files in `tmp_path`. Integration tests go through Starlette
  `TestClient` → the real routes, mirroring `tests/integration/test_events_endpoints.py`.
- Path prefixes: `BE` = `apps/webapp/backend`, `FE` = `apps/webapp/frontend/src`, `E2E` =
  `apps/webapp/e2e`.
- No feature flag (approved 2026-10-03, research R-9).

---

## Phase 1: Setup

- [x] T001 Symlink the shared wrapper: `BE/scripts/run_unit_integration_tests.sh -> ../../../denidin-app/scripts/run_unit_integration_tests.sh` (same pattern as `apps/morning-mcp-app/scripts/`). Verify it resolves `BE/venv/bin/python3` (it `cd`s to the symlink's parent, so dirname/..). Run it once on the existing suite as a green baseline.
- [x] T002 Add the per-test sound-off hook to `BE/conftest.py`: a `>>> TEST [k/N] STATUS: <nodeid>` line per test, on by default, opt-out `DENIDIN_TEST_SOUNDOFF=0`. Port it from `apps/denidin-app/conftest.py`'s hook, unchanged in behavior. Re-run the baseline and confirm the lines stream.

## Phase 2: Foundational (blocks all stories)

- [x] T003 In `BE/src/webapp_backend/clients_reader.py`, extend `_paths()` with `status` (`client_status.json`), `hidden` (`hidden_unmatched.json`) and `migrations` (`migrations.json`). Pure plumbing, with no behavior change. The existing suite stays green. Also give `BE/src/webapp_backend/server.py`'s `build_app` an optional `official_clients_fn` parameter, defaulting to the Morning source, so the integration tests (T008/T019/T028) can supply the client list without a Morning call. This is dependency injection, not a mock.

---

## Phase 3: US1 + US2 + US3 — explicit line status, hack removal, migration (P1) 🎯 MVP

These three stories share one mechanism (where `_row_status`'s flags come from), so they ship
as one increment.

**Independent test:** every line routes by `client_status.json`. Closing never changes amounts.
Comments no longer route. On first load, each line is in the same section the old comment
routing gave it.

### Task A — tests (RED, then human approval)

- [x] T004 [P] [US1] `BE/tests/unit/test_clients_line_status.py` — routing from `client_status.json`:
  - `closed` → `settled`, `check` → `check`, `active` → `active`;
  - a missing key → computed `settled`/`debt`/`missing_agreement`;
  - priority check > active > closed > past;
  - an unknown stored value is ignored, with a WARNING;
  - a `closed` row outranks `past` (pre-existing behavior kept).
- [x] T005 [P] [US1] Same file — **bugfix-068 regression**: a client agreed 10,000 and paid 2,000 with status `closed` gives `display_agreed == 10000`, `display_paid == 2000`, `status == "settled"`, and no YELLOW `agreed_status`/`paid_status` caused by closing (`*_inferred` absent).
- [x] T006 [P] [US2] Same file — comments no longer route, and nothing else changes:
  - a comment containing `לסגור` / `אפשר לסגור` / `לבדוק` / `לקוח פעיל` / `לקוחה פעילה`, with **no** status entry (migration marker already set), routes by numbers only;
  - **unchanged:** `למחוק` still yields `past` + a `removed_clients.json` entry, `לאחד "X"` still merges, `הסכם 5,000` still sets `manual_agreement_amount`, `להוריד` still dedupes deposits, and `לבדוק`/`לא ברור`/`חסר` still set YELLOW amount colouring.
- [x] T007 [P] [US3] `BE/tests/unit/test_clients_migration.py` — migration:
  - **(a) parity matrix.** For each comment (a single keyword; `לבדוק … לסגור`; `לקוח פעיל … למחוק`; `לקוח פעיל … לסגור`; `אפשר לסגור`; `לקוחה פעילה`; plain text), the section after migration + new routing equals the section from a **frozen inline copy of the pre-092 routing** in the test file. That copy is the test's own oracle, not imported from src.
  - **(b)** The migration writes `migrations.json["092_comment_line_status"]` (an Israel-local ISO timestamp with offset).
  - **(c)** It runs once: deleting a status afterward and recomputing does **not** re-create it.
  - **(d)** It never overwrites a pre-existing `client_status.json` entry.
  - **(e)** `client_comments.json` is byte-identical before and after.
  - **(f)** Merged-away clients are skipped.
- [x] T008 [P] [US1] `BE/tests/integration/test_clients_endpoints.py` — `POST /api/clients/{id}/status`, per `contracts/clients-api.md`:
  - `close`/`check`/`active` → 200 and persisted;
  - `reopen` on a closed debt line → `null` and routes to `debt`;
  - `reopen` on a closed line with agreed == paid → `active`;
  - `reopen` on a computed-green line (no status) → `active`;
  - bad or missing action → 400; unknown client → 404; `past` line → 409; no token → 401;
  - after each write, `GET /api/clients` reflects the new section without `refresh=1`.
  - Uses a fixture-injected `official_clients_fn`, the same as `test_caching.py`'s `_reader`. That's a constructor-injected callable, not a mock.
- [x] T009 [US1] Run T004–T008 via the T001 wrapper. Confirm all are RED for the right reason. **STOP: human approval of the tests.**

### Task B — implementation (blocked on T009 approval)

- [x] T010 [US1] `clients_reader.py`:
  - add `_apply_line_status(stats, client_status)`, which sets `is_check` / `is_active_client` / `is_manually_settled` from the file and WARNs on unknown values;
  - in `_apply_status_directives`, delete the `לקוח פעיל`, `לבדוק` and `לסגור` branches, including the whole `max(agreed, paid)` hack and the `*_inferred` markers;
  - keep the delete branch and the `removed_clients` return verbatim.
- [x] T011 [US3] `clients_reader.py` — add `_legacy_comment_status(comment, is_merged_away)`, a frozen port of research R-1's detection and precedence, used only by the migration. Add `ClientsReader._migrate_comment_status_once(stats, client_comments)`, called from `_compute_report()` after merge directives (so `is_merged_away` is known) and before `_apply_line_status`, under the existing `self._lock`. Marker in `migrations.json`, with `now_local()` (the same import style as `ledger_reader.py`). Log at INFO the count migrated per status.
- [x] T012 [US1] `clients_reader.py` — `_build_client_rows` adds `line_status`. New `ClientsReader.set_line_status(client_id, action)` implementing contract semantics (reopen per research R-3: recompute the row with the status cleared, using the same pure functions). Raises distinct exceptions for not-found and past. Invalidates `_report_cache`. Logs at INFO (client, action, result).
- [x] T013 [US1] `BE/src/webapp_backend/server.py` — route `POST /api/clients/{client_id}/status` (`run_in_threadpool`, `_error` mapping 400/404/409, Hebrew messages per contract). Register it next to the existing clients routes.
- [x] T014 [P] [US2] `FE/api.ts` — `ClientRow.line_status`; `setClientLineStatus(clientId, action)`.
- [x] T015 [US2] `FE/ClientsView.tsx` + `FE/clientsTheme.ts` — button group in the `ClientRowCard` header row:
  - **לסגור** (green, from `CLIENT_STATUS_COLORS.settled`) on check/active/debt/missing_agreement;
  - **לפתוח** (gray, `past` colour) on `settled`;
  - **לבדוק** (blue, `check`) and **לקוח פעיל** (light blue, `active`), each hidden when it targets the current section;
  - **no buttons on `past`**;
  - a press must not toggle expansion;
  - disable the group while saving, then re-fetch `fetchClients(false)` and replace state;
  - show an inline error on failure;
  - stable testIDs: `line-btn-close|reopen|check|active-<official_name>`.
- [x] T016 [US1] Run T004–T008 via the wrapper. All GREEN, and the full existing backend suite stays green (`test_caching.py` included).

---

## Phase 4: US4 + US5 — `Unknown-<event_id>` names and undo of name mappings (P2)

**Independent test:**
- no-name events appear as separate `Unknown-<event_id>` resolve-list rows, mappable like any
  name;
- an explicitly mapped alias can be unlinked and returns to the list with its note.

### Task A — tests (RED, then human approval)

- [x] T017 [P] [US4] `BE/tests/unit/test_clients_resolution.py` — naming:
  - events with no `client_name`/`payer_name`, or with literal `"Unknown"`, each become `unmatched` rows named `Unknown-<event_id>` with `event_count == 1`;
  - two such events never merge;
  - adding an older-dated no-name event leaves the existing names unchanged;
  - mapping `Unknown-<id>` → client X adds exactly that event's amount to X's totals and lists it in X's events;
  - a **named** alias mapped to `"Unknown"` keeps its own name (unchanged behavior).
- [x] T018 [P] [US5] Same file — `mapped_aliases`:
  - it contains only explicit `client_mapping.json` keys pointing at this client;
  - fuzzy-matched names and `לאחד` merge sources appear in `raw_names` but **not** in `mapped_aliases`.

  `unlink_mapping(raw_name)`:
  - removes only that key;
  - the raw name reappears in `unmatched` with its `mapping_notes.json` note intact;
  - the client's totals revert;
  - an unknown key raises not-found.
- [x] T019 [P] [US5] `BE/tests/integration/test_clients_endpoints.py` — `POST /api/clients/mapping/unlink`: 200 with `unlinked_from`; 404 unknown; 400 missing; 401 no token; the follow-up `GET /api/clients` shows the name back in `unmatched`.
- [x] T020 [US4] Run T017–T019 RED. **STOP: human approval.**

### Task B — implementation (blocked on T020)

- [x] T021 [US4] `clients_reader.py` `_aggregate_events` — the `Unknown-<event_id>` raw name (research R-5). With no `event_id`, keep plain `"Unknown"` and log a WARNING.
- [x] T022 [US5] `clients_reader.py` — `_build_client_rows` adds `mapped_aliases`, computed from `client_mapping.json`. Add `ClientsReader.unlink_mapping(raw_name)`: invalidate the cache and log at INFO.
- [x] T023 [US5] `server.py` — route `POST /api/clients/mapping/unlink`, registered **before** any route that could shadow it.
- [x] T024 [P] [US5] `FE/api.ts` — `ClientRow.mapped_aliases`; `unlinkClientMapping(rawName)`.
- [x] T025 [US5] `FE/ClientsView.tsx` — in the expanded `ClientRowCard`, list `mapped_aliases`, each with an unlink "×" (testID `unlink-<raw_name>`). On success, re-fetch.
- [x] T026 [US4] Run T017–T019 GREEN, and the full backend suite.

---

## Phase 5: US6 + US7 — "הסר מהרשימה" and ESC (P3)

### Task A — tests (RED, then human approval)

- [x] T027 [P] [US6] `BE/tests/unit/test_clients_resolution.py` — `hide_unmatched(raw_name)`:
  - it persists to a sorted, unique `hidden_unmatched.json`;
  - the name disappears from `unmatched`;
  - it's idempotent;
  - existing note-keyword hiding still works;
  - `למחוק` in a resolve-list note does **not** hide (no keyword was added).
- [x] T028 [P] [US6] `BE/tests/integration/test_clients_endpoints.py` — `POST /api/clients/unmatched/hide`: 200 `{hidden: true}`; idempotent; 400 missing; 401 no token; still hidden after `GET /api/clients?refresh=1`.
- [x] T029 [US6] Run RED. **STOP: human approval.**

### Task B — implementation (blocked on T029)

- [x] T030 [US6] `clients_reader.py` — `_split_unmatched` skips hidden names. Add `ClientsReader.hide_unmatched`. `server.py` route.
- [x] T031 [P] [US6] `FE/api.ts` `hideUnmatched`. `FE/ClientsView.tsx` `UnmatchedRowCard`: **הסר מהרשימה** button (testID `hide-unmatched-<raw_name>`), which removes the row from local state on success.
- [x] T032 [P] [US7] `FE/ClientsView.tsx` `ClientPicker` — a `useEffect` bound to `open`: a `window` `keydown` listener; `Escape` → `setOpen(false)` and clear the query; cleanup on close and unmount (research R-8).
- [x] T033 [US6] Run T027–T028 GREEN, and the full backend suite.

---

## Phase 6: Acceptance (approved UAT 1–9) — written and run together, once, after Phases 3–5 are GREEN

- [x] T034 Extend `E2E/seed_clients_fixture.py`, **additively**: every existing manifest key and event stays, so `10-clients.spec.ts` is unaffected. Pick the extra **real sandbox clients** with read-only search; nothing is created in Morning.
  - debt client: agreement 10,000 + invoice 2,000 (UAT 1);
  - fully paid client: agreement 3,000 = invoice 3,000 (UAT 2);
  - past client: activity before 2025-09-01 (UAT 4);
  - two mapping targets (UAT 6/7);
  - three no-name events, ₪500 / ₪1,200 / ₪3,000 (UAT 6);
  - raw name "Yisrael I" with a note (UAT 7);
  - one extra unmatched name (UAT 8);
  - pre-seeded `client_comments.json` with `לבדוק`, `לקוח פעיל` and `לסגור` on three distinct clients, with **no** `migrations.json`, so UAT 5 observes a real first-run migration.

  Write all names, ids and amounts to `manifest.json`. For UAT 6's "older event arrives later", the spec writes the 4th event file mid-test and reloads the ledger through the app's existing refresh path (`?refresh=1`).
- [x] T035 `E2E/tests-clients/11-line-status-and-resolution.spec.ts` — one `test()` per approved UAT 1–9, wording mirroring `spec.md`, serial, reusing `10-clients.spec.ts`'s login/navigation helpers. Assertions are on what the user sees: section membership, the displayed ₪ amounts, button presence and absence, resolve-list rows, dropdown visibility.
- [x] T036 Run `./node_modules/.bin/playwright test -c playwright.clients.config.ts` (both `10-` and `11-` files), relaying each result as it lands. **Stop on first failure and report.**

---

## Phase 7: Polish & release prep

- [x] T037 [P] `BE/scripts/preview_092_migration.py` — read-only CLI per `quickstart.md` §3 (`--clients-dir`, plus `--events-dir` for amounts). It imports the real `clients_reader` functions, writes nothing, and prints:
  - the statuses the migration would write;
  - section diffs (expected: none);
  - amount diffs (expected: the `לסגור` lines plus the R-4 edge).

  Plus a unit test in `BE/tests/unit/test_preview_092_migration.py` on a `tmp_path` fixture. Its A/B gate is folded into this task: show the RED run before implementing.
- [x] T038 [P] Update `CLAUDE.md`'s `apps/webapp/` section (Clients tab: the line-status buttons replace the `לסגור`/`לבדוק`/`לקוח פעיל` keywords; `Unknown-<event_id>`; the new JSON files) and `E2E/README.md` (the `11-` spec).
- [x] T039 Lint and type-check the touched files; `npm run build` in `apps/webapp/frontend` (tsc + vite) must pass.
- [ ] T040 Hand back for the **human-run** prod migration preview (quickstart §3) and the haleluya/release decisions. No cut, deploy or haleluya without explicit instruction.

---

## Dependencies

```
T001–T002 → T003 → Phase 3 (US1/2/3) ─┬→ Phase 4 (US4/5)
                                      └→ Phase 5 (US6/7)
Phases 3–5 GREEN → Phase 6 (acceptance) → Phase 7
```

- Phases 4 and 5 are independent of each other, and both touch `clients_reader.py` and
  `ClientsView.tsx`. Run them sequentially in one clone to avoid merge churn. Run them in
  parallel only if split across Avi/Bina with an agreed file-region boundary.
- Within a phase, the `[P]` test files are parallel. Backend B tasks are sequential (same file).
  `api.ts` tasks are `[P]` against backend work.

## Parallel examples

- Phase 3 A: T004/T005/T006 (one file, separate test classes — write together), T007 and T008
  side by side.
- Phase 3 B: T014 (`api.ts`) in parallel with T010–T013 (backend). T015 after T014.
- Phase 5 B: T031 and T032 (different components of the same file; trivial to sequence if one
  person).

## Implementation strategy

1. **MVP = Phase 3.** It kills the bugfix-068 corruption, delivers the four buttons, and keeps
   every line where it was. It's shippable on its own.
2. Phase 4, then Phase 5, as increments.
3. Acceptance (Phase 6) runs once over the whole feature, per the approve-early/code-late rule.

## Summary

| Phase | Stories | Tasks |
|---|---|---|
| 1–2 Setup/Foundational | — | 3 |
| 3 | US1 / US2 / US3 | 13 |
| 4 | US4 / US5 | 10 |
| 5 | US6 / US7 | 7 |
| 6 Acceptance | UAT 1–9 | 3 |
| 7 Polish | — | 4 |
| **Total** | | **40** |
