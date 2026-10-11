# Feature Specification: Realistic Message Handling — Conversation Without "Turns"

**Feature Branch**: `feature/067-realistic-message-handling`
**Created**: 2026-08-30
**Revised**: 2026-10-11 — Feature 090 ("Removing the Concept of a Turn") folded in; the design was
re-clarified one question at a time with the product owner (see Clarifications, Session
2026-10-11). This revision **supersedes** the 2026-08-30 discard-and-merge-turn design.
**Status**: In progress — spec revised 2026-10-11. `plan.md`, `research.md`, `data-model.md`,
`contracts/`, `quickstart.md` still describe the SUPERSEDED turn-based design and must be redone
(`speckit.plan`) against the post-Feature-063 backbone before `speckit.tasks`.
**Priority**: P2 (first-pass estimate)
**Absorbs**: Feature 090 (obsolete, folded in — `specs/repo/features/090-remove-turn-concept/`).
**Input**: User description (2026-08-30): "Today the denidin bot responds 1:1 to any message
sent. so if user sends msg1 the bot replies with reply1 and then msg2 gets reply2. But if msg2 is
sent before reply1 is returned, the understanding is that the user is *adding* to msg1, and not
really sending a separate msg2. This can easily happen as replies can take many seconds and users
grow impatient. So this feature is basically to support treating followup msgs before a reply to
be treated as a single message."
Refined 2026-10-11: "There should be no concept of a 'turn' — that's not how a conversation
works."

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I–III, §V, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS, §XVII, §XVIII): No env
  vars, Israel-local timestamps, feature-branch workflow, integration tests as E2E, no
  monkey-patching, bounded-retry on external handshakes.
- **METHODOLOGY.md** (§I, II, VI, VIII, IX, X, XXI-style constitution boundary): Spec-first
  development, mandatory user stories, the 2026-08-18 "TDD" redefinition, Terminology Glossary,
  Technology Choices, Requirement IDs, explicit `runtime_constitution.md` boundary section for
  new behavior.

**Required Files**: `user-stories.md` ✅ · `spec.md` (this file) ✅ · `plan.md` ⛔ (superseded,
redo) · `data-model.md` ⛔ · `contracts/` ⛔ · `research.md` ⛔ (partly reusable) ·
`quickstart.md` ⛔ · `tasks.md` ⏳

---

## Clarifications

### Session 2026-10-11 (product owner, one question at a time)

- Q: What is wrong with "one inbound WhatsApp message = one turn" (Feature 090's question)? → A:
  **There should be no concept of a "turn" at all** — it is the wrong model of a conversation.
  (The 2026-08-30 design kept "turn" as a core term: in-flight turn, discarded turn, reset after
  reply. That framing is dropped.)
- Q: What do capability/flow state, the idle reset and the stale-tap guard key off once there is
  no turn? → A:
  - **Loaded capabilities/flows are loaded and unloaded by the model**, when it needs or no longer
    needs them — never by code at a turn boundary. (The backbone already works this way via
    `load_capabilities`/`unload_*`.)
  - **The idle reset (`capability_reset_service`, `capabilities_reset_minutes`) stays** — it is a
    **guardrail**, kept in code on purpose.
  - **The stale-tap guard clears only when the pending approval itself is cleared** (resolved,
    superseded by a newer one, or cancelled) — never because a new message arrived. Its matching
    rule (tap's `stanzaId` == the approval's `sent_message_id`) is unchanged.
- Q: Is the 2026-08-30 "cancel / merge" behavior still right? → A: **Yes, with these nuances:**
  - A model call that is already running cannot be safely aborted (blocking `responses.create`,
    no streaming/background; server-side Morning tool calls run atomically inside one call).
    **Stopping happens only at the points where the model hands control back to the app** (a tool
    call, a progress update, a reaction, a recording, …).
  - **At every hand-back, the app decides what to give the model next from two things: (A) what
    the model just sent, and (B) what the user sent in the meantime — merging the two.**
  - **The model must be told WHEN things happened.** Every user message (and media caption) carries
    a **timestamp**, and the app marks which user messages arrived **before** vs **after** the
    model's last output, so the model can build a timeline and not get confused.
  - **It is acceptable for the model to be confused and ask the user what to do next** — users are
    confusing.
  - **Message bursts**: if a user sends many messages (e.g. 10) in quick succession, the **first is
    processed immediately**, and at **each later hand-back the app attaches every user message read
    since**. The model's first output may therefore have been based only on message 1, while its
    next input carries many of the rest.
  - The **"כן" approval-execution step is non-interruptible** (unchanged): it always runs to
    completion; messages arriving during it are held and handed to the model afterwards.
- Q: When does the app "start over" / stop accumulating user messages? → A: **There is no
  start-over and no end.** The app is a reactor to data, not a cycle: whenever control returns to
  it, it looks at (a) the model's output items (tool calls, `send_to_user`, …) and (b) user
  messages not yet handed to the model, and sends whatever is owed to the model or to the user. If
  nothing is owed, **nothing happens until the next WhatsApp message** — idle is simply the absence
  of work, not a state the app "enters". (Facts that make this safe, from the code as of
  2026-10-11: the first model call for each inbound message carries the rolling 14-day verbatim
  history, trimmed from the oldest to the role's token cap; later calls chain via
  `previous_response_id`; everything is persisted as it happens, so a chain can be restarted from
  the rolling window at any time without loss.)
- Q: Feature flag? → A: **No flag.** (Supersedes the 2026-08-30 decision for
  `feature_flags.realistic_message_handling`; rollback is the previous release.)

### Session 2026-08-30 (still in force unless contradicted above)

- Media (image/document/video/audio) is **out of scope for merging**: a media message is handled
  on its existing path, is not merged into text, and does not interrupt text handling. Full
  media-burst handling is a separate future decision.
- **Group chats: per chat.** A new message from anyone in the group is treated as part of that
  chat's single stream (one shared history, one typing indicator, one pending-approval slot).
- **Acknowledge immediately on receipt** (`deleteNotification` as soon as the message is read and
  handed on). Accepted residual risk: a crash between acknowledgement and handling loses that
  message — to be documented in the re-done `research.md`.
- **No `threading.Lock`/`RLock`/`Semaphore`/`queue.Queue` without a separate explicit human
  approval.** Follow the project precedent (lock-free background jobs, documented residual risk);
  a one-way cross-thread flag is acceptable.
- Typing indicator is re-fired when new user messages are handed to the model.
- A failure while handling work is logged, the worker sleeps 5s and continues — it never exits.

## Terminology Glossary

- **Hand-back**: any moment the model returns control to the app — a tool call, a progress
  update, a reaction, a recording, `send_to_user`, an approval request, or plain text.
- **Pending user messages**: user messages that have been received (and persisted) but not yet
  handed to the model.
- **Merge**: at a hand-back, composing the model's next input from the model's own output
  (tool results etc.) **and** the pending user messages, each with its timestamp and an
  explicit before/after marker relative to the model's last output.
- **Burst**: many user messages in the same chat arriving faster than the model hands back.
- **Side effect**: a change made outside the conversation (an invoicing document created in the
  external system, a ledger/reminder record). The model sees the results of its own side effects
  in its call chain; no separate "journal" concept is required.
- **Idle**: no model output awaiting handling and no pending user messages. Not a state the app
  transitions into — simply nothing to do.

*(The words "turn", "in-flight turn", "discarded turn" and "reset after reply" are retired and
must not be used in code, docs or prompts written for this feature.)*

## Technology Choices

Detailed design (threading model, class seams, exact hand-back points) is deferred to the re-done
`plan.md` / `research.md`. Constraints fixed now:

- **No new runtime dependency** is expected.
- **No `threading.Lock`/`RLock`/`Semaphore`/`queue.Queue`** without separate explicit human
  approval; a one-way cross-thread flag is permitted.
- The **replay/export player path** (`PlayerExportSource`) and the shared dispatch/handler code it
  runs through MUST remain synchronous and behaviorally unchanged — any producer/hand-back
  machinery lives behind the **live** message source only.
- Handling stays **single-threaded per chat** — at most one model exchange runs at a time for a
  given chat.
- Applies to the **Dynamic Capability Backbone** (Feature 063, the live path). Whether the legacy
  `AIHandler` path is touched at all is **not yet decided** — see Open Items.
- Calls to the model remain blocking `responses.create`; true in-call cancellation (e.g. the API's
  background mode) is **not** part of this feature and is unverified (CONSTITUTION: no unverified
  third-party assumptions).

## User Stories Reference

Authoritative stories with Given-When-Then criteria are in **`user-stories.md`**. Quick reference:

- **US1 (P1)** — Additive burst: several quick messages forming one request get one coherent
  answer; later messages reach the model at the next hand-back.
- **US2 (P1)** — A long burst (≈10 messages): the first is handled at once and the rest are
  picked up at later hand-backs, with timestamps.
- **US3 (P2)** — "Do X" then "stop, don't do X" arriving mid-work: the correction reaches the model
  at its next hand-back, before any approval-gated write; nothing is created without approval.
- **US4 (P2)** — A write the model already performed server-side before the correction arrived is
  visible to the model in its own chain and reported truthfully.
- **US5 (P2)** — Timeline: every user message carries a timestamp and a before/after marker, and
  the model may ask when it is confused.
- **US6 (P2)** — Media doesn't merge and doesn't interrupt.
- **US7 (P3)** — Group chat: per-chat stream.
- **US8 (P3)** — Approval execution ("כן") is not interrupted; messages sent during it are handled
  afterwards.
- **US9 (P3)** — Stale-tap guard clears only with its approval; the idle reset still works.

## Requirements *(mandatory)*

### Functional Requirements

**Hand-back merge**

- **REQ-RMH-001**: At every hand-back, the system MUST compose the model's next input from (A) the
  model's own output and (B) all pending user messages for that chat, merged.
- **REQ-RMH-002**: The first user message after idle MUST be handed to the model immediately; the
  system MUST NOT wait for a debounce window.
- **REQ-RMH-003**: User messages arriving while the model is working MUST be received and
  persisted immediately, individually, and handed to the model at the next hand-back.
- **REQ-RMH-004**: In a burst, each hand-back MUST attach every user message read since the
  previous hand-back (all of them, in arrival order), not just one.
- **REQ-RMH-005**: Every user message MUST be persisted individually to the conversation history
  in arrival order.
- **REQ-RMH-006**: Per-chat scope, including group chats: a message from any participant belongs
  to that chat's single stream.

**Timeline**

- **REQ-RMH-007**: Every user message handed to the model (and every media caption) MUST carry its
  timestamp (Israel local, via `now_local()`-based values already stored on the message).
- **REQ-RMH-008**: When merging, the system MUST distinguish for the model which user messages
  were sent **before** its last output and which **after**.
- **REQ-RMH-009**: `runtime_constitution.md` / the backbone prompt MUST tell the model how to read
  that timeline and that it MAY ask the user what to do when the sequence is confusing.

**Stopping and side effects**

- **REQ-RMH-010**: The system MUST NOT attempt to abort a running model call. Control over what
  happens next is exercised only at hand-backs.
- **REQ-RMH-011**: At a hand-back with pending user messages, the system MUST NOT execute a
  proposed action that requires approval; the model is given the new messages first. (Writes are
  already approval-gated in the backbone.)
- **REQ-RMH-012**: The model MUST be able to see the results of side effects it already caused
  (Morning tool results, ledger/reminder writes) in its own call chain, so it can report them
  truthfully and not repeat them.
- **REQ-RMH-013**: Handling of a hand-back with pending user messages versus the model's other
  output items (reads, loads, progress, `send_to_user`) is **not yet decided** — see Open Items.
- **REQ-RMH-014**: The "כן"/"לא" approval-**execution** step MUST be non-interruptible: it always
  runs to completion and its reply is sent; messages arriving during it are persisted and handed
  to the model afterwards.

**No turn / no end**

- **REQ-RMH-015**: The system MUST NOT define, track or branch on a "turn" boundary. When nothing
  is owed to the model or the user, the system MUST do nothing until the next inbound message.
- **REQ-RMH-016**: Loaded capabilities/flows MUST be loaded and unloaded by the model only; the
  existing idle reset (`capability_reset_service`) MUST remain as a code guardrail.
- **REQ-RMH-017**: A button-tap staleness guard MUST be cleared only when its pending approval is
  cleared (resolved, superseded or cancelled), never because of a new inbound message; its
  matching rule is unchanged.
- **REQ-RMH-018**: The typing indicator MUST be re-fired when new user messages are handed to the
  model.

**Media boundary**

- **REQ-RMH-019**: A media message MUST NOT be merged into text handling and MUST NOT interrupt
  it; it is processed on its existing media path.

**Safety**

- **REQ-RMH-020**: There is **no feature flag** (product owner, 2026-10-11).
- **REQ-RMH-021**: The inbound notification MUST be acknowledged to the upstream queue
  immediately on receipt; the crash-window MUST be documented as accepted residual risk.
- **REQ-RMH-022**: The replay/export player path MUST remain synchronous and unchanged.
- **REQ-RMH-023**: At most one model exchange MUST run at a time per chat.
- **REQ-RMH-024**: A failure while handling one item MUST be logged (sleep 5s, continue) and MUST
  NOT stop handling of later messages.
- **REQ-RMH-025**: No `threading.Lock`/`RLock`/`Semaphore`/`queue.Queue` without separate explicit
  human approval; accepted residual concurrency risk MUST be documented.

**Constitution boundary**

- **REQ-RMH-026**: The backbone prompt / `runtime_constitution.md` MUST gain a section defining
  how to treat messages that arrive while it is working (timeline, before/after, may ask), and
  that a short trailing message answers the most recent pending question in the same context.
- **REQ-RMH-027**: Existing tool-bearing sections MUST cross-reference it.

### Key Entities

- **Pending user messages** (per chat, in-memory queue-like list; persisted copies already in
  session storage): received but not yet handed to the model.
- **Hand-back record**: what the model last returned, used to mark messages before/after it.

*(The 2026-08-30 entities "Burst buffer", "Active turn handle" and "Already done journal" are
retired.)*

## Success Criteria *(mandatory)*

- **SC-001**: A 3-message additive burst sent within the model's latency is understood as one
  request; the model's final answer reflects all three.
- **SC-002**: In a 10-message burst, message 1 is handled immediately and all later messages reach
  the model at subsequent hand-backs in order, each with its timestamp.
- **SC-003**: A "stop, don't do X" sent while the model is working reaches the model before any
  approval-gated write; zero writes occur without approval.
- **SC-004**: Anything the model already did server-side is reported truthfully and not repeated.
- **SC-005**: Every user message appears in history, in order, individually.
- **SC-006**: A handling failure is logged and the next inbound message is still handled.
- **SC-007**: A message sent during a "כן" approval execution never causes that execution to be
  aborted or run twice.

## Open Items — to ask the product owner (one at a time) before `speckit.plan`

1. **A `send_to_user` (or other reply-producing output) that comes back while newer user messages
   are already waiting**: send it as is, hold it and merge first, or something else? (Not yet
   answered.)
2. **Other model outputs at a hand-back with pending messages** (read tools, capability loads,
   progress updates): execute them and attach the pending messages to the function results, or
   hand the messages over first? (Not yet answered.)
3. **Legacy `AIHandler` path**: in scope, or backbone-only? (Not yet answered.)
4. **Media-burst handling** and **`contactsArrayMessage`** remain a separate future decision.
