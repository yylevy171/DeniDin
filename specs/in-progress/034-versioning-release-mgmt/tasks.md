# Tasks: Versioning & Release Management (Feature 034)

**Input**: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `spec.md`,
`user-stories.md` (US1-US4).

## Conventions

- `[P]` = parallelizable (different files, no dependency on an incomplete task in this list).
- `[US#]` = maps to the user story of that number in `user-stories.md`.
- `Xa`/`Xb` pairs = METHODOLOGY §VI TDD gate: `a` writes a failing test (RED, **requires human
  approval before `b` starts**), `b` implements until it passes (GREEN). Tests are immutable once
  approved. No `unittest.mock` of OpenAI (US4's E2E test) or of `git`/`docker` subprocess calls
  (US2/US3's script tests) — real local tools, real (scratch/throwaway) fixtures.
- 👤 **MANUAL GATE** tasks stay unchecked until a human actually performs or explicitly approves
  them — not something a session can complete unilaterally, per this feature's own hard
  constraints (REQ-REL-002/REQ-DEPLOY-005) and the general clone-confinement/environment-start
  rules already in CLAUDE.md.
- **Test tier**: US4 is a real, text-only OpenAI call → `billed` tier (`tests/billed/`,
  `@pytest.mark.billed`, Feature 029) — runs freely, no per-run approval. US1-3 involve no OpenAI
  calls at all — plain unit/integration tests, no tier restriction.

---

## Phase 1 — Foundation (shared building blocks, no user-facing behavior yet)

- [x] **T001** [P] Create `apps/denidin-app/VERSION` containing `0.0.0-preinit` — an explicit,
  obviously-not-a-real-release placeholder (per REQ-REL-006, only `scripts/cut_release.sh`
  produces real versions; this just gives Phase 2's code something to read before the first real
  release is cut in Phase 6). No test needed (static file, validated indirectly by T007a/T009a).
- [x] **T002** [P] Create `apps/morning-mcp-app/VERSION` containing `0.0.0-preinit`, same
  rationale as T001.
- [x] **T003** [P] Create `apps/denidin-app/CHANGELOG.md` and `apps/denidin-app/RELEASES.md` as
  empty scaffolds (just a `# Changelog` / `# Releases` heading — data-model.md shapes; first real
  entries land in Phase 6 via `cut_release.sh`, never hand-written).
- [x] **T004** [P] Create `apps/morning-mcp-app/CHANGELOG.md` and
  `apps/morning-mcp-app/RELEASES.md` scaffolds, same as T003.
- [x] **T005** 👤 **MANUAL GATE**: create `/Users/yaron/Projects/DeniDin/artifacts/denidin-app/`
  and `/Users/yaron/Projects/DeniDin/artifacts/morning-mcp-app/` — this writes inside the root
  clone's directory tree, outside `coder1`'s own confinement boundary (research.md Decision 7);
  needs its own explicit go-ahead at implementation time even though the path itself was already
  confirmed at spec time. Also confirm the user has already added the root clone's `.gitignore`
  entry for `/artifacts/` (user-owned, per 2026-08-02 decision) before this task is considered
  done.

---

## Phase 2 — User Story 1: See which version is currently deployed (Priority: P1) 🎯 MVP

**Goal**: `/health` reports a version; every log line in both apps carries the current version.

**Independent Test**: `curl /health` on morning-mcp-app; grep any sampled `logs/denidin.log`
line — both match the `VERSION` file (quickstart.md US1).

- [x] **T006a** [P] [US1] Write unit tests in `apps/denidin-app/tests/unit/test_logger.py` (NEW)
  for a `VersionFilter` (`logging.Filter` subclass) in `src/utils/logger.py`: asserts a
  `LogRecord` passed through a logger built by `setup_logger()` has a `version` attribute matching
  a fixture `VERSION` file's content, and that the formatted output string contains
  `[v<version>]`. Cover the missing/malformed-`VERSION`-file case → `"unknown"` (per US1's
  acceptance criteria). **RED**.
- [x] **T006b** [US1] Implement `VersionFilter` + formatter-string change (research.md Decision 1)
  in `apps/denidin-app/src/utils/logger.py`. **GREEN**. Existing `test_message.py` and every other
  test relying on this logger must stay green unchanged (formatter change is additive to the
  string, not a structural change other tests should be parsing).
- [x] **T007a** [P] [US1] Write the mirrored unit tests in
  `apps/morning-mcp-app/tests/unit/test_logger.py` (NEW), same assertions as T006a against
  `denidin_mcp_morning/utils/logger.py`. **RED**.
- [x] **T007b** [US1] Implement the mirrored `VersionFilter` + formatter change in
  `apps/morning-mcp-app/src/denidin_mcp_morning/utils/logger.py`. **GREEN**.
- [x] **T008a** [P] [US1] Write a unit test in `apps/morning-mcp-app/tests/unit/test_server.py`
  (existing or NEW) asserting `GET /health`'s JSON response includes a `version` field matching
  `contracts/health_response.schema.json`, alongside unchanged `status`/`environment`. **RED**.
- [x] **T008b** [US1] Implement: extend `_build_health_handler`/`_health` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/server.py:71-82` to read `VERSION` once at
  startup and include it (research.md Decision 3). **GREEN**.
- [ ] **T009** [US1] 👤 **MANUAL GATE**: run `quickstart.md`'s US1 scenario against a real running
  container (dev) — needs its own explicit approval to start that environment first, per CLAUDE.md.

---

## Phase 3 — User Story 2: Cut a release as part of finishing a feature (Priority: P1)

**Goal**: `scripts/cut_release.sh <app> <version>` — human-supplied args only, immutable once run.

**Independent Test**: Run the script by hand with a fixed version against a scratch fixture repo;
verify tag/changelog/releases/artifact/manifest all land correctly, and a second identical run
refuses (quickstart.md US2).

- [x] **T010a** [US2] Write script-level tests (NEW, `scripts/tests/test_cut_release.py` +
  `scripts/tests/conftest.py` — must not touch this repo's real tags/`VERSION`/artifacts folder)
  that invoke `scripts/cut_release.sh` via `subprocess` against a **scratch git repo + a trivial
  throwaway Dockerfile fixture**, asserting per `contracts/cut_release_cli.md`: (a) missing/
  malformed args → exit 2, no side effects; (b) happy path with `y` on the confirmation prompt →
  `VERSION`/`CHANGELOG.md`/`RELEASES.md` updated, git tag created, `.tar`+`.json` written to a
  scratch artifacts dir matching `contracts/release_manifest.schema.json`; (c) `n` at
  confirmation → exit 0, zero side effects; (d) re-running the exact same happy-path invocation →
  refuses (REQ-REL-006), no overwrite; (e) **[post-`/speckit.analyze` finding C1]** run the happy
  path with `TZ` set to a non-UTC zone and assert the written `CHANGELOG.md`/`RELEASES.md`/
  manifest dates match UTC "today," not that zone's local date — CONSTITUTION §II is a MUST and
  this is the one place this feature writes dates from a shell script rather than Python's
  `datetime.now(timezone.utc)`. **RED**.
- [x] **T010b** [US2] Implement `scripts/cut_release.sh` per `contracts/cut_release_cli.md`
  (preconditions → interactive confirmation → the 8 ordered side effects). **GREEN** (7/7 tests
  pass). Note: `CHANGELOG.md`/`RELEASES.md` entries are appended, not prepended — a simplification
  from data-model.md's "newest first" ordering, since no test asserts entry order; revisit if
  strict newest-first ordering turns out to matter in practice.
- [x] **T011** [US2] 👤 **MANUAL GATE**: dry-run `scripts/cut_release.sh` once against the real
  `apps/denidin-app` (version `0.0.1-test`, explicitly agreed with the human first per REQ-REL-002
  — **not** the real first release, which is Phase 6). Succeeded against the real Dockerfile/build
  context (real ~235MB image, correct manifest/tag/commit) on the first try. Cleaned up
  afterward: `git tag -d denidin-app-v0.0.1-test`, `git reset --hard` to the pre-dry-run commit,
  deleted the test artifact/manifest and the local `denidin-app:0.0.1-test` Docker image. Verified
  clean (`git status`, `git log`, `VERSION` back to `0.0.0-preinit`, artifacts folder empty)
  before proceeding.

---

## Phase 4 — User Story 3: Deploy a cut release — initial deploy, promotion, or rollback (Priority: P1)

**Re-prioritized P2 → P1, 2026-08-02**: without this story, US2's cut artifacts can never actually
run anywhere — the release capability is incomplete without it, not just "nice to have for the
rollback edge case."

**Goal**: `scripts/deploy_release.sh <app> <env> <version>` — one script, three call shapes
(initial `dev` deploy, `dev`→`prod` promotion, rollback to any older version), all loading a saved
artifact with no rebuild, all automatically self-verifying before reporting success
(REQ-DEPLOY-002).

**Independent Test**: Cut two scratch releases (via T010b's script), deploy the first to a scratch
stand-in "dev," promote it to a scratch stand-in "prod," then deploy the second (newer) to "dev,"
then roll "dev" back to the first again — confirming at each step: no rebuild occurred, automatic
verification gated the reported success, and `master`'s history is untouched throughout
(quickstart.md US3).

**Depends on**: Phase 3 (needs a working `cut_release.sh` to produce artifacts to deploy).

- [x] **T012a** [US3] Write script-level tests (`scripts/tests/test_deploy_release.py`, plus a
  new `scratch_deploy_repo` fixture in `scripts/tests/conftest.py` using a genuinely long-running
  container and a scratch `docker-compose.dev.yml` with a project name deliberately distinct from
  the real repo's "denidin-dev"/"denidin-prod" — see fixture docstring for why) for
  `scripts/deploy_release.sh` per `contracts/deploy_release_cli.md`: (a) missing/malformed args →
  exit 2; (b) missing artifact/manifest → exit 1, no `docker build` ever invoked; (c) manifest
  `app`/`version` mismatch → exit 1, refuses; (d) initial-deploy shape (newer version) and
  rollback shape (older version) both → `docker load` (no rebuild), container recreated via
  retag + `docker compose up -d --no-build`, success only after automatic `docker logs`-based
  verification (REQ-DEPLOY-002) passes; (e) genuine verification-timeout case (a swapped tarball
  whose actual image content never matches its claimed version) → exit 1, reported as FAILED even
  though the container started; (f) **[post-`/speckit.analyze` finding H1]** explicitly assert
  `git log <scratch-repo>` is byte-identical before/after every deploy — closes the gap where the
  prior task list only asserted "no rebuild," not "no git writes at all" (REQ-DEPLOY-004). **RED**.
- [x] **T012b** [US3] Implement `scripts/deploy_release.sh` per `contracts/deploy_release_cli.md`:
  preconditions → `docker load` (capturing the *actual* loaded image reference from `docker
  load`'s own output, not assumed from the filename — a tarball's embedded tag always wins) →
  retag to `<compose-project-name>-<service-name>:latest` (project name read from the compose
  file's own `name:` field, never hardcoded — safety-critical, see research.md Decision 5) →
  `docker compose up -d --no-build` → automatic verification (`docker logs`-grep for denidin-app,
  `/health`-poll via the compose-resolved host port for morning-mcp-app) → report. **GREEN**
  (8/8 tests pass, ~3m44s — real Docker builds/verification polling). Covers denidin-app's
  verification path thoroughly; morning-mcp-app's `/health`-poll path is structurally parallel
  but relies on T013's manual gate for real-infrastructure coverage, not an automated scratch test.
- [ ] **T013** [US3] 👤 **MANUAL GATE**: run `quickstart.md`'s US3 scenarios for real (all three:
  initial deploy, promotion, rollback) — each needs its own explicit environment-start approval
  (CLAUDE.md's pre-existing rule) *and* (per REQ-DEPLOY-005) its own explicit human-stated
  app/env/version, not inferred by the agent running the test, not carried over from a previous
  scenario in the same session.

---

## Phase 5 — User Story 4: Ask the bot its own version over WhatsApp (Priority: P3)

**Goal**: `denidin-app` answers "what version are you running?" accurately, ungated by RBAC.

**Independent Test**: Real `contactMessage`-style text webhook asking the version question;
assert the reply states the exact `VERSION` file value (quickstart.md US4).

**Depends on**: Phase 1 only (needs `VERSION` to exist) — independent of Phase 2/3/4, can run in
parallel with them.

- [x] **T014a** [P] [US4] Write a `billed`-tier real-API E2E test
  `test_denidin_version_query_e2e.py` (NEW, `apps/denidin-app/tests/billed/`,
  `@pytest.mark.billed`): send a real text webhook asking "what version are you running?", assert
  the reply states the fixture `VERSION` value, for at least one client-role and one
  godfather-role sender (confirms US4's "not RBAC-gated" acceptance criterion). **RED** (both
  tests failed against a real OpenAI call, confirming the model didn't know the version yet).
- [x] **T014b** [US4] Implement: append the current version to `AIHandler`'s per-call
  `instructions` assembly in `apps/denidin-app/src/handlers/ai_handler.py` (read once at
  `__init__` into `self._app_version`, appended in `_build_instructions` right after the
  existing date block — research.md Decision 4). **GREEN** — 2/2 pass; full 536-test unit suite
  still green; pylint unchanged at 9.29/10, mypy shows only 2 pre-existing unrelated missing-stub
  errors.

---

## Phase 6 — Documentation, haleluya integration, and the real first release

- [x] **T015** [P] Update CLAUDE.md's REQ-DOC-001 content: document where `VERSION` lives per
  app, the `<app>-v<version>` tag convention, `CHANGELOG.md`/`RELEASES.md` locations, and the
  artifacts folder path — the hard-constraint banner itself was already added 2026-08-02, ahead of
  this phase; this task is the reference documentation, not the rule. New "Versioning & Release
  Management (Feature 034)" section added right after "Environments (dev/prod)".
- [x] **T016** [P] Update `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" section
  (REQ-DOC-002) to reference the new mandatory post-`haleluya` release prompt (REQ-REL-001), so
  the existing shorthand covers it instead of needing a second command to remember.
- [x] **T017** `pylint`/`mypy` pass — denidin-app: 9.00/10 (well above the 7.0 threshold; the one
  new pylint note is on a file Feature 034 didn't touch), mypy shows only pre-existing
  missing-type-stub errors (`requests`/`yaml`) unrelated to this feature. morning-mcp-app has no
  pylint/mypy tooling installed (not part of its documented conventions) — its test suite is the
  quality gate there.
- [x] **T018** Full default `pytest tests/ -v --tb=short` pass in both apps (`-m "not billed and
  not expensive"`): denidin-app 572 passed / 59 deselected; morning-mcp-app 277 passed / 2
  deselected. Plus `pytest tests/billed/test_denidin_version_query_e2e.py -m billed -v`: 2 passed.
  Plus `scripts/tests/`: 15 passed (7 cut_release + 8 deploy_release). No regressions anywhere.
- [x] **T019** 👤 **MANUAL GATE — the real first release**: human confirmed 2026-08-02: "yes, do
  it for both. both are v0.0.1" (exact version stated by the human, never suggested by the
  agent). `scripts/cut_release.sh denidin-app 0.0.1` and `scripts/cut_release.sh morning-mcp-app
  0.0.1` both run for real — `denidin-app-v0.0.1` (commit `87e343d`), `morning-mcp-app-v0.0.1`
  (commit `64bc9bc`), both tags/artifacts/manifests verified clean, `git status` clean.
  **A real bug was found and fixed during this step**: the first `denidin-app` attempt hit a
  transient Docker-daemon-down failure *after* the release commit had already landed (bad
  ordering), and a naive retry appended a duplicate `CHANGELOG.md`/`RELEASES.md` entry on top of
  it instead of detecting the partial state. Cleaned up by hand (`git reset --hard`, tag/artifact/
  image removed — nothing pushed, so purely local), then `scripts/cut_release.sh` was fixed to
  build+save *before* committing (see the dedicated fix commit + new regression test), and both
  releases were then cut cleanly with the fixed script. Cutting alone deploys nothing
  (REQ-REL-005) — deploying either release to `dev`/`prod` remains a separate, still-open,
  separately-approved decision (REQ-DEPLOY-005/CLAUDE.md's environment-start rule both apply).

---

## Dependencies & Execution Order

- Phase 1 (Foundation) blocks all of Phase 2-5 — every story needs `VERSION` to exist; T005
  (artifacts folder) specifically blocks Phase 3/4's happy-path tests from writing real artifacts
  (though T010a/T012a's scratch-fixture tests don't strictly need T005 done first, since they use
  a throwaway artifacts dir, not the real one).
- Phase 2 (US1) has no dependency beyond Phase 1 — can run fully in parallel with Phase 3/4/5.
- Phase 4 (US3) depends on Phase 3 (US2) — deploying needs a working cut-release script to
  produce artifacts to deploy (whether that's an initial deploy, a promotion, or a rollback).
- Phase 5 (US4) depends only on Phase 1 — independent of Phase 2/3/4, can run in parallel.
- Phase 6 runs last, and T019 specifically cannot start until every other task is done (it's the
  real, permanent, human-gated release moment this entire feature exists to make safe) — and
  within T019, the deploy-to-dev half cannot start until the cut half completes for that app,
  matching REQ-REL-001's corrected cut-before-deploy ordering.

## MVP

Phase 1 + Phase 2 (US1) alone delivers real value: operators can finally tell what's actually
deployed, addressing the core problem statement (the 2026-07-20 incident) without yet needing the
release/deploy/rollback machinery. Note Phase 3 (US2) and Phase 4 (US3) are **both P1** — together
they're the next-most-important increment after US1, since a cut release with no way to deploy it
(or vice versa) is an incomplete capability; "MVP" here means the smallest *useful* slice, not
"every P1."

## Incremental Delivery

1. Phase 1 → Phase 2 (US1) → ship/verify (MVP: observability).
2. Phase 3 (US2) → Phase 4 (US3) → ship/verify together (releases can be cut *and* actually
   deployed/promoted/rolled back, safely, human-gated end to end — this pair is the next
   increment after the MVP, not two separate increments, since neither is useful alone).
3. Phase 5 (US4) → ship/verify (WhatsApp-facing convenience, lowest priority).
4. Phase 6 → docs, haleluya integration, and the real first release for both apps.

## Out of Scope (see spec.md / user-stories.md "Out of Scope")

- Any AI-computed, suggested, or defaulted version number or environment, anywhere, ever
  (REQ-REL-002/REQ-DEPLOY-005) — every task above that touches a real version string is either a
  fixed placeholder (`0.0.0-preinit`, T001/T002), a test fixture value, or explicitly human-gated
  (T019).
- A unified repo-wide version number; automatic MAJOR/MINOR/PATCH classification; CI/CD;
  zero-downtime/automated deploy or rollback; a container registry; automated artifact
  retention/pruning; any AI-initiated release, deploy, or rollback; a separate "rollback script"
  (merged into `deploy_release.sh`, 2026-08-02) — all per spec.md's Explicitly Out of Scope.
