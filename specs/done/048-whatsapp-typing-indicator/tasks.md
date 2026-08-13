# Tasks: WhatsApp Typing Indicator While Processing — Feature 048

**Feature**: 048-whatsapp-typing-indicator
**Input**: `plan.md`, `spec.md`, `user-stories.md` (all CLARIFIED/ready)
**Status**: DONE — merged to master (PR #217, 2026-08-13). **No test tasks**, by explicit user decision
(see plan.md's "Testing" note). This is a deliberate, scoped exception to the usual
Task A (tests) → approval → Task B (implementation) split — not a precedent.

---

## Task 1 — Add `TypingIndicatorRenewer` (DONE, revised 2026-08-13)

**File**: `apps/denidin-app/src/utils/green_api_bot.py`

Shipped initially as a one-shot `send_typing_indicator` helper; live testing (see spec.md Q1)
showed the single 20s call visibly lapsing on longer turns, so it was revised same day to a
background renewal class, mirroring `SessionCleanupThread`'s `threading.Thread(daemon=True)`
shape but using `threading.Event` for responsive `stop()`: fires `sendTyping` immediately and
every 15s thereafter, hard-capped at 180s, exceptions caught/logged/never propagated.

## Task 2 — Wire the call site into `_process_conversational_message` (DONE, revised 2026-08-13)

**File**: `apps/denidin-app/denidin.py`

Constructs and `.start()`s a `TypingIndicatorRenewer(bot, message.chat_id)` (if not blocked)
after message parsing, then wraps `ai_response = denidin_app.ai_handler.get_response(...)` in
try/finally, calling `.stop()` in the finally block — so it stops reliably whether the turn
succeeds or raises, right before DeniDin's reply is sent (spec.md Q4). Fires on every
conversational turn uniformly, including a user's "yes"/"no" reply to a pending approval
(user-stories.md US1 scenario 4) — no special-casing needed, it's the same entry point.

## Task 3 — Manual live confirmation (substitutes for automated tests)

**Round 1 (DONE, 2026-08-13)**: single-call design confirmed working, but indicator visibly
lapsed after 20s — this is what triggered the Q1 revision to a renewal loop (Task 1/2 above).

**Round 2 (pending)**: re-confirm against the revised renewal-loop design on a real device:
- Typing dots appear shortly after sending, and stay continuously visible (no 20s lapse) on a
  turn that runs longer than 20 seconds.
- Dots disappear once DeniDin's reply arrives (within ~15s of the reply being sent).
- (If convenient to trigger) send an approval-gated request, confirm dots reappear after
  answering "yes"/"no" and stop once the confirmation message lands.

Not a formal test file — a pre-merge check, per plan.md's explicit no-tests decision.

## Task 4 — Close out

Once merged: move `specs/in-progress/048-whatsapp-typing-indicator/` to `specs/done/`, update
its spec.md Status line and the `specs/ROADMAP.md` entry from 🔄 to ✅ — handled by the
`haleluya` flow, not done separately here.
