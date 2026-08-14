# Tasks: WhatsApp Interactive Buttons for the Approval Gate

**Input**: Design documents from `specs/in-progress/047-whatsapp-interactive-approval-buttons/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/pending-approval-message-binding.md`, `contracts/whatsapp-buttons-send.md`,
`contracts/button-tap-resolution.md`, `quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III (config-only, Israel local time, feature
branch workflow) and METHODOLOGY.md §VI (TDD, human approval gates, tests IMMUTABLE once
approved).

**Tests**: TDD — every "a" task (tests) requires explicit human approval before its matching
"b" task (implementation) begins. Once approved, a test is immutable without a fresh, explicit
re-approval. Integration tests dispatch real webhook-shaped notifications through `bot.router`
(no `unittest.mock`), per CONSTITUTION §V. No `billed/`/`expensive/` tests needed — nothing in
this feature calls OpenAI or vision; the one new external call (`sendInteractiveButtons`) is a
real Green API send, already verified live during Gate Zero and exercised going forward the
same way every other Green API send in this app is (real dispatch through integration tests,
never mocked).

**Path Conventions**: Single project — `apps/denidin-app/src/`, `apps/denidin-app/denidin.py`,
`apps/denidin-app/tests/` (per `plan.md`'s Project Structure).

## Version Control steps (applied at the end of every phase below)

- **VC0**: Confirm `git branch --show-current` is `feature/047-whatsapp-interactive-approval-buttons`.
- **VC1**: `git add` only the files touched by that phase (never a broad `git add -A`).
- **VC2**: `git commit` with a conventional-commit message referencing the phase's US# ids.
- **VC3**: Push — **only when the user explicitly asks to push**.
- **VC4**: (end of feature only) Open PR — own explicit approval required.
- **VC5**: (end of feature only) Merge — own explicit approval required, never inferred from
  an earlier "yes" to something else (haleluya flow).

---

## Phase 1: Setup

- [ ] T001 Confirm `git branch --show-current` is
  `feature/047-whatsapp-interactive-approval-buttons` (already created). No new dependencies
  needed (research.md: `whatsapp_api_client_python`/`whatsapp_chatbot_python` already project
  dependencies, `sendInteractiveButtons`/`sending.sendInteractiveButtons` already exposed).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The data-model changes every later phase builds on — `PendingApproval`'s new
field, the manager's new method, `AIResponse`'s new field, and the two button-id constants.
**No story-specific wiring starts until this phase's tests are approved and implementation
passes.**

- [ ] T002a [P] Write tests for `PendingApproval.sent_message_id` and the new
  `BUTTON_ID_APPROVE`/`BUTTON_ID_DECLINE` constants in
  `tests/unit/test_pending_approval_manager.py`: a freshly-constructed `PendingApproval`
  defaults `sent_message_id=None`; constructing one with an explicit value round-trips
  correctly (plain field, no derived logic).
- [ ] T002b [P] Add `sent_message_id: Optional[str] = None` to `PendingApproval` and the
  module-level `BUTTON_ID_APPROVE = "denidin_approve"` / `BUTTON_ID_DECLINE = "denidin_decline"`
  constants, `apps/denidin-app/src/managers/pending_approval_manager.py` (BLOCKED until T002a
  approved).

- [ ] T003a [P] Write tests for `PendingApprovalManager.attach_sent_message_id` in
  `tests/unit/test_pending_approval_manager.py`: (1) a pending approval exists for `chat_id` →
  its `sent_message_id` is updated to the given value, `get(chat_id)` reflects it; (2) no
  pending approval exists for `chat_id` → no-op, does not raise, does not create one; (3) a
  *different* pending approval than expected is present (simulating the race
  contracts/pending-approval-message-binding.md describes) → still just updates whatever's
  currently there (the manager has no way to distinguish "expected" from "different" — this
  documents that limitation as accepted behavior, not a bug).
- [ ] T003b [P] Implement `attach_sent_message_id(self, chat_id: str, id_message: str) -> None`
  on `PendingApprovalManager`, same file (BLOCKED until T003a approved). Logs at `info`,
  `[022]`-prefixed, matching `get`/`set`/`clear`'s existing style.

- [ ] T004a [P] Write tests for `AIResponse.offer_approval_buttons` in
  `tests/unit/test_message.py` (co-located with `AIResponse`'s other field tests, matching this
  repo's existing convention): defaults `False`; constructing one with `offer_approval_buttons=True`
  round-trips; existing `__post_init__` invariant (`should_reply` + non-empty text) is
  unaffected by the new field's presence.
- [ ] T004b [P] Add `offer_approval_buttons: bool = False` to `AIResponse`,
  `apps/denidin-app/src/models/message.py` (BLOCKED until T004a approved).

**Checkpoint**: All three new pieces of state exist, independently tested, unused by any
behavior yet. Run `tests/unit/test_pending_approval_manager.py tests/unit/test_message.py -v`,
confirm all green before proceeding.

VC0-VC2 for this phase.

---

## Phase 3: User Story 1 — Approve a document with one tap (Priority: P1) 🎯 MVP

**Goal**: A pending approval is offered with real, tappable `"כן"`/`"לא"` buttons; tapping
either one resolves it exactly as the equivalent typed reply would, exactly once.

**Independent Test**: `quickstart.md` US1 (real WhatsApp device, real Morning sandbox document).

**Design note**: `resolve_button_tap`'s `stanza_id`-matching guard (data-model.md's state
diagram) is implemented here, as part of the same method, rather than deferred — it's not
optional behavior layered on top of approve/decline, it's the precondition that decides whether
approve/decline should run at all. Phase 4 (US3) adds dedicated tests proving this guard
specifically, on top of the coverage this phase already requires for its own correctness.

- [ ] T005a [P] [US1] Write tests for `WhatsAppHandler`'s buttons-send path in
  `tests/unit/test_whatsapp_handler.py`: `send_response` called with
  `response.offer_approval_buttons=True` → calls
  `notification.api.sending.sendInteractiveButtons` (not `notification.answer`) with
  `body=response.response_text` and exactly two buttons
  (`{"type": "reply", "buttonId": BUTTON_ID_APPROVE, "buttonText": "כן"}`,
  `{"type": "reply", "buttonId": BUTTON_ID_DECLINE, "buttonText": "לא"}`), and returns the sent
  `idMessage` on success; `offer_approval_buttons=False` → unchanged existing behavior
  (`notification.answer`, returns `None`) — regression guard.
- [ ] T005b [P] [US1] Implement the buttons-send branch in `send_response`,
  `apps/denidin-app/src/handlers/whatsapp_handler.py` — return type becomes `Optional[str]`
  (BLOCKED until T005a approved). Per contracts/whatsapp-buttons-send.md.

- [ ] T006a [P] [US1] Write tests for `AIHandler.resolve_button_tap`'s approve/decline paths in
  `tests/unit/test_ai_handler.py`: pending approval exists, `stanza_id` matches its
  `sent_message_id`, `selected_id=BUTTON_ID_APPROVE` → calls `_call_openai_approval_api` with
  `approve=True`, reuses the existing duplicate-execution guards, clears the pending approval,
  returns a real `AIResponse`; same setup with `selected_id=BUTTON_ID_DECLINE` → `approve=False`,
  clears, returns a real `AIResponse` (decline confirmation). Reuses/extends the same fixtures
  `_resolve_pending_approval`'s existing tests already use for the OpenAI-call boundary.
- [ ] T006b [P] [US1] Implement `resolve_button_tap(chat_id, selected_id, stanza_id, sender,
  recipient)` on `AIHandler`, `apps/denidin-app/src/handlers/ai_handler.py` (BLOCKED until
  T006a approved). Sets `AIResponse.offer_approval_buttons=True` at the existing
  `pending_approval_manager.set(...)` call site (~line 1591-1599) for every new pending
  approval. Per contracts/button-tap-resolution.md and contracts/pending-approval-message-binding.md.

- [ ] T007a [US1] Write an integration test in
  `tests/integration/test_button_tap_routing.py` (new file): a real webhook-shaped
  `interactiveButtonsResponse` notification (same shape as
  `gate-zero-captured-notifications.json`, `selected_id=BUTTON_ID_APPROVE`, `stanza_id` matching
  a pending approval's `sent_message_id` set up beforehand) dispatched through `bot.router` →
  the approved tool executes exactly once, the pending approval is cleared, a confirmation is
  sent. Repeat with `selected_id=BUTTON_ID_DECLINE` → nothing executes, decline confirmation
  sent, pending approval cleared. True integration (real `bot.router.route_event`, real
  `AIHandler`/`WhatsAppHandler`/`PendingApprovalManager` objects, no `unittest.mock`), per
  CONSTITUTION §V.
- [ ] T007b [US1] Register `@bot.router.message(type_message="interactiveButtonsResponse")` in
  `apps/denidin-app/denidin.py` (**not** `@bot.router.buttons(...)` — research.md's confirmed
  library gap). Extracts `chat_id`/`selected_id`/`stanza_id` from `notification.event`, calls
  `ai_handler.resolve_button_tap(...)`; if result is `None`, sends nothing (Phase 4 covers this
  branch's own dedicated tests); otherwise passes the result to
  `whatsapp_handler.send_response(...)`. Also wires: after any turn's `send_response` call
  returns a non-`None` `idMessage`, calls
  `ai_handler.pending_approval_manager.attach_sent_message_id(chat_id, id_message)` (BLOCKED
  until T007a approved).

**Checkpoint**: Tapping a live button approves/declines a real pending approval exactly once,
end to end. Run
`tests/unit/test_whatsapp_handler.py tests/unit/test_ai_handler.py tests/integration/test_button_tap_routing.py -v`,
confirm all green. Verify via `quickstart.md` US1 (real device).

VC0-VC2 for this phase.

---

## Phase 4: User Story 3 — A stale tap does nothing observable (Priority: P1)

**Goal**: Dedicated proof that the `stanza_id`-matching guard implemented in Phase 3 actually
blocks the two concrete stale scenarios spec.md calls out: no pending approval at all, and a
pending approval that's been *superseded* by a newer one (the scenario a naive "any pending
approval exists" check would get wrong).

**Independent Test**: `quickstart.md` US3, both scenarios (simple stale tap, and the
supersession case).

- [ ] T008a [US3] Write tests for the stale-tap guard in `tests/unit/test_ai_handler.py`:
  (1) no pending approval exists for `chat_id` → `resolve_button_tap` returns `None`, no OpenAI
  call made; (2) a pending approval exists but `sent_message_id != stanza_id` (simulating a tap
  on a since-superseded message — set up a pending approval, overwrite it with a second `set()`
  call carrying a different `sent_message_id`, then tap with the *first* message's `stanza_id`)
  → returns `None`, no OpenAI call made, the *second* (current) pending approval is left
  completely untouched (not cleared, not resolved) — the specific correctness property
  data-model.md's state diagram exists for.
- [ ] T008b [US3] No new implementation — the guard is already delivered by T006b
  (`resolve_button_tap`'s `stanza_id`-match check). This task exists to record that Phase 3's
  implementation is what T008a's tests exercise, not to duplicate it (BLOCKED until T008a
  approved, same as any other pairing — approval gates the test, not a no-op implementation
  step).
- [ ] T009a [US3] Write an integration test in `tests/integration/test_button_tap_routing.py`:
  a real `interactiveButtonsResponse` notification whose `stanza_id` does not match any current
  pending approval's `sent_message_id`, dispatched through `bot.router` → no reply sent (assert
  `WhatsAppHandler.send_response`/`notification.answer` never called), no tool executes, no
  state change.
- [ ] T009b [US3] No new implementation — same as T008b, delivered by T007b's `None`-handling
  branch (send nothing). (BLOCKED until T009a approved.)

**Checkpoint**: Both stale-tap scenarios from spec.md US3 are proven, not just assumed from
Phase 3's own passing tests. Run
`tests/unit/test_ai_handler.py tests/integration/test_button_tap_routing.py -v`, confirm all
green. Verify via `quickstart.md` US3 (both scenarios, real device).

VC0-VC2 for this phase.

---

## Phase 5: User Story 2 — Typing still works, always (Priority: P1)

**Goal**: Regression guard — the existing free-text approval path (`_resolve_pending_approval`,
`_is_affirmative_reply`) is completely unaffected by this feature, including when a tap and a
typed reply could plausibly race.

**Independent Test**: `quickstart.md` US2.

**Design note**: No code in this feature modifies `_resolve_pending_approval` or
`_is_affirmative_reply` at all (per contracts/button-tap-resolution.md, `resolve_button_tap` is
a fully separate entry point). The regression risk isn't "did we break the text path" in the
literal sense — it's "does the *new* path ever interfere with it." That's what's tested here.

- [ ] T010a [US2] Write a test in `tests/unit/test_ai_handler.py`: existing
  `_resolve_pending_approval`/`_is_affirmative_reply` behavior (already covered by pre-existing
  tests) is exercised once more here specifically to confirm it still passes unmodified after
  T002b/T006b's changes — a straightforward regression assertion, not new logic. Additionally: a
  pending approval resolved via `resolve_button_tap` (Phase 3) is fully cleared before any
  further tap or text reply could act on it — i.e. resolving it once, by either path, leaves
  nothing for the other path to accidentally also resolve.
- [ ] T010b [US2] No implementation — regression-only, nothing to change (BLOCKED until T010a
  approved).

**Checkpoint**: Run the full existing `_resolve_pending_approval` test suite plus T010a, confirm
no regressions. Verify via `quickstart.md` US2 (real device, ignore the buttons, type `כן`).

VC0-VC2 for this phase.

---

## Phase 6: User Story 4 — The question is still fully stated (Priority: P2)

**Goal**: Confirm the `📋 לאישור:` details block content is byte-for-byte unchanged by this
feature — buttons change delivery, never content.

**Independent Test**: `quickstart.md` US4.

**Design note**: `_build_pending_approval_details` (ai_handler.py ~283) is not touched by any
task in this feature — `response.response_text` (which becomes the buttons message `body`,
T005b) is built exactly as it is today. There is no new code here to unit-test; this is a pure
non-regression claim, verified by inspection (this function has zero call-site changes in this
feature) plus a manual check.

- [ ] T011a [US4] No new test — `_build_pending_approval_details` has no call-site or
  implementation changes in this feature (confirmed: grep for its call sites shows only the
  existing one at ai_handler.py ~1618, untouched). Nothing new to unit-test.
- [ ] T011b [US4] No implementation — nothing to change.

**Checkpoint**: Verify via `quickstart.md` US4 (real device) — read the button message body,
confirm it matches the pre-047 text-only prompt's content exactly.

VC0-VC2 for this phase.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The two clarified behaviors that don't map cleanly to a single user story (audit
logging, send-failure handling), plus repo-wide checks.

- [ ] T012a [P] Write a test in `tests/unit/test_ai_handler.py`: resolving a pending approval
  via `resolve_button_tap` produces a distinguishable `[047]`-prefixed log line (e.g. via
  `caplog`) noting `tool_name`/`selected_id`, separate from `_resolve_pending_approval`'s
  existing `[022]` text-resolution logging — the audit-trail clarify decision (spec.md
  Clarifications).
- [ ] T012b [P] Add the `[047]`-prefixed audit log line to `resolve_button_tap`,
  `apps/denidin-app/src/handlers/ai_handler.py` (BLOCKED until T012a approved).

- [ ] T013a [P] Write tests for the send-failure path in `tests/unit/test_whatsapp_handler.py`:
  `sendInteractiveButtons` raises → `send_response` logs the failure (same categorized pattern
  as existing HTTP-error handling), does **not** raise past the boundary uncaught in a way that
  skips the error notice, sends a distinct plain-text error message via `notification.answer`
  (not the `📋 לאישור:` block), and returns `None` (no `idMessage` to attach) — per
  contracts/whatsapp-buttons-send.md's "surface an error, not a silent fallback" decision.
- [ ] T013b [P] Implement the failure branch, same file (BLOCKED until T013a approved).

- [ ] T014 [P] Run `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and
  `python3 -m mypy src/ --config-file=mypy.ini` from `apps/denidin-app/` — fix any new findings
  introduced by this feature's changes (pre-existing findings elsewhere untouched).
- [ ] T015 [P] Run the full non-billed, non-expensive suite:
  `python3 -m pytest tests/ -v --tb=short` from `apps/denidin-app/` — confirm 0 failures, 0
  regressions.
- [ ] T016 Update `CLAUDE.md`'s Architecture section (`### Message flow` /
  `### Key components`): note the new `interactiveButtonsResponse` router case, the
  `PendingApproval.sent_message_id` binding, and that document approvals now have two entry
  points (typed reply, unchanged; button tap, new) into the same gate.

**Checkpoint**: All tests green, lint/type-check clean, docs updated. Ready for `haleluya`.

VC0-VC2 for this phase.

---

## Dependencies & Execution Order (TDD-Aware)

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories — `sent_message_id`,
  `attach_sent_message_id`, and `offer_approval_buttons` are prerequisites for every later
  phase. T002/T003/T004 pairs are independent of each other (different files/concerns),
  parallelizable.
- **US1 (Phase 3)**: Depends on Phase 2. T005 (send path) and T006 (resolution logic) touch
  different files and are independent of each other; T007 (router wiring) depends on both.
- **US3 (Phase 4)**: Depends on Phase 3 (tests the guard Phase 3 already implements — no new
  implementation, test-only phase).
- **US2 (Phase 5)**: Depends on Phase 3 (regression-checks the new path doesn't interfere with
  the pre-existing one).
- **US4 (Phase 6)**: Depends on Setup only — independent of Phases 2-5 (different code path
  entirely, and confirmed untouched). Could run in parallel with any of them in practice.
- **Polish (Phase 7)**: Depends on Phase 3 (T012/T013 extend code Phase 3 introduces).

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → **STOP, validate via
   `quickstart.md` US1** — this alone delivers the core "approve with one tap" capability end
   to end, including the staleness guard's basic no-pending-approval case (T006a/T007a's setup
   incidentally covers it, even though Phase 4 is what dedicates tests to it specifically).

### Incremental Delivery

Phase 2 (Foundational) → US1 (MVP) → US3 (stale-tap proof) → US2 (regression) → US4 (regression,
can run in parallel with any of the above) → Polish. Each checkpoint is independently
demonstrable via its `quickstart.md` section.

## Notes

- `PendingApproval.sent_message_id` (Phase 2) is the single piece of state every later phase
  depends on getting right — if it's ever wrong (e.g. attached to the wrong chat, or attached
  after a race clears the pending approval first), the failure mode is silent (a tap that should
  resolve does nothing, or — worse — a stale tap resolves the wrong thing). This is exactly why
  Phase 4 exists as its own dedicated phase rather than being folded silently into Phase 3's own
  passing tests.
- No `tests/billed/`/`tests/expensive/` additions — confirmed in plan.md's Technical Context,
  nothing in this feature touches OpenAI content generation or vision; the model's own
  `📋 לאישור:` text generation (Feature 022) is completely unchanged.
- Close-out (moving this spec to `specs/done/`, updating `specs/ROADMAP.md`) is handled by the
  `haleluya` flow, not a task here.
