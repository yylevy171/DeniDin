# Tasks: WhatsApp Interactive Buttons for the Approval Gate

**Status (2026-08-14)**: Implementation complete (T001-T008, T012-T014). Phase 5's manual
verification (T009-T011) is not yet done — it requires a real device/dev environment and is
explicitly a human-driven check, not something to run unattended.

**Input**: Design documents from `specs/in-progress/047-whatsapp-interactive-approval-buttons/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/pending-approval-message-binding.md`, `contracts/whatsapp-buttons-send.md`,
`contracts/button-tap-resolution.md`, `quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III (config-only, Israel local time, feature
branch workflow).

**Tests**: **No new automated tests for this feature**, by explicit user decision (2026-08-14,
same kind of scoped exception as Feature 048's) — see plan.md's Testing section. This is NOT the
usual Task A (tests) → human approval → Task B (implementation) split; tasks below implement
directly. In its place, a **hard requirement**: every existing test that exercises the approval
gate must keep passing with **no change to its logic or assertions** —
`tests/unit/test_ai_handler.py`'s pending-approval/`_resolve_pending_approval`/
`_is_affirmative_reply` tests, `tests/unit/test_whatsapp_handler.py`'s `send_response` tests, and
any integration test dispatching a real text-based approval reply. This feature is additive (a
new, parallel entry point) — if implementing it ever seems to require changing what one of those
tests asserts, that's a signal to stop and reconsider the approach, not to edit the test. The
full suite is run once at the end (Phase 6) as the acceptance check.

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

- [x] T001 Confirm `git branch --show-current` is
  `feature/047-whatsapp-interactive-approval-buttons` (already created). No new dependencies
  needed (research.md: `whatsapp_api_client_python`/`whatsapp_chatbot_python` already project
  dependencies, `sendInteractiveButtons` already exposed).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The data-model changes every later phase builds on. **No story-specific wiring
starts until this phase is complete.**

- [x] T002 Add `sent_message_id: Optional[str] = None` to `PendingApproval` and the
  module-level `BUTTON_ID_APPROVE = "denidin_approve"` / `BUTTON_ID_DECLINE = "denidin_decline"`
  constants, `apps/denidin-app/src/managers/pending_approval_manager.py`.
- [x] T003 Implement `attach_sent_message_id(self, chat_id: str, id_message: str) -> None` on
  `PendingApprovalManager`, same file. No-op (logged at `info`, `[022]`-prefixed matching
  `get`/`set`/`clear`'s existing style) if no pending approval currently exists for `chat_id` —
  never raises. Per contracts/pending-approval-message-binding.md.
- [x] T004 Add `offer_approval_buttons: bool = False` to `AIResponse`,
  `apps/denidin-app/src/models/message.py`.

**Checkpoint**: All three new pieces of state exist, unused by any behavior yet.

VC0-VC2 for this phase.

---

## Phase 3: User Story 1 — Approve a document with one tap (Priority: P1) 🎯 MVP

**Goal**: A pending approval is offered with real, tappable `"כן"`/`"לא"` buttons; tapping
either one resolves it exactly as the equivalent typed reply would, exactly once.

**Independent Test**: `quickstart.md` US1 (real WhatsApp device, real Morning sandbox document).

**Design note**: `resolve_button_tap`'s `stanza_id`-matching guard (data-model.md's state
diagram) is implemented here, as part of the same method, rather than deferred — it's the
precondition that decides whether approve/decline should run at all, not optional behavior
layered on top. This is also what delivers US3 (stale tap) and US2 (text path untouched) —
neither gets its own implementation task below; they're verified via `quickstart.md` and the
Phase 6 full-suite run.

- [x] T005 [US1] Implement the buttons-send branch in `send_response`,
  `apps/denidin-app/src/handlers/whatsapp_handler.py`: when `response.offer_approval_buttons` is
  `True`, call `notification.api.sending.sendInteractiveButtons(chatId=chat_id,
  body=response.response_text, buttons=[{"type": "reply", "buttonId": BUTTON_ID_APPROVE,
  "buttonText": "כן"}, {"type": "reply", "buttonId": BUTTON_ID_DECLINE, "buttonText": "לא"}])`
  instead of `notification.answer(...)`; return type becomes `Optional[str]` (the sent
  `idMessage`, or `None` for the unchanged plain-text/failure cases). On failure: log (same
  categorized pattern as existing HTTP-error handling), leave the pending approval in place
  uncleared, send a distinct plain-text error notice via `notification.answer(...)` (not the
  `📋 לאישור:` block) — per contracts/whatsapp-buttons-send.md's "surface an error, not a silent
  fallback" decision. When `offer_approval_buttons` is `False`: **byte-for-byte unchanged**
  existing behavior.
- [x] T006 [US1] Implement `resolve_button_tap(chat_id, selected_id, stanza_id, sender,
  recipient) -> Optional[AIResponse]` on `AIHandler`,
  `apps/denidin-app/src/handlers/ai_handler.py`. Looks up
  `pending = pending_approval_manager.get(chat_id)`; returns `None` immediately (US3: silent, no
  reply) if `pending is None` or `pending.sent_message_id != stanza_id`. Otherwise resolves via
  the same `_call_openai_approval_api`/duplicate-execution-guard logic
  `_resolve_pending_approval` already uses — reused, not duplicated — branching on
  `selected_id == BUTTON_ID_APPROVE` vs. anything else. Logs a `[047]`-prefixed audit line
  (`tool_name`/`selected_id`) distinguishing this from `_resolve_pending_approval`'s existing
  `[022]` text-resolution logging (spec.md Clarifications' audit requirement). Sets
  `AIResponse.offer_approval_buttons=True` at the existing `pending_approval_manager.set(...)`
  call site (~line 1591-1599) for every new pending approval. Per
  contracts/button-tap-resolution.md and contracts/pending-approval-message-binding.md.
  **Does not modify `_resolve_pending_approval` or `_is_affirmative_reply` in any way** — this
  is a fully separate method (US2's non-interference requirement).
- [x] T007 [US1] Register `@bot.router.message(type_message="interactiveButtonsResponse")` in
  `apps/denidin-app/denidin.py` (**not** `@bot.router.buttons(...)` — research.md's confirmed
  library gap: that decorator only matches the old deprecated button-reply types). Extracts
  `chat_id`/`selected_id`/`stanza_id` from `notification.event`, calls
  `ai_handler.resolve_button_tap(...)`; if the result is `None`, sends nothing at all (US3: no
  `send_response` call, no `notification.answer` call); otherwise passes the result to
  `whatsapp_handler.send_response(...)`. Also wires: after any turn's `send_response` call
  returns a non-`None` `idMessage`, calls
  `ai_handler.pending_approval_manager.attach_sent_message_id(chat_id, id_message)`.

**Checkpoint**: Tapping a live button approves/declines a real pending approval exactly once,
end to end. Verify via `quickstart.md` US1 (real device).

**✅ Verified live, 2026-08-14** (approve path only) — see `quickstart.md` US1. Real invoice
#52120 created, exactly once, via a real button tap; `sent_message_id`/`stanza_id` binding
confirmed working. Found and fixed one unrelated operational issue along the way (not a code
bug in this feature): `run_all.sh dev` recreated the container from a stale pre-047 image
without rebuilding — silently produced plain-text-only prompts with no buttons and no error.
Documented in `quickstart.md` Prerequisites so it isn't hit again. Decline path and Phase 4/5
scenarios (T009-T011) still pending live confirmation.

VC0-VC2 for this phase.

---

## Phase 4: User Story 4 — The question is still fully stated (Priority: P2)

**Goal**: Confirm the `📋 לאישור:` details block content is byte-for-byte unchanged — buttons
change delivery, never content.

**Independent Test**: `quickstart.md` US4.

- [x] T008 [US4] No implementation — `_build_pending_approval_details` (ai_handler.py ~283) has
  zero call-site or logic changes anywhere in this feature (its one existing call site,
  ai_handler.py ~1618, is untouched). This task exists only to record that the claim was
  checked, not assumed.

**Checkpoint**: Verify via `quickstart.md` US4 (real device) — read the button message body,
confirm it matches the pre-047 text-only prompt's content exactly.

VC0-VC2 for this phase (if T008 produced any change; otherwise folded into Phase 3's commit).

---

## Phase 5: Manual Verification

(Substitutes for the dedicated automated coverage the original TDD task pairs would have
provided.)

**Purpose**: US3 (stale tap) and US2 (text path untouched) have no dedicated implementation
task of their own — their behavior is delivered entirely by Phase 3 (T005-T007) and Phase 2
(T002-T004). This phase is where they're actually checked.

- [ ] T009 [US3] Manual check per `quickstart.md` US3, both scenarios: (1) tap a button on an
  already-resolved (via text) pending approval — confirm nothing observable happens; (2) trigger
  a pending approval, then trigger a second one before resolving the first (supersedes it in
  `PendingApprovalManager`), then tap the **first** message's button — confirm the *second*
  (current) pending approval is untouched, nothing observable happens. This second scenario is
  the specific correctness property `sent_message_id`/`stanza_id`-matching exists for.
- [ ] T010 [US2] Manual check per `quickstart.md` US2: with a pending approval showing buttons,
  ignore them and type `כן` (or `אישור`, `לאשר`, with/without a leading RTL mark) instead —
  confirm it resolves exactly as it did before this feature existed.
- [ ] T011 Manual check per `quickstart.md`'s Groups section: trigger and tap-resolve an
  approval in the project's test group — confirm the tap is attributed to the actual tapping
  member and resolves correctly.

VC0-VC2 for this phase (documentation-only — no code changes expected; if any bug is found and
fixed here, it lands in Phase 3's files, and that fix gets its own VC1-VC2).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T012 [P] Run `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and
  `python3 -m mypy src/ --config-file=mypy.ini` from `apps/denidin-app/` — fix any new findings
  introduced by this feature's changes (pre-existing findings elsewhere untouched).
- [x] T013 Run the full non-billed, non-expensive suite: `python3 -m pytest tests/ -v --tb=short`
  from `apps/denidin-app/`. **This is the acceptance check for the "no new tests" decision**:
  confirm 0 failures, and specifically confirm every existing approval-gate test
  (`test_ai_handler.py`'s pending-approval tests, `test_whatsapp_handler.py`'s `send_response`
  tests) passes with its assertions exactly as they were before this feature — if any of them
  needed to change to pass, stop and report rather than editing the test.
- [x] T014 Update `CLAUDE.md`'s Architecture section (`### Message flow` /
  `### Key components`): note the new `interactiveButtonsResponse` router case, the
  `PendingApproval.sent_message_id` binding, and that document approvals now have two entry
  points (typed reply, unchanged; button tap, new) into the same gate.

**Checkpoint**: All existing tests green and unmodified, lint/type-check clean, docs updated.
Ready for `haleluya`.

VC0-VC2 for this phase.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS Phase 3.
- **US1 (Phase 3)**: Depends on Phase 2. T005 (send path) and T006 (resolution logic) touch
  different files and could be done in either order; T007 (router wiring) depends on both.
- **US4 (Phase 4)**: Depends on Setup only — independent of Phases 2-3, confirmed untouched.
- **Manual Verification (Phase 5)**: Depends on Phase 3 (needs the real end-to-end mechanism
  working to check against).
- **Polish (Phase 6)**: Depends on Phase 3 (T012/T013 cover code Phase 3 introduces) and
  benefits from Phase 5 having already surfaced any real-device issues.

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → **STOP, validate via
   `quickstart.md` US1** — this alone delivers the core "approve with one tap" capability end
   to end.

### Full Delivery

Phase 2 → Phase 3 (US1, MVP) → Phase 5 (manual verification of US2/US3/groups) → Phase 4 (US4,
can run anytime in parallel) → Phase 6 (polish, full-suite acceptance check).

## Notes

- `PendingApproval.sent_message_id` (Phase 2) is the single piece of state every later phase
  depends on getting right — if it's ever wrong (attached to the wrong chat, or attached after a
  race clears the pending approval first), the failure mode is silent (a tap that should resolve
  does nothing, or a stale tap resolves the wrong thing). Phase 5's second scenario (T009) is
  exactly the check this risk calls for.
- No `tests/billed/`/`tests/expensive/` — confirmed in plan.md's Technical Context, nothing in
  this feature touches OpenAI content generation or vision.
- Close-out (moving this spec to `specs/done/`, updating `specs/ROADMAP.md`) is handled by the
  `haleluya` flow, not a task here.
