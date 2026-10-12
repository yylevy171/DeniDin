# Research: Realistic Message Handling — Conversation Without "Turns"

**Date**: 2026-10-12 | **Spec**: `./spec.md` | **Plan**: `./plan.md`

Findings are from the code as of 2026-10-12 (master `1ebbe55a` merged). Anything about a
third-party system (OpenAI, Green API) that has not been seen in a real response is listed under
"Verification items" and is **not** assumed (CONSTITUTION: no unverified third-party assumptions).
Nothing was run during planning.

---

## Facts established from the code

| # | Fact | Where |
|---|------|-------|
| F1 | The live loop is serial: `run_forever` polls one notification, runs the hook, calls `router.route_event(body)` (which runs the whole handler **synchronously on the polling thread**), then `deleteNotification`. While a message is handled, nothing is polled. | `src/utils/green_api_bot.py` `DeniDinGreenAPIBot.run_forever` |
| F2 | A message is stored the moment it is received (`DeniDin.receive` → `store_inbound`), before any AI work. Each message is its own file; `SessionManager.add_message` also updates `session.json` (message ids, counters) — shared state. | `denidin.py:393`, `src/managers/session_manager.py:383` |
| F3 | The reply is sent **after** `single_turn` returns. `send_to_user` / `approval_with_yes_no_buttons` end the resolution loop and hand back the final text; `_process_conversational_message` then sends it. Progress updates go out inline through `DeniDin.send_progress_update`. | `denidin.py:741+`, `backbone.py:_execute_round_calls` |
| F4 | Backbone rounds: first call = rolling 14-day window + the new message; follow-up calls chain with `previous_response_id` and send only `function_call_output` items. Instructions and tools are rebuilt every round. | `backbone.py:609-680` |
| F5 | The backbone's approval is stateless buttons; `Session.approval_message_id` (one per chat) holds the id of the last approval-buttons message; `resolve_button_tap` ignores a tap whose `stanzaId` differs. | `backbone.py:996-1040` |
| F6 | Media enters the backbone raw as an `AIRequest` carrying **one** `Media`; `analyze_media` reads `turn_context["media"]` (that one file). | `denidin.py:_process_media_message_via_backbone`, `capabilities/media_analysis/handler.py:147` |
| F7 | The model's own Morning tool results are in its call chain (`mcp_call` items in `response.output`); the backbone already collects them (`_turn_mcp_calls`). | `backbone.py:812`, `ai_manager.py:616` |
| F8 | The replay/export player calls `dispatch_notification` synchronously and never constructs the live bot. | `denidin.py`, Feature 043 |
| F9 | `DeniDin` is the object every manager/AI implementation takes as its only constructor argument; cross-references are read at use time and None-guarded (REQ-063-08). | `CLAUDE.md` Feature 063 |

## Decisions

### D1 — Producer / dispatcher split behind the live bot only (revised 2026-10-12)
The dispatcher knows nothing about Green API: the Green API message source builds each `Notification` and gives the dispatcher only `(notification, stored message)` plus the injected `dispatch(type, notification)` (the contract the player already uses). Sends are unchanged (shared bot client — already used concurrently today by the reminder and typing-keepalive schedulers).
`run_forever` becomes a **producer**: poll → hook → hand the raw body to an `IntakeCoordinator` →
acknowledge immediately. A single **dispatcher thread** pulls bodies and calls the same
`dispatch(type, notification)` the router's handler calls today, so every existing handler runs unchanged on the
dispatcher. When no coordinator is attached (player, tests that build a bot without one) `run_forever`
is the current synchronous code, byte-for-byte.
*Why*: it is the smallest change that lets polling continue during a model call (F1). The dispatcher
stays **single and global**, exactly as serial as today (one chat's long-running handling still delays
another chat — unchanged, out of scope).
*Rejected*: per-chat dispatcher threads (new concurrency surface, no requirement for it); making
handlers async (large rewrite).

### D2 — The poller stores; `SessionManager` becomes an actor (revised 2026-10-12)
The poller receives a message, **stores it through `SessionManager`**, acknowledges it, and
enqueues the stored message. This is safe only if `SessionManager` is: today `get_session`
reloads `session.json` from disk on every call and every setter rewrites the whole file
(`session_manager.py:317, 376, 922`), so a poller `add_message` racing a dispatcher
`set_approval_message_id` can lose an update, duplicate an `order_num`, or let a reader hit a
half-written file. Decision (product owner): `SessionManager` is a **database-style actor** — its
own thread, one thread-safe queue for reads **and** writes, requests executed one at a time (D15).
REQ-RMH-003 is now met literally: the message is durable before it is acknowledged.

### D3 — One queue technology: bounded `queue.Queue` (revised 2026-10-12)
Per chat: a `queue.Queue(maxsize=…)` of **pre-received items** `(notification, WhatsAppMessage)`;
plus one `arrival` `queue.Queue` of chat ids that preserves cross-chat order and is what the
dispatcher blocks on (`get(timeout)`) — no separate wake-up Event. The dispatcher takes a chat id from
`arrival`, then `get_nowait()` from that chat's queue (an empty queue = stale id, skip). A
hand-back drain is `get_nowait()` until `queue.Empty` on that chat's queue. The hard limit is
`maxsize` on the per-chat queue; a global ceiling is the `arrival` queue's `maxsize`. Both
`SessionManager`'s queue (D15) and these use the same class and the same limit/warn/health
machinery (D16). The dispatcher-private `deferred` list and media backlog are not queues.

### D4 — Hand-back merge
In `Backbone._run_resolution_loop`, after a round's tool calls have run and before the follow-up
`responses.create`, the loop asks the coordinator (through `DeniDin`) to **drain** that chat's
attachable pending bodies. For each: take the message the poller already stored (`receive()` returns the pre-stored message, it does not store again), then append a user input item to
the round's `input`, **after** the `function_call_output` items:
`outputs + pending_user_items`. The item text carries the message timestamp and a before/after
marker relative to the model's last output (contract `hand-back-merge.md`).
- A `send_to_user` / approval round does **not** drain: the reply is sent as is (spec). Bodies
  still queued are simply handled next, starting from the rolling window — it already
  contains the sent reply and (once persisted) everything else.
- Plain-text-only rounds (reminded once to use `send_to_user`) also drain on the follow-up.
- Progress updates are not a separate case: they are a tool call → a round → a drain.

### D5 — What is attachable
Only text-bearing types from non-blocked senders: `textMessage`, `extendedTextMessage`,
`contactMessage`. Everything else (`interactiveButtonsResponse` taps, `contactsArrayMessage`,
edited/deleted, error types, a blocked sender) is **deferred**: moved, in order, to the dispatcher's
per-chat `deferred` list and dispatched later through the normal `dispatch` path. Order
within a chat is preserved (deferred items run before newer queued ones).

### D6 — Media (REQ-RMH-019/019a/019b)
At a drain, a media body is `receive()`d (stored as `[<filename> sent]` or its caption, with
timestamp), **noted** to the model (a one-line "a file arrived at HH:MM:SS" item), and moved to
the chat's **media backlog** (dispatcher-only). When the current work has nothing more owed, the
dispatcher dispatches the backlog item through the normal media path, in arrival order. The media
handler must not store it a second time: the dispatcher passes the already-received
`WhatsAppMessage` (looked up by `message_id`) so `_process_media_message` skips `receive`.
`analyze_media` is untouched (one file at a time). Several media at once = Feature 102.

### D7 — Approved-write handling does not drain (REQ-RMH-014)
`Backbone.single_turn` already computes `_turn_is_approved_write` = (an approval was pending) AND
(the incoming message is an affirmative reply — a typed "כן" or a button tap, which is
synthesised as "כן") (`backbone.py:496-500`). When it is true that handling runs with draining
**off**: messages arriving meanwhile stay queued and are handled next. A "לא" is not a
write, so it drains normally. No new state. *(V4 resolved by reading.)*

### D14 — The stale-tap guard must stop clearing on every new message (REQ-RMH-017)
**Conflict found:** `single_turn` clears `Session.approval_message_id` at the start of *every*
incoming message (`backbone.py:501`, "any new turn supersedes whatever approval buttons were
outstanding"). So today an unrelated message already makes an older approval's buttons stale —
the opposite of REQ-RMH-017 and acceptance scenario A7. Change: clear it only when
(a) the incoming message is the answer to it (a typed or tapped affirmative/negative reply — the existing
`approval_was_pending` branch), or (b) a newer approval-buttons message is sent
(`record_sent_message_id` overwrites it, as now). An unrelated message no longer clears it.
Cancelled-by-the-model has no mechanism today; see Open Question Q1.

### D13 — Timestamps in history (REQ-RMH-007)
`SessionManager._render_history_item` returns `{role, content}` with **no timestamp** (V5
resolved). The backbone's rolling-window call gets an opt-in parameter that prefixes each user
item's content with its Israel-local time (`[HH:MM:SS dd/mm]`); the default stays off so the legacy
`AIHandler` path is byte-identical. Hand-back items carry the same format plus the before/after
marker. Because a message's rendered text never changes once stored, the prefix is stable for
prompt caching.

### D8 — Check room, store, acknowledge, enqueue (revised 2026-10-12)
If the intake is full the message is dropped **before** it is stored (REQ-RMH-033: a full intake means something is very wrong).
`receive → store (SessionManager actor) → deleteNotification → enqueue`. A crash after the store
loses nothing: the stored message is in the session, and if the upstream redelivers it the
existing notification deduper drops it. A crash **between store and acknowledge** just means a
redelivery. A failed store is not acknowledged. The earlier ack-before-persist crash window (R1)
is **closed**. What a crash can still lose is the *queue position* of a stored-but-not-yet-handled
message: on restart it is in history but nobody answers it — to be addressed by a startup sweep
(unanswered final user message in a chat → hand to the dispatcher); listed as task candidate, not
required by the spec.

### D9 — Typing indicator
When a drain attaches messages, `send_typing_indicator` is re-fired (REQ-RMH-018), as
`send_progress_update` already does after each progress message.

### D10 — Model-facing instructions (REQ-RMH-009/026/027/028)
A new section in `config/prompts/backbone.md`, "Messages that arrive while you work": how to read
the timestamp/before-after markers; combined messages are one conversation; ask when the
sequence is confusing; **finish a pending approval before starting the next request**; a short
reply answers the most recent pending question in the same context. Each capability prompt that
can write (`cap_invoicing_write`, reminders, ledger) gets a one-line cross-reference. The legacy
`runtime_constitution.md` is untouched (backbone only).

### D11 — No turn vocabulary in new code
New names: `IntakeCoordinator`, `DeniDinDispatcher`, `drain_attachable`, `HandBack`, `pending
messages`. Existing `begin_turn`/`end_turn`/`single_turn`/`_turn_*` names are **not** renamed in
this feature (a rename is a separate, mechanical change; flagged to the product owner).

### D12 — Flag
None (product owner, 2026-10-12). Rollback is the previous release.

## Verification items (Gate Zero — before building on them; none were run in planning)

| # | Question | How to verify | Blocks |
|---|----------|---------------|--------|
| V1 | Does `responses.create` accept a **user message item alongside `function_call_output` items** in one `input` array when chaining with `previous_response_id`? | One real `billed` probe call (text only) | D4 |
| V2 | When a call returns, is every server-side Morning tool call fully present in `response.output` and nothing still running? | Inspect an existing logged real `mcp_call` response, or one billed run | D4 summary, SC-004 |
| V3 | *(Resolved by reading.)* `Notification(event, api, state_manager)` is constructible directly (`whatsapp_chatbot_python/manager/handler.py:16-28`), so the source builds notifications with the existing bot client; the dispatcher needs no router or session. | — | — |
| V4 | *(Resolved — see D7/D14.)* | — | — |
| V5 | *(Resolved — see D13.)* History items have no timestamps. | — | — |
| V6 | Does post-reply `_run_post_turn_ledger_recognition` behave correctly when one reply covers several user messages (it takes one `reply_text`)? | Read it; one integration test | A1/A2 |

## Residual risks (documented, not locked away)

- **R1** *(closed by D8)* ack-before-persist window. Remaining: a stored-but-unhandled message
  after a crash (see D8).
- **R2** The dispatcher is global-serial: long-running handling in one chat delays all others (unchanged
  from today).
- **R3** Producer and dispatcher share only the bounded queues; a
  message appended in the instant a drain finishes lands in the deque and is picked up by the next
  drain or as the next message to handle — never dropped (the dispatcher re-checks `has_work` before it
  sleeps).
- **R5** The poller and the sends share one bot client. Already true today (reminder/typing-keepalive scheduler threads send while the poller waits); no new exposure beyond sends now also coming from the dispatcher thread. Accepted.
- **R4** Models may still mishandle a burst; the safeguard is the prompt rules plus the right to
  ask the user (spec).

### D15 — SessionManager as an actor (REQ-RMH-029)
- Rename today's class body to `SessionStore` (not thread-safe, used **only** by the actor thread)
  and make `SessionManager` a thin facade with the **same public method signatures**; each method
  puts `(operation, args, kwargs, Future)` on the single queue and blocks on the `Future`
  (bounded wait; a timeout is a loud error, never a silent default). Explicit forwarding methods
  — no `__getattr__` magic, no monkey-patching.
- The actor thread loops: `get()` → run the matching `SessionStore` method → `Future.set_result`
  / `set_exception`. Internal calls between `SessionStore` methods are direct (no re-queueing, so
  no self-deadlock).
- Returned `Session`/`Message` objects are fresh copies (they already are — loaded from disk), so
  they cross threads safely.
- Lifecycle: the thread is a daemon started by the facade (lazily on first call, or explicitly in
  `initialize_app`); `close()` drains and stops it. Tests, `BackfillDeniDin`, `WebappDeniDin` and
  the player keep working because the facade is a drop-in; each owns its own manager/thread.
- Cost: every session read/write now round-trips through one thread; a long read (a 14-day
  rolling window) delays the poller's store of the next message by that read's duration (tens of
  ms). Accepted.
- Other writers of session files (daily roll, capability reset, reminders touching sessions) go
  through the facade — to be enumerated in tasks.md; any code that opens `session.json` directly
  is a bug to fix in this phase.

### D16 — Limits, warnings and visibility for every queue (REQ-RMH-033/034/035)
- A small `BoundedQueue` wrapper around `queue.Queue` (composition, no subclass tricks) adds:
  `put_or_raise(item)` → `queue.Full` becomes `QueueLimitExceeded` (ERROR log with name, size,
  limit, item id; dropped counter++); `last_get_at`; `size()`; high-water mark. All queues
  (per-chat intake, `arrival`, `SessionManager`'s) are `BoundedQueue`s — one tech, one set of behavior.
- Config (names settled in tasks.md): per-queue max, a warning size, a stall-seconds threshold,
  defaults in `config.example.json` — a `message_queues` block: `intake_max_per_chat` 500, `intake_max_total` 2000, `session_max` 200, `warn_fraction` 0.5, `stall_seconds` 30, `monitor_interval_seconds` 10, `supervisor_interval_seconds` 5, `supervisor_max_restarts` 3, `supervisor_window_seconds` 600, `session_call_timeout_seconds` 60, `slow_call_seconds` 5.
- A `QueueMonitor` (an existing APScheduler job style, every ~10 s) logs WARNING when a queue's
  size ≥ warning size or `size > 0` and `now - last_get_at` > stall seconds (rate-limited), logs INFO
  depths when non-empty, and publishes **boolean** fields into `/health`'s info (`build_health_info_fns` fields are pass/fail strings): `queues_within_limits` and `queues_not_stalled`, report-only like `whatsapp_authorized`; numeric depths/limits/dropped go to the INFO log line. Thread liveness is a real `build_health_check_fns` check (flips `status`).
- The `SessionManager` facade waits on its `Future` with a bounded timeout and raises loudly;
  operations slower than a threshold are logged at WARNING with their name.
- *Why this answers "the store queue blows up unnoticed":* it is bounded (hard stop + ERROR),
  warned on at a fraction of the bound, warned on when stalled, logged periodically and in `/health`.

### D17 — Keeping the threads alive (REQ-RMH-036)
- Today nothing watches a thread. If the new dispatcher or actor thread died, the poller would keep
  storing and queuing and nothing would ever be handled/answered; if the actor died every session
  call would time out — a silent outage.
- Every thread loop wraps **each item** in `try/except Exception` (log, continue; the dispatcher keeps
  REQ-RMH-024's sleep-5 posture) and a last-resort `except BaseException` that logs CRITICAL before
  the thread ends.
- A `ThreadSupervisor` (same scheduler as the monitor, every ~5 s) checks `thread.is_alive()`;
  a dead thread is logged at CRITICAL and replaced (the queues persist; the item in flight has its
  `Future` failed). A restart counter within a window (configurable) that is exceeded makes
  `/health` report non-ok so the existing prober (bugfix-043) restarts the container — the same
  recovery path prod already relies on. The poller is the process's main loop and is unchanged
  (its loop already survives item errors; if it ends the process ends).
