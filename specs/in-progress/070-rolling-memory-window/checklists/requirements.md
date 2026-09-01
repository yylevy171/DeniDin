# Specification Quality Checklist: Rolling 14-Day Short-Term Memory Window

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-01 · **Restructured**: 2026-09-02 (legacy defects folded into US1-US3 per
user direction — no separate Bug-Driven Development track)
**Feature**: [spec.md](../spec.md) · [user-stories.md](../user-stories.md)

## Content Quality

- [x] No implementation details that pre-empt `plan.md` — scheduling tech (`APScheduler`), the
      time helper (`time_utils`), and the storage substrates (existing session JSON + ChromaDB)
      are named because they are *existing* project infrastructure this feature must reuse
      (Technology Choices section, per METHODOLOGY §IX), not new design decisions. Genuinely open
      design points (roll-marker storage, token backstop value, canonical-store shape, flag name,
      `top_k_results`) are explicitly deferred.
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
      - **REQ-MEM-046** — roll-marker storage mechanism (markers file under `data/` vs metadata
        flag on the daily-summary record vs small index).
      - **REQ-MEM-047** — token-backstop value `N`, and whether daily-summary `recall()` needs a
        larger `top_k_results` than the current 5 for multi-week questions.
      - **REQ-MEM-024 / REQ-MEM-024b** — the token-backstop value `N` (cross-referenced with
        REQ-MEM-047; candidate is the godfather `max_tokens_by_role` 100000 or lower).
      These are the intended inputs to `/speckit.clarify`; they are scoped and enumerated, not
      vague. All three are design-parameter choices; none block understanding the feature.
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
- [x] Scope is clearly bounded — "Out of Scope" lists the 27-duplicate-record purge, recall-
      scoring/embedding changes, ledger changes, timestamp migration, cold storage, any
      deploy/flag-enable, and standalone bugfix-035/044 regression suites.
- [x] Dependencies and assumptions identified — the completed raw-data-preservation audit
      (2026-09-01), the two-prod-chats / 2026-08-05 go-live facts, the two unverified third-party
      facts (`gpt-5.6-luna` limits, prompt-cache behavior) that block design lock-in per
      CONSTITUTION, and the note that the legacy bugfix specs get a status pointer at haleluya
      time rather than a Bug-Driven Development track.

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
- [x] Feature-flagged, default off, byte-for-byte identical when off (REQ-MEM-005, REQ-MEM-060,
      SC-011).
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
      separate from feature-build approval and from any deploy.
- [x] `specs/` placement: spec lives under `specs/in-progress/070-rolling-memory-window/` while
      being worked (per CLAUDE.md); branch is `feature/070-rolling-memory-window`.

## Notes

- The 3 remaining [NEEDS CLARIFICATION] markers are deliberate and at the METHODOLOGY cap. They
  are all design-parameter choices for `/speckit.clarify` → `/speckit.plan`, not comprehension
  gaps. Recommended next step: **`/speckit.clarify`** to close REQ-MEM-046 / REQ-MEM-047 /
  REQ-MEM-024, then `/speckit.plan`.
- `plan.md` must additionally settle: the canonical-current-message-store shape (one long-lived
  session per chat located by `whatsapp_chat`, vs per-chat message storage — REQ-MEM-014);
  whether any in-memory chat→store index survives and therefore whether the `remove_from_index`
  guard (REQ-MEM-016) applies; the archive-retention policy value (REQ-MEM-034); the
  integration-vs-`billed` coverage split for the flag-gated new model (REQ-MEM-062); and the
  boot ordering of `run_startup_cleanup` / catch-up sweep / message handling.
- Not yet validated by a second reviewer / `/speckit.analyze` cross-artifact pass (no `plan.md`
  or `tasks.md` yet).
