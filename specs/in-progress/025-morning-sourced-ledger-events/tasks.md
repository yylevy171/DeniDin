# Tasks: Morning-Sourced Ledger Events

**Input**: Design documents from `specs/in-progress/025-morning-sourced-ledger-events/`
**Prerequisites**: `plan.md` ✅ · `spec.md` ✅ · `user-stories.md` ✅ · `research.md` ✅ ·
`data-model.md` ✅ · `contracts/` ✅

**Revised 2026-08-20 per `speckit.analyze`**: incorporates fixes for that pass's C1 (added T020,
a live-verification task closing the previously-unverified "all document types work with no new
`morning-mcp-app` tooling" assumption), H1 (added T010, a Gate-Zero task proving the novel
headless OpenAI+MCP call mechanism live before the full Acceptance pass, mirroring Feature 054's
own T014 precedent), M2 (T012a's file path is now fixed, no more either/or), M3 (T006a now
explicitly asserts no WhatsApp send occurs), L1 (T002b now explicitly includes the stale-comment
fix), and L2 (phases reordered to strict priority order: P1 stories US1/US2/US4 as Phases 3-5,
P2 stories US3/US5 as Phases 6-7 — previously US3 sat between two P1 stories). All task IDs were
renumbered as part of this pass (nothing was checked off yet, so this is safe).

---

**IMPORTANT**: This task list complies with:
- **CONSTITUTION.md** (§I-III): Config-only (no env vars), Israel local time throughout
  (bugfix-037), feature branch workflow.
- **METHODOLOGY.md** (§VI): every "a" (test) task requires human approval before its paired "b"
  (implementation) task; once approved, tests are IMMUTABLE without explicit re-approval.
  **§VI.a's 2026-08-18 TDD redefinition applies** (this feature is planned entirely after that
  date): the `billed`/`expensive` acceptance scenarios below are **descriptions only** — no test
  code is written, and nothing is run, until every unit/integration task (Phases 1-7's "a"/"b"
  pairs, plus the Gate-Zero task) is GREEN. At that point every 👤-marked task's description
  becomes real test code, written and run together, once, as the feature's actual acceptance
  pass.

**Tests**: TDD (§VI.b, unchanged) for all unit/integration work; §VI.a (redefined) for
`billed`/`expensive`.
**Organization**: Grouped by user story (`user-stories.md`'s priorities), after a shared
Foundational phase every story depends on (the extended `LedgerEvent` record shape + tool
schema).

## Format: `[ID] [P?] [Story] Description`
- **[P]**: can run in parallel (different files, no dependency on each other)
- **[Story]**: which user story this task belongs to
- **[T###a]**: write tests (requires human approval before T###b)
- **[T###b]**: implement (blocked until T###a approved)
- 👤: acceptance-scenario definition — description only at this stage, per §VI.a above

---

## Phase 1: Setup

- [ ] T001 Create `apps/denidin-app/src/services/accounting_reconciliation_service.py` module
  skeleton — docstring (per `contracts/accounting-reconciliation-service.md`), imports
  (`apscheduler`, `now_local`, `LedgerEventManager`), placeholder constants
  (`STARTUP_SWEEP_LOOKBACK`, `PERIODIC_SWEEP_LOOKBACK`, `RECONCILIATION_SWEEP_JOB_ID` — real
  values sized in T023), mirroring `services/reminder_delivery_service.py`'s file shape. No test
  (pure scaffolding, no logic yet).

---

## Phase 2: Foundational (blocks all user stories)

**⚠️ CRITICAL**: no user-story work begins until this phase is complete and approved — every
story depends on the extended persisted-record shape and tool schema existing.

- [ ] T002a [P] Write tests in `apps/denidin-app/tests/unit/test_ledger_event_manager.py` for the
  extended record shape (`data-model.md`): `source_type="חשבונית"` persists with all five
  `accounting_document_id`/`_number`/`_type`/`_status`/`_creation_date` fields populated;
  `event_subtype="הפקה"` accepted for `חשבונית`; all five fields are forced `null` for
  `הסכם`/`בנק` regardless of what's passed; `agreement_id`/`component_id`/`component_label`/
  `trigger_condition`/`percent`/`percent_base`/`hours`/`hourly_rate`/`bank_number`/
  `bank_branch`/`bank_account`/`payer_name` are all forced `null` for `חשבונית`;
  `schema_version=2` on every new write regardless of `source_type` (including `הסכם`/`בנק` —
  proves the bump is global, per spec.md's Clarifications); the old reserved field names
  (`morning_document_id`/`invoice_number`/`invoice_type`/`invoice_status`/
  `invoice_actual_creation_date`) no longer appear anywhere in a persisted record.
- [ ] T002b Implement the record-shape changes in `add_ledger_event`
  (`apps/denidin-app/src/managers/ledger_event_manager.py`): field renames, `_LETTER_BY_SOURCE_TYPE`
  gains `"חשבונית": "H"`, `event_subtype` enum extension, `CURRENT_SCHEMA_VERSION = 2` (BLOCKED
  until T002a approved). **Also update `_LETTER_BY_SOURCE_TYPE`'s own comment** (currently reads
  `"H"/חשבונית is Morning-invoice-sourced and never produced by capture_ledger_event (Feature
  025)"`) — that statement becomes false once this feature ships (it IS produced, via the new
  reconciliation handler in T006b, just never via the conversational path) — reword to say so
  explicitly rather than leaving a stale, misleading comment in place (`speckit.analyze` finding
  L1).
- [ ] T003a [P] Write tests for `scan_accounting_documents` in
  `apps/denidin-app/tests/unit/test_ledger_event_manager.py`: empty `storage_dir` → `(set(), None)`;
  one `חשבונית` event → its id + date; multiple → the correct maximum date; `הסכם`/`בנק` events
  ignored entirely; a malformed/unparseable JSON file is skipped with a WARNING, never raises
  (mirrors `_load_event`'s existing defensive-read discipline).
- [ ] T003b Implement `scan_accounting_documents` in `ledger_event_manager.py` (BLOCKED until
  T003a approved, depends on T002b). Needs new imports not currently present in this file:
  `Set`/`Tuple` from `typing`, `date` from `datetime` (`speckit.analyze` finding L3).
- [ ] T004a [P] Write tests for the duplicate guard in `add_ledger_event`
  (`tests/unit/test_ledger_event_manager.py`): a second `חשבונית` call with an
  `accounting_document_id` already present among persisted events returns `None`, logs a
  WARNING naming the duplicate id, and writes no new file; a genuinely new
  `accounting_document_id` succeeds normally; the guard never fires for `הסכם`/`בנק` (their
  `accounting_document_id` is always `None`).
- [ ] T004b Implement the duplicate guard at the top of `add_ledger_event` (before `_next_seq`,
  per `contracts/ledger-event-manager-extension.md`) (BLOCKED until T004a approved, depends on
  T003b).
- [ ] T005a [P] Write tests for the extended `LEDGER_EVENT_TOOL` schema in
  `apps/denidin-app/tests/unit/test_ai_handler_ledger_events.py`: `source_type` enum includes
  `"חשבונית"`; `event_subtype` enum includes `"הפקה"`; the five new top-level properties exist,
  are `["string", "null"]`, and are present in `required` (strict-mode compliance);
  `additionalProperties` stays `False`; tool `description` distinguishes the free-text-signal
  use case from the transcribe-given-structured-data use case.
- [ ] T005b Implement the `LEDGER_EVENT_TOOL` schema extension in
  `apps/denidin-app/src/handlers/ai_handler.py` (BLOCKED until T005a approved).

---

## Phase 3: User Story 1 — A background sweep captures a Morning document DeniDin never saw (P1) 🎯 MVP core

**Goal**: the reconciliation sweep can list, detail, and persist a not-yet-known Morning
document as a `LedgerEvent`, end to end, without touching the conversational suppression path.

**Independent Test**: per `user-stories.md` US1.

- [ ] T006a [P] [US1] Write tests for the NEW reconciliation-capture handler in
  `tests/unit/test_ai_handler_ledger_events.py`: given a synthetic Responses-API response object
  containing both `mcp_call` item(s) (`list_invoices`/`get_invoice_details`) and one
  `capture_ledger_event` call, the new handler persists it via
  `LedgerEventManager.add_ledger_events_from_call`, **unaffected** by
  `_handle_ledger_event_capture`'s same-turn-`mcp_call` suppression (proven by never calling
  that method); a malformed/unparseable `capture_ledger_event` call is rejected and logged, not
  silently dropped (mirrors REQ-DATA-008's existing discipline); persisted events use the
  `session_id="accounting-reconciliation"`/`message_id=None` sentinel (data-model.md). **Also
  assert that no `WhatsAppHandler.send_response`/`send_proactive_message` call occurs anywhere
  in this path** — the contract's "no confirmation reply is sent anywhere, no chat, nothing
  user-facing" guarantee (`contracts/accounting-reconciliation-service.md` step 6) had no test
  coverage until now (`speckit.analyze` finding M3).
- [ ] T006b [US1] Implement the new handler method (exact name TBD at implementation — e.g.
  `_handle_accounting_reconciliation_capture`) in `ai_handler.py` (BLOCKED until T006a approved,
  depends on T002b, T004b, T005b).
- [ ] T007a [P] [US1] Write tests for the sweep worker's watermark derivation and prompt
  construction in `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py`: given
  known `חשבונית` events, `since` = the latest `accounting_document_creation_date`; given none,
  `since` = `now_local().date() - <fallback lookback>`; the built prompt text includes the
  correct `since` date and instructs one `capture_ledger_event` call per not-yet-known document.
- [ ] T007b [US1] Implement `_sweep_accounting_documents`'s watermark/prompt-building logic in
  `services/accounting_reconciliation_service.py` (the real OpenAI call itself is exercised for
  real only in T010/T011) (BLOCKED until T007a approved, depends on T003b).
- [ ] T008a [P] [US1] Write tests for scheduler wiring in
  `tests/unit/test_accounting_reconciliation_service.py`:
  `start_accounting_reconciliation_scheduler` registers exactly one job with `max_instances=1`;
  `run_startup_accounting_reconciliation_sweep` invokes the shared sweep function synchronously
  with the startup lookback; a testability-seam `trigger` override (mirroring
  `reminder_delivery_service.py`'s own) proves the real `add_job()`+`BackgroundScheduler` wiring
  fires without waiting on a real `CronTrigger` boundary.
- [ ] T008b [US1] Implement scheduler start/stop + `run_startup_accounting_reconciliation_sweep`
  in `services/accounting_reconciliation_service.py` (BLOCKED until T008a approved, depends on
  T007b).
- [ ] T009 [US1] Wire the scheduler into `apps/denidin-app/denidin.py`'s
  `if __name__ == "__main__":` block — start alongside `bot.run_forever()`, store as
  `denidin.accounting_reconciliation_scheduler`, `.shutdown()` in the SIGINT/SIGTERM handler and
  the `KeyboardInterrupt` block, alongside the existing `cleanup_thread`/`reminder_scheduler`
  shutdowns. **NOT** inside `initialize_app()` (per `contracts/accounting-reconciliation-service.md`'s
  explicit constraint — `tests/integration/` calls that bootstrap directly against a real `bot`,
  same risk `reminder-delivery.md`'s own 2026-08-17 correction already documents). No dedicated
  automated test — this exact placement is what a test can't exercise without a real process;
  verified manually via `quickstart.md` instead, same as `reminder_scheduler`'s own wiring
  (BLOCKED until T008b approved).
- [ ] T010 [US1] 👤 **GATE ZERO** (added by `speckit.analyze`, finding H1 — mirrors Feature 054's
  T014 precedent): a real, minimal, standalone OpenAI Responses API call — Morning MCP tools +
  `LEDGER_EVENT_TOOL` attached, explicitly **no** session/`chat_id`/`AIRequest`, using the
  dedicated reconciliation prompt shape from `contracts/accounting-reconciliation-service.md` —
  succeeds live, once, against the real `dev` Morning sandbox + real OpenAI. This proves the
  core novel mechanism this entire phase is built on (a "headless" OpenAI+MCP call outside the
  normal conversational path has never been exercised anywhere in this codebase before) actually
  works, **before** T011's full multi-scenario Acceptance pass is written. A single manual/live
  check is sufficient here (does not need to be a formal pytest suite entry) — its purpose is
  early, cheap risk reduction, not coverage. Run only after T006b/T007b/T008b/T009 all exist
  (needs the real tool-attachment plumbing to issue the call through), but explicitly **before**
  T011 is attempted.
- [ ] T011 [US1] 👤 **Acceptance scenario definition (`billed` tier — text-only OpenAI + Morning
  MCP round-trip, no vision/image calls involved)**: description only, per §VI.a — no test code
  yet. A document is created directly in the Morning **dev sandbox**, outside any DeniDin
  conversation. One reconciliation sweep tick is triggered for the test (via T008a's
  testability-seam trigger) against the real sandbox + real OpenAI. After it completes, a new
  `dev_data/events/H{DDMMYY}{HHMM}{seq}.json` file exists with `source_type="חשבונית"`, all five
  `accounting_document_*` fields matching the real sandbox document (cross-checked against the
  Morning sandbox UI, not just internal consistency), `schema_version=2`. Validates User Story
  1. Test code written and run together with every other 👤 task below, once, only after Phase 7
  is entirely GREEN.

**Checkpoint**: US1 fully functional and independently demoable (a genuinely new Morning
document gets captured), even without the dedup/multi-doc/regression guarantees below.

---

## Phase 4: User Story 2 — A document already captured is never re-captured (P1)

**Goal**: the dedup guard actually prevents duplicate persistence, not just the prompt's own
framing.

**Independent Test**: per `user-stories.md` US2. **Must ship together with US1** (per
`user-stories.md`'s own priority note — without this, US1 alone is actively harmful, not merely
incomplete).

- [ ] T012a [P] [US2] Write a test in
  `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py` (fixed file — was
  left as an either/or before `speckit.analyze` finding M2) proving the composed flow: a first
  simulated sweep persists a synthetic document via the new handler (T006b); a second simulated
  sweep whose (synthetic) model response attempts to capture the SAME `accounting_document_id`
  is refused by T004b's guard — real `LedgerEventManager`/handler objects throughout, only the
  OpenAI response object itself is a test-constructed stand-in (no live network), matching this
  codebase's existing pattern for `ai_handler.py` unit tests. No real router/webhook entry point
  exists for this feature (CONSTITUTION §V) — `unit`, not `integration`, tier.
- [ ] T012b [US2] Any glue code the test surfaces as missing (expected: none new — this proves
  T004b's guard and T007a/T007b's watermark logic already compose correctly together) (BLOCKED
  until T012a approved).
- [ ] T013 [US2] 👤 **Acceptance scenario definition (`billed`)**: description only. A second
  sweep tick, run with no new Morning documents created since T011's scenario, produces zero new
  `dev_data/events/` files, and the log shows the sweep actually ran (distinguishable from a
  silent no-op). Validates User Story 2.

**Checkpoint**: US1+US2 together are the MVP — a document is captured exactly once, ever.

---

## Phase 5: User Story 4 — An ordinary conversational Morning question is unaffected (P1)

**Goal**: prove, not assume, that this feature introduces zero regression risk to the existing
(and previously-broken, then fixed) conversational suppression path. Reordered ahead of the P2
stories (`speckit.analyze` finding L2 — this is a P1 story; it depends only on Phase 2, not on
Phase 3/4, so nothing blocks doing it this early).

**Independent Test**: per `user-stories.md` US4.

- [ ] T014a [P] [US4] Extend the existing `_handle_ledger_event_capture` suppression tests in
  `tests/unit/test_ai_handler_ledger_events.py` (the ones covering the 2026-07-28/2026-08-02
  incidents) to run unchanged against the now-extended `LEDGER_EVENT_TOOL` schema: same-turn
  `mcp_call`/`mcp_approval_request` still suppresses every `capture_ledger_event` call; more
  than one call in a turn is still a protocol violation there — both completely independent of
  the new `source_type="חשבונית"` additions.
- [ ] T014b [US4] Fix anything T014a's regression check surfaces (expected: none —
  `_handle_ledger_event_capture` is explicitly unmodified by this feature, per
  `contracts/ledger-event-manager-extension.md`'s "UNCHANGED" section) (BLOCKED until T014a
  approved).
- [ ] T015 [US4] 👤 **Acceptance scenario definition (`billed`)**: description only. From a
  godfather/admin phone, a real Morning question that causes `list_invoices`/`get_invoice_details`
  to run in the same conversational turn (the original 2026-07-28 incident's shape — e.g. "list
  all payments for client X"). The reply is complete and correct (the original empty-reply
  symptom does not reproduce), and no new `dev_data/events/` file is created by that turn.
  Validates User Story 4 — the regression check for this entire feature's core assumption.

---

## Phase 6: User Story 3 — Multiple new documents in one window are all captured (P2)

**Goal**: the reconciliation handler's multi-call-per-turn path actually persists every call,
not just the first.

**Independent Test**: per `user-stories.md` US3.

- [ ] T016a [P] [US3] Extend T006a's test file: given a synthetic response containing TWO
  `capture_ledger_event` calls in the same turn (two distinct `accounting_document_id`s), both
  are persisted as separate `LedgerEvent` files.
- [ ] T016b [US3] Confirm/adjust the handler from T006b to support N calls per turn (expected:
  already correct by construction — it deliberately does not inherit
  `_handle_ledger_event_capture`'s one-call-per-turn rule; this task exists to prove it, not
  necessarily add new code) (BLOCKED until T016a approved).
- [ ] T017 [US3] 👤 **Acceptance scenario definition (`billed`)**: description only. Two
  documents are created in the Morning sandbox before one sweep tick; after that tick, two new
  distinct `H...json` files exist, one per document. Validates User Story 3.

---

## Phase 7: User Story 5 — A sweep failure never silently skips a window (P2)

**Goal**: prove the watermark's derived-not-counted design actually self-corrects after a
failure, not just in theory.

**Independent Test**: per `user-stories.md` US5.

- [ ] T018a [P] [US5] Write tests in `tests/unit/test_accounting_reconciliation_service.py`:
  given the sweep worker raises partway through (simulated OpenAI/MCP failure) before persisting
  anything, the function catches it, logs at ERROR, and returns cleanly; a subsequent watermark
  derivation (`scan_accounting_documents`) afterward returns exactly the same result as before
  the failed attempt — proving no separate counter was silently advanced.
- [ ] T018b [US5] Implement the try/except wrapper around the sweep tick's
  OpenAI-call-through-persist logic in `services/accounting_reconciliation_service.py` (BLOCKED
  until T018a approved, depends on T007b, T008b).
- [ ] T019 [US5] 👤 **Acceptance scenario definition (`billed`)**: description only. One sweep
  tick is made to fail (e.g. a temporarily unreachable Morning MCP URL for that single tick),
  then a subsequent successful tick still covers the full window back to the last real captured
  document — nothing silently skipped. Validates User Story 5.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T020 **Live-verify the all-document-types scope decision** (added by `speckit.analyze`,
  finding C1): `research.md`'s "no new `morning-mcp-app` tooling needed" conclusion was derived
  entirely from static code reading (no `type` filter sent to `/documents/search`/
  `/documents/{id}`), never confirmed by an actual live call. Against the real Morning **dev
  sandbox**, create one non-invoice document (a receipt or credit note) and confirm
  `list_invoices`/`get_invoice_details` genuinely return it (not just invoices) — per
  `CONSTITUTION.md`'s "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" principle. If this does NOT hold,
  the "all document types" scope decision (spec.md Clarifications round 2) needs to be revisited
  with the user before T011/T017 assume it. Run before T020/T021 below, and well before any 👤
  Acceptance task runs for real.
- [ ] T021 **Verify `source_type="חשבונית"`'s real-world usage** against the actual
  hand-maintained `Events.csv` (spec.md's flagged, still-open naming risk — see `research.md`'s
  "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" note). A real-data check, not code — document the
  finding (confirm the term, or revise it) **before** the Acceptance tasks (T011/T013/T017/T015/
  T019) run for real, since they'd otherwise ship a wrong term into real persisted data.
- [ ] T022 **Confirm `event_subtype="הפקה"`** reads correctly as real accounting terminology
  (spec.md's second still-open item) — same kind of real-world sanity check as T021, not code.
- [ ] T023 **Size the real poll interval + fallback lookback constants** (placeholders from T001/
  T007b) — an explicit tuning decision needing human input (cost/traffic tradeoff, per
  `plan.md`'s Technical Context), not a default to silently pick.
- [ ] T024 Update `CLAUDE.md`'s feature-summary section with a new "Accounting Document
  Reconciliation (Feature 025)" paragraph, mirroring the "Reminders (Feature 054)" section's
  shape — done as part of `haleluya`'s docs-update step, not here.

---

## Dependencies & Execution Order

1. **Phase 1 (Setup)** → **Phase 2 (Foundational)** — strictly sequential, blocks everything else.
2. **Phase 3 (US1)** depends on Phase 2 fully complete.
3. **Phase 4 (US2)** depends on Phase 3 (needs a real capture to attempt to duplicate) — ships
   together with US1 as the MVP (see Implementation Strategy).
4. **Phase 5 (US4)** depends on Phase 2 only (regression check against the schema extension) —
   independent of Phases 3-4/6-7, can run any time after Phase 2.
5. **Phase 6 (US3)** depends on Phase 3 (extends T006's handler/tests) — independent of Phases
   4-5/7.
6. **Phase 7 (US5)** depends on Phase 3 (needs the sweep worker to exist) — independent of
   Phases 4-6.
7. **T010 (Gate Zero)** depends on T006b/T007b/T008b/T009 all existing, and must complete
   **before** T011 (US1's Acceptance definition is written into real code).
8. **Phase 8 (Polish)** T020/T021/T022 should happen before any 👤 Acceptance task actually
   runs; T023 before T007b/T008b are meaningfully testable end-to-end; T024 last
   (post-implementation).
9. **All 👤 Acceptance tasks (T011/T013/T015/T017/T019)**: written and run together, once, only
   after every other task in Phases 1-7 (including Gate Zero, T010) is GREEN (§VI.a).

## Parallel Example: Foundational Phase

```text
# T002a, T003a, T004a, T005a can be written in parallel (different test concerns, though
# T002a/T003a/T004a share one file — coordinate within that file; T005a is a separate file):
Task: "Write tests for extended LedgerEvent record shape in test_ledger_event_manager.py"
Task: "Write tests for scan_accounting_documents in test_ledger_event_manager.py"
Task: "Write tests for the duplicate guard in test_ledger_event_manager.py"
Task: "Write tests for the extended LEDGER_EVENT_TOOL schema in test_ai_handler_ledger_events.py"
```

---

## Implementation Strategy

### MVP First (Phases 1-4: Setup + Foundational + US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (including Gate Zero, T010, before T011)
4. Complete Phase 4: User Story 2 (dedup — ships with US1, not after it, per
   `user-stories.md`'s own priority rationale)
5. **STOP and VALIDATE**: T020/T021/T022/T023 resolved, US1+US2's 👤 scenarios (T011/T013)
   written and run for real
6. This is the MVP — a genuinely new Morning document gets captured exactly once, silently,
   with zero regression to existing conversational behavior only once Phase 5 (US4) also lands

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 (+ Gate Zero) + US2 → MVP demoable (single-document capture, dedup-safe, mechanism
   proven live early rather than only at the very end)
3. US4 → regression safety net confirmed (now Phase 5, priority-ordered — pure verification, no
   new capability, cheap and safe to do early relative to any real dev/prod exposure)
4. US3 → multi-document correctness
5. US5 → failure-resilience correctness
6. Each story adds value without breaking previous stories; Phase 8 closes remaining real-world
   verification/tuning gaps before Acceptance runs for real

## Notes

- [P] tasks = different files (or clearly separable concerns within one file), no dependency on
  each other.
- [Story] label maps task to specific user story for traceability.
- Verify each "a" task's tests fail before writing its paired "b" implementation.
- Commit after each approved task or logical group (per CLAUDE.md's "never merge without
  approval" — commits within the branch are fine; PR/merge to `master` is its own separate gate,
  handled by `haleluya`).
- Stop at each Checkpoint to validate that story independently before continuing.
- `apps/morning-mcp-app` needs zero changes for this entire feature (`research.md`'s finding,
  live-verified by T020) — no task above touches it.
