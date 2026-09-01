# Specification Quality Checklist: Rolling 14-Day Short-Term Memory Window

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-01
**Feature**: [spec.md](../spec.md) · [user-stories.md](../user-stories.md)

## Content Quality

- [x] No implementation details that pre-empt `plan.md` — scheduling tech (`APScheduler`), the
      time helper (`time_utils`), and the storage substrates (existing session JSON + ChromaDB)
      are named because they are *existing* project infrastructure this feature must reuse
      (Technology Choices section, per METHODOLOGY §IX), not new design decisions. Genuinely open
      design points (roll-marker storage, token backstop value, flag name) are explicitly deferred.
- [x] Focused on user value: "the bot stops forgetting a conversation that paused for a day";
      "raw data is never lost"; "restart doesn't wipe context".
- [x] Written so a non-technical stakeholder can follow the user stories and success criteria.
- [x] All mandatory sections completed (User Scenarios & Testing, Edge Cases, Requirements, Key
      Entities, Success Criteria, plus Terminology Glossary and Technology Choices per METHODOLOGY
      §VIII/IX).
- [x] Separate `user-stories.md` exists with Given-When-Then for every story and explicit
      routing/flow + integration-test requirements (spec approval gate satisfied).

## Requirement Completeness

- [~] **3 [NEEDS CLARIFICATION] markers remain** (at the METHODOLOGY limit, not over):
      - REQ-MEM-053 — roll-marker storage mechanism (markers file vs record flag vs index).
      - REQ-MEM-054 — behavior when a (chat, date) needs rolling but raw messages aren't in hot
        storage (may be moot if `expired/` retention is "keep forever").
      - REQ-MEM-062 — the token-backstop value `N`.
      These are the intended inputs to `/speckit.clarify`; they are scoped and enumerated, not
      vague. All three are design-parameter choices, none block understanding the feature.
- [x] Requirements are testable and unambiguous (each REQ-MEM-* maps to at least one Given-When-
      Then scenario and at least one Success Criterion).
- [x] Success criteria are measurable (counts, percentages, p95 latency, token headroom).
- [x] Success criteria are technology-agnostic (phrased as observable outcomes, not code).
- [x] All acceptance scenarios are defined in `user-stories.md`, including a final cross-story
      `billed` acceptance pass (AC-1..AC-5) per the "TDD" redefinition (METHODOLOGY §VI).
- [x] Edge cases identified: DST on roll night, boundary-timestamp attribution, pre-2026-08-10
      `+00:00` timestamps, clock skew, late-night message at the cutoff, empty chats, first-ever
      collection, >14-day outage, scheduler/script race, flag flipped off with summaries present,
      backstop smaller than a day, poison session mid-roll.
- [x] Scope is clearly bounded — "Out of Scope" lists the duplicate-record purge, recall-scoring
      changes, ledger changes, timestamp migration, cold storage, and any deploy/flag-enable.
- [x] Dependencies and assumptions identified — Bug-Driven Development gate for US1-US3, the
      completed raw-data-preservation audit, the two-prod-chats/go-live facts, and the two
      unverified third-party facts (`gpt-5.6-luna` limits, prompt-cache behavior) that block
      design lock-in per CONSTITUTION.

## Feature Readiness

- [x] Every functional requirement has acceptance criteria (REQ-MEM-* ↔ US scenario ↔ SC-*).
- [x] User scenarios cover the primary flows: prerequisite fixes (transfer completes, tolerant
      load, restart continuity), the new model (14-day window, nightly roll), the safety property
      (archive-only), and the one-time operational tasks (migration, log-retention audit).
- [x] Feature maps to measurable outcomes in Success Criteria (SC-001..SC-011).
- [x] Implementation detail is confined to the Technology Choices section and framed as
      "reuse existing infra", not new invention.

## Constitution / Methodology cross-checks

- [x] No environment variables anywhere — all tunables are config keys (REQ-MEM-091).
- [x] Israel local time only — window and day-bucketing both via `time_utils` (REQ-MEM-032).
- [x] Feature-flagged, default off, byte-for-byte identical when off (REQ-MEM-034, REQ-MEM-090,
      SC-011).
- [x] ZERO MOCKING of internal components — every integration-test requirement names real
      `SessionManager`/`MemoryManager`/`AIHandler` with only the OpenAI/Green API network
      boundary mocked, never in `tests/integration/`.
- [x] NO UNVERIFIED THIRD-PARTY ASSUMPTIONS — model context/pricing and prompt-cache behavior are
      called out as must-verify-against-a-real-call before design lock (REQ-MEM-064, Assumptions).
- [x] Bug-Driven Development preserved — US1-US3 reference the existing bugfix specs and state
      that this spec does not bypass their root-cause approval gate.
- [x] Ledger untouched — REQ-MEM-052 explicitly forbids a `CURRENT_SCHEMA_VERSION` change.
- [x] The one-time prod migration is gated as its own explicit-approval action (REQ-MEM-075),
      separate from feature-build approval and from any deploy.
- [x] `specs/` placement: spec lives under `specs/in-progress/070-rolling-memory-window/` while
      being worked (per CLAUDE.md); branch is `feature/070-rolling-memory-window`.

## Notes

- The 3 remaining [NEEDS CLARIFICATION] markers are deliberate and at the METHODOLOGY cap. They
  are all design-parameter choices for `/speckit.clarify` → `/speckit.plan`, not comprehension
  gaps. Recommended next step: **`/speckit.clarify`** to close REQ-MEM-053 / REQ-MEM-054 /
  REQ-MEM-062, then `/speckit.plan`.
- Prerequisite bug fixes (US1-US3) still require their own Bug-Driven Development root-cause
  approval from the user before test-gap analysis begins — the user's "agree and approve, lets do
  it" authorized drafting this spec and the overall direction, not the per-bug root-cause sign-off
  that METHODOLOGY §VII requires.
- Not yet validated by a second reviewer / `/speckit.analyze` cross-artifact pass (no `plan.md` or
  `tasks.md` yet).
