# Tasks: Reminders — Functionality and Management

**Input**: Design documents from `specs/in-progress/054-reminders-functionality-mgmt/`
**Prerequisites**: `plan.md` ✅ · `spec.md` ✅ · `research.md` ✅ · `data-model.md` ✅ · `contracts/` ✅

---

**IMPORTANT**: This task list complies with:
- **CONSTITUTION.md** (§I-III): Config-only (no env vars), Israel local time throughout, feature
  branch workflow.
- **METHODOLOGY.md** (§VI): TDD with human approval gates — every "a" (test) task requires human
  approval before its paired "b" (implementation) task; once approved, tests are IMMUTABLE without
  explicit re-approval. No TDD exception was requested or granted for this feature (unlike
  Feature 047) — normal TDD applies throughout.

**Tests**: TDD — all tests written and approved before implementation, per task pair.
**Organization**: Grouped by user story (per `user-stories.md`'s priorities) so each is
independently implementable/testable/deliverable, after a shared Foundational phase.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: can run in parallel (different files, no dependency on each other)
- **[Story]**: which user story this task belongs to
- **[T###a]**: write tests (requires human approval before T###b)
- **[T###b]**: implement (blocked until T###a approved)

---

## Phase 1: Setup

- [ ] T001 Add `icalendar`, `recurring_ical_events`, `apscheduler` to
  `apps/denidin-app/requirements.txt`; reinstall venv, confirm no conflicts with existing
  dependencies.
- [ ] T002 [P] Add `reminders: Dict = field(default_factory=dict)` to `AppConfiguration`
  (`src/models/config.py`), plus a defaults-merge block (`max_active_reminders: 20`) mirroring
  the existing `mcp` section's pattern. No `enable_reminders` feature-flag key — by design (see
  spec.md Clarifications).
- [ ] T003 [P] Add the `reminders` config section to `config/config.example.json`,
  `config.dev.json`, `config.prod.json`, `config.test.json`.

---

## Phase 2: Foundational (blocks all user stories)

**⚠️ CRITICAL**: no user-story work begins until this phase is complete and approved.

- [ ] T004a Write tests for `ReminderManager`'s core storage/construction in
  `tests/unit/test_reminder_manager.py`: SQLite schema creation (`reminders`/
  `reminder_exceptions`/`fired_occurrences` tables), one-time reminder creation, 5-minute rounding
  (including the "rounds into the past" edge case per FR-005), past-date rejection (checked
  *after* rounding), RRULE string construction for every `freq`/end-condition combination
  (daily/weekly/monthly × never/after_n/until_date, plus `month_nth_weekday`), structural
  rejection of a yearly frequency (FR-007), 20-reminder cap enforcement.
- [ ] T004b Implement `ReminderManager.__init__`/`create_reminder`/cap-checking/rounding/RRULE
  construction in `src/managers/reminder_manager.py` (BLOCKED until T004a approved).
- [ ] T005a Write tests for `ReminderManager`'s resolution logic in
  `tests/unit/test_reminder_manager.py`: `icalendar`/`recurring_ical_events` tz-preservation
  (both `+02:00`/`+03:00` DST offsets — closes one of `research.md`'s open sanity-check items),
  narrow-window query efficiency against a `never`-ending RRULE (closes the other), single-
  occurrence exception resolution (a `reminder_exceptions` row correctly overrides the plain rule
  for its date), whole-series edits never touching existing exception rows (the permanence rule),
  `list_active()` filtering out cancelled reminders.
- [ ] T005b Implement `ReminderManager.list_active`/the sweep-facing resolution helper/
  `_reconstruct_calendar` in `src/managers/reminder_manager.py` (BLOCKED until T005a approved,
  depends on T004b).
- [ ] T006a [P] Write tests for `PendingLocalToolApprovalManager` in
  `tests/unit/test_pending_local_tool_approval_manager.py`: get/set/clear/
  attach_sent_message_id, matching `PendingApprovalManager`'s existing test shape.
- [ ] T006b [P] Implement `PendingLocalToolApproval`/`PendingLocalToolApprovalManager` in
  `src/managers/pending_local_tool_approval_manager.py` (BLOCKED until T006a approved) — new
  file, `pending_approval_manager.py` untouched throughout this feature.

**Checkpoint**: storage, recurrence resolution, and the new approval-state manager all work in
isolation. User-story implementation can now begin.

---

## Phase 3: User Story 1 — Create a one-time reminder with guided detail capture and approval (P1) 🎯 MVP

**Goal**: a godfather/admin user can create a one-time reminder end-to-end through conversation,
gated by the existing approval UX.

**Independent Test**: per `user-stories.md` US1.

- [ ] T007a [US1] Write tests for `create_reminder` tool attachment/dispatch in
  `tests/unit/test_ai_handler_reminders.py`: RBAC-gated attachment (GODFATHER/ADMIN only, no
  feature flag involved), `extract_function_call` parsing, a matched call creates a
  `PendingLocalToolApproval` (never dispatches immediately, unlike `capture_ledger_event`).
- [ ] T007b [US1] Implement `CREATE_REMINDER_TOOL` schema + attachment in `_assemble_tools` +
  `PendingLocalToolApproval` creation in `src/handlers/ai_handler.py` (BLOCKED until T007a
  approved, depends on T004b, T006b).
- [ ] T008a [US1] Write tests for approval resolution in `tests/unit/test_ai_handler_reminders.py`:
  `_resolve_pending_local_tool_approval`'s approve path (dispatches to
  `ReminderManager.create_reminder` with already-parsed arguments, no second OpenAI round-trip for
  the action itself, then one follow-up call for the confirmation reply) and decline path (clears
  pending, falls through to fresh-turn processing); the dual-check dispatch order in
  `get_response()`/`resolve_button_tap()` (MCP-pending checked first, then local-tool-pending);
  the manager-level re-check on approve (TOCTOU: cap/past-date re-verified, not just at proposal
  time).
- [ ] T008b [US1] Implement `_resolve_pending_local_tool_approval` +
  `_call_openai_reminder_followup_api` + the dual-check additions to `get_response()`/
  `resolve_button_tap()` in `src/handlers/ai_handler.py` (BLOCKED until T008a approved, depends on
  T005b, T007b).
- [ ] T009a [US1] Write an integration test in
  `tests/integration/test_reminder_conversation_routing.py`: a real `textMessage`-shaped
  notification through `bot.router`, exercising the full create-reminder flow up to a
  `PendingLocalToolApproval` being set — real internal objects throughout, no mocking (CONSTITUTION
  §V).
- [ ] T009b [US1] Any router/handler wiring the integration test surfaces as missing (expected:
  none — `WhatsAppHandler.send_response()`'s `offer_approval_buttons` branch and `denidin.py`'s
  `attach_sent_message_id` wiring are already tool-mechanism-agnostic per `contracts/local-tool-
  approval-gate.md`; this task exists to confirm that, not to add new code) (BLOCKED until T009a
  approved).
- [ ] T010 [US1] 👤 **MANUAL APPROVAL GATE**: write and run
  `tests/billed/test_reminder_lifecycle_billed.py::test_godfather_creates_one_time_reminder_text_approval`
  and `::test_godfather_creates_one_time_reminder_button_approval` (real OpenAI calls, no per-run
  approval needed per CLAUDE.md's `billed` tier rules — the gate here is the human accepting the
  story as done, not the test-run itself).

**Checkpoint**: US1 fully functional and independently testable/demoable (a reminder can be
created and persisted, even though nothing fires yet — that's US2).

---

## Phase 4: User Story 2 — Scheduled delivery via a single shared mechanism (P1)

**Goal**: a due reminder actually fires as a WhatsApp message.

**Independent Test**: per `user-stories.md` US2.

- [ ] T011a [US2] Write tests for the proactive-send helper in
  `tests/unit/test_green_api_bot.py`: success (`response.code == 200`, returns `idMessage`) and
  failure (non-200, returns `None`, logs, never raises) paths, against a stub `bot.api.sending`.
  No lock-related test (none exists, by design — see `contracts/reminder-delivery.md`).
- [ ] T011b [US2] Implement `send_proactive_message(bot, chat_id, message)` in
  `src/utils/green_api_bot.py` (BLOCKED until T011a approved).
- [ ] T012a [US2] Write tests for the sweep worker in
  `tests/unit/test_reminder_delivery_service.py`: due/not-due determination via the
  `icalendar`/`recurring_ical_events` reconstruction (T005b), successful delivery inserts a
  `fired_occurrences` row and calls `session_manager.add_message(...)`, a failed send leaves the
  occurrence undelivered for retry on the next tick, one-time and recurring reminders share the
  identical code path (no special-casing) — all against a stub `bot`/`send_proactive_message`.
- [ ] T012b [US2] Implement `_sweep_due_reminders`/`run_startup_reminder_sweep` in
  `src/services/reminder_delivery_service.py` (BLOCKED until T012a approved, depends on T005b,
  T011b).
- [ ] T013 [US2] Wire the APScheduler `BackgroundScheduler` + `CronTrigger(minute='*/5')` job +
  `run_startup_reminder_sweep()` call + shutdown handling into `denidin.py`'s `initialize_app()`
  and both shutdown paths (SIGINT/SIGTERM handler, `KeyboardInterrupt` block), alongside the
  existing `SessionCleanupThread` wiring (no dedicated test file — covered by T012a's worker tests
  plus the manual gate below).
- [ ] T014 [US2] 👤 **GATE ZERO — blocking, needs its own explicit human approval, human present**:
  a real `bot.api.sending.sendMessage()` call, live, outside any webhook-response context, against
  a real dev number. Capture the raw request/response in `research.md`, replacing its currently-
  open Gate Zero section. **This story is not done until this closes.**
- [ ] T015 [US2] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` scenarios #1 (text approval + real
  delivery), #2 (button approval), #18 (restart survives and catches up).

**Checkpoint**: US1 + US2 together deliver the MVP — create a one-time reminder, it actually
fires.

---

## Phase 5: User Story 3 — Modify an existing reminder, single occurrence or whole series (P2)

**Goal**: find and change an existing reminder conversationally, with correct scope handling.

**Independent Test**: per `user-stories.md` US3.

- [ ] T016a [US3] Write tests for `list_reminders` in `tests/unit/test_ai_handler_reminders.py`:
  RBAC-gated attachment, immediate (non-approval-gated) dispatch, schedule-summary formatting for
  both one-time and recurring reminders.
- [ ] T016b [US3] Implement `LIST_REMINDERS_TOOL` schema + immediate dispatch in
  `src/handlers/ai_handler.py` (BLOCKED until T016a approved, depends on T005b).
- [ ] T017a [US3] Write tests for `ReminderManager`'s modify methods in
  `tests/unit/test_reminder_manager.py`: `modify_single_occurrence` (creates/updates a
  `reminder_exceptions` row, subject to the same past-date rejection as creation, does not touch
  the master `RRULE`), `modify_whole_series` (updates `RRULE`/`message_text`, explicitly does NOT
  touch any existing `reminder_exceptions` row — the single most important assertion in this
  phase, per `quickstart.md` #12), rounding applied to any new time.
- [ ] T017b [US3] Write tests for the `modify_reminder` tool + resolution path in
  `tests/unit/test_ai_handler_reminders.py`: scope disambiguation prompt when ambiguous, dispatch
  to the correct `ReminderManager` method by `scope`.
- [ ] T017c [US3] Implement `ReminderManager.modify_single_occurrence`/`modify_whole_series` +
  `MODIFY_REMINDER_TOOL` schema + its approval-resolution wiring (BLOCKED until T017a and T017b
  approved, depends on T008b, T016b).
- [ ] T018 [US3] 👤 **MANUAL APPROVAL GATE**: billed tests
  `test_modify_one_time_reminder`, `test_modify_single_occurrence_of_recurring_reminder`,
  `test_modify_whole_series_pattern` (must explicitly assert a pre-existing Detached/exception
  occurrence survives the whole-series edit) + `quickstart.md` #9, #11, #12, #15.

**Checkpoint**: US1+US2+US3 — reminders can be created, delivered, and corrected.

---

## Phase 6: User Story 4 — Delete an existing reminder, single occurrence or whole series (P2)

**Goal**: cancel a reminder or one of its occurrences conversationally.

**Independent Test**: per `user-stories.md` US4.

- [ ] T019a [US4] Write tests for `ReminderManager`'s delete methods in
  `tests/unit/test_reminder_manager.py`: `delete_single_occurrence` (marks/creates a `CANCELLED`
  `reminder_exceptions` row, rest of series unaffected), `delete_whole_series` (marks `reminders`
  row cancelled, cancels all pending exceptions, `fired_occurrences` untouched).
- [ ] T019b [US4] Write tests for the `delete_reminder` tool + resolution path in
  `tests/unit/test_ai_handler_reminders.py`: scope disambiguation, dispatch by `scope`.
- [ ] T019c [US4] Implement `ReminderManager.delete_single_occurrence`/`delete_whole_series` +
  `DELETE_REMINDER_TOOL` schema + its approval-resolution wiring (BLOCKED until T019a and T019b
  approved, depends on T017c).
- [ ] T020 [US4] 👤 **MANUAL APPROVAL GATE**: billed tests `test_delete_one_time_reminder`,
  `test_delete_whole_series` + `quickstart.md` #10, #13, #14.

**Checkpoint**: US1-4 — full create/deliver/modify/delete lifecycle for both one-time and
recurring reminders.

---

## Phase 7: User Story 5 — Recurring reminders with standard calendar-app cadence (P3)

**Goal**: confirm the full recurrence surface (already largely implemented as part of Phase 2/3's
shared `create_reminder` path, since one-time and recurring reminders share one tool/method) is
conversationally reachable and correctly bounded.

**Independent Test**: per `user-stories.md` US5.

- [ ] T021a [US5] Write tests confirming a yearly-cadence request is rejected structurally (no
  `FREQ=YEARLY` value exists in the schema at all, not just discouraged) in
  `tests/unit/test_reminder_manager.py` — if not already fully covered by T004a, extend it here.
- [ ] T021b [US5] Any remaining implementation gap T021a surfaces (expected: none, this is
  confirmation of Phase 2 work, not new functionality) (BLOCKED until T021a approved).
- [ ] T022 [US5] 👤 **MANUAL APPROVAL GATE**: billed test `test_godfather_creates_recurring_reminder`
  + `quickstart.md` #6 (weekly), #7 (monthly Nth-weekday), #8 (end conditions, observed across
  real sweep ticks).

**Checkpoint**: all five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T023 [P] Write `test_client_role_denied_reminder_tools` and
  `test_cap_declined_at_21st_reminder` (billed) — cross-cutting RBAC/cap coverage not specific to
  any single user story above.
- [ ] T024 [P] Run the full existing test suite (`pytest tests/ -v --tb=short`) to confirm zero
  regressions — in particular every existing Feature 022/047 approval-gate test, since
  `pending_approval_manager.py` was never touched but `get_response()`/`resolve_button_tap()`
  were extended.
- [ ] T025 Run the remaining `quickstart.md` scenarios not yet covered by earlier gates: #3
  (decline), #4 (past-date rejection), #5 (cap), #16 (client/blocked denial), #17 (admin acts on
  godfather's behalf), #19 (group-chat creation still fires to 1:1).
- [ ] T026 👤 **FINAL MANUAL APPROVAL GATE**: full `quickstart.md` run-through, end to end.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies, can start immediately.
- **Foundational (Phase 2)**: depends on Phase 1 — BLOCKS all user stories. T004a→T004b→T005a→T005b
  is a strict chain (resolution logic needs construction logic first); T006a/T006b are independent
  of both, `[P]`.
- **User Stories (Phase 3-7)**: all depend on Phase 2. Proceed in priority order (US1/US2 tied at
  P1 — US1 must land before US2 has anything to deliver, so treat as US1 then US2 despite the tie;
  US3 before US4, since US4's delete methods are structurally simpler versions of the same
  scope-handling US3 establishes; US5 mostly validates Phase 2/3 work already done).
- **Polish (Phase 8)**: depends on all five user stories.

## Notes

- No feature flag anywhere in this task list, by design (spec.md Clarifications) — `[P]` tasks
  and story checkpoints are the only gating mechanism, RBAC is the only runtime gate.
- Gate Zero (T014) is the one task in this entire list that cannot be completed inside a
  planning/coding session alone — it requires its own separate, explicit, human-present approval
  when the time comes, per CLAUDE.md's environment-start and unverified-third-party-assumption
  rules. Every other 👤 gate in this list is an ordinary human acceptance review, not a live-traffic
  action.
- `pending_approval_manager.py` (Feature 022/047) is never edited by any task above — verified by
  T024's full-suite regression run.
