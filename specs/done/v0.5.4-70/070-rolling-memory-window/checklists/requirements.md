# Specification Quality Checklist: Rolling 14-Day Short-Term Memory Window

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-01 · **Restructured**: 2026-09-02 (legacy defects folded into US1-US3 per
user direction — no separate Bug-Driven Development track) · **Clarified**: 2026-09-02
(`/speckit.clarify` Session — all 5 open questions closed; ready for `/speckit.plan`)
**Feature**: [spec.md](../spec.md) · [user-stories.md](../user-stories.md)

## Content Quality

- [x] No implementation details that pre-empt `plan.md` — scheduling tech (`APScheduler`), the
      time helper (`time_utils`), and the storage substrates (existing session JSON + ChromaDB +
      a small SQLite roll-marker DB, same pattern as Feature 054's `reminders.db`) are named
      because they are *existing* project infrastructure this feature must reuse (Technology
      Choices section, per METHODOLOGY §IX), not new design decisions. Genuinely open design
      points (exact roll-marker path/schema and race handling, backstop trim mechanism, whether
      the in-memory `chat_to_session` cache survives, `top_k_results` for multi-week recall) were
      explicitly deferred to `plan.md` — **all now settled**, see the Notes section.
- [x] Focused on user value: "the bot stops forgetting a conversation that paused for a day";
      "raw data is never lost"; "restart doesn't wipe context".
- [x] Written so a non-technical stakeholder can follow the user stories and success criteria.
- [x] All mandatory sections completed (User Scenarios & Testing, Edge Cases, Requirements, Key
      Entities, Success Criteria, plus Terminology Glossary and Technology Choices per METHODOLOGY
      §VIII/IX).
- [x] Separate `user-stories.md` exists with Given-When-Then for every story and explicit
      routing/flow + integration-test requirements (spec approval gate satisfied).

## Requirement Completeness

- [x] **All [NEEDS CLARIFICATION] markers resolved** by `/speckit.clarify` Session 2026-09-02:
      - **REQ-MEM-046** — roll markers = a small **SQLite DB under `data/`**, `UNIQUE(chat, date)`,
        empty days included (Feature 054 `reminders.db` pattern). Exact path/schema/race handling
        deferred to `plan.md`.
      - **REQ-MEM-024b / REQ-MEM-024** — token-backstop value `N` = the acting role's existing
        `max_tokens_by_role` limit; no dedicated config key. Group turns use the role
        `GroupMembershipResolver` resolves.
      - **REQ-MEM-047** — `N` settled (above). Daily-summary `recall()` `top_k` **settled by
        `plan.md` 2026-09-02**: new key `memory.longterm.daily_summary_top_k` (default 10) on the
        single per-turn conversational recall call; global `top_k_results` (5) untouched
        (`contracts/ai-handler-recall.md`).
- [x] Requirements are testable and unambiguous (each REQ-MEM-* maps to at least one Given-When-
      Then scenario and at least one Success Criterion).
- [x] Success criteria are measurable (counts, percentages, p95 latency, token headroom).
- [x] Success criteria are technology-agnostic (phrased as observable outcomes, not code).
- [x] All acceptance scenarios are defined in `user-stories.md`, including a final cross-story
      acceptance pass covering every user story (billed AC-1/2/3/5 + SC-007, plus non-billed AC-6 for US5) per the "TDD" redefinition (METHODOLOGY §VI).
- [x] Edge cases identified: DST on roll night, boundary-timestamp attribution, pre-2026-08-10
      `+00:00` timestamps, clock skew, late-night message at the cutoff, empty chats, first-ever
      collection, >14-day outage, scheduler/script race, new-model code deployed before the
      backfill was run against that env, backstop smaller than a day, poison session mid-roll.
- [x] Scope is clearly bounded — "Out of Scope" lists the 27-duplicate-record purge, recall-
      scoring/embedding changes, ledger changes, timestamp migration, cold storage, deploying the
      new model to any env, running the one-time backfill against prod, and standalone
      bugfix-035/044 regression suites.
- [x] Dependencies and assumptions identified — the completed raw-data-preservation audit
      (2026-09-01), the two-prod-chats / 2026-08-05 go-live facts, the two unverified third-party
      facts (`gpt-5.6-luna` limits, prompt-cache behavior) that block design lock-in per
      CONSTITUTION, the backfill-before-deploy rollout ordering (clarified 2026-09-02), and the
      note that the legacy bugfix specs get a status pointer at haleluya time rather than a
      Bug-Driven Development track.

## Feature Readiness

- [x] Every functional requirement has acceptance criteria (REQ-MEM-* ↔ US scenario ↔ SC-*).
- [x] User scenarios cover the primary flows: the new model (14-day window, restart continuity,
      tolerant load — US1; nightly roll — US2; archive-only safety + token backstop — US3) and
      the one-time operational tasks (migration — US4; log-retention audit — US5).
- [x] Legacy defects each have a disposition (structurally eliminated vs fixed inline) and a
      named proving scenario — spec.md §"Legacy Defects and How the New Model Addresses Them"
      table (bugfix-035 H1 → US2 AC-1; H2 → US1 sc.6 + AC-5; H3 → US3 sc.5; bugfix-044 → US1
      sc.5 + AC-2).
- [x] Feature maps to measurable outcomes in Success Criteria (SC-001..SC-011).
- [x] Implementation detail is confined to the Technology Choices section and framed as
      "reuse existing infra", not new invention.

## Constitution / Methodology cross-checks

- [x] No environment variables anywhere — all tunables are config keys under the `memory` block
      (REQ-MEM-061).
- [x] Israel local time only — window and day-bucketing both via `time_utils` (REQ-MEM-003,
      REQ-MEM-031).
- [x] No feature flag (clarified 2026-09-02, deliberate override of the CONSTITUTION
      "feature-flag new behavior" default per explicit user direction) — clean cutover; the
      retired paths (24h idle expiry, the hourly expire→transfer→`transferred_to_longterm`
      cycle, `_prune_until_under_limit`) are **removed**, not left dormant, and no test asserts
      the old session-expiry behavior (REQ-MEM-005, REQ-MEM-060, REQ-MEM-062, SC-011).
- [x] ZERO MOCKING of internal components — every integration-test requirement names real
      `SessionManager` / `MemoryManager` / `AIHandler` with only the OpenAI / Green API network
      boundary mocked, never in `tests/integration/`.
- [x] NO UNVERIFIED THIRD-PARTY ASSUMPTIONS — model context/pricing and prompt-cache behavior are
      called out as must-verify-against-a-real-call before design lock (REQ-MEM-037, Technology
      Choices, Assumptions).
- [x] **No Bug-Driven Development gate** — per explicit user direction (2026-09-01), the legacy
      defects are addressed within the new-model stories, not as standalone root-cause-approval
      tracks. The bugfix specs get a status note pointing at Feature 070 at haleluya time
      (Assumptions; spec.md §"Legacy Defects").
- [x] Ledger untouched — REQ-MEM-043 explicitly forbids a `CURRENT_SCHEMA_VERSION` change.
- [x] The one-time prod migration is gated as its own explicit-approval action (REQ-MEM-048),
      separate from feature-build approval and from any deploy, and (clarified 2026-09-02) runs
      standalone against the target env *before* the new-model code is deployed there.
- [x] `specs/` placement: spec lives under `specs/done/v0.5.4-70/070-rolling-memory-window/` while
      being worked (per CLAUDE.md); branch is `feature/070-rolling-memory-window`.

## Notes

- `/speckit.clarify` Session 2026-09-02 closed all 5 open questions (roll-marker storage = SQLite
  under `data/`; token backstop `N` = `max_tokens_by_role`; canonical store = one long-lived
  `Session` per chat; no feature flag / tests cover new behavior only; catch-up bounded by
  running the backfill before deploying the new-model code).
- `/speckit.plan` completed 2026-09-02 → `plan.md`, `research.md`, `data-model.md`, `contracts/`
  (9 files), `quickstart.md`. A `/speckit.analyze` partial pass (spec ↔ plan ↔ design) ran the
  same day: 0 CRITICAL, all findings folded back into the artifacts. **Recommended next step:
  `/speckit.tasks`**, then re-run `/speckit.analyze` for the full task-coverage pass.
- ~~`plan.md` must still settle:~~ **All settled by `/speckit.plan` 2026-09-02** (`plan.md`,
  `research.md` D1–D13, `contracts/`):
  - SQLite roll-marker path/schema/race handling → `{data_root}/memory_rolls/roll_markers.db`,
    `PRIMARY KEY(chat, date)`, **claim-first two-phase** `claimed`→`committed` with
    `sqlite3.IntegrityError` as the claim-loss signal, stale-claim re-take after
    `memory.roll.stale_claim_minutes` (research D6/D7, `contracts/roll-marker-store.md`).
  - Backstop trim mechanism → **read-only per-turn context cut** (drop oldest) **+ nightly
    physical archive move** at the largest role N (100000); never `unlink` (research D10,
    `contracts/session-manager-window.md`).
  - In-memory `chat_to_session` cache → **kept as a non-authoritative read-through cache** over
    the new `chat_index.db`; `remove_from_index` + the whole 4-step cleanup are **deleted**, so
    the REQ-MEM-016 guard is moot (research D2/D3).
  - Archive-retention policy → **retain forever by design**; `memory.archive_retention_days`
    default `0` = never prune; no pruner built (research D4).
  - `top_k` for multi-week recall → new `memory.longterm.daily_summary_top_k` (default 10) on the
    single per-turn conversational recall call; global `top_k_results` (5) untouched (research D5,
    `contracts/ai-handler-recall.md`).
  - Boot ordering → `initialize_app` loses `run_startup_cleanup` / `SessionCleanupThread` /
    `recover_orphaned_sessions`; `__main__` runs reminder + accounting sweeps, then the **NEW**
    daily-roll catch-up sweep (bounded by `catchup_lookback_days`), then the daily-roll scheduler,
    then `message_source.start()` (research D1/D9).
  - "Bounded retry budget" (REQ-MEM-025/027) → the catch-up lookback window is the bound; no
    per-item retry counter (`contracts/daily-summary-roll-service.md` §"Retry semantics").
- `/speckit.analyze` **partial pass done 2026-09-02** (spec ↔ plan ↔ design scope — no `tasks.md`
  yet): 0 CRITICAL, all findings resolved into the artifacts. A full task-coverage / ordering pass
  is still pending and runs after `/speckit.tasks`.
