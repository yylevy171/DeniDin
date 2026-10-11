# Phase 0 Research: Realistic Message Handling — Multiple Interfering Messages

**Feature**: `feature/067-realistic-message-handling` · **Date**: 2026-08-30

This document records the design decisions that need a rationale, the third-party behaviours the
design leans on and their verification status (CONSTITUTION "NO UNVERIFIED THIRD-PARTY
ASSUMPTIONS"), and every accepted residual risk (REQ-RMH-021a, REQ-RMH-025).

---

## D1 — Producer/consumer split instead of a debounce timer

**Decision**: A background producer thread drains the Green API queue continuously; a single
consumer thread runs turns one at a time. No "wait N milliseconds for more messages" timer.

**Rationale**: The user explicitly rejected a debounce window ("No window… a follow-up only
matters if it arrives before the reply to the earlier message has been sent"). The only thing
that makes an interfering message noticeable is that polling never stops during a turn — today's
`run_forever` does not fetch the next notification until the current turn fully returns. Splitting
poll (producer) from process (consumer) is the minimal change that gives us a live view of the
queue while a turn runs, without introducing artificial latency on the common no-burst case.

**Alternatives considered**:
- *Debounce timer* — rejected by the user; also adds latency to every single-message turn.
- *Async/await rewrite of the whole path* — far larger blast radius; `AIHandler`, the Green API
  library, and every handler are synchronous; out of scope.
- *Second worker for parallelism* — violates REQ-RMH-023 (at most one turn per chat) and every
  existing "no parallel turns" assumption in session/approval handling.

---

## D2 — Lock-free concurrency (`threading.Event` + `collections.deque`, no `Lock`/`queue.Queue`)

**Decision**: The only cross-thread primitives are:
- one `threading.Event` per in-flight turn (`active_turn[chat_id].cancelled`) — producer calls
  `.set()`, the turn thread calls `.is_set()` at round boundaries. One-way, monotonic.
- one `collections.deque` as the producer→consumer work handoff — producer `.append(...)`,
  consumer `.popleft()`; consumer blocks on a short `Event.wait(timeout=...)` / poll when empty.
- plain dict/list state inside `IntakeCoordinator` (`pending_text`, `active_turn`, `carryover`),
  keyed by `chat_id`.

No `threading.Lock`, `RLock`, `Semaphore`, or `queue.Queue` — per the user's explicit standing
instruction (spec Clarifications; memory `feedback_tdd_gate_only_billed_no_locks`: "never add
threading.Lock without asking first").

**Rationale**: The topology is strict single-producer / single-consumer. Under CPython the GIL
makes `deque.append` / `deque.popleft` individually atomic, and a dict insert/lookup/delete on
distinct keys is atomic — the coordinator never does a read-modify-write across threads that
would need a critical section. This mirrors the project's established precedent:
`send_proactive_message` documents its shared-`requests.Session` race as "an accepted, unmitigated
residual risk" (explicit user decision 2026-08-16); `SessionCleanupThread` uses a plain bool
`_running`; the APScheduler services run lock-free against shared conversation state.

**Enumerated shared-state accesses and their accepted outcomes**:

| Interaction | Threads | Outcome without a lock | Accepted? |
|---|---|---|---|
| Producer `.append` to the work `deque` while consumer `.popleft`s | P + C | atomic under GIL; no item lost or duplicated | ✅ |
| Producer sets `active_turn[chat_id].cancelled` while the turn thread reads `.is_set()` | P + C | `Event` is designed for exactly this; worst case the check is one round late (still a round boundary, still before the reply is sent) | ✅ |
| Producer appends to `pending_text[chat_id]` (a list) while consumer drains it after cancel | P + C | `list.append` is atomic under GIL; consumer drains by swapping the list reference out first (`buf, self.pending_text[cid] = self.pending_text[cid], []`) — a message appended in the swap window lands in the fresh list and is folded into the *next* turn, never dropped | ✅ |
| Burst message lands in the exact instant the turn transitions "in flight" → "reply sent" | P + C | if `active_turn[chat_id]` is still set, `cancelled` is raised but the turn has already passed its last round boundary → the reply is sent AND the burst message starts a fresh turn (one extra reply, never a lost message, never a double action) | ✅ — same "one extra reply" outcome as flag-OFF |
| Consumer clears all per-chat state in `on_turn_finished` while producer submits a new message for that chat | P + C | producer either sees `active_turn=None` (→ new work item, correct) or the just-cleared state (→ new work item, correct); the clear is a sequence of atomic dict ops, no torn read that matters | ✅ |

**Residual risk explicitly accepted**: the "burst message in the send-transition instant" row —
it can produce one extra reply (the fresh-turn reply) in a sub-millisecond window. This is
strictly no worse than flag-OFF behaviour (which always replies per message) and never causes a
double side effect or a lost message. Documented here per REQ-RMH-025.

**If this proves insufficient in practice**: the fallback is a single `threading.Lock` around the
`IntakeCoordinator` state transitions — but that requires separate explicit human approval before
being added (REQ-RMH-025), and is not part of this plan.

---

## D3 — Acknowledge (`deleteNotification`) immediately, before the turn

**Decision**: On the flag-ON path the producer calls `deleteNotification(receiptId)` as soon as
it has read the notification and handed the body to the coordinator — not after the turn
completes (which is today's order in `run_forever`).

**Rationale**: (a) A burst is exactly the case where a turn takes many seconds; holding the ack
that long keeps the notification eligible for Green API redelivery (~32s, per
`RecentNotificationDeduper`'s existing TTL comment) and inflates the deduper's job. (b) The
consumer may discard the turn that "owns" a given `receiptId` and re-process its text inside a
merged turn — there is no longer a clean 1:1 "this turn finished, ack its notification" mapping,
so acking per-turn-completion is not even well-defined once coalescing is in play. Acking on
receipt is the only order that stays coherent.

**Accepted residual risk (REQ-RMH-021a)**: if the process crashes between the ack and the turn
completing, that message (and any buffered burst siblings already acked) is lost — Green API will
NOT redeliver it. Today's order loses nothing in that window because the ack hasn't happened yet.
This is a real regression in crash-recovery for a narrow window, accepted by explicit clarify
decision. Mitigations already in place: the consumer mirrors the live loop's log-sleep-5s-continue
posture (REQ-RMH-024) so a *turn* exception does not crash the process; only a hard process kill
hits this window. Messages not yet acked (still in the producer's hand or mid-read) are
redelivered and handled as new messages on restart (spec Edge Cases).

**Verification status**: Green API's redelivery-of-un-acked-notification behaviour is already
relied on by `RecentNotificationDeduper` (documented ~32s redelivery). **OPEN**: confirm that
figure still holds and that an *acked* notification is definitively not redelivered — a single
observation during Phase 0 or the `quickstart.md` manual run suffices (send a message, ack it,
confirm it never reappears in `receiveNotification`).

---

## D4 — Round-boundary cancellation only; a single model HTTP call is allowed to return

**Decision**: `cancel_check` is consulted only between discrete steps — before the first
`responses.create`, at the top of each `_run_local_tool_dispatch_loop` iteration (before
dispatching any local tool and before the follow-up `responses.create`), and before
`_finalize_response`. A `responses.create` call already in flight is never aborted mid-request.

**Rationale**: The OpenAI Responses API path here is a code-controlled loop of discrete blocking
`responses.create` calls (`timeout=30.0`, `max_retries` at client level), no streaming. There is
no safe way to cancel a running `responses.create` from another thread without tearing down the
shared client. A 30s worst-case wait for one in-flight call to return before the merged turn
starts is acceptable — the common burst case is messages arriving 1–5s apart while the model is
still on its *first* call, which we catch at the very next boundary.

**Server-side tool execution nuance**: remote MCP tools (Morning invoicing) are executed
**server-side by OpenAI, atomically within one `responses.create`**. We cannot interrupt that.
What we *can* do is detect, on return, what was executed — see D5.

**Alternatives considered**:
- *Kill the HTTP call* — no clean mechanism; risks a half-read response and a poisoned client.
- *Check a flag inside a streaming loop* — would require switching to streaming; larger change;
  still can't un-execute a server-side MCP call.

---

## D5 — Detecting side effects a discarded turn already caused

**Decision**: On a positive `cancel_check` after a `responses.create` has returned, the journal is
built from:
1. **Server-side MCP calls** — `response.output` items with `type == "mcp_call"` (the same list
   `_finalize_response` already builds into `AIResponse.mcp_calls` at `ai_handler.py:2936-2945`),
   each carrying `name` / `arguments` / `output` / `error`. An item present with no `error` is a
   real document/action created in Morning.
2. **Local ledger events already persisted this turn** — `_handle_ledger_event_capture` writes one
   immutable JSON file per event mid-turn; any file already written before the interruption is
   real and stays. The journal records its `event_id` + a human summary.
3. **Reminder writes** — only happen on a "כן" approval-execution turn, which is
   **non-interruptible** (D7), so in practice a reminder write is never in a discarded turn. If
   that ever changes, the same "already committed → journal it" rule applies.

Items that mean **nothing executed** and are therefore NOT journalled: `response.output` items
with `type == "mcp_approval_request"` (`ai_handler.py:2967-2970`) — the model is *asking* to run
a tool, it has not run. Proposed local tool calls not yet dispatched — likewise.

**Verification status — OPEN**: confirm that once `responses.create` returns, every server-side
MCP call it performed is fully represented in `response.output` and nothing is still executing
server-side ("the call can return, but … we KNOW what it did when it returns"). This is almost
certainly true (the Responses API is request/response, not a background job), but per CONSTITUTION
it must be confirmed against a real response — achievable by inspecting an existing
`billed`/`expensive` test log that already captured a real `mcp_call` output item, or one fresh
`billed` run of an existing Morning-tool test. No new test needed just for this.

---

## D6 — Journal delivery via a dedicated `AIRequest.system_note` field, after the date line

**Decision**: The journal reaches the merged turn's model call through a new
`AIRequest.system_note: str = ""` field. `ai_handler.py` assembles `instructions` as it does
today — constitution text, then recalled memory context, then a `---` separator, then the
per-call Israel-local date line — and **then**, only if `system_note` is non-empty, appends it.

**Rationale**: `instructions` today is ordered specifically so the constitution (~4.0K tokens,
byte-identical every call) is the stable prefix that OpenAI's automatic prompt caching keys on;
everything that varies (memories, date) comes after. The date line already breaks the cached
prefix, so appending `system_note` *after* it costs nothing more in cache terms — the
constitution + memories bytes stay identical to a non-`system_note` call. Putting the journal in
`user_prompt` instead would work but muddies "what the user said" with "what the system is
telling the model", and the user chose the dedicated field in clarify.

**Journal text shape**: built from the structured records in D5, never free model text, e.g.

```
[מערכת — פעולות שכבר בוצעו בתור קודם שבוטל, ואי אפשר לבטלן. דווח עליהן למשתמש אם רלוונטי, ואל תנסה לבצע אותן שוב:
- נוצרה קבלה מס' 1234 עבור לקוח X על סך ₪500 (בוצע במערכת החשבוניות)
- נרשם אירוע יומן: הסכם שכ"ט 10% מול Y]
```

The model's obligations around this note (factor it in, report if relevant, do NOT re-attempt)
are specified in the new `runtime_constitution.md` section (REQ-RMH-014/026).

**Lifecycle**: `carryover[chat_id]` holds the structured records; it is set when a cancelled
result comes back and cleared by `on_turn_finished(chat_id)` once the merged turn's reply is
actually sent (REQ-RMH-015).

---

## D7 — The "כן"/"לא" approval-execution turn is non-interruptible

**Decision**: `cancel_check` is NOT passed into `_resolve_pending_approval`,
`_resolve_pending_local_tool_approval`, or `_call_openai_approval_api`. When `get_response` takes
the approval-resolution branch, it runs to completion and returns a normal reply regardless of
any burst.

**Rationale**: `_call_openai_approval_api` runs with `.with_options(max_retries=0)` specifically
because of the past double-invoice incident (bugfix-022) — it is the one path where a retry could
double-charge a client. Making it interruptible would reintroduce exactly the class of risk that
guard exists to prevent: a burst mid-execution could leave the approval half-resolved, or trigger
a re-resolution that runs the invoicing action twice. The user chose non-interruptible in clarify
as "the safest choice against double-execution of a real invoicing action."

**Consequence**: burst messages that arrive during an approval-execution turn are buffered by the
coordinator and coalesced into the **next** fresh turn (they do not merge into the approval turn,
and no journal is produced because nothing was discarded). Verified by IT-2b / SC-007.

---

## D8 — Feature flag read once at process start

**Decision**: `config.feature_flags.realistic_message_handling` is read once in `denidin.py`
`__main__` and passed into `GreenAPIMessageSource`. `run_forever` branches on the value the
`DeniDinGreenAPIBot` was given; it is never re-read mid-session.

**Rationale**: The flag decides the *thread topology* of the process (one loop vs. producer +
consumer). Re-reading it mid-run would mean tearing down and rebuilding threads live — pointless
complexity for a flag that changes only on a deliberate operator redeploy. `runtime_constitution.md`
hot-reloads on mtime; a *feature flag* does not, and shouldn't. When OFF, no `IntakeCoordinator`
is constructed and `run_forever` executes its current body verbatim (REQ-RMH-021).

**Verification status**: N/A — this is an internal wiring decision, no third-party behaviour.

---

## D9 — Typing indicator re-fired on a merged turn

**Decision**: When the consumer starts a merged turn, `_process_conversational_message` calls
`send_typing_indicator(...)` again for that chat (REQ-RMH-017a).

**Rationale**: `sendTyping` has a fixed ~20s window (`typingTime=20000`) and no renewal (Feature
048, reverted to single-call). A discarded turn's typing indicator may well have lapsed by the
time the merged turn starts; re-firing is one cheap best-effort call (already never raises) and
keeps the UX honest that DeniDin is still working. No downside — `sendTyping` is idempotent from
the user's view.

**Verification status**: `sendTyping` behaviour is already established in the codebase (Feature
048). No new assumption.

---

## D10 — Worker-thread exception posture

**Decision**: The consumer loop wraps each work item in `try/except Exception` → log → `time.sleep(5.0)`
→ `continue`, mirroring `run_forever`'s existing `except Exception` arm verbatim
(`green_api_bot.py:192-197`). `KeyboardInterrupt` breaks the loop for clean shutdown. The
consumer thread never exits on a turn error.

**Rationale**: Today a turn exception in `run_forever` logs, sleeps 5s, and continues — message
processing is never silently dead. The consumer must preserve exactly that property (REQ-RMH-024,
spec Edge Cases). The producer thread gets the same treatment for its own poll/ack loop.

**Verification status**: N/A — mirrors existing in-repo behaviour.

---

## Open items summary (must close before the dependent code is "done")

| # | Item | How to close | Blocks |
|---|---|---|---|
| O1 | Server-side MCP calls fully represented in `response.output` on return; nothing still executing server-side | Inspect an existing real-MCP `billed`/`expensive` test log, or one fresh `billed` run of a Morning-tool test | Phase 3 (journal assembly) considered done |
| O2 | Green API: un-acked notification redelivery timing still ~32s; acked notification never redelivered | One observation in Phase 0 or the `quickstart.md` manual dev run | Ack-immediately (Phase 5) considered done |

Neither open item blocks writing the Tier-1 tests or the non-dependent phases; each blocks
marking its own dependent phase complete.
