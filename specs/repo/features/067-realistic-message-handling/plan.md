# Implementation Plan: Realistic Message Handling — Conversation Without "Turns"

**Branch**: `feature/067-realistic-message-handling` | **Date**: 2026-10-12 | **Spec**: `./spec.md`
**Input**: `specs/repo/features/067-realistic-message-handling/spec.md` (revised 2026-10-11/12; Feature 090 folded in; acceptance scenarios A1–A8 approved 2026-10-12)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md**: no env vars; Israel-local time (`now_local()`) for every new timestamp; branch
  workflow; integration tests simulate a real entry point (a Green API webhook body); **no
  monkey-patching** (the producer split is a Template-Method change inside the existing
  `DeniDinGreenAPIBot` subclass plus a dependency-injected `IntakeCoordinator`); no
  `Lock`/`RLock`/`Semaphore`/`queue.Queue` (REQ-RMH-025); `pathlib`; no new dependency; bounded-retry
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
is sent as is; whatever is still queued becomes the next exchange. There is no turn boundary,
no reset, no end state: a single worker keeps reacting to whatever is queued.

Backbone only. The legacy `AIHandler`, the replay player and `HANDLER_REGISTRY` are untouched.

## Technical Context

- **Language/Version**: Python 3.9 (app venv); **no new dependency**.
- **Storage**: no new durable state. In-memory per-chat deques (lock-free), existing session files.
- **Testing**: unit + integration (`scripts/run_unit_integration_tests.sh`), `billed` A1–A7,
  `expensive` A8 (own approval). Never a bare `pytest`.
- **Threads**: poller (producer) + one worker. Shared state is limited to the per-chat deques, the
  arrival deque and one `threading.Event`.
- **Unknowns**: none left as NEEDS CLARIFICATION; third-party behavior to confirm is listed as
  Gate Zero in `research.md` (V1, V2, V3-test, V6).

## Constitution Check

| Rule | Status |
|---|---|
| Zero-mock / real internal paths | Integration tests drive real webhook bodies through the real producer, coordinator, worker and router; only Green API's HTTP is faked (external) |
| No env vars | ✅ none introduced |
| Israel local time | ✅ `now_local()`; timestamps formatted from stored message timestamps |
| No monkey-patching | ✅ subclass override already exists; coordinator injected via an attribute set at startup, like `on_notification_received` |
| No locks / queue.Queue | ✅ deque + Event (REQ-RMH-025); residual risks in research.md R1–R5 |
| Feature flag | ✅ none by human decision |
| Tests immutable once approved | ✅ new tests only |
| Player/registry unchanged | ✅ REQ-RMH-022; `HANDLER_REGISTRY` stays 8 types |
| New tool-bearing behavior needs constitution boundary | ✅ `backbone.md` section + cross-references (D10) |

Post-design re-check: ✅ no violations; no Complexity Tracking entries.

## Design (decisions D1–D14 are in `research.md`)

```
Green API queue
  └─ POLLER (producer)  DeniDinGreenAPIBot.run_forever
       receive → read-receipt hook → intake.submit(body) → deleteNotification (immediately)
  └─ IntakeCoordinator  (per-chat deque of raw bodies + global arrival deque + wake Event)
  └─ WORKER (one thread)  IntakeWorker.run
       next body (deferred first, then arrival order) → router.route_event(body)   # unchanged handlers
          → _process_conversational_message → Backbone.single_turn → _run_resolution_loop
               each round: run the model's tool calls
                           ├─ send_to_user / approval round  → return final text (sent as is)
                           └─ otherwise → drain_attachable(chat)  → receive() each → build user items
                                         → responses.create(input = outputs + pending items)
       reply sent; worker loops: anything queued is simply the next exchange
       media bodies seen at a drain → stored, noted, parked in the media backlog → dispatched after
```

### What changes where

| Area | Change |
|---|---|
| `src/utils/green_api_bot.py` | `DeniDinGreenAPIBot.run_forever`: when `self.intake` is set → producer path (submit + immediate delete); else today's code unchanged |
| `src/intake/intake_coordinator.py` (new) | `submit`, `drain_attachable(chat_id)`, `next_work_item()`, `park_media`, `has_work()`; classification (D5) |
| `src/intake/intake_worker.py` (new) | thread; `route_event` per item; log + sleep 5 + continue on error (REQ-RMH-024); media backlog dispatch |
| `src/sources/green_api_source.py` + `denidin.py` `__main__` | build coordinator + worker, attach `bot.intake`, start worker before the poll loop; `DeniDin.intake` for the AI side (None-guarded) |
| `DeniDin` (`denidin.py`) | `receive_pending(chat_id)` → list of received `WhatsAppMessage` + media notes; `receive` made reusable for a pre-received media message |
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
coordinator on the player) · 023 → single worker · 024 → worker loop · 025 → D3.

## Project Structure

```text
specs/repo/features/067-realistic-message-handling/
├── spec.md · user-stories.md · plan.md (this) · research.md · data-model.md · quickstart.md
├── contracts/ intake-producer-worker.md · hand-back-merge.md
└── tasks.md                      # next: speckit.tasks

apps/denidin-app/
├── src/intake/{__init__,intake_coordinator,intake_worker}.py        # new
├── src/backbone/{backbone,pending_messages}.py                      # edit / new
├── src/utils/green_api_bot.py · src/sources/green_api_source.py · denidin.py   # edit
├── src/managers/session_manager.py                                  # edit (opt-in timestamps)
├── config/prompts/backbone.md · capabilities/*.md                   # edit
└── tests/{unit,integration,billed,expensive}/…                      # per tasks.md
```

## Phases

- **Phase 0 — Gate Zero** (before building on third-party behavior; one `billed` probe, text only):
  V1, V2, V6, plus the V3 concurrency test. If V1 fails, D4 falls back to sending the pending
  messages as their own user message in a **separate** follow-up call after the tool outputs.
- **Phase 1 — Intake** (US stories 1,2,7): coordinator + producer + worker; unit + integration.
- **Phase 2 — Hand-back merge** (US 1,2,3,5): drain, formatter, timestamps, typing indicator.
- **Phase 3 — Guards & approvals** (US 8,9): D7, D14; reply-as-is path.
- **Phase 4 — Media** (US 6): note + backlog + pre-received message.
- **Phase 5 — Prompts** (REQ-026/027/028).
- **Phase 6 — Acceptance**: write and run A1–A8 once (A8 `expensive`, own approval).

## Decisions from the plan review (product owner, 2026-10-12)

- D1–D14 approved as written.
- **Q1 resolved:** cancelling a pending approval — **rely on the model**; no invalidation tool. The
  buttons stay live until answered or replaced.
- **Q2 resolved:** **rename every reference to "turn"** — in code, tests, prompts and docs — except
  history (git history, persisted data and logs). Naming scheme and scope: see the open items below.
- **Existing documentation must be adjusted** to the new model (`CLAUDE.md`, `.github/ARCHITECTURE.md`,
  `apps/denidin-app/README.md`/docs, `config/prompts/*` wording): a docs task in `tasks.md`.

## Open items before `speckit.tasks`

- **O1** Where inbound messages are stored relative to the queue (finding 2): store in the poller,
  or spool a raw file in the poller and store on the worker — see the discussion in the chat/
  research D2. *Pending decision.*
- **O2** The worker must not use the poller's HTTP session (finding 3): give the worker its own
  Green API client. *Pending confirmation.*
- **O3** The "turn" rename: replacement vocabulary and exact scope. *Pending decision.*

## Complexity Tracking

None.
