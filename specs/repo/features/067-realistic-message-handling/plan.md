# Implementation Plan: Realistic Message Handling — Conversation Without "Turns"

**Branch**: `feature/067-realistic-message-handling` | **Date**: 2026-10-12 | **Spec**: `./spec.md`
**Input**: `specs/repo/features/067-realistic-message-handling/spec.md` (revised 2026-10-11/12; Feature 090 folded in; acceptance scenarios A1–A8 approved 2026-10-12)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md**: no env vars; Israel-local time (`now_local()`) for every new timestamp; branch
  workflow; integration tests simulate a real entry point (a Green API webhook body); **no
  monkey-patching** (the producer split is a Template-Method change inside the existing
  `DeniDinGreenAPIBot` subclass plus a dependency-injected `IntakeCoordinator`); no
  `Lock`/`RLock`/`Semaphore`; the one `queue.Queue` is SessionManager's actor queue, explicitly
  approved 2026-10-12 (REQ-RMH-025/029); `pathlib`; no new dependency; bounded-retry
  rule §XVIII not touched (no new external handshake).
- **METHODOLOGY.md**: spec-first; the 2026-09-12 TDD redefinition — the approved `billed`/`expensive`
  scenarios (user-stories.md A1–A8) are the final acceptance pass, written and run once at the end;
  unit/integration tasks are RED→GREEN with approval gates; a `backbone.md` boundary section
  (REQ-RMH-026/027/028).
- **Feature flag**: none (product owner, 2026-10-12). Rollback = previous release.

---

## Summary

Today a message is handled start-to-finish on the polling thread; nothing is read from WhatsApp
while the model works (F1). This plan lets polling continue, queues what arrives per chat, and
**merges queued user messages into the model's input at every hand-back** (the points where the
model returns control: every round of the backbone's resolution loop). A reply that comes back
is sent as is; whatever is still queued is handled next. There is no turn boundary,
no reset, no end state: a single dispatcher keeps reacting to whatever is queued.

Backbone only. The legacy `AIHandler`, the replay player and `HANDLER_REGISTRY` are untouched.

## Technical Context

- **Language/Version**: Python 3.9 (app venv); **no new dependency**.
- **Storage**: no new durable state. In-memory bounded `queue.Queue`s, existing session files.
- **Testing**: unit + integration (`scripts/run_unit_integration_tests.sh`), `billed` A1–A7,
  `expensive` A8 (own approval). Never a bare `pytest`.
- **Threads**: poller (producer) + one dispatcher + the SessionManager actor (+ monitor/supervisor
  jobs on the existing scheduler). Shared state is limited to the bounded queues.
- **Unknowns**: none left as NEEDS CLARIFICATION; third-party behavior to confirm is listed as
  Gate Zero in `research.md` (V1, V2, V3-test, V6).

## Constitution Check

| Rule | Status |
|---|---|
| Zero-mock / real internal paths | Integration tests drive real webhook bodies through the real producer, coordinator, dispatcher and router; only Green API's HTTP is faked (external) |
| No env vars | ✅ none introduced |
| Israel local time | ✅ `now_local()`; timestamps formatted from stored message timestamps |
| No monkey-patching | ✅ subclass override already exists; coordinator injected via an attribute set at startup, like `on_notification_received` |
| Locks | ✅ only inside `queue.Queue`, one technology for both queues, human-approved 2026-10-12 (REQ-RMH-025/029) |
| Feature flag | ✅ none by human decision |
| Tests immutable once approved | ✅ new tests only |
| Player/registry unchanged | ✅ REQ-RMH-022; `HANDLER_REGISTRY` stays 8 types |
| New tool-bearing behavior needs constitution boundary | ✅ `backbone.md` section + cross-references (D10) |

Post-design re-check: ✅ no violations; no Complexity Tracking entries.

## Design (decisions D1–D14 are in `research.md`)

```
Green API queue
  └─ POLLER (producer)  DeniDinGreenAPIBot.run_forever
       receive → read-receipt hook → store via SessionManager (actor) → deleteNotification
              → intake.submit(body, stored_message)
  └─ SessionManager ACTOR  (own thread; ONE thread-safe queue for reads + writes; sole owner of session files)
  └─ IntakeCoordinator  (ONE bounded worker queue of (notification, stored message), in arrival order)
  └─ DISPATCHER (one thread; knows nothing about Green API)  DeniDinDispatcher.run
       next item (deferred first, then arrival order) → dispatch(type, notification)   # injected, same as the player's;
                                                          # handlers unchanged; DeniDin.receive() returns the pre-stored message
          → _process_conversational_message → Backbone.handle_message → _run_resolution_loop
               each round: run the model's tool calls
                           ├─ send_to_user / approval round  → return final text (sent as is)
                           └─ otherwise → drain_attachable(chat)  → (already stored) build user items
                                         → responses.create(input = outputs + pending items)
       reply sent; dispatcher loops: anything queued is simply handled next
       media items seen at a drain → noted, parked in the media backlog → dispatched after
```

### What changes where

| Area | Change |
|---|---|
| `src/managers/session_store.py` (new) / `session_manager.py` | today's `SessionManager` body becomes `SessionStore` (single-thread-only); `SessionManager` becomes the actor facade — same public signatures, one thread, one `queue.Queue`, `Future` results (D15) |
| `src/utils/green_api_bot.py` | `DeniDinGreenAPIBot.run_forever`: when `self.intake` is set → producer path (store → delete → submit); else today's code unchanged |
| `src/intake/intake_coordinator.py` (new) | `submit`, `drain_attachable(chat_id)`, `next_work_item()`, `park_media`, `has_work()`; classification (D5) |
| `src/intake/denidin_dispatcher.py` (new) | thread; calls only the injected `dispatch(type, notification)` — no Green API knowledge (REQ-RMH-032); log + sleep 5 + continue on error (REQ-RMH-024); media backlog dispatch |
| `src/sources/green_api_source.py` + `denidin.py` `__main__` | the source owns all Green API; builds each `Notification` from the event with the existing bot client; builds coordinator + dispatcher (given `dispatch`), attaches `bot.intake`, starts the dispatcher before the poll loop; `DeniDin.intake` for the AI side (None-guarded) |
| `DeniDin` (`denidin.py`) | `prestore(notification)` (poller: same content rules each handler uses today); `receive()` returns the pre-stored message instead of storing twice; `receive_pending(chat_id)` → stored messages + media notes |
| `src/utils/bounded_queue.py` (new) · `src/services/queue_monitor_service.py` (new) · `src/services/thread_supervisor.py` (new) · `/health` info | `BoundedQueue` (D16), `QueueMonitor`, `ThreadSupervisor` (D17); depths/limits/dropped/thread liveness in `/health`; config: queue limits, warning size, stall seconds, restart window (`config.example.json` + dev/prod) |
| Rename "turn" (REQ-RMH-030) | proposed: `handle_message`→`handle_message`, `mark_chat_busy`/`mark_chat_idle`→`mark_chat_busy`/`mark_chat_idle`, `_busy_chats`→`_busy_chats`, backbone `_turn_*`→descriptive per-message names; also `turn_context`, tests, prompts, docs (not `specs/done/`, release records, logs); final names settled in `tasks.md` |
| Existing docs (REQ-RMH-031) | `CLAUDE.md`, `.github/ARCHITECTURE.md`, `.github/*` mentions, app README/docs |
| `src/backbone/backbone.py` | `_run_resolution_loop`: drain at each non-final hand-back (off when `_turn_is_approved_write`, REQ-RMH-014); record `last_output_at`; D14 — stop clearing `approval_message_id` on unrelated messages |
| `src/backbone/pending_messages.py` (new) | format user items: timestamp + before/after marker; media note |
| `src/managers/session_manager.py` | opt-in timestamp prefix for the backbone's rolling window (D13); default off |
| `config/prompts/backbone.md` + cap prompts | "Messages that arrive while you work" section; finish a pending approval first (REQ-RMH-028); cross-references (D10) |
| Typing indicator | re-fired when a drain attaches (REQ-RMH-018) |
| Untouched | `AIHandler`, `MediaHandler`, `analyze_media`, `HANDLER_REGISTRY`, player, `capability_reset_service`, stale-tap matching rule |

### Requirement → design traceability

REQ-001/004 hand-back merge → D4 · 002 immediate first message → D1 (no window) · 003/005 persist
individually → D2/D4 · 006 per chat → D3 · 007/008 timestamps + before/after → D13 + contract ·
009/026/027/028 prompt → D10 · 010 no abort → D4 (rounds only) · 011 approvals → unchanged ·
012 side effects visible → chain (F7) · 013 reply as is → D4 · 014 → D7 · 015 no turn → D11 ·
016 → untouched · 017 → D14 · 018 → D9 · 019/019a/019b → D6 · 021 → D8 · 022 → D1 (no
coordinator on the player) · 023 → single dispatcher · 024 → dispatcher loop · 025 → D3.

## Project Structure

```text
specs/repo/features/067-realistic-message-handling/
├── spec.md · user-stories.md · plan.md (this) · research.md · data-model.md · quickstart.md
├── contracts/ intake-producer-dispatcher.md · hand-back-merge.md
└── tasks.md                      # next: speckit.tasks

apps/denidin-app/
├── src/intake/{__init__,intake_coordinator,denidin_dispatcher}.py        # new
├── src/backbone/{backbone,pending_messages}.py                      # edit / new
├── src/utils/green_api_bot.py · src/sources/green_api_source.py · denidin.py   # edit
├── src/managers/session_manager.py                                  # edit (opt-in timestamps)
├── config/prompts/backbone.md · capabilities/*.md                   # edit
└── tests/{unit,integration,billed,expensive}/…                      # per tasks.md
```

## Phases

- **Phase 0 — Gate Zero** (before building on third-party behavior; one `billed` probe, text only):
  V1, V2, V6. If V1 fails, D4 falls back to sending the pending messages as their own user
  message in a **separate** follow-up call after the tool outputs.
- **Phase 0b — SessionManager actor (D15)**: the data-integrity foundation; facade + store split,
  every existing caller unchanged; unit tests (serialization, exception propagation, timeout,
  shutdown), plus a stress test of concurrent writers proving no lost update.
- **Phase 0c — Queue safety (D16/D17)**: `BoundedQueue`, monitor, supervisor, `/health` fields, config; unit tests for limit-raise-and-drop, warning on size and stall, thread death → restart → health non-ok.
- **Phase 1 — Intake** (US stories 1,2,7): coordinator + producer + dispatcher; unit + integration.
- **Phase 2 — Hand-back merge** (US 1,2,3,5): drain, formatter, timestamps, typing indicator.
- **Phase 3 — Guards & approvals** (US 8,9): D7, D14; reply-as-is path.
- **Phase 4 — Media** (US 6): note + backlog + pre-received message.
- **Phase 5 — Prompts and docs** (REQ-026/027/028, REQ-031).
- **Phase 5b — Rename "turn"** (REQ-030): last, as one mechanical sweep, so it never muddies the behavior diffs.
- **Phase 6 — Acceptance**: write and run A1–A8 once (A8 `expensive`, own approval).

## Decisions from the plan review (product owner, 2026-10-12)

- D1–D14 approved; D2/D3/D8 revised and D15 added the same day (see `research.md`).
- Poller stores via `SessionManager`, then acknowledges, then enqueues; `SessionManager` is an
  actor with one thread-safe queue for reads and writes (approved `queue.Queue`).
- The dispatcher knows nothing about Green API: the message source hands it ready notifications; it calls only `dispatch`. Sends stay as today (shared bot client).
- Cancelling a pending approval: rely on the model.
- Rename every "turn" (code, tests, prompts, docs), except history and `specs/done/`; no umbrella noun, each thing named after what it does; update existing docs.

## Open items before `speckit.tasks`

None. (O3 closed 2026-10-12: rename per function, no umbrella noun; `specs/done/` untouched.)

## Complexity Tracking

None.
