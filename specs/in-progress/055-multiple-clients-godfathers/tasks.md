# Tasks: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Input**: Design documents from `specs/in-progress/055-multiple-clients-godfathers/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/messaging-gateway.md`, `contracts/invoicing-capability.md`,
`contracts/group-resolution-tenant-scoping.md`, `contracts/tenant-scoped-rbac.md`,
`contracts/tenant-scoped-data-managers.md` (three added at `speckit.analyze` remediation),
`quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III (config-only, Israel local time, feature
branch workflow) and METHODOLOGY.md §VI (TDD, human approval gates, tests IMMUTABLE once
approved).

**Tests**: TDD — every "a" task (tests) requires explicit human approval before its matching
"b" task (implementation) begins. Once approved, a test is immutable without a fresh, explicit
re-approval. Unit tests may mock the Green API/Morning/OpenAI HTTP boundary (constitution §I/V);
integration tests exercise real internal components (`TenantManager`, `UserManager`,
`SessionManager`, etc.) with no `unittest.mock` of internal objects.

**Override (2026-08-17, this feature only)**: `tests/billed/` and `tests/expensive/` are
**not run and not modified at any point during this implementation** — stricter than this
repo's normal "billed tests run freely, no per-run approval" default. This is the enforcement
mechanism behind the parity guarantee (REQ-PARITY-001, `spec.md` Clarifications): every
extended method's `tenant_id` parameter is optional, defaulting to the migrated tenant, so
these untouched, unrun test files keep exercising byte-identical single-tenant behavior by
construction. T029a/b (a new billed test) is deferred under this constraint — see that task's
entry in Phase 7.

**Path Conventions**: Two apps — `apps/denidin-app/src/`, `apps/denidin-app/tests/`,
`apps/morning-mcp-app/src/denidin_mcp_morning/`, `apps/morning-mcp-app/tests/` (per `plan.md`'s
Project Structure).

**Scope note**: This is a large, multi-component feature. `plan.md`'s Summary already flagged
that delivery may be split into sub-phases; the phase structure below is written so each
`Checkpoint` is a real, shippable-behind-a-feature-flag increment — `speckit.implement` may
stop after any checkpoint without leaving the codebase in a broken state.

**Scope decision (2026-08-17)**: no real second-tenant credentials (Green API/WhatsApp number,
Morning account) exist or will be created for this feature — there is no real second paying
client yet. This feature's actual scope is **parity with the existing single-tenant behavior
(migrated as "tenant #1") plus the plumbing/capability to onboard a real second tenant when one
exists** — not live-verified multi-tenant behavior. Every task below still gets built and tested
(via a synthetic second tenant, mocked at the same HTTP boundary this repo's tests already use
for the single tenant today), but tasks requiring a genuinely live second WhatsApp
number/Morning account are explicitly split into a "now" part (automated, synthetic) and a
"deferred" part (blocked, pending a real second client) — see T014a/b, T020a/b, T025a/c,
T026a/b, T030a/b. Deferred parts are not required to consider this feature complete.

## Version Control steps (applied at the end of every phase below)

- **VC0**: Confirm `git branch --show-current` is `feature/055-multiple-clients-godfathers`.
- **VC1**: `git add` only the files touched by that phase (never a broad `git add -A`).
- **VC2**: `git commit` with a conventional-commit message referencing the phase's US#/REQ ids.
- **VC3**: Push — **only when the user explicitly asks to push**.
- **VC4**: (end of feature only) Open PR — own explicit approval required.
- **VC5**: (end of feature only) Merge + deploy — own explicit approval required, never
  inferred from an earlier "yes" to something else.

---

## Phase 1: Setup

- [x] T001 Confirm `git branch --show-current` is `feature/055-multiple-clients-godfathers`
  (already exists).
- [x] T002 **Spike, not a TDD pair**: confirmed 2026-08-17 via direct source inspection of the
  installed `whatsapp_chatbot_python==0.9.9` package (no code executed) — feasible, plain
  `threading.Thread` per tenant, two implementation gotchas found (duplicate log handlers;
  per-instance handler registration). Full finding: `research.md` §7. Hosting-model decision
  (`research.md` §1) does NOT need revisiting.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `Tenant` model and `TenantManager` (loads/joins `tenants.json` +
`config.<env>.json`'s `tenant_credentials`, resolves `tenant_id` lookups) that every other
phase depends on. **No story-specific wiring starts until this phase's tests are approved and
implementation passes** — this is the literal foundation `research.md` §2 calls out as the one
place a shared-process design has to get isolation right.

- [x] T003a [P] Write tests for `Tenant` dataclass in `apps/denidin-app/tests/unit/test_tenant.py`:
  construction from a `tenants.json` entry + matching `tenant_credentials` entry; missing
  optional fields (e.g. no `morning`/invoicing capability) default sanely; `data_root` is
  always derived (`{data_root}/{tenant_id}/`), never settable directly. **16 tests.**
- [x] T003b [P] Implement `Tenant` dataclass in `apps/denidin-app/src/models/tenant.py` — per
  `data-model.md`'s Tenant Identity + Tenant Credentials tables. All 16 tests pass.

- [x] T004a [P] Write tests for `TenantManager.load()` in
  `apps/denidin-app/tests/unit/test_tenant_manager.py`: loads `tenants.json` + the active
  environment's `tenant_credentials`, joins by `tenant_id`; raises a clear config error (not a
  silent skip) on a `tenant_credentials` entry with no matching `tenants.json` identity
  (resolved which direction errors: orphaned *credentials* error; a `tenants.json` identity
  simply not yet credentialed in this environment is valid, phased onboarding); raises on
  duplicate `account_name` or duplicate `mcp_auth_token` within one environment
  (REQ-TENANT-004/005); a tenant missing invoicing-provider credentials loads successfully
  (REQ-CAP-005 — degraded, not an error).
- [x] T004b [P] Implement `TenantManager` in `apps/denidin-app/src/managers/tenant_manager.py`.

- [x] T005a Write tests for `TenantManager.get_tenant(tenant_id)` /
  `TenantManager.all_tenants()` lookup helpers in the same test file: unknown `tenant_id`
  **raises `KeyError`** (decided — no silent wrong-tenant fallback); dict-backed O(1) lookups.
- [x] T005b Implement the lookup helpers. **9 tests total for T004+T005; 25 across Phase 2.**

**Checkpoint**: `TenantManager` fully tested standalone, unused by any behavior yet. Run
`apps/denidin-app/tests/unit/test_tenant.py` `test_tenant_manager.py` — all green before
proceeding.

VC0-VC2 for this phase.

---

## Phase 3: User Story 1 — Tenant infrastructure isolation (Priority: P1) 🎯 MVP

**Goal**: Two tenants can run concurrently with fully isolated Green API/WhatsApp/Morning/
OpenAI/memory/sessions/ledger events — `research.md` §1's shared-multi-tenant-services model.

**Independent Test**: `quickstart.md` "Verifying tenant isolation (SC-002)".

### Messaging (`contracts/messaging-gateway.md`, superseded — see below)

**Corrected 2026-08-17, after direct design discussion with the user**: there is no separate
"gateway" component, and no `tenant_id` tagging/routing layer. `Tenant` (`src/models/tenant.py`)
is itself a complete, self-contained messaging endpoint — `Tenant.start()` builds its own
`Bot`/`AIHandler`/`WhatsAppHandler`/`MediaHandler`/`GroupMembershipResolver` and registers all 9
message-type handlers as **bound methods** on its own bot's router (never a module global,
never a parameter-threaded `tenant_id`) — each handler only ever sees `self`. Outbound routing
is automatically correct by construction: `WhatsAppHandler` replies via `notification.answer()`,
and Green API's `Notification` is intrinsically tied to whichever `Bot` received it.
Crash isolation (REQ-BG-002) comes from one `threading.Thread` per tenant running
`bot.run_forever()`, combined with that method's own built-in retry-on-exception (confirmed at
the T002 spike, `research.md` §7).

- [x] T006a/T007a/T008a [P] [US1] Write tests for `Tenant.start()`/handler registration/
  multi-tenant isolation in `apps/denidin-app/tests/unit/test_tenant_runtime.py` (new file, 19
  tests): all 9 message types registered on the tenant's own bot.router; registered handlers
  are bound methods whose `__self__` is that exact tenant instance; invoking tenant A's handler
  never touches tenant B's `ai_handler`; `bot_factory` is injectable (real Green API bot
  construction always makes a real HTTP call, confirmed during this task — no way around it,
  hence the injection point) so tests never hit the real network; own-WhatsApp-number fetch
  (bugfix-024) fails open per-tenant; read-receipt hook (Feature 045) wired per-tenant.
- [x] T006b/T007b/T008b [P] [US1] Implement `Tenant.start()` + the 9 handler bound methods +
  `_process_conversational_message`/`_process_media_message`/`_resolve_group_user_phone` in
  `apps/denidin-app/src/models/tenant.py` — ported from `denidin.py`'s former module-level free
  functions (`denidin_app.X` → `self.X`, `bot` → `self.bot`; the old `if denidin_app is None`
  guard removed — structurally impossible now, handlers are never registered until `self` is
  fully built). **`denidin.py`'s own module-level `bot`/`denidin_app`/9 free functions are
  intentionally left untouched by this task** — 6 existing integration tests hard-depend on
  that exact module-level shape; switching the real entry point over to construct `Tenant`
  instances is scoped as an explicit follow-up, not bundled into this pass. All 19 new tests
  pass; full unit suite verified green (842 passed, up from 823 — no regressions).

### Tenant-scoped data paths + OpenAI credential — corrected 2026-08-17 (implementation
discovery, `research.md` §8; supersedes the original T009-T012 split below)

`SessionManager`/`MemoryManager`/`LedgerEventManager` are already constructor-scoped (storage
dir, and for `MemoryManager` the OpenAI client, passed once at construction — not per call).
**They need zero internal code changes.** The correct design is one full stack per tenant via a
new `TenantAIHandlerFactory`, per `contracts/tenant-scoped-data-managers.md`. This also
subsumes the original T012 (OpenAI credential) — it falls out of the same factory, not a
separate `AIHandler` change.

- [x] T009a [P] [US1] Write tests for `TenantAIHandlerFactory.build(tenant, base_config)` in
  `apps/denidin-app/tests/unit/test_tenant_ai_handler_factory.py` (new file, 11 tests): given
  two `Tenant` objects, produces two `AIHandler` instances whose `session_manager.storage_dir`,
  `memory_manager.storage_dir`, `ledger_event_manager.storage_dir` all resolve under each
  tenant's own `{data_root}/{tenant_id}/...`, never cross over; each `AIHandler.client`
  (OpenAI) is built from that tenant's own `openai` credential, never shared; RBAC (admin/
  godfather) resolves independently per tenant; environment-wide values (`ai_embedding_model`)
  pass through from `base_config` unchanged. **REQ-PARITY-001 confirmed**: zero changes needed
  to `AIHandler`/`SessionManager`/`MemoryManager`/`LedgerEventManager`/`UserManager`.
- [x] T009b [P] [US1] Implement `TenantAIHandlerFactory` in
  `apps/denidin-app/src/managers/tenant_ai_handler_factory.py` — builds a tenant-scoped
  `AppConfiguration` view via `dataclasses.replace`, then calls the unmodified `AIHandler`
  constructor. Scope note: Phase 3 wires only the first configured godfather (via today's
  existing singular `godfather_phone` field) — full multi-godfather is T015's extension. All
  11 tests pass; full unit suite verified green (823 passed, up from 812 — no regressions).

### Tenant-scoped OpenAI credential

Subsumed into T009 above — no separate task.

### Migration (REQ-MIGRATE-001)

- [x] T013a [US1] Write tests for the migration script in
  `apps/denidin-app/tests/unit/test_migrate_to_tenant.py` (named after the script itself,
  `scripts/migrate_to_tenant.py`, rather than the `test_tenant_migration.py` name originally
  sketched here — kept consistent with this repo's `test_<module_under_test>.py` convention):
  existing `sessions/`, `memory/`, `events/` are copied (never moved/deleted — copy-only) into
  `{data_root}/{tenant_id}/...`; a missing source subdir is skipped without error; the script is
  idempotent (second run reports "already migrated", doesn't duplicate/corrupt/raise); dry-run
  mode reports the plan and touches nothing (no target dir created, source untouched). 8 tests,
  all passing against the T013b implementation below.
- [x] T013b [US1] Implement the migration script,
  `apps/denidin-app/scripts/migrate_to_tenant.py` — location confirmed at `speckit.analyze`
  (finding A1) against this directory's existing precedent, `migrate_stray_ledger_events.py` (a
  comparable one-off data-migration script already there); per REQ-MIGRATE-001. `migrate_tenant_data
  (data_root, tenant_id, dry_run=False) -> List[str]` does a plain `shutil.copytree` per subdir
  (never `shutil.move`/`rmtree` — the flat-layout source is left in place untouched on purpose, so
  a bad run can never lose data and the script is trivially safe to re-run), returning
  human-readable action strings for the CLI to print; idempotency comes from checking whether the
  tenant-scoped destination already exists before copying (skip + "already migrated", rather than
  letting `copytree` raise `FileExistsError` on a second run). `argparse` CLI wrapper takes
  `--data-root`/`--tenant-id`/`--dry-run`, matching `migrate_stray_ledger_events.py`'s existing
  shape. Full unit suite: 850 passed (up from 842), zero regressions.

- [x] T014a [US1] **Now (synthetic second tenant)**: integration test suite proves isolation
  end to end, `apps/denidin-app/tests/integration/test_tenant_isolation.py` (4 tests) — two
  synthetic tenants (fabricated `green_api` values, distinct OpenAI api_key strings, no real
  second Green API/Morning/OpenAI account — see 2026-08-17 scope note in Clarifications),
  dispatched via the real production entry point (`tenant.bot.router.route_event(webhook_dict)`
  — real `Router`/`Observer`/`Handler` dispatch chain, not a direct method call, per
  CONSTITUTION SS V's "real entry point" integration-test rule). Only the two genuine external
  network boundaries are stood in for (Green API's HTTP client via the same real-Router/
  fake-API-client `_FakeBot` pattern `test_tenant_runtime.py` established; OpenAI's
  `client.responses.create`, stubbed per this repo's existing `_mock_response`-shaped fixture
  convention) — SessionManager, UserManager/RBAC, LedgerEventManager, WhatsAppHandler are all
  real, unmodified. Proves: a message to tenant A is answered only via tenant A's own bot and
  never invokes tenant B's OpenAI client; Tier-1 session data lands only under the receiving
  tenant's own `data_root` (the other tenant's dir exists — eagerly created at construction,
  not a signal — but stays empty); two tenants receiving messages independently never cross-
  contaminate; ledger events written via one tenant's `LedgerEventManager` land only under that
  tenant's own `events/` dir. This is the actual acceptance test for SC-002 as scoped by this
  feature. Long-term (ChromaDB) memory disabled per tenant in the test config, so no real
  OpenAI network call of any kind occurs — honors this session's "billed/expensive untouched"
  constraint by construction, not just by omission. Full unit suite still 850 passed (test
  lives under `tests/integration/`, so the unit count is unaffected); integration suite run in
  full for regressions.
- [ ] T014b [US1] 👤 **DEFERRED — MANUAL APPROVAL GATE, blocked pending a real second tenant**:
  `quickstart.md` "Verifying tenant isolation" with two *real*, live WhatsApp numbers. Not
  required to consider US1/this feature complete — exercised whenever a real second client's
  credentials exist.

**Checkpoint**: User Story 1 fully functional and independently testable — this alone is a
viable MVP increment (a single migrated tenant plus room to onboard a second).

VC0-VC2 for this phase.

---

## Phase 4: User Story 2 — Multi-godfather per tenant (Priority: P1)

**Goal**: A tenant can designate more than one godfather-level phone number.

**Independent Test**: `quickstart.md` (extend with a two-godfather scenario per US2's
Acceptance Scenarios in `user-stories.md`).

**Corrected 2026-08-17 (`research.md` §8)**: `UserManager` doesn't need `tenant_id` threaded
through `get_user` — one `UserManager` instance per tenant (via `TenantAIHandlerFactory`,
Phase 3) already scopes RBAC correctly. The one real, additive code change needed is
multi-godfather support (today's `godfather_phone` is genuinely singular), per
`contracts/tenant-scoped-data-managers.md`.

- [x] T015a [US2] Write tests for `UserManager`'s new `godfather_phones: Optional[List[str]]`
  parameter in `apps/denidin-app/tests/unit/test_user_manager.py` (extend existing file): a
  `UserManager` constructed with two `godfather_phones` resolves `Role.GODFATHER` for either
  number; **REQ-PARITY-001** — every pre-existing test in this file, constructing `UserManager`
  with only the existing singular `godfather_phone`, unmodified, still passes unchanged
  (verifies this is additive, not a breaking rename). 11 new tests (`TestUserManagerMultipleGodfathers`
  + a `TestUserManagerPreExistingSingularGodfatherPhoneUnaffected` regression tripwire); all 36
  pre-existing tests in the file confirmed unchanged and passing before T015b (red-phase run).
- [x] T015b [US2] Add `godfather_phones` to `UserManager.__init__` in
  `apps/denidin-app/src/managers/user_manager.py` — checked in addition to (not instead of) the
  existing `godfather_phone` via a second `_godfather_phones_normalized` set, ORed into the same
  role-resolution branch. `TenantAIHandlerFactory` now passes `tenant.godfathers` through
  `AppConfiguration.user_roles["godfather_phones"]` (matching `admin_phones`/`blocked_phones`'s
  existing dict-key convention, rather than a new top-level `AppConfiguration` field), read by
  `AIHandler`'s `UserManager` construction alongside the pre-existing keys; `godfather_phone` is
  also still set to `tenant.godfathers[0]` for backward compat with anything else reading that
  field directly. One pre-existing test (`test_ai_handler_rbac.py`'s
  `test_initializes_user_manager_with_config`) pins the exact `UserManager(...)` call signature
  via `assert_called_once_with` and needed one line added (`godfather_phones=[]`) to keep
  matching post-T015b's additive kwarg — a mechanical widening of the assertion, not a change to
  what the test actually verifies (godfather_phone/admin_phones/blocked_phones wiring). Full
  unit suite: 863 passed (up from 850), zero other regressions.

- [x] T016a [US2] Write tests confirming token-limit/tool attachment (including Morning MCP)
  is identical for both godfathers of one tenant, and that ledger events/invoices either
  godfather creates are visible to the other (shared tenant-level state — both godfathers'
  `AIHandler` requests resolve to the *same* per-tenant `AIHandler` instance/data root, not
  per-godfather siloed) — `apps/denidin-app/tests/integration/test_multi_godfather.py` (new
  file, real internal components per CONSTITUTION §V, real `route_event` dispatch matching
  `test_tenant_isolation.py`'s convention). 5 tests: identical token limit; literally-equal
  assembled tools list (the always-on ledger-event tool, RBAC-independent — real Morning MCP
  attachment isn't exercised here, no live server in this test env); both godfathers' storage_dir
  pointing at the one shared tenant `sessions`/`events` dirs; both godfathers' real webhook turns
  landing on the one stubbed `client.responses.create` (proving no hidden second AIHandler);
  ledger events attributed to either godfather persisted side by side in the one shared
  `events/` dir. All 5 passed on the first run.
- [x] T016b [US2] Wire-through if any gaps found by T016a — **no-op**, confirmed: T016a's 5
  tests all passed immediately against the existing T009/T015 implementation with zero further
  code changes, exactly as the shared-instance design predicted.

- [ ] T017 [US2] 👤 **MANUAL APPROVAL GATE — not blocked, needs no second tenant**: real
  WhatsApp test on the existing (migrated) tenant — two godfather phone numbers on that one
  tenant, both get full godfather behavior. Only a second real *phone number* is needed here,
  not a second tenant's infrastructure, so this gate is fully exercisable now.

**Checkpoint**: User Stories 1 AND 2 both work independently.

VC0-VC2 for this phase.

---

## Phase 5: User Story 3 — Super-admin oversight across all tenants (Priority: P1)

**Goal**: ylevy's phone number resolves as admin in every tenant independently.

**Independent Test**: `quickstart.md` "Verifying super-admin access (SC-004)".

- [ ] T018a [US3] Write tests for cross-tenant admin resolution in
  `apps/denidin-app/tests/integration/test_multi_tenant_admin.py` (new file, real internal
  components): ylevy's number, listed in two different tenants' `admins`, resolves
  `Role.ADMIN` independently in each tenant's own `AIHandler`/`UserManager` instance (via
  `TenantAIHandlerFactory`) — not a special-cased global check; version-query admin capability
  (ungated by RBAC) still resolves per-tenant version info.
- [ ] T018b [US3] Confirm this is the natural behavior of `TenantAIHandlerFactory` (T009b) +
  per-tenant `admins` (likely a no-op — one `UserManager` per tenant already implies
  independence; fix here only if a real gap is found) (BLOCKED until T018a approved).

- [ ] T019a [US3] Write tests for REQ-ROLE-005 (no break-glass): a tenant whose config omits
  ylevy's admin number resolves that number as a normal (non-admin) role for that tenant only —
  no fallback, no cross-tenant leakage of admin status.
- [ ] T019b [US3] Confirm this is the natural behavior of `TenantAIHandlerFactory`'s
  per-tenant construction (no new code expected; if a gap is found, fix here) (BLOCKED until
  T019a approved).

- [ ] T020a [US3] **Now**: on the existing (migrated) tenant, real WhatsApp test — ylevy's
  number resolves admin, "what version are you running?" answers correctly. Cross-tenant
  independence itself (T018a/T019a) is already covered by automated tests with a synthetic
  second tenant.
- [ ] T020b [US3] 👤 **DEFERRED — MANUAL APPROVAL GATE, blocked pending a real second tenant**:
  ylevy's number resolves admin on a second *real*, live tenant too — confirms the config-driven
  independence holds over real infrastructure, not just synthetic test config.

**Checkpoint**: User Stories 1, 2, AND 3 all work independently — the three P1 stories
complete.

VC0-VC2 for this phase.

---

## Phase 6: User Story 4 — Pluggable capability abstraction (Priority: P2)

**Goal**: Messaging/invoicing providers are interfaces with DI-resolved implementations,
selected per tenant; the shared morning-mcp-app server distinguishes tenants by auth token.

**Independent Test**: `quickstart.md` "Verifying capability degraded-start (REQ-CAP-005)" +
`contracts/invoicing-capability.md`'s scenarios.

### Capability interfaces (`apps/denidin-app`)

- [ ] T021a [P] [US4] Write tests for the `messaging_provider`/`invoicing_provider` interfaces
  and DI resolution in `apps/denidin-app/tests/unit/test_capabilities.py` (new file): resolving
  `(tenant_id, "invoicing_provider")` returns the tenant's configured implementation; a tenant
  with no invoicing provider configured resolves to `None`/a documented sentinel, not an
  exception (REQ-CAP-005); resolution is per-call (a registry lookup), not a startup-only
  singleton (`research.md` §5).
- [ ] T021b [P] [US4] Implement `apps/denidin-app/src/capabilities/messaging_provider.py`,
  `invoicing_provider.py` (interfaces) + `impl/green_api_messaging.py`,
  `impl/morning_invoicing.py` (BLOCKED until T021a approved).

- [ ] T022a [US4] Write tests confirming a tenant missing the invoicing provider still starts
  and serves messaging (REQ-CAP-005) — `apps/denidin-app/tests/integration/test_capability_degraded_start.py`
  (new file).
- [ ] T022b [US4] Wire the degraded-start behavior into `AIHandler`'s tool-attachment logic
  (BLOCKED until T022a approved).

### Shared MCP server multi-tenancy (`apps/morning-mcp-app`)

- [ ] T023a [P] [US4] Write tests for per-tenant bearer tokens in
  `apps/morning-mcp-app/tests/unit/test_bearer_middleware.py` (extend/create): each tenant's
  token resolves to that tenant's `tenant_id`; an unrecognized token is rejected exactly as an
  invalid shared secret is today; two tenants configured with the same token is a config-load
  error, not silently merged access (contract requirement).
- [ ] T023b [P] [US4] Extend `BearerTokenMiddleware` to a per-tenant token map in
  `apps/morning-mcp-app/src/denidin_mcp_morning/server.py` (BLOCKED until T023a approved).

- [ ] T024a [US4] Write tests for tenant-attributed audit logging in
  `apps/morning-mcp-app/tests/unit/test_audit.py` (extend existing file): every audit line
  (mutation and refusal alike) records the resolved `tenant_id`.
- [ ] T024b [US4] Extend `apps/morning-mcp-app/src/denidin_mcp_morning/audit.py` (BLOCKED
  until T024a approved).

- [ ] T025a [US4] **Downgraded 2026-08-17 (no second real Morning account available yet)**:
  write tests confirming tool handlers use the resolved tenant's credentials for the underlying
  API call, not a shared/global credential — `apps/morning-mcp-app/tests/integration/
  test_multi_tenant_morning.py` (new file). Uses the *existing* real Morning sandbox account,
  referenced by two distinct synthetic `tenant_id`s in test config — proves the per-tenant
  credential-threading plumbing against a real API call, but does **not** prove true
  cross-account isolation (both synthetic tenants hit the same real backend account). That
  stronger guarantee is deferred to T025c below. Still real-sandbox, no mocking, per
  CONSTITUTION §V.
- [ ] T025b [US4] Wire tenant-resolved credentials into `server.py`'s
  `_call_with_error_boundary` (BLOCKED until T025a approved).
- [ ] T025c 👤 **DEFERRED, blocked pending a real second Morning sandbox/account**: re-run
  T025a's scenario with two genuinely distinct Morning accounts, confirming real cross-account
  isolation (not just credential-threading correctness). Logged as an explicit, known coverage
  gap until then — not silently assumed covered by T025a.

- [ ] T026a [US4] **Now**: `quickstart.md` capability degraded-start scenario — needs only the
  existing (migrated) tenant, temporarily configured with no invoicing provider. 👤 Manual
  approval gate. **Added at `speckit.analyze` remediation, finding G2**: reviewer also
  explicitly confirms REQ-CAP-003/SC-005 — walk through what adding a hypothetical second
  invoicing-provider implementation (e.g. "ypay") would require, and confirm it's registration +
  a tenant config reference only, with zero `AIHandler`/`denidin.py` dispatch-code changes. Not
  an automated test (there's no second real implementation to test against yet) — a documented
  design-review confirmation at this gate, recorded in the approval note.
- [ ] T026b 👤 **DEFERRED — MANUAL APPROVAL GATE, blocked pending a real second tenant**: a
  real two-tenant Morning MCP call confirming correct credential/audit attribution across two
  genuinely distinct live tenants.

**Checkpoint**: All P1 stories plus capability abstraction work independently.

VC0-VC2 for this phase.

---

## Phase 7: User Story 5 — Per-tenant constitution supplement (Priority: P2)

**Goal**: Common constitution becomes a template (bot name substitution); tenant supplement
(a linked `.md` file) concatenates after it.

**Independent Test**: `quickstart.md` (extend) + SC-006.

- [ ] T027a [P] [US5] Write tests for constitution template rendering in
  `apps/denidin-app/tests/unit/test_constitution_loader.py` (extend/create): `{bot_name}`
  placeholder substituted correctly per tenant; two calls for the *same* tenant produce
  byte-identical rendered common section (SC-006); two *different* tenants' rendered common
  sections differ only in `bot_name` (and any other template values), never in supplement
  content leaking across.
- [ ] T027b [P] [US5] Implement template rendering (likely in the existing constitution-loading
  helper referenced by `AIHandler`, `apps/denidin-app/src/handlers/ai_handler.py` or a small
  new `constitution_loader.py`) (BLOCKED until T027a approved).

- [ ] T028a [US5] Write tests for supplement file loading + concatenation:
  `constitution_supplement_file` (relative path from `tenants.json`) is read and appended after
  the rendered common section; an empty/missing-but-declared-empty file produces no error and
  no stray blank section (REQ-CONST-003).
- [ ] T028b [US5] Implement supplement loading (BLOCKED until T028a approved).

- [ ] T029a/T029b 👤 **DEFERRED 2026-08-17 — not written or run as part of this
  implementation** (user directive: no `billed`/`expensive` tests run or changed during this
  work, overriding this tier's normal no-approval-needed default). Would have been: a
  regression test for Feature 039's group `@Name` self-recognition with a non-"DeniDin"
  `bot_name`, confirming the mechanism isn't hardcoded to the literal string "DeniDin" anywhere
  in the no-reply pipeline. **Known, explicitly-flagged gap** until this is written/run on
  explicit future request — a static grep for the literal string `"DeniDin"` across
  `apps/denidin-app/src/`/`prompts/` (a free, non-billed check) is a reasonable interim
  substitute worth doing during T027-T028's implementation, even though it can't fully replace
  a real model-behavior test.

- [ ] T030a [US5] **Now**: T027a-T029a (unit + `billed`) already confirm rendering/self-
  recognition correctness for a distinct `bot_name` without needing a second live tenant. On
  the existing (migrated) tenant, real WhatsApp confirms its own persona/rules render correctly
  post-refactor (parity check, not a new-behavior check).
- [ ] T030b 👤 **DEFERRED — MANUAL APPROVAL GATE, blocked pending a real second tenant**: two
  *real* tenants with distinct `bot_name`/supplement, confirmed via live conversation that each
  responds as its own persona with its own rules, over real infrastructure.

**Checkpoint**: All 5 user stories independently functional.

VC0-VC2 for this phase.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Requirements that span multiple stories rather than belonging to one.

- [ ] T031a [P] Write tests for tenant-attributed log lines (REQ-LOG-001) in
  `apps/denidin-app/tests/unit/test_logging_utils.py` and the equivalent in
  `apps/morning-mcp-app/tests/unit/`: every tenant-scoped log line includes a `tenant=<bot_name>`
  key=value token (format decided 2026-08-17, for grep/logfmt-style parsing — not bracket
  notation), appended to the existing `[v<version>]` prefix, e.g.
  `[v1.4.2] tenant=Jabaloola ...`. Single combined log file per environment, unchanged from
  today (`logs/dev/denidin.log`) — no per-tenant log file/directory split (rejected: matches
  the "don't multiply infrastructure per tenant" principle already applied elsewhere; a
  combined stream stays useful for debugging cross-tenant timing, and `grep 'tenant=Jabaloola'`
  gives the per-tenant view on demand).
- [ ] T031b [P] Implement in both apps' logging setup (BLOCKED until T031a approved).

- [ ] T032a [P] Write tests for unified `SessionCleanupThread`/startup cleanup (REQ-BG-001) in
  `apps/denidin-app/tests/unit/test_cleanup_service.py` (extend existing file): a single sweep
  iterates every tenant's data root in turn; one tenant's cleanup error doesn't abort the sweep
  for other tenants.
- [ ] T032b [P] Extend `apps/denidin-app/src/services/cleanup_service.py` (BLOCKED until T032a
  approved).

- [x] T033a/b/c/d **No longer needed — resolved by construction, 2026-08-17
  (`research.md` §8, supersedes `speckit.analyze` finding G1)**: `GroupMembershipResolver` is
  constructor-scoped, exactly like `SessionManager`/`MemoryManager`. `TenantAIHandlerFactory`
  (T009b) already builds one resolver instance per tenant, with that tenant's own
  `groups_client` — no shared cache exists to collide, no runtime client lookup needed.
  `GroupMembershipResolver` itself is not modified. Confirm with a single regression test in
  `test_multi_godfather.py`/`test_multi_tenant_admin.py`-style integration coverage (Phase 4/5)
  rather than a dedicated test file — no new task number needed.

- [ ] T034 **Audit task, not a TDD pair**: review every other module-level/in-memory cache or
  shared mutable state in `apps/denidin-app/src/` for the same cross-tenant leak risk flagged
  in `plan.md`'s Constitution Check (§XVII). Produce a short written finding (list of
  caches found, which needed re-keying, which didn't and why) — fix any found in a follow-up
  commit within this same phase, not deferred silently.

- [ ] T035 Run `quickstart.md` end to end against the migrated real tenant + a synthetic second
  tenant (per the 2026-08-17 scope note) as the final sanity check — this is "feature complete"
  under this feature's scope (parity + onboarding capability). The fully-live, two-real-tenant
  version of `quickstart.md` remains open, tracked via the T014b/T020b/T025c/T026b/T030b
  deferred gates above, exercised whenever a real second client exists — not a blocker to
  calling this feature done.

**Checkpoint**: Feature complete per `spec.md`'s Requirements/Success Criteria, under this
feature's scope (see Clarifications, 2026-08-17).

VC0-VC2 for this phase.

---

## Dependencies & Execution Order (TDD-Aware)

- **Setup (Phase 1)**: No dependencies. T002's spike finding gates Phase 3 (messaging gateway
  design assumption).
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS every user story — `TenantManager` is a
  hard dependency of Phases 3-8.
- **User Stories (Phase 3-7)**: All depend on Phase 2. Recommended order matches priority
  (P1 stories 3→4→5, then P2 stories 6→7) since US1 is the real MVP and US2/US3 build directly
  on US1's tenant-scoped `UserManager` work — but US4/US5 (P2) are independent of each other and
  could be parallelized by separate implementers once Phase 3 lands.
- **Polish (Phase 8)**: Depends on all five user stories (T031/T032's logging/cleanup work
  depends on US1's `TenantAIHandlerFactory`/tenant registry existing).

### Parallel Opportunities

- Phase 2: T003/T004/T005 are sequential within Foundational (model → manager → lookups) but
  all "a" test tasks across different phases with `[P]` can be drafted in parallel by different
  implementers once their dependencies land.
- Phase 3: T006-T008 (messaging gateway) and T009 (`TenantAIHandlerFactory`) can be developed
  in parallel by different implementers — the factory doesn't depend on the gateway existing.
- Phase 6: T021 (capability interfaces) and T023 (bearer middleware) are `[P]` — different apps
  entirely.
- Phase 8: T031/T032 are `[P]` — independent concerns (logging vs. cleanup).

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational — `TenantManager`).
2. Complete Phase 3 (US1 — tenant isolation, including migration of the existing deployment
   into "tenant #1").
3. **STOP and VALIDATE**: `quickstart.md`'s isolation scenario with a second real tenant.
4. This alone is a deployable increment behind a feature flag — a second tenant can go live on
   isolated infrastructure even before multi-godfather/super-admin/capability-abstraction/
   per-tenant-constitution land.

### Incremental Delivery

Phase 2 → Phase 3 (MVP) → Phase 4 → Phase 5 (all three P1 stories) → Phase 6 → Phase 7 (P2
stories) → Phase 8 (polish). Each phase's Checkpoint is independently demoable.
