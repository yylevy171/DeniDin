# Handoff: Feature 055 (Multi-Tenancy) — 2026-08-17

**Read this first if you're picking up this session fresh.** Everything below reflects the
actual state as of this write — check git log/status yourself too, don't just trust this file
if time has passed.

## Where things stand right now

- **Branch**: `feature/055-multiple-clients-godfathers` (already checked out).
- **5 local commits NOT YET PUSHED** (push only when the user explicitly asks — standing rule,
  see "Rules to not forget" below). Local HEAD: `477c102`. Remote HEAD: `10f9f6c`. Run
  `git log origin/feature/055-multiple-clients-godfathers..HEAD --oneline` to see them.
- **1 uncommitted file**: `apps/denidin-app/tests/unit/test_migrate_to_tenant.py` — T013a's
  tests are written (11 tests) but **T013b (the actual `scripts/migrate_to_tenant.py`
  implementation) has not been started**. This is the literal next thing to do.
- All prior work is committed and, per this feature's own test suite runs, green: 842/842 unit
  tests pass, 29/29 integration tests pass, zero regressions.

## Read these, in order, before doing anything

1. `specs/in-progress/055-multiple-clients-godfathers/spec.md` — the full spec, Clarifications
   log tells the whole decision history (multiple sessions' worth, dated).
2. `specs/in-progress/055-multiple-clients-godfathers/research.md` — **§7 and §8 are the most
   important sections**: §7 is the T002 concurrency spike (passed), §8 is the big mid-implementation
   architecture correction (see below) that superseded most of the original plan.
3. `specs/in-progress/055-multiple-clients-godfathers/tasks.md` — the task list, kept up to
   date with `[x]`/`[ ]` as work completes. **This is the actual source of truth for "what's
   done"** — read it, don't just trust this handoff's summary below.
4. `specs/in-progress/055-multiple-clients-godfathers/contracts/` — three of five contract
   files are marked **SUPERSEDED** in place (not deleted — kept for historical record):
   `tenant-scoped-rbac.md`, `group-resolution-tenant-scoping.md`,
   `messaging-gateway.md`. Only `tenant-scoped-data-managers.md` and
   `invoicing-capability.md` reflect the current design. Don't implement anything from a
   superseded contract without checking `tenant-scoped-data-managers.md` first.

## The one architectural fact that matters most

**A `Tenant` (`apps/denidin-app/src/models/tenant.py`) is a fully self-contained messaging
endpoint, not a config object routed through by a shared gateway.** This was NOT the original
plan — it was discovered by actually reading the code mid-implementation (`research.md` §8) and
then refined further through direct discussion with the user (the "App = DeniDin, Tenant =
Tenant" naming conversation).

Concretely:
- `Tenant.start(base_config, bot_factory=...)` builds its own `Bot`, `AIHandler`,
  `WhatsAppHandler`, `MediaHandler`, `GroupMembershipResolver` — all via
  `TenantAIHandlerFactory` (`src/managers/tenant_ai_handler_factory.py`) — and registers all 9
  message-type handlers as **bound methods** on its own bot's router.
- `SessionManager`, `MemoryManager`, `LedgerEventManager`, `GroupMembershipResolver`,
  `AIHandler` needed **zero internal code changes** — they were already constructor-scoped in
  this codebase. `UserManager` needs one small additive change (multi-godfather support,
  T015 — not done yet).
- There is **no separate "messaging gateway" or dispatch/routing component**. Outbound routing
  is automatically correct by construction (`WhatsAppHandler` replies via
  `notification.answer()`, which is intrinsically tied to whichever `Bot` received it).
- `denidin.py`'s own module-level `bot`/`denidin_app`/9 free functions are **intentionally
  untouched** — 6 existing integration tests hard-depend on that exact shape. Wiring the real
  entry point over to construct `Tenant` instances (via a new `DeniDin` App class holding
  `List[Tenant]`) is an **explicit, not-yet-started follow-up**, scoped separately on purpose.

If you're tempted to "clean up" `denidin.py`'s module-level bot/handlers to match the new
`Tenant` — don't, without re-reading the "Rules to not forget" section below first and
confirming with the user. This was a deliberate scope boundary, not an oversight.

## What's actually implemented (all committed, all tested)

| Phase | Status | Files |
|---|---|---|
| **1. Setup** | ✅ done | T001 (branch confirm), T002 (spike — see `research.md` §7) |
| **2. Foundational** | ✅ done | `src/models/tenant.py` (Tenant dataclass — identity/credentials part), `src/managers/tenant_manager.py` (loads/joins `tenants.json` + `config.<env>.json`'s `tenant_credentials`) |
| **3. US1 (tenant isolation)** | ✅ done | T009 (`TenantAIHandlerFactory`), T006-T008 (Tenant runtime), T013a/b (`scripts/migrate_to_tenant.py` + 8 tests), T014a (`tests/integration/test_tenant_isolation.py`, 4 tests — real `route_event` dispatch through two synthetic tenants, proves SC-002). T014b remains deferred (blocked pending a real second tenant, not required for completeness). |
| **4. US2 (multi-godfather)** | 🟡 mostly done | T015a/b (`UserManager.godfather_phones`, additive), T016a/b (`tests/integration/test_multi_godfather.py`, 5 tests — T016b was a no-op, confirmed). **T017 remains: a 👤 manual-approval-gate real-WhatsApp test — needs only a second real phone number on the existing tenant, not a second tenant's infrastructure, so it's exercisable now but requires the user.** |
| **5. US3 (super-admin)** | 🟡 mostly done | T018a/b, T019a/b (`tests/integration/test_multi_tenant_admin.py`, 6 tests — both b-halves confirmed no-ops). **T020a remains: a real WhatsApp test on the existing tenant — requires starting a live environment, which needs fresh per-action human approval every time (CLAUDE.md), not attempted here. T020b is the usual deferred-pending-a-real-second-tenant gate.** |
| **6. US4 (capability abstraction)** | 🟡 mostly done | T021a/b (`src/capabilities/` - `MessagingProvider`/`InvoicingProvider` interfaces + `CapabilityRegistry`, wired into `Tenant.start()`/`TenantAIHandlerFactory`), T022a/b (degraded-start - found and closed a REAL pre-existing cross-tenant token-leak gap, not just a missing test), T023a/b + T024a/b (`apps/morning-mcp-app`: per-tenant `BearerTokenMiddleware` + `utils/tenant_context.py` ContextVar, empirically verified through the real FastMCP/Starlette/uvicorn stack before committing to the design; tenant-attributed audit logging), T025a/b (per-tenant `MorningClient` resolution in `create_server`, real-sandbox test **written but not executed** - blocked by a pre-existing `config.test.json` schema gap in this clone, unrelated to this feature, confirmed via the same gap blocking the pre-existing `test_mcp_server_e2e.py`). **T025c/T026a/T026b remain: all manual/deferred gates, none attempted.** |
| **7. US5 (per-tenant constitution)** | 🟡 mostly done | T027a/b (`{bot_name}` template rendering, `test_constitution_loader.py`, 13 tests), T028a/b (supplement concatenation, same file, 6 tests), T029a's static-grep interim substitute (found and fixed a REAL gap: `_normalize_self_mentions` was hardcoded to `"@DeniDin"` regardless of tenant - now `bot_name`-aware, 5 new tests in `test_ai_handler_self_mention_normalization.py`). `config/runtime_constitution.md` itself now fully templated (all 6 literal "DeniDin" occurrences → `{bot_name}`). **T029a/b's own real `billed` model-behavior test stays deferred** (frozen this session, per the user's explicit directive) - the static-grep fix only proves code-level plumbing, not re-verified live model behavior. **T030a remains: a real WhatsApp parity check on the existing tenant** - same live-environment-start gate as T017/T020a, not attempted. T030b is the usual deferred-pending-a-real-second-tenant gate. |
| **8. Polish** | 🟡 mostly done | T031a/b (tenant-attributed `tenant=<bot_name>` log tags, `threading.local()`-based, bound once per tenant's own dispatch thread — `test_logger.py`, 7 tests), T032a/b (`MultiTenantSessionCleanupThread`/`run_startup_cleanup_for_tenants`, one unified sweep with per-tenant exception isolation — `test_background_cleanup.py`, 5 tests), T033 (already resolved by construction, pre-055), T034 (cache audit — clean bill of health, written finding at `T034-cache-audit-findings.md`, no fix needed). **T035 remains: `quickstart.md`'s live-tenant half needs a live environment start (same gate as T017/T020a/T030a) — not attempted; its synthetic-second-tenant half is, in substance, already exercised throughout this session's test suite.** |

Test files that exist (denidin-app): `test_tenant.py`, `test_tenant_manager.py`,
`test_tenant_ai_handler_factory.py`, `test_tenant_runtime.py`, `test_migrate_to_tenant.py`,
`test_capabilities.py`, plus integration: `test_tenant_isolation.py`, `test_multi_godfather.py`,
`test_multi_tenant_admin.py`, `test_capability_degraded_start.py`.
Test files that exist (morning-mcp-app, new/extended this phase): `test_auth_middleware.py`
(extended), `test_config.py` (extended), `test_audit.py` (new), `test_multi_tenant_morning.py`
(new, integration - see the config.test.json caveat above before assuming it passes).

**Known environmental blocker for a fresh session to fix or hand to the user**: this clone's
`apps/morning-mcp-app/config/config.test.json` (gitignored, real credentials) is missing the
`auth_url` field Feature 053 made required - blocks EVERY real-sandbox integration test in that
app (all of `tests/integration/`, not just the new T025a test), confirmed pre-existing (not
caused by this feature) by running the untouched `test_mcp_server_e2e.py` and seeing the exact
same `ConfigError`. Do not edit this file without the user's involvement (CLAUDE.md: config is
code, not silently patched mid-run) - surface it and ask for the missing value, likely from
`creds/` or wherever this app's real sandbox credentials are kept.

## Immediate next step

**All 8 phases are now done except manual/deferred/live-infrastructure gates and one execution
caveat.** This is, in substance, the end of the automatable work for this feature under its
current scope. denidin-app: unit suite 906 passed, integration suite 50 passed. morning-mcp-app:
unit suite 308 passed (4 pre-existing, unrelated failures caused by the config.test.json gap -
do not "fix" these either without the user). Zero regressions introduced by this feature
throughout, on either app, at every single phase checkpoint.

**Open manual-approval-gate items, all needing the user, none attempted in this session:**
T017 (Phase 4), T020a (Phase 5), T025c/T026a/T026b (Phase 6), T030a/T030b (Phase 7), T035 (Phase
8) - see each phase's row above for specifics. Every one of these requires either a live
environment start (needs fresh per-action approval, CLAUDE.md) or a real second tenant/second
Morning account that doesn't exist yet. Do not attempt to simulate or skip any of them — leave
them `[ ]` and move on. T029a/b (Phase 7's own `billed` test) is a DIFFERENT kind of gap - not a
manual/live gate, but explicitly frozen per this session's own "billed/expensive stay untouched"
constraint; don't write/run it without the user first lifting that freeze.

**Next up, if the user wants further work on this feature:**
1. Get the user to fix (or explicitly hand you) `apps/morning-mcp-app/config/config.test.json`'s
   missing `auth_url` field, then actually RUN `tests/integration/test_multi_tenant_morning.py`
   (T025a) - it's written and should pass, but was never executed in this session.
2. Work through the manual-approval-gate list above, one at a time, with the user's explicit
   per-action sign-off each time (per CLAUDE.md - no blanket approval carries across these).
3. Revisit T029a/b (the real `billed` self-recognition test) once the user lifts this session's
   billed/expensive freeze.
4. Otherwise: this feature's code and its own test suite are complete. The next natural step
   is the `/haleluya` finish-feature flow (spec status update, commit, PR, merge) - but per this
   repo's standing rule, only when the user actually says the word, not before.

## Rules to not forget (violating any of these was explicitly corrected by the user this session)

- **`tests/billed/` and `tests/expensive/` are NOT run and NOT modified at any point during
  this implementation** — stricter than this repo's normal "billed tests run freely" default.
  This is a hard, explicit user directive (not just the usual per-run approval rule), the
  enforcement mechanism for parity. See spec.md's **REQ-PARITY-001** and the "Session 2026-08-17
  (implementation-start constraint)" Clarifications entry.
- **Blanket approval already granted for all unit/integration test work** — no need to stop and
  ask before each TDD "a"/"b" pair for those tiers. This does NOT extend to billed/expensive
  (see above), and does NOT extend to starting any dev/prod container or deploying anything —
  those still need fresh, explicit, per-action approval every time, per this repo's standing
  `CLAUDE.md` rules (unrelated to this feature, always in force).
- **Push only when the user explicitly asks.** Commit freely at each phase/task boundary
  (matches the VC0-VC2 convention documented at the top of `tasks.md`), but VC3 (push) is
  gated. Don't batch too much uncommitted work either — commit at natural checkpoints as you go.
- **No real second-tenant credentials exist and none will be created for this feature.** Scope
  is "parity with today's single tenant (migrated) + the plumbing to onboard a real second
  tenant later" — verified via a **synthetic** second tenant in automated tests, not live
  infrastructure. Every task requiring genuinely live two-tenant WhatsApp/Morning verification
  is already split in `tasks.md` into a "now" (automated) part and a "deferred, blocked pending
  a real second client" part (e.g. T014a/b, T020a/b, T025a/c, T026a/b, T030a/b) — the deferred
  halves are NOT required to consider this feature complete.
- **Always use `apps/denidin-app/venv/bin/python3`**, never a bare `python3` — this clone's
  venv is Python 3.9; a bare `python3` on this machine resolves to a system 3.14 install.
  Confirmed the hard way earlier this session.
- **Real `GreenAPIBot`/`DeniDinGreenAPIBot` construction always makes a real HTTP call** — no
  combination of constructor args avoids it. Any test touching bot construction must inject a
  fake via the `bot_factory` parameter (see `test_tenant_runtime.py`'s `_FakeBot`/`_FakeGreenAPI`
  for the established pattern — reuse it, don't reinvent).
- Every commit message in this branch's history is deliberately long/detailed (explains *why*,
  not just *what*, often citing which finding/discussion prompted a change) — match that style,
  don't drop to one-liners.
