# Implementation Plan: WhatsApp Typing Indicator While Processing — Feature 048

**Feature**: 048-whatsapp-typing-indicator
**Branch**: `feature/048-whatsapp-typing-indicator`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md`
**Status**: DONE — merged to master (2026-08-13). Single-call design (final) after a renewal-loop
attempt was tried, found buggy, and reverted same day — see spec.md Q1.
**Updated**: 2026-08-13

**Compliance**: CONSTITUTION.md (§I no env vars — reuses existing Green API credentials
already in config; §II Israel local time — N/A, no timestamps added; §III git workflow; §V
real-external-call, zero-mocking — `sendTyping` is a real Green API call, confirmed via the
installed client library + Green API's own docs (spec.md Q0); §XVII no monkey-patching).
**No feature flag** (explicit user call, 2026-08-13, same reasoning as feature 045): small,
low-risk, easily-revertable, purely cosmetic, best-effort/log-only failure mode — no
gradual-rollout or kill-switch need that would justify one. Always on once merged.
**No automated tests** (explicit user decision, 2026-08-13): this feature ships without a
`tests/unit/`or `tests/billed/` addition — see "Testing" below for what replaces it.

---

## Summary

All open questions resolved during `speckit.clarify` (see spec.md). **Deliverable**: call
`bot.api.serviceMethods.sendTyping(chat_id, typingTime=20000)` once, at the start of processing
a conversational turn in `_process_conversational_message` (`denidin.py`), for every non-blocked
sender. No resend/renewal loop (v1 limitation, accepted). No explicit "stop typing" call —
DeniDin sending its own next message is what ends the turn; nothing further to do once the
reply is sent. Best-effort: failures are logged only, never block the rest of the flow, never
retried.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new — `bot.api.serviceMethods.sendTyping` is already available
  via the existing `whatsapp-chatbot-python`/`whatsapp_api_client_python` dependency (same
  family feature 045 used for `bot.api.marking.readChat`).
- **Storage**: N/A — no new persisted state.
- **Testing**: **explicitly skipped for this feature**, by user decision. No `tests/unit/`
  decision-logic test, no `tests/billed/` real-API test. In place of automated coverage: a
  one-time manual live check (send a real message to DeniDin's dev number, confirm the typing
  indicator appears) before merging, functionally the same confirmation feature 045 did during
  `speckit.clarify` for `readChat`, just performed here during implementation instead of a
  dedicated test file. This is a deliberate, scoped exception — not a precedent for skipping
  tests on other features.
- **Target Platform**: N/A — no container/runtime change beyond the code change itself (existing
  rebuild-on-merge process applies, per "Merging a code fix does not redeploy it").
- **Constraints**: must fire *after* `message` is parsed (needs `message.chat_id`) but *before*
  the OpenAI call (`ai_handler.get_response`) — unlike feature 045's read receipt, which
  deliberately fires earlier, before RBAC/session resolution, at the raw-notification-body
  hook. This one belongs inside `_process_conversational_message` itself, not
  `on_notification_received`.
- **Scale/Scope**: one new call site (`denidin.py`'s `_process_conversational_message`), one new
  small helper function (co-located with `mark_message_read` in
  `src/utils/green_api_bot.py`, same file already owning these small Green-API side-effect
  helpers). No new test files.

## Constitution Check

- **No env vars** — PASS: reuses existing `green_api_instance_id`/`green_api_token` config.
- **Israel local time** — N/A, no timestamps added.
- **Feature branch** — PASS: `feature/048-whatsapp-typing-indicator`.
- **Feature flags** — N/A by explicit user decision (2026-08-13): same reasoning as 045.
- **Real-sandbox/zero-mocking (§V)** — PASS in spirit: `sendTyping` is a real Green API call
  (spec.md Q0), never mocked. No automated test means no mock to worry about avoiding, by
  explicit user decision (see Testing above) — not a §V violation, since §V governs how *tests*
  must be written, and this feature deliberately has none.
- **No monkey-patching** — PASS: new call site + new helper function, no runtime patching.
- **Friendly errors (§X)** — PASS: failures are logged only (cosmetic, non-blocking), no
  user-facing error message needed since nothing about the rest of the flow changes.

## Project Structure

```text
specs/in-progress/048-whatsapp-typing-indicator/
├── spec.md          # done — CLARIFIED
├── user-stories.md  # done — CLARIFIED
├── plan.md          # this file
└── tasks.md         # next — /speckit.tasks (no test tasks, per user decision)
```
(No `research.md` — the design-relevant open question (Q1, resend cadence) was resolved by
explicit user decision during `speckit.clarify`, not deferred to a research phase. No
`data-model.md`/`contracts/` — no new entities or external contracts beyond the already-existing,
already-confirmed `sendTyping` call shape. No `quickstart.md` — no new user-facing setup steps,
no config to touch, nothing to enable.)

### Source Code

```text
apps/denidin-app/src/utils/green_api_bot.py
  # + TypingIndicatorRenewer class (revised 2026-08-13 from an earlier one-shot
  #   send_typing_indicator function, after live testing showed the single-call design
  #   visibly lapsing after 20s on longer turns). Mirrors SessionCleanupThread's
  #   threading.Thread(daemon=True) shape, but uses threading.Event for responsive
  #   stop() rather than a plain sleep loop. start() fires sendTyping immediately and
  #   every RESEND_INTERVAL_SECONDS=15 thereafter; stop() signals the event and joins
  #   the thread; the loop hard-stops at MAX_DURATION_SECONDS=180 regardless. Exceptions
  #   on each sendTyping call are caught, logged as a warning, never propagated.

apps/denidin-app/denidin.py
  # _process_conversational_message: after message parsing and the blocked-status
  #   lookup (ai_handler.user_manager.get_user(message.sender_id).is_blocked, same
  #   pattern as the existing _on_notification_received closure), construct and
  #   .start() a TypingIndicatorRenewer(bot, message.chat_id) if not blocked. Wraps
  #   `ai_response = denidin_app.ai_handler.get_response(...)` in try/finally, calling
  #   .stop() in the finally block — so it stops reliably whether the turn succeeds or
  #   raises, right before DeniDin's reply is sent (spec.md Q4).
```

## Phased Execution

### Phase 1 — Implementation
Add `send_typing_indicator` to `green_api_bot.py`, wire the single call site into
`_process_conversational_message`. No test-writing phase (explicit user decision) — implement
directly.

### Phase 2 — Manual live confirmation
Send a real message to DeniDin's dev WhatsApp number, observe (on a real device) that the typing
indicator appears while DeniDin processes and disappears once the reply lands. This is the
substitute for feature 045's live-verified automated test — a one-time manual check performed
before merge, not repeated per-PR.

### Phase 3 — Close out
Move spec to `specs/done/` once merged.

## Complexity Tracking

No Constitution Check violations requiring justification. The no-tests decision is an explicit,
scoped user call documented above, not a constitutional exception to justify.
