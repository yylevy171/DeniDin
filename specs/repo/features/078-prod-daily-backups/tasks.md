# Tasks: Automated Daily Prod Backups

**Input**: Design documents from `specs/repo/features/078-prod-daily-backups/`
**Prerequisites**: plan.md, spec.md, user-stories.md, research.md, data-model.md, contracts/, quickstart.md

---

**IMPORTANT**: Complies with CONSTITUTION.md §I (no env vars — `scripts/backup_prod/config.json`,
gitignored, mirrors `docker-compose.*.local.yml`'s per-host-config precedent), §II (Israel local
time — every timestamp/trigger/filename date), §XVI (exit codes), and METHODOLOGY.md §VI
(TDD gates below) / §VII (Integration Contracts, already in `contracts/script-contracts.md`).

**Test tooling**: pytest driving real subprocess calls against the real bash scripts, using
scratch fixture trees instead of mocks — the exact pattern already established by
`scripts/health_monitoring/tests/test_env_scripts.py` (per CONSTITUTION §I/§V: real internal
code paths, zero `unittest.mock`). SQLite fixtures are real, tiny, throwaway `.db` files created
per-test, not recordings. The real-SSH / real-Windows-Task-Scheduler / real-LaunchAgent paths
have **no automated coverage** here — same documented, accepted gap as
`register_prober_schedule.sh`'s own `schtasks.exe` branch and `deploy_release.sh`'s remote path —
covered instead by `quickstart.md`'s manual verification steps, run only with explicit approval
per CLAUDE.md's environment-start rule.

**Acceptance (`billed`/`expensive`-equivalent) scenarios**: N/A — this feature makes no OpenAI
calls. UAT 1/3 (zero-downtime, restore integrity) are the closest equivalents here; per
METHODOLOGY.md §VI.a they were already drafted and approved before `speckit.plan` ran (see
`plan.md`'s header) and are exercised as the manual `quickstart.md` gates in US1/US3 below, not
as pytest code — consistent with how this repo treats real-environment/real-hardware scenarios
it cannot safely automate (same treatment as the `schtasks.exe`/SSH gaps above).

---

**Tests**: TDD — every "a" test task requires human approval before its paired "b" implementation
task; once approved, tests are immutable without explicit re-approval.

**Organization**: Grouped by user story (UAT 1-5 from `user-stories.md`), independently testable.

## Path Conventions

Single project — new `scripts/backup_prod/` directory at repo root, sibling to
`scripts/health_monitoring/`/`scripts/windows_prod/` (per `plan.md`'s Structure Decision). No
`apps/` changes.

---

## Phase 1: Setup

**Purpose**: Directory scaffold + config template — no logic yet.

- [ ] T001 Create `scripts/backup_prod/` directory with `tests/` subdirectory
- [ ] T002 [P] Create `scripts/backup_prod/config.example.json` (committed template: Windows-side
  `daily_backup_dir`/`monthly_backup_dir` + source `data_dir`/`config_dir`/`logs_prod_dir`
  absolute paths; Mac-side `mac_daily_backup_dir`/`mac_monthly_backup_dir` + `ssh_host_alias`
  defaulting to `denidin-winprod`) — no real paths/secrets, matching `config.example.json`'s
  existing safe-placeholder convention
- [ ] T003 [P] Add `scripts/backup_prod/config.json` to `.gitignore`

**Checkpoint**: Directory exists, no runnable code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared helpers every user story's scripts import/source — config loading and
filename-date parsing, since both are used identically by the Windows-side and Mac-side scripts
(research.md R5's "two independent, identically-defined purge passes").

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004a [P] Write tests for config loading in `scripts/backup_prod/tests/test_config.py`:
  real subprocess call to a small `load_config.sh` sourced-function helper against a real scratch
  `config.json` fixture — test all required keys present/missing (missing key → non-zero exit +
  clear stderr message, per CONSTITUTION §XVI), test malformed JSON → non-zero exit
- [ ] T004b [P] Implement `scripts/backup_prod/lib/load_config.sh` (a sourceable bash function,
  `jq`-based, matching `env_lock.sh`'s existing sourced-helper pattern) (BLOCKED until T004a
  approved)

- [ ] T005a [P] Write tests for filename-date parsing/retention math in
  `scripts/backup_prod/tests/test_retention_purge.py`: given a set of synthetic
  `denidin-prod-backup-YYYY-MM-DD.tgz` filenames and a fixed "today," assert which are kept vs.
  purged for both the 30-day daily rule and the 36-month monthly rule (REQ-078-05/06); cover
  boundary dates (exactly 30 days old, exactly 36 months old), non-matching filenames (ignored,
  never deleted), and an empty directory
- [ ] T005b [P] Implement `scripts/backup_prod/lib/retention_purge.sh` (a sourceable function,
  `purge_older_than <dir> <days|months>`, used identically by both Windows and Mac sides per
  research.md R5) (BLOCKED until T005a approved)

**Checkpoint**: Config loading + retention math are real, tested, shared building blocks.

---

## Phase 3: User Story 1 — Zero-Downtime Execution (UAT 1, Priority: P1) 🎯 MVP

**Goal**: The core backup archive (SQLite `.backup` snapshots + `tar czf` of `data/`, `config/`,
`logs/prod/`) is produced correctly, atomically, and without ever touching the running containers.

**Independent Test**: Run `run_daily_backup.sh` against a scratch fixture tree (fake `data/`
with real tiny SQLite DBs + ordinary files) and confirm a valid, complete `.tgz` lands in the
target folder, with zero calls to `docker`/`docker compose` made during the run.

### Implementation for User Story 1 (TDD Pattern)

- [ ] T006a [US1] Write tests for hot SQLite backup in
  `scripts/backup_prod/tests/test_sqlite_backup.py`: real `sqlite3` CLI backup of a real scratch
  `.db` (with a concurrent writer thread hammering inserts during the backup, to actually exercise
  the "safe under concurrent writes" claim from research.md R2) — assert the output passes
  `PRAGMA integrity_check` and matches expected row count as of backup start
- [ ] T006b [US1] Implement `scripts/backup_prod/lib/sqlite_backup.sh` (`.backup`-based, per
  research.md R2) (BLOCKED until T006a approved)

- [ ] T007a [US1] Write tests for staging + atomic archive assembly in
  `scripts/backup_prod/tests/test_run_daily_backup.py`: real subprocess run of
  `run_daily_backup.sh` against a scratch fixture tree containing `data/sessions/chat_index.db`,
  `data/reminders/reminders.db`, `data/memory_rolls/roll_markers.db`, `data/memory/chroma.sqlite3`,
  plus ordinary JSON/media files under `data/`/`config/`/`logs/prod/` — assert: (a) a
  `.tgz.partial` is never left behind on success, (b) the final `.tgz` filename matches
  `denidin-prod-backup-YYYY-MM-DD.tgz` for the fixture's frozen "today," (c) un-tarring reproduces
  every source file byte-for-byte except the four `.db` files, which instead pass
  `PRAGMA integrity_check`, (d) a forced mid-run failure (kill the process after staging but
  before the final `mv`) leaves no `.tgz` under the real target filename (no partial-looking
  success), (e) per research.md R6a (speckit.analyze finding F2): a `roll_markers.db` fixture with
  no `committed` row for yesterday still lets the run succeed (exit 0) but logs a WARNING line
  naming the check; a fixture with a committed row logs no such warning
- [ ] T007b [US1] Implement `scripts/backup_prod/run_daily_backup.sh` (stages into a temp dir,
  calls `sqlite_backup.sh` per store, `tar czf`s to `<name>.tgz.partial`, atomic `mv` into place
  only on full success, non-blocking roll-marker pre-flight check per R6a; depends on T004b, T006b)
  (BLOCKED until T007a approved)

- [ ] T008a [US1] Write tests for the zero-downtime guarantee itself in
  `scripts/backup_prod/tests/test_run_daily_backup.py` (same file, additional cases): assert
  `run_daily_backup.sh`'s own source contains no `docker`/`docker compose` invocation anywhere
  (a static grep-based guard, since a real Windows-box container can't be spun up in this repo's
  CI-less test environment) — codifies research.md R6's decision as an enforced regression check,
  not just a claim in prose
- [ ] T008b [US1] N/A — T008a is itself the enforcement (a static assertion against T007b's
  source, no separate implementation) (BLOCKED until T008a approved)

- [ ] T009 [US1] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md` step 1 (register + trigger-once)
  and step 3 (zero-downtime proof) against real dev — not prod — infrastructure first if
  available, then, with fresh separate approval per CLAUDE.md's environment-start rule, against
  real prod; confirm the bot keeps responding throughout with no observable delay (UAT 1)

**Checkpoint**: A correct, atomic, zero-downtime backup archive can be produced on demand.

---

## Phase 4: User Story 2 — Tier 1 (Daily) Storage and Transfer (UAT 2, Priority: P1)

**Goal**: Every daily archive lands in `denidin daily backups/` on the Windows host AND is
reliably pulled to the matching Mac folder, tolerating the Mac being offline at 03:00.

**Independent Test**: Drop synthetic `.tgz` files into a scratch "Windows-side" folder reachable
over a real local SSH loopback (or a real local `ssh localhost`-style fixture, matching
`test_env_scripts.py`'s "real, not mocked, but scratch/throwaway" precedent), run
`pull_backups.sh` against it, and confirm the Mac-side scratch folder ends up with an identical
copy.

### Implementation for User Story 2 (TDD Pattern)

- [ ] T010a [P] [US2] Write tests for the pull logic in
  `scripts/backup_prod/tests/test_pull_backups.py`: real `rsync`/`scp` over `ssh localhost`
  against two real scratch folders (source = fake "Windows daily backups," dest = fake "Mac daily
  backups"); cover zero-new-files (no-op, exit 0), several-new-files-at-once (simulates a Mac that
  was asleep for days), a partially-transferred file from a prior interrupted run (must not be
  treated as complete/skip-worthy), and an unreachable host (non-zero exit, dest folder untouched)
- [ ] T010b [P] [US2] Implement `scripts/backup_prod/pull_backups.sh` (depends on T004b; per
  research.md R4/contracts' `pull_backups.sh` contract) (BLOCKED until T010a approved)

- [ ] T011 [US2] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md` step 2 against the real
  `denidin-winprod` SSH alias and confirm the archive from US1's T009 gate now also exists
  locally on the Mac (UAT 2) — requires the real dev/prod archive from T009 to already exist

**Checkpoint**: Daily archives exist redundantly on both hosts.

---

## Phase 5: User Story 3 — Data Consistency & Restore Integrity (UAT 3, Priority: P1)

**Goal**: Any completed archive can be proven restorable — no SQLite corruption, and
`denidin-app` actually boots against the extracted data.

**Independent Test**: Run `verify_restore.sh` against a known-good archive produced by US1 and
confirm it reports every store as passing `PRAGMA integrity_check` plus a successful throwaway
boot; run it against a deliberately-corrupted archive and confirm it reports the specific failing
store, non-zero exit.

### Implementation for User Story 3 (TDD Pattern)

- [ ] T012a [US3] Write tests for the integrity-check pass in
  `scripts/backup_prod/tests/test_verify_restore.py`: real un-tar of a fixture `.tgz` into a real
  temp dir, real `PRAGMA integrity_check` per `.db` found; cover an all-healthy archive (exit 0,
  every store reported individually) and one with a deliberately truncated/corrupted `.db` inside
  (exit non-zero, names the specific corrupt store — not just "something failed")
- [ ] T012b [US3] Implement the integrity-check portion of
  `scripts/backup_prod/verify_restore.sh` (depends on T004b) (BLOCKED until T012a approved)

- [ ] T013a [US3] Write tests for the throwaway-boot smoke check in
  `scripts/backup_prod/tests/test_verify_restore.py` (same file, additional cases): real
  `docker compose` invocation against an ephemeral compose override pointed at the extracted temp
  dir (real container, real port, but fully isolated — never real prod ports/credentials per
  contracts' `verify_restore.sh` contract), asserting the container reaches a healthy state and is
  torn down afterward regardless of outcome
- [ ] T013b [US3] Implement the boot-smoke-check portion of `verify_restore.sh` (depends on T012b)
  (BLOCKED until T013a approved)

- [ ] T014 [US3] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md` step 4 against a real archive
  pulled in US2's T011 gate; confirm every store passes and `denidin-app` boots against the
  extracted data (UAT 3, SC-002)

**Checkpoint**: Restore integrity is provable on demand, not just assumed.

---

## Phase 6: User Story 4 — Tier 1 Retention Sweep (UAT 4, Priority: P2)

**Goal**: `denidin daily backups/` never grows unbounded — anything older than 30 days is purged
automatically on both hosts.

**Independent Test**: Seed a scratch daily-backups folder with archives dated across a wide
range (today back to 40+ days ago), run the purge, confirm exactly the >30-day-old ones are gone
and the rest untouched.

### Implementation for User Story 4 (TDD Pattern)

- [ ] T015a [US4] Write tests for wiring the Phase 2 retention helper into both entry points in
  `scripts/backup_prod/tests/test_run_daily_backup.py` /
  `scripts/backup_prod/tests/test_pull_backups.py` (additional cases in each): assert
  `run_daily_backup.sh` calls `purge_older_than <daily_dir> 30` after a successful archive, and
  `pull_backups.sh` calls the same after a successful pull — both against real scratch folders
  seeded per T005a's fixtures
- [ ] T015b [US4] Wire `retention_purge.sh`'s `purge_older_than` into both
  `run_daily_backup.sh` (post-archive) and `pull_backups.sh` (post-pull) (depends on T005b, T007b,
  T010b) (BLOCKED until T015a approved)

- [ ] T016 [US4] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` step 5's documented manual
  spot-check (UAT 4) — not exercised live at initial rollout per `quickstart.md`, revisit once the
  feature has been live 30+ days

**Checkpoint**: Tier 1 stays bounded at 30 days on both hosts automatically.

---

## Phase 7: User Story 5 — Tier 2 (Monthly) Promotion and Retention (UAT 5, Priority: P2)

**Goal**: The 1st-of-month archive is additionally promoted into `denidin monthly backups/` on
both hosts, retained 36 months.

**Independent Test**: Run the backup/pull pipeline with a frozen "today" of the 1st of a month and
confirm the archive is copied into both hosts' monthly folder in addition to the daily one; run it
on a non-1st date and confirm no monthly copy is made. Seed a scratch monthly folder with
archives spanning >36 months and confirm only the too-old ones purge.

### Implementation for User Story 5 (TDD Pattern)

- [ ] T017a [US5] Write tests for monthly promotion in
  `scripts/backup_prod/tests/test_run_daily_backup.py` (additional cases): frozen "today" = 1st of
  month → archive also copied (byte-identical) into scratch monthly folder + 36-month purge runs;
  frozen "today" = any other day → monthly folder untouched
- [ ] T017b [US5] Implement monthly promotion + purge in `run_daily_backup.sh` (depends on T005b,
  T007b) (BLOCKED until T017a approved)

- [ ] T018a [US5] Write tests for the Mac-side monthly pull mirroring T010a's daily-pull tests,
  in `scripts/backup_prod/tests/test_pull_backups.py` (additional cases): pulls both daily and
  monthly folders where present, applies 36-month purge locally after pulling
- [ ] T018b [US5] Extend `pull_backups.sh` to also pull/purge the monthly tier (depends on T005b,
  T010b) (BLOCKED until T018a approved)

- [ ] T019 [US5] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` step 5's monthly-tier
  spot-check (UAT 5) — same "not exercised live at initial rollout" note as T016; revisit at the
  next real 1st-of-month run once live

**Checkpoint**: All 5 UATs are independently satisfied.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Register `scripts/backup_prod/register_backup_schedule.sh` (Windows Scheduled Task
  via `schtasks.exe`/WSL2 for prod; Darwin LaunchAgent for local dev-box testing only) — mirrors
  `scripts/health_monitoring/register_prober_schedule.sh`'s `enable|disable|trigger-once`
  interface exactly, per research.md R1 (no automated coverage on the `schtasks.exe` branch, same
  documented gap as its sibling — Darwin branch gets real `launchctl` tests, matching
  `test_env_scripts.py`'s existing precedent)
- [ ] T021 [P] Register the Mac-side pull LaunchAgent (`com.denidin.backuppull.plist` or similar,
  same `launchctl load`/`unload` shape as `scripts/windows_prod/install_persistent_mount.sh`)
- [ ] T022 [P] Add `scripts/backup_prod/README.md` cross-referencing `quickstart.md` and this
  `tasks.md`, for anyone landing in this directory without full spec context
- [ ] T023 Update root `CLAUDE.md` "Repository Layout"/environments sections with a short pointer
  to `scripts/backup_prod/` once merged (per haleluya's docs-update step — deferred to that flow,
  not done mid-implementation)
- [ ] T024 Run full `scripts/backup_prod/tests/` suite once more end-to-end after all phases land,
  confirm no regressions across US1-US5's cumulative test files

---

## Dependencies & Execution Order (TDD-Aware)

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (config loading + retention
  math are shared by every later script).
- **US1 (Phase 3)**: Depends on Foundational. Must land first — every other story's "independent
  test" needs a real archive to operate on.
- **US2 (Phase 4)**: Depends on Foundational + a real archive existing (from US1). Independent of
  US3/US4/US5.
- **US3 (Phase 5)**: Depends on Foundational + a real archive existing (from US1). Independent of
  US2/US4/US5 (does not require the Mac-side pull to have run — can verify a Windows-side archive
  directly).
- **US4 (Phase 6)**: Depends on Foundational + US1's `run_daily_backup.sh` + US2's
  `pull_backups.sh` (wires into both).
- **US5 (Phase 7)**: Depends on Foundational + US1 + US2, same shape as US4; independent of US4
  itself (different retention tier, no shared state).
- **Polish (Phase 8)**: Depends on US1-US5 all landing (scheduling wires up the fully-implemented
  scripts).

### Suggested Order

Setup → Foundational → **US1 (MVP)** → US2 → US3 → US4 → US5 → Polish. US2 and US3 could run in
parallel by different people once US1 lands (both only need a real archive from US1, not from each
other); US4 and US5 similarly parallelize once US1+US2 land.

### Parallel Opportunities

- T002/T003 (Setup) in parallel.
- T004a/T005a (Foundational tests) in parallel; T004b/T005b likewise, after approval.
- T010a+T010b (US2) and T012a/T012b + T013a/T013b (US3) can proceed in parallel once US1's T007b
  lands, by different people.
- T020/T021/T022 (Polish) in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

Setup → Foundational → US1 → **STOP and VALIDATE** (T009's manual gate against real dev
infrastructure first) before touching prod. This alone proves the hardest, highest-risk claim
(REQ-078-02's zero-downtime guarantee) before investing in transfer/retention/restore tooling
around it.

### Incremental Delivery

1. Setup + Foundational → shared helpers ready.
2. US1 → a correct, atomic, zero-downtime archive can be produced on demand (MVP).
3. US2 → redundant Mac copy.
4. US3 → provable restore integrity.
5. US4 + US5 → bounded, tiered retention.
6. Polish → real scheduling wired up, docs updated.

Each step adds value without breaking the previous one; US1 alone is already a meaningful safety
net even before transfer/retention/restore-proof land.
