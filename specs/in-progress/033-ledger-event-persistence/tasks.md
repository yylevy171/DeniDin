# Tasks: Ledger Event Persistence

**Input**: Design documents from `specs/in-progress/033-ledger-event-persistence/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/ledger-event-manager.md`, `quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III (config-only, UTC timestamps, feature
branch workflow) and METHODOLOGY.md §VI (TDD, human approval gates, tests IMMUTABLE once
approved).

**Tests**: TDD — every "a" task (tests) requires explicit human approval before its
matching "b" task (implementation) begins. Once approved, a test is immutable without a
fresh, explicit re-approval.

**Path Conventions**: Single project — `apps/denidin-app/src/`, `apps/denidin-app/tests/`,
`apps/denidin-app/scripts/` (per `plan.md`'s Project Structure).

## Version Control steps (applied at the end of every phase below)

- **VC0**: Confirm `git branch --show-current` is `feature/033-ledger-event-persistence`.
- **VC1**: `git add` only the files touched by that phase (never a broad `git add -A`).
- **VC2**: `git commit` with a conventional-commit message referencing the phase's
  REQ-###/US# ids (per CONSTITUTION §III format).
- **VC3**: Push (`git push -u origin ...` first time, `git push` after) — **only when the
  user explicitly asks to push**, same as every other push in this project (per this
  session's standing rule: no push without its own fresh approval).
- **VC4**: (end of feature only) Open PR — own explicit approval required.
- **VC5**: (end of feature only) Merge + delete branches — own explicit approval required,
  never inferred from an earlier "yes" to something else.

---

## Phase 1: Setup

- [x] T001 Confirm `git branch --show-current` is `feature/033-ledger-event-persistence`
  (already created). No dependency changes needed (research.md: stdlib only).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `LedgerEventManager` fully functional and independently testable, standalone,
before any handler wiring begins. **No user-story work starts until this phase's tests are
approved and implementation passes.**

- [x] T002a [P] Write tests for `LedgerEventManager` core in
  `tests/unit/test_ledger_event_manager.py`: storage dir created on init if absent; a
  minimal valid `add_ledger_event(...)` call writes `data/events/{event_id}.json`; file
  content has all 29 CSV-mapped keys + 9 internal keys per `data-model.md`, alphabetized,
  UTF-8, `ensure_ascii=False`; input `event` dict not mutated by the call.
- [x] T002b [P] Implement `LedgerEventManager.__init__`/`add_ledger_event` skeleton +
  core atomic-write path in `src/managers/ledger_event_manager.py` (BLOCKED until T002a
  approved).

- [x] T003a [P] Write tests for `event_id` generation in
  `tests/unit/test_ledger_event_manager.py`: `source_type=הסכם`→`A` prefix,
  `source_type=בנק`→`B` prefix; a known UTC `message_timestamp` converts to the correct
  Asia/Jerusalem `DDMMYY`/`HHMM` (including a DST-boundary case); first event for a new
  letter+minute gets `seq=0`; a second event for the same letter+minute gets `seq=1`;
  `seq` scoped per-letter (an `A...` and a `B...` event at the identical minute do NOT
  share a `seq` counter); collision-checking reads only `data/events/*.json`, never
  `Events.csv` (test asserts no attempt to open that path); 11th event for the same
  letter+minute is rejected — no file written, `add_ledger_event` returns `None`
  (not an `event_id` string), an ERROR is logged.
- [x] T003b [P] Implement `event_id` generation (`zoneinfo`-based local-time conversion,
  per-letter-per-minute `seq` counter scanning `storage_dir`, returns `Optional[str]`) in
  `src/managers/ledger_event_manager.py` (BLOCKED until T003a approved).

- [x] T004a [P] Write tests for `amount` normalization in
  `tests/unit/test_ledger_event_manager.py`: `"8,000₪"`→`8000`, `"-7,000"`→`-7000`,
  `"₪12,500.00"`→`12500`, `"1,500 ש\"ח"`→`1500`, `None`→`None`, unparseable text (e.g. a
  leftover multi-amount string) → `None` result + WARNING logged + original text
  preserved in `notes`.
- [x] T004b [P] Implement `amount` normalization in `src/managers/ledger_event_manager.py`
  (BLOCKED until T004a approved).

- [x] T005a [P] Write tests for `replaced_event_id`/`reference` placeholder logic in
  `tests/unit/test_ledger_event_manager.py`: `replaces_hint` non-null →
  `replaced_event_id="צריך למצוא"`; `replaces_hint` null → `replaced_event_id` blank;
  `reference` is always blank/null regardless of `reference_hint`.
- [x] T005b [P] Implement placeholder logic in `src/managers/ledger_event_manager.py`
  (BLOCKED until T005a approved).

- [x] T006a [P] Write tests for the reserved-null fields in
  `tests/unit/test_ledger_event_manager.py`: `agreement_id`, `component_id`,
  `component_label`, `trigger_condition`, `split_partner`, `split_percent`, `due_date`,
  and all 5 `invoice_*` fields are always `null` in the written file, present as keys
  (never omitted).
- [x] T006b [P] Ensure these fields are explicitly set `None` (not omitted) in the written
  record in `src/managers/ledger_event_manager.py` (BLOCKED until T006a approved).

- [x] T007a [P] Write tests for `Session`/`Message` model changes in
  `tests/unit/test_session_manager.py` (replacing `TestPendingLedgerEvents`): `Session`
  has no `pending_ledger_events` attribute/field at all; a freshly created `Message` has
  `ledger_event_ids == []`; a `Message` with `ledger_event_ids` set persists and reloads
  correctly across a fresh `SessionManager` instance pointed at the same storage dir
  (mirrors the old `test_add_pending_ledger_event_persists_across_reload` coverage).
- [x] T007b [P] Remove `Session.pending_ledger_events` and
  `SessionManager.add_pending_ledger_event`; add `Message.ledger_event_ids` in
  `src/managers/session_manager.py` (BLOCKED until T007a approved).

**Checkpoint**: `LedgerEventManager` fully functional and independently testable in
isolation — no handler wiring yet. Run full `tests/unit/test_ledger_event_manager.py` +
updated `tests/unit/test_session_manager.py`; all green before proceeding.

VC0-VC2 for this phase (commit message references REQ-STORE-001/002/003, REQ-ID-001/002/003,
REQ-DATA-001/002/003, REQ-TRACE-003).

---

## Phase 3: User Story 1 — Text-path event persists to its own permanent file (Priority: P1) 🎯 MVP

**Goal**: A godfather's text-message fee-agreement capture lands under `data/events/`,
never `session.json`; the source message records the resulting `ledger_event_ids`.

**Independent Test**: `quickstart.md` US1 (real WhatsApp text message).

- [x] T008a [US1] Write component-integration tests (real objects, no mocks, per
  CONSTITUTION §V) for `AIHandler._handle_ledger_event_capture` → `LedgerEventManager`
  wiring, in `tests/unit/test_ai_handler_ledger_events.py` (existing file, currently only
  covers `extract_function_call`/`extract_function_call_id`/`extract_all_function_calls` —
  no conflict, these are net-new test classes): asserts `LedgerEventManager.add_ledger_event` is called once per resolved
  `capture_ledger_event` call with the correct `message_id`/`message_timestamp`/`sender`;
  asserts the stored user message's `ledger_event_ids` contains the resulting `event_id`;
  asserts a normal conversational reply is still produced alongside the capture (per
  constitution, capture is additive, never a replacement for the reply).
- [x] T008b [US1] Implement `AIHandler._handle_ledger_event_capture` changes: call
  `LedgerEventManager.add_ledger_event` (not the removed `SessionManager` method), collect
  resulting `event_id`(s), thread into the `add_message`/`add_message_with_token_limit`
  call for the source user message, in `src/handlers/ai_handler.py` (BLOCKED until T008a
  approved; depends on Phase 2 completion). Also wire `LedgerEventManager` into
  `denidin.py`'s `initialize_app` (constructor injection, same pattern as `MemoryManager`).

- [ ] T009 [US1] 👤 **MANUAL APPROVAL GATE**: Run `quickstart.md`'s US1 scenario against a
  running dev container (own explicit approval to start `dev`, per CLAUDE.md) — real
  WhatsApp text message, verify the resulting file and message linkage by hand.

**Checkpoint**: US1 fully functional and independently testable. VC0-VC2 (REQ-TRACE-003
wiring, US1).

---

## Phase 4: User Story 2 — Image-path event persists the same way (Priority: P1)

**Goal**: Image-path captures gain `message_id` (currently impossible — not threaded at
all) and go through the same `LedgerEventManager`, in capture-before-store order.

**Independent Test**: `quickstart.md` US2 (real bank-transfer screenshot).

- [x] T010a [US2] Write component-integration tests in
  `tests/unit/test_media_handler.py` (existing file): `WhatsAppHandler.handle_media_message`
  passes `message.message_id` through to `MediaHandler.process_media_message`; a captured
  ledger event's `message_id` is non-null and matches the media-turn message's own id; the
  media-turn message is stored with `ledger_event_ids` populated at creation (not patched
  afterward — assert call order: capture happens before `_store_media_turn`).
- [x] T010b [US2] Implement: new `message_id` parameter threaded from
  `WhatsAppHandler.handle_media_message` (`src/handlers/whatsapp_handler.py`) into
  `MediaHandler.process_media_message` (`src/handlers/media_handler.py`); reorder so ledger
  capture happens before `_store_media_turn`; fix the `sender_phone` docstring (REQ-DOC-001)
  (BLOCKED until T010a approved; depends on Phase 2 + T008b).

- [ ] T011 [US2] 👤 **MANUAL APPROVAL GATE**: Run `quickstart.md`'s US2 scenario (real
  bank-transfer screenshot).

**Checkpoint**: US1 AND US2 both work independently. VC0-VC2 (REQ-TRACE-001/002, US2).

---

## Phase 5: User Story 3 — Multi-component message → multiple separate event files (Priority: P2)

**Goal**: N `capture_ledger_event` calls in one turn → N separate files, sequential `seq`,
all N ids recorded on the source message.

**Independent Test**: `quickstart.md` US3.

- [x] T012a [US3] Write tests (extending T008a's test file) asserting: a turn with 3
  resolved `capture_ledger_event` calls produces 3 `LedgerEventManager.add_ledger_event`
  calls (already required by T008b's per-call loop — this story adds the multi-call
  assertion specifically); the 3 resulting `event_id`s share the same
  `letter`+`DDMMYY`+`HHMM` prefix with `seq` 0,1,2; the source message's
  `ledger_event_ids` has exactly 3 entries in call order.
- [x] T012b [US3] Verify/adjust `_handle_ledger_event_capture`'s existing per-call loop
  (already iterates `ledger_calls`, per Feature 024) correctly accumulates all resulting
  `event_id`s (not just the last, and skipping any `None` from REQ-ID-003's rare
  exhaustion case) into the list passed to `add_message` in `src/handlers/ai_handler.py`
  (BLOCKED until T012a approved).

- [ ] T013 [US3] 👤 **MANUAL APPROVAL GATE**: Run `quickstart.md`'s US3 scenario (a real
  multi-stage fee-agreement message). Complemented by the real, unmodified, verbatim
  גיליאן דוידיאן message as an actual expensive test — see Phase 7, T023.

**Checkpoint**: US1, US2, US3 all work independently. VC0-VC2 (REQ-STORE-002 multi-call
coverage, US3).

---

## Phase 6: User Story 4 — Historical session migrates to the new format (Priority: P3)

**Goal**: Session `4454746c-350a-4fa7-a5ef-fda2c685b0d5`'s 3 combined events become 6
correctly-split files under `data/events/`, and its `session.json` is cleared.

**Independent Test**: `quickstart.md` US4.

- [x] T014a [US4] Write tests for the migration script's pure splitting/mapping logic in
  `tests/unit/test_migrate_stray_ledger_events.py`, using a fixture mirroring the real
  session's 3 combined records (not the real dev_data file): asserts the גיליאן דוידיאן
  record splits into exactly 3 components with the correct per-stage `description`/
  `amount`, the שרית יוגב/מרדכי רצבגר record splits into exactly 2, the מלכה בן סעדון
  record stays a single event; asserts every call goes through
  `LedgerEventManager.add_ledger_event` (per `contracts/ledger-event-manager.md` — never a
  direct file write); asserts `message_id=None` is passed explicitly for all 6.
- [x] T014b [US4] Implement `scripts/migrate_stray_ledger_events.py`: reads a given
  session's `pending_ledger_events`, applies the component-split mapping (hardcoded for
  this specific historical session — this is a one-off script, not general-purpose
  splitting logic), calls `LedgerEventManager.add_ledger_event` per component, and (only
  after all succeed) clears `pending_ledger_events` from that session's `session.json`.
  Supports a `--dry-run` flag that prints what would be written without writing (BLOCKED
  until T014a approved; depends on Phase 2).

- [ ] T015 [US4] 👤 **MANUAL APPROVAL GATE**: Run
  `scripts/migrate_stray_ledger_events.py --dry-run`, present the exact output for
  approval (per this feature's design conversation — migration output must be
  human-reviewed before writing).
- [ ] T016 [US4] 👤 **MANUAL APPROVAL GATE**: After T015 approval, run the script for
  real; verify via `quickstart.md` US4 (6 files exist, `session.json` cleared).

**Checkpoint**: All 4 user stories complete and independently functional. VC0-VC2
(REQ-MIGRATE-001, US4).

---

## Phase 7: Expensive E2E Test Suite (real OpenAI + real images, no mocking)

**Purpose**: `tests/expensive/test_ledger_event_capture_e2e.py` is this feature's real
proof — component-level tests (Phases 2-6) verify the persistence/wiring logic works
*given* a captured event, but only a real model call proves the model still calls
`capture_ledger_event` correctly against the new persistence layer, and proves what it
*actually* does with genuinely ambiguous cases (multi-stage splitting, cancellation
amount sign). **Every task below is its own expensive-test run: explicit approval
required per run, one at a time, never a bare `-m expensive` sweep, per CLAUDE.md/
CONSTITUTION §VII.** 13 separate approval+run cycles total across this phase — flagging
the scale plainly since it's real cost, not a rubber-stamp phase.

### Update the 5 existing tests (assertions only — same scenarios, same test names)

- [x] T017a Update `test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured`:
  assert `data/events/{event_id}.json` (not `session.json`), all 29 keys present,
  `message_id` non-null and matches the sent message, `Message.ledger_event_ids` contains it.
- [x] T017b Update `test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured`:
  assert no file created under `data/events/`.
- [x] T017c Update `test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path`:
  same as T017a, plus this is the first real proof `message_id` threading works on the
  image path end-to-end (component tests in Phase 4 use a real object but not a real
  model call).
- [x] T017d Update `test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit`:
  same as T017c, `B`-prefixed `event_id`.
- [x] T017e Update `test_given_non_agreement_image_when_processed_then_no_ledger_event_captured`:
  assert no file.
- [ ] T018 👤 **HUMAN APPROVAL GATE**: T017a-e modify 5 existing **approved** tests
  (CONSTITUTION §VIII: immutable without explicit re-approval) — sign-off needed on the
  diff itself before commit, tagged `HUMAN APPROVED:` per CONSTITUTION §VIII, before any
  of T017a-e are re-run.
- [ ] T019 👤 **EXPENSIVE-TEST APPROVAL + RUN** (one at a time, 5 separate cycles): re-run
  each of T017a-e individually after T018's sign-off.

### New: real multi-stage message, verbatim (US3)

- [x] T020a Write `test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component`
  using the **exact, unmodified** גיליאן דוידיאן message text (raw excerpt from the
  original stray capture — see `data-model.md`'s migration reference data). Asserts the
  *correct* target behavior per this feature's design: 3 separate files, sequential `seq`,
  correct per-stage `amount`/`trigger_condition`-worthy content. Per explicit instruction:
  write the strict correct assertion, don't pre-soften it — if the model doesn't split it
  today, the test fails and that's real information to act on separately (this behavior
  depends partly on the deferred nuances-feature constitution wording, tracked
  independently — a failure here doesn't block this feature's other tests).
- [ ] T021 👤 **EXPENSIVE-TEST APPROVAL + RUN**: run T020a once.

### New: data-model correctness for agreements (5 tests, source_type=הסכם field coverage)

- [x] T022a Write `test_given_new_agreement_flat_fee_then_all_fields_correctly_persisted`
  (`event_subtype=יצירה`, explicit `vat_status`, flat `amount`) — asserts every direct-mapped
  field (client_name, description, amount, vat_status) is correct in the persisted file.
- [x] T022b Write `test_given_agreement_correction_then_replaced_placeholder_correct`
  (`event_subtype=עדכון`, message states a correction to a named prior arrangement) —
  asserts `replaces_hint` captured non-null and `replaced_event_id == "צריך למצוא"` in the
  persisted file (REQ-DATA-002).
- [x] T022c Write `test_given_agreement_cancellation_then_subtype_and_amount_correct`
  (`event_subtype=ביטול`) — asserts `event_subtype` correct and `amount` is negative in
  the persisted file (REQ-DATA-001's cancellation-reverses-a-positive-amount case) — a
  genuinely open question about real model+parser behavior; strict assertion, real answer
  either way is useful.
- [x] T022d Write `test_given_agreement_payment_confirmation_then_subtype_correct`
  (`event_subtype=אישור-מימוש`) — asserts subtype and amount correct.
- [x] T022e Write `test_given_agreement_percent_based_fee_then_percent_fields_correct`
  (a percentage-of-outcome fee, no fixed amount — mirrors the real `Events.csv` "אתי
  אסולין" pattern found during this feature's research) — asserts `percent`/`percent_base`
  populated and `amount` blank/null in the persisted file.
- [ ] T023 👤 **EXPENSIVE-TEST APPROVAL + RUN** (one at a time, 5 separate cycles): run
  T022a-e individually.

### New: real-image data-model correctness (2 tests, images supplied 2026-07-29)

Images supplied: `Agreement-test-image.jpg`, `Bank-test-image.jpg`
(`tests/fixtures/media/ledger_events/`). No separate human transcript existed for
these two (unlike the original 3 images) — ground truth was read directly from the
images by the implementing agent and documented in each test's docstring.

- [x] T024a Write `test_given_real_multi_component_agreement_image_then_components_correctly_persisted`
  — the agreement image turned out to itself be a real 4-component tiered fee document
  (10,000 / hourly-800-capped-10h / 15,000 / 5,000 ₪), with no pre-agreed "correct" split
  (unlike T020a's גיליאן דוידיאן case) — asserts structurally strict properties instead of
  an exact count: every persisted event has a well-formed `A`-prefixed `event_id` and
  `source_type=הסכם`, and the three flat-fee amounts (10000/15000/5000) are each
  represented somewhere across the persisted event(s).
- [x] T024b Write `test_given_real_bank_deposit_image_then_full_fields_correctly_persisted`
  — single clean bank transfer, asserts exact `amount=1500`, `event_subtype=הפקדה`,
  `B`-prefixed `event_id`.
- [ ] T025 👤 **EXPENSIVE-TEST APPROVAL + RUN** (2 separate cycles): run T024a, then T024b.

**Checkpoint**: Full expensive-test suite (13 tests: 5 updated + 8 new) proves this
feature's behavior against the real model, not just component-level wiring.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T026 [P] Run `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and
  `python3 -m mypy src/ --config-file=mypy.ini`; fix any new findings introduced by this
  feature.
- [x] T027 [P] Run the full non-expensive suite: `python3 -m pytest tests/ -v --tb=short`;
  all green.

---

## Phase 9 (Addendum, 2026-07-30): REQ-DATA-004 — agreement_id/component_id

Reopened after the real migration run: the user flagged `agreement_id`/`component_id` null
on real output as unacceptable (the historical `Events.csv` always links multi-component
captures this way). See spec.md Clarifications (2026-07-30 entry) for the full evidence and
design. Also folds in two related fixes found in the same review: real `message_id` for the
6 migrated events (was previously spec'd null — REQ-MIGRATE-001 revised), and removal of
migration-script process commentary that had leaked into the `notes` field.

- [x] T028 Amend spec.md (REQ-DATA-003 narrowed, new REQ-DATA-004, REQ-MIGRATE-001 revised,
  new SC-006, Clarifications entry with the Events.csv evidence).
- [x] T029 Amend data-model.md (agreement_id/component_id/component_label population rules,
  new `agreement_label` internal field, migration appendix updated with real message_ids +
  agreement_label/component_label per component).
- [x] T030 Amend contracts/ledger-event-manager.md (`add_ledger_event` gains `agreement_id`
  param, new `build_agreement_id` method, migration-script contract revised).
- [x] T031 Extend `LEDGER_EVENT_TOOL` (`agreement_label`/`component_label`, both required
  per `strict: True`); implement `LedgerEventManager.build_agreement_id`/`_slugify`/
  agreement_id+component_id derivation; wire batch-level single-computation into
  `AIHandler._handle_ledger_event_capture`.
- [x] T032 Rewrite `migrate_stray_ledger_events.py`: real `message_id` per component
  (recovered from the session's own `messages/*.json` by content match), hand-written
  `agreement_label`/`component_label`, `notes` cleaned of migration/process commentary,
  patch the 3 source message files' `ledger_event_ids`.
- [x] T033 Update/extend unit tests: `test_ledger_event_manager.py` (new
  `TestAgreementAndComponentIds`, `TestReservedNullFields` narrowed),
  `test_ai_handler_ledger_events.py` (new batch-consistency test),
  `test_migrate_stray_ledger_events.py` (real message_id/agreement_id/component_id/notes
  assertions, message-file-patch assertions).
- [x] T034 Revert the incorrect first migration run (delete the 6 stray files under
  `dev_data/events/`) and re-run the corrected script for real against
  `dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5/` — verified: 3 גיליאן components
  share one `agreement_id`, 2 שרית components share a different one, מלכה's בנק event has
  both null, all 6 have real `message_id`, all 3 source message files patched.
- [x] T035 [P] Full verification: `pytest tests/` (623 passed), `pylint` (9.47/10, no new
  findings beyond pre-existing patterns), `mypy` (zero new errors in touched files).
- [ ] T036 👤 The 5 existing expensive tests already flagged at T018 for modification, plus
  any new data-model-correctness expensive tests, should additionally assert
  `agreement_id`/`component_id` behavior (REQ-DATA-004/SC-006) before their next run — not
  yet done, deferred to whenever T018-T025's expensive-test approval cycle happens.

---

## Phase 10 (Addendum, 2026-07-30): REQ-DATA-005 — `שעות_תאריך` (hours-work-date)

Requested directly by the user with 3 real hourly work-log examples, alongside scoping
Feature 032 (see `specs/in-progress/032-.../` — quoted-message/reply reference resolution for
agreement cancellations, split out as its own feature rather than folded into 033).

- [x] T037 Amend spec.md (new Clarifications entry with the 3 real examples, `REQ-DATA-005`,
  `REQ-DATA-003` column count 29→30, new `SC-007`).
- [x] T038 Amend data-model.md (`hours_date`/`שעות_תאריך` CSV-mapped row, column count 29→30,
  validation rule).
- [x] T039 Amend contracts/ledger-event-manager.md (`event` dict key count 18→19).
- [x] T040 Extend `LEDGER_EVENT_TOOL` with `hours_date` (ISO-8601, required non-null iff
  `hours` non-null); implement `LedgerEventManager._normalize_hours_date` (AI's ISO string →
  persisted `DD/MM/YYYY`, `None` + WARNING if unparseable when `hours` is set) and wire into
  `add_ledger_event`'s record dict.
- [x] T041 Update unit tests: `test_ledger_event_manager.py` (new `TestHoursDate`, 6 tests;
  `CSV_MAPPED_FIELDS`/`SAMPLE_EVENT` updated), `test_ai_handler_ledger_events.py`
  (`SAMPLE_EVENT` updated) — 110/110 green.
- [x] T042 Write 3 new expensive E2E tests using the user's exact real examples verbatim
  ("רן אורפני 4 שעות על היום"; "ענבר בן סימון תגובה לטיעון משלים אתמול 4 שעות היום 5 שעות";
  "רן אורפני דרך הראל על אתמול שעתיים על היום שעתיים") — asserts hours/client_name/
  payer_name/hours_date, hours_date computed at test-run time via real local
  Asia/Jerusalem "today"/"yesterday" (never hardcoded, since the model resolves relative
  dates against its own real injected current-date context, independent of any synthetic
  notification timestamp). Not yet run (no billing) — collection-verified only (16 deselected).
- [ ] T043 👤 **EXPENSIVE-TEST APPROVAL + RUN** (3 separate cycles): run T042's 3 new tests.

---

## Dependencies & Execution Order (TDD-Aware)

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories. All "a" tasks
  parallelizable; 👤 approval gate for each before its "b"; "b" tasks parallelizable after
  approval (different concerns within the same new file, but sequenced by the tool to
  avoid conflicting edits to `ledger_event_manager.py` in practice, even though marked [P]
  for conceptual independence).
- **User Stories (Phase 3-6)**: All depend on Phase 2. US1 (P1) and US2 (P1) can proceed in
  parallel once Phase 2 is done, but US2's implementation (T010b) also depends on T008b
  (both touch the same `add_message` call-site pattern) — sequenced, not parallel, in
  practice. US3 depends on US1 (extends the same code path). US4 (migration) depends only
  on Phase 2 (uses `LedgerEventManager` directly, independent of the handler wiring).
- **Expensive E2E Suite (Phase 7)**: Depends on Phases 2-6 all being implemented and
  passing their own (non-expensive) tests — no point spending real API calls to validate
  wiring that unit/component tests haven't already confirmed.
- **Polish (Phase 8)**: Depends on Phase 7.

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → **STOP, validate via
   quickstart.md US1** → this alone already fixes the core "not permanent" problem.

### Incremental Delivery

Phase 2 → US1 (MVP) → US2 → US3 → US4 (migration) → Expensive E2E Suite → Polish. Each checkpoint is independently
demonstrable; nothing later blocks anything earlier from already being correct and shipped
if the team wants to stop after any checkpoint.

## Notes

- [P] tasks touch different concerns; several land in the same new file
  (`ledger_event_manager.py`) so in solo (non-multi-agent) execution they're done
  sequentially in practice despite being conceptually parallel/independent.
- Every "a" task MUST be shown failing (no implementation yet) before its "b" task starts.
- Commit after each phase's checkpoint, not after every single task.
- T020/T021 are deliberately separated from every other gate in this file — modifying an
  approved test and re-running an expensive test are each their own standing project rule,
  not specific to this feature, and must never be bundled into a feature-level approval.
