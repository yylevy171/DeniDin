# Tasks: Dev/Prod Environment Separation

**Input**: Design documents from `/specs/019-env-separation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

---

**IMPORTANT**: This task list MUST comply with:
- **CONSTITUTION.md** (§I-III): Config-only (NO env vars), UTC timestamps, Git workflow with feature branches
- **METHODOLOGY.md** (§VI): TDD with human approval gates — Tests MUST be approved before implementation

**Note on TDD scope for this feature**: This is a deployment/ops-topology feature (Dockerfiles, compose files, config files, shell scripts) rather than new application logic. Where a task produces genuinely testable code (config loading/path resolution, the entrypoint's ngrok-status-write logic), it follows the standard TDD pair (`a` test → 👤 approval → `b` implementation). Where a task is pure infrastructure config with no unit-testable code path (writing a Dockerfile, a compose YAML file, a `.example.json`), it is a single task validated by a **manual verification step** instead — per CONSTITUTION §V this is appropriate since these aren't internal application components with business logic.

**Organization**: Tasks are grouped by user story (from spec.md / user-stories.md), in priority order: US1 (P1), US2 (P1), US3 (P2), US4 (P2), US5 (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- **[T###a]**: Write tests (REQUIRES HUMAN APPROVAL before T###b)
- **[T###b]**: Implement code (BLOCKED until T###a approved, tests are IMMUTABLE)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Rename/split the data roots and scaffold the per-environment config skeletons everything else depends on.

- [X] T001 Rename `apps/denidin-app/test_data/` to `apps/denidin-app/dev_data/` (git mv, preserving any existing dev-relevant contents)
- [X] T002 [P] Create `apps/denidin-app/config/config.dev.example.json` (committed) — same schema as today's `config.example.json`, `data_root: "dev_data"`, placeholder Morning MCP shared-secret field matching the dev morning-mcp-app example
- [X] T003 [P] Create `apps/denidin-app/config/config.prod.example.json` (committed) — `data_root: "data"`, otherwise mirrors today's `config.example.json`
- [X] T004 [P] Create `apps/morning-mcp-app/config/config.dev.example.json` (committed) — `api_url` sandbox host, placeholder `mcp.ngrok_authtoken`/`mcp.auth_token`/`mcp.status_file` for the dev environment
- [X] T005 [P] Create `apps/morning-mcp-app/config/config.prod.example.json` (committed) — `api_url` production host, placeholder dev-distinct ngrok/auth/status fields
- [X] T006 Update `apps/denidin-app/config/config.test.json`'s `data_root` (and nested `memory.session.storage_dir`/`memory.longterm.storage_dir`) to a new ephemeral root separate from `dev_data/` (e.g. keep literal `test_data` as pytest's own root name, now decoupled from the renamed persistent dir) — no edit needed: `config.test.json` already said `"test_data"`, which is now automatically decoupled since the populated directory was renamed to `dev_data/`
- [X] T007 [P] Create `shared/mcp-status-dev/` and `shared/mcp-status-prod/` directories at repo root (empty, `.gitkeep`-only — actual status files are runtime-generated, gitignored)
- [X] T008 Remove the old top-level `apps/denidin-app/config/config.example.json` and `apps/morning-mcp-app/config/config.example.json` once T002–T005 are confirmed to fully replace them (see plan.md Project Structure)

**Manual verification**: `python3 -c "from src.models.config import AppConfiguration; AppConfiguration.from_file('config/config.dev.example.json')"` (and same for `.prod.example.json`) load without validation errors in both apps; `pytest tests/unit/test_session_manager.py -q` still passes against the repointed `config.test.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Container/entrypoint machinery that every user story's "run it in Docker" requirement depends on. No user story can be verified end-to-end until this phase is done.

- [X] T009a [P] Write tests for the morning-mcp-app status-file writer in `apps/morning-mcp-app/tests/unit/test_status_writer.py`: given a tunnel URL, writes `{"status": "running", "server_url": ..., "updated_at": <UTC ISO8601>}`; given no tunnel, writes `{"status": "not running", "server_url": null, ...}`; UTC timestamp format asserted per CONSTITUTION §II
- [X] T009b Extract the status-file-writing logic currently inline in `run_morning_mcp.sh` (bash `write_status_running`/`write_status_not_running`) into a small Python helper (e.g. `apps/morning-mcp-app/src/denidin_mcp_morning/status_writer.py`) callable from the container entrypoint (BLOCKED until T009a approved)
- [X] T010 [P] Add ngrok CLI installation to `apps/morning-mcp-app/Dockerfile` (matching the architecture ngrok releases support; pin a version) — already present from feature 018; confirmed and left as-is
- [X] T011 Write `apps/morning-mcp-app/docker-entrypoint.sh`: starts the FastMCP server, then (if `mcp.ngrok_authtoken` is set in the mounted config) starts `ngrok http` against the server's port inside the container, polls ngrok's local inspector API for the public URL, and calls the T009b status-writer to publish it to the mounted status-file path; writes `"not running"` first as the safe default (mirrors today's `run_morning_mcp.sh` ngrok block, relocated into the container) — depends on T009b, T010 — already existed from feature 018; refactored its inline bash JSON-writing to delegate to the T009b Python helper instead of duplicating the logic
- [X] T012 [P] Update `apps/morning-mcp-app/Dockerfile` `CMD`/`ENTRYPOINT` to invoke `docker-entrypoint.sh` from T011 instead of running the server module directly — already present from feature 018; confirmed and left as-is
- [X] T013 [P] Write `docker-compose.dev.yml` at repo root: `denidin-app-dev` + `morning-mcp-app-dev` services, each mounting its own `config.dev.json`, `apps/denidin-app/dev_data` (denidin only), `apps/*/logs`, and the shared `./shared/mcp-status-dev` volume into both
- [X] T014 [P] Write `docker-compose.prod.yml` at repo root: `denidin-app-prod` + `morning-mcp-app-prod` services, mounting `config.prod.json`, `apps/denidin-app/data`, `apps/*/logs`, and `./shared/mcp-status-prod` into both — structurally must NOT reference `mcp-status-dev` anywhere
- [X] T015 Remove the old top-level `docker-compose.yml` once T013/T014 are verified to supersede it
- [X] T016 [P] Rewrite `apps/denidin-app/run_denidin.sh` and `stop_denidin.sh` per `contracts/run-stop-script-contract.md`: positional `dev`/`prod` arg, `docker compose -f docker-compose.<env>.yml {up -d|stop} denidin-app-<env>` wrapper only, no PID-file/nohup logic
- [X] T017 [P] Rewrite `apps/morning-mcp-app/run_morning_mcp.sh` and `stop_morning_mcp.sh` the same way, targeting `morning-mcp-app-<env>` (also fixed `restart_morning_mcp.sh`, a direct consequence not originally listed as a task)

**Manual verification (👤 approval gate) — NOT YET PERFORMED, requires the operator**: `./run_morning_mcp.sh dev` then `docker compose -f docker-compose.dev.yml ps` shows `morning-mcp-app-dev` healthy; `cat shared/mcp-status-dev/*.json` shows `"status": "running"` with a real `https://*.ngrok-free.app` URL within ~10s of container start. Requires Docker running and real dev ngrok/Morning credentials in `config.dev.json` — could not be executed by the implementing agent.

**Checkpoint**: Foundation ready — user story implementation/verification can now proceed.

---

## Phase 3: User Story 1 — Run all four instances side by side (Priority: P1) 🎯 MVP

**Goal**: All four containers (denidin-dev, denidin-prod, morning-dev, morning-prod) can run concurrently on one machine with zero port/data conflicts. Per the WhatsApp-session clarification, `denidin-app-dev` and `denidin-app-prod` sharing one real Green API instance means only one of that *pair* should be actively polling real traffic at a time — the two morning-mcp-app containers have no such restriction and can always run together.

**Independent Test**: Start all four via the Phase 2 scripts (with `denidin-app-dev` intentionally stopped, or `denidin-app-prod` intentionally stopped, to respect FR-014); confirm via `docker compose ... ps` across both compose files that the intended set is up, with distinct ports/volumes/logs and no conflicts.

- [X] T018 [P] [US1] Confirm/adjust host port mappings in `docker-compose.dev.yml`/`docker-compose.prod.yml` so denidin-dev/prod and morning-dev/prod each bind distinct host ports (no two services claim the same host port) — morning-mcp-app-dev:8000, morning-mcp-app-prod:8001; denidin-app has no host port exposure (only polls outbound)
- [ ] T019 [US1] 👤 **REQUIRES OPERATOR**: Populate real `apps/denidin-app/config/config.dev.json` and `config.prod.json` (identical `green_api_instance_id`/`green_api_token` per FR-014; role mapping per FR-015/US5 — prod `godfather_phone`="972506205541", prod `admin_phones`=["972522968679"], fixed; dev starts with `972522968679` in *either* `godfather_phone` or `admin_phones`, operator's choice, never both), and `apps/morning-mcp-app/config/config.dev.json`/`config.prod.json` from the T002–T005 examples (operator-provided secrets — not committed; agent cannot supply real Green API/Morning/OpenAI/ngrok credentials)
- [ ] T020 [US1] 👤 **MANUAL APPROVAL GATE — REQUIRES OPERATOR + DOCKER**: Run `./run_morning_mcp.sh dev`, `./run_morning_mcp.sh prod`, and `./run_denidin.sh prod` (leaving `denidin-app-dev` stopped, per FR-014); verify all 3 containers show `Up` with no port-bind or volume errors. Separately, `./stop_denidin.sh prod` then `./run_denidin.sh dev`; verify it starts cleanly and prod's containers are unaffected — demonstrating the hand-off procedure from User Story 1's Acceptance Scenario 3.

**Checkpoint**: User Story 1 fully functional — all four instances can coexist, with the documented one-denidin-at-a-time-for-real-traffic rule understood and exercised.

---

## Phase 4: User Story 2 — Env-pairing / no cross-boundary MCP calls (Priority: P1)

**Goal**: dev denidin-app's MCP calls resolve only to dev morning-mcp-app (sandbox Morning); prod resolves only to prod (production Morning). Structurally impossible to cross, not just configured correctly.

**Independent Test**: Send an invoice command to dev denidin-app; confirm it lands in Morning sandbox. Repeat for prod against production. Confirm neither compose file's containers have any mount/env path referencing the other environment's shared-status directory.

- [X] T021a [P] [US2] Write tests in `apps/denidin-app/tests/unit/test_morning_mcp_locator_env.py`: given `config.dev.json`'s `mcp.morning_status_file` path, `MorningMcpLocator` resolves only that path; a status file written at the prod-equivalent path is never read
- [X] T021b [US2] Verify/adjust `MorningMcpLocator` (existing code in `apps/denidin-app/src/`) needs no logic change — only confirm it already resolves purely from the injected config path with no hardcoded fallback to another path (BLOCKED until T021a approved) — confirmed, no change needed
- [X] T022 [US2] Grep `docker-compose.dev.yml` and `docker-compose.prod.yml` to confirm no service in one file mounts the other file's `shared/mcp-status-*` directory (structural isolation check, can be a one-line CI-able grep assertion or manual review) — confirmed clean, zero cross-references
- [ ] T023 [US2] 👤 **MANUAL APPROVAL GATE — REQUIRES OPERATOR + DOCKER + REAL WHATSAPP**: With `denidin-app-prod` + `morning-mcp-app-prod` running, send a real invoice-creation WhatsApp command from AH's number; confirm it lands in Morning **production** only. Then, per the hand-off procedure, stop `denidin-app-prod` and start `denidin-app-dev` (morning-mcp-app-dev already running); send the same command from ylevy's number (dev's godfather); confirm it lands in Morning **sandbox** only. Restore prod afterward (stop dev, start prod).

**Checkpoint**: User Stories 1 AND 2 both verified — environments run together and never cross-wire.

---

## Phase 5: User Story 3 — Operator can tell environments apart at a glance (Priority: P2)

**Goal**: Process/container names, log paths, and status files are unambiguous per environment without opening config.

**Independent Test**: `docker compose -f docker-compose.dev.yml ps` / `...prod.yml ps` show clearly-named services; log files are distinguishably pathed; stopping one environment doesn't touch the other.

- [X] T024 [P] [US3] Confirm service names in `docker-compose.dev.yml`/`docker-compose.prod.yml` are unambiguous (`denidin-app-dev`, `denidin-app-prod`, `morning-mcp-app-dev`, `morning-mcp-app-prod` — already set in T013/T014; this task is a naming-consistency review pass)
- [X] T025 [P] [US3] Per FR-004, each service's mounted log directory MUST be environment-scoped and distinctly named — update `docker-compose.dev.yml`/`docker-compose.prod.yml` volume mounts to `apps/denidin-app/logs/dev/` + `apps/morning-mcp-app/logs/dev/` (dev) and `.../logs/prod/` (prod), rather than both environments' containers mounting today's single shared `logs/` directory
- [ ] T026 [US3] 👤 **MANUAL APPROVAL GATE — REQUIRES OPERATOR + DOCKER**: With all 4 running, run `./stop_denidin.sh dev`; confirm only `denidin-app-dev` stops (`docker compose -f docker-compose.prod.yml ps` shows `denidin-app-prod` still `Up`, unaffected)

**Checkpoint**: User Stories 1–3 verified.

---

## Phase 6: User Story 4 — Shared OpenAI key, split Morning credentials (Priority: P2)

**Goal**: dev and prod denidin-app configs carry identical OpenAI fields; dev and prod morning-mcp-app configs carry distinct Morning sandbox/production fields.

**Independent Test**: Diff the two denidin-app configs' OpenAI fields (must match); diff the two morning-mcp-app configs' Morning fields (must differ, sandbox vs. production host).

- [X] T027 [P] [US4] Add a config-consistency check documented in `apps/denidin-app/README.md` (or a short comment in `config.dev.example.json`/`config.prod.example.json`) stating `ai_api_key`/`ai_model`/`ai_vision_model`/`ai_embedding_model` MUST be identical across the two real config files — since there's no OpenAI sandbox, this is a documentation/process control, not enforceable code — documented via the "Environments (dev/prod)" section added to CLAUDE.md
- [ ] T028 [US4] 👤 **MANUAL APPROVAL GATE — REQUIRES OPERATOR**: Diff real `apps/denidin-app/config/config.dev.json` vs `config.prod.json` — confirm OpenAI-related fields match exactly; diff real `apps/morning-mcp-app/config/config.dev.json` vs `config.prod.json` — confirm `api_url`/`api_key_id`/`api_key_secret` differ and dev's `api_url` is the sandbox host (needs T019's real config files to exist first)

**Checkpoint**: User Stories 1–4 verified.

---

## Phase 7: User Story 5 — Operator-switchable role testing in dev (Priority: P2)

**Goal**: The operator can test as godfather or admin in dev, using their one real number (`972522968679`), by editing config and restarting — no fake/synthetic numbers involved.

**Independent Test**: Inspect dev/prod `godfather_phone`/`admin_phones`; flip dev's field, restart, confirm the resolved role for `972522968679` changes accordingly.

- [ ] T029 [P] [US5] 👤 **REQUIRES OPERATOR (T019)**: Confirm `apps/denidin-app/config/config.prod.json`'s `godfather_phone` = `"972506205541"` and `admin_phones` = `["972522968679"]` (fixed, per FR-015); confirm `config.dev.json` currently has `972522968679` in exactly one of `godfather_phone`/`admin_phones` (builds on T019) — the `.example.json` files created in T002/T003 already default dev to godfather and prod to the fixed mapping; this task confirms the *real* config files match once T019 is done
- [X] T030a [P] [US5] Write a test in `apps/denidin-app/tests/unit/test_user_manager.py` (extend existing, if present) or a new `tests/unit/test_role_config_mutual_exclusivity.py`: given a config where the same phone number appears in both `godfather_phone` and `admin_phones`, `UserManager.resolve_role()` returns ADMIN (documents existing precedence — a regression guard for the "operator forgot to remove it from the old field" edge case, not new behavior) — added as new file `test_role_config_mutual_exclusivity.py` (existing `test_user_manager.py` left untouched, immutable per METHODOLOGY); actual API is `UserManager.get_user(phone).role`, not `resolve_role()`
- [X] T030b [US5] No production code change expected — `UserManager` already resolves purely from injected `admin_phones`/`godfather_phone` config values with ADMIN > GODFATHER precedence (verified in `apps/denidin-app/src/managers/user_manager.py`); T030a merely pins this down as a regression test (BLOCKED until T030a approved) — confirmed, no change needed
- [ ] T031 [US5] 👤 **MANUAL APPROVAL GATE — REQUIRES OPERATOR + DOCKER + REAL WHATSAPP**: With `972522968679` in dev's `godfather_phone`, text `denidin-app-dev` from that number; confirm GODFATHER behavior (e.g. higher token limit, memory access per `user_roles.godfather`). Then edit `config.dev.json` to move it into `admin_phones` instead, restart `denidin-app-dev`, and text again; confirm ADMIN behavior instead.

**Checkpoint**: All five user stories verified independently and together.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T032 [P] Update `CLAUDE.md`: (a) Commands section — new `./run_denidin.sh dev|prod` / `./run_morning_mcp.sh dev|prod` invocation, retired PID-file behavior, one-denidin-at-a-time-for-real-traffic rule (FR-014); (b) Repository Layout section — replace the description of the single root `docker-compose.yml` (removed per T015) with `docker-compose.dev.yml`/`docker-compose.prod.yml` — also added a new "Environments (dev/prod)" section and updated the Morning MCP integration / config-paths paragraphs
- [X] T033 [P] Update `apps/morning-mcp-app`/`apps/denidin-app` READMEs (or the "Running Both Apps Together" doc referenced from `docker-compose.yml`'s old comments) to describe the new dev/prod split and the hand-off procedure — also fixed `restart_morning_mcp.sh` (uncovered dependency on the old scripts' no-arg contract)
- [ ] T034 👤 **REQUIRES OPERATOR + DOCKER**: Run `quickstart.md` end-to-end exactly as written; fix any drift between the doc and actual behavior discovered during the run
- [X] T035 [P] `python3 -m pylint src/ --fail-under=7.0` and `python3 -m mypy src/ --config-file=mypy.ini` in both apps, confirming the new `status_writer.py` (T009b) passes existing lint/type gates — morning-mcp-app's status_writer.py: 10.00/10 pylint, clean mypy; denidin-app: 8.75/10 pylint (pre-existing debt, unrelated to this feature, still passes the 7.0 gate), same 22 pre-existing mypy errors as before (none in files this feature touched); full unit suite (462 tests) passes

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 (needs the renamed data dir and example configs to mount). BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2. Independent otherwise — this is the MVP.
- **User Story 2 (Phase 4)**: Depends on Phase 2 and (for its manual gate) Phase 3's containers being up (respecting the one-denidin-at-a-time rule). T021a/T021b are independently doable once Phase 2's compose files exist.
- **User Story 3 (Phase 5)**: Depends on Phase 2; its manual gate depends on Phase 3.
- **User Story 4 (Phase 6)**: Depends on Phase 1 (example configs) only — can run in parallel with Phases 3–5 if desired.
- **User Story 5 (Phase 7)**: Depends on Phase 1 (config values from T019) and Phase 2 (containers to test against); independent of Phases 4–6 otherwise.
- **Polish (Phase 8)**: Depends on all preceding phases the operator chooses to complete.

### Parallel Opportunities

- T002–T005 (all four `.example.json` files): parallel, different files.
- T013/T014 (the two compose files): parallel, different files, though both depend on T011/T012 existing conceptually (entrypoint referenced by both).
- T016/T017 (the two apps' run/stop script rewrites): parallel, different files.
- Phase 6 (US4) and Phase 7 (US5) can run any time after Phase 1, in parallel with Phases 3–5.

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1: all four running).
2. **STOP and VALIDATE**: four containers up, no conflicts — this alone is a meaningful, demoable milestone even before the MCP-pairing story is exercised end-to-end.

### Incremental Delivery

1. Setup + Foundational → containers buildable.
2. US1 → all four run concurrently (MVP).
3. US2 → verify env-pairing is unbreakable (the safety-critical story — do this before trusting dev with real Morning sandbox data).
4. US3 → operator ergonomics.
5. US4 → config-hygiene documentation/verification (can slot in anytime after Setup).
