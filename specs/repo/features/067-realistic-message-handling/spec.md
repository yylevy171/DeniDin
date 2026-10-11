# Feature Specification: Realistic Message Handling — Multiple Interfering Messages

**Feature Branch**: `feature/067-realistic-message-handling`
**Created**: 2026-08-30
**Clarified**: 2026-08-30 (initial design conversation + `speckit.clarify` session — see
Clarifications; all Open Questions resolved)
**Status**: In progress — spec drafted and clarified 2026-08-30. `speckit.plan` next.
**Priority**: P2 (first-pass estimate)
**Input**: User description (2026-08-30): "Today the denidin bot responds 1:1 to any message
sent. so if user sends msg1 the bot replies with reply1 and then msg2 gets reply2. But if msg2 is
sent before reply1 is returned, the understanding is that the user is *adding* to msg1, and not
really sending a separate msg2. This can easily happen as replies can take many seconds and users
grow impatient. So this feature is basically to support treating followup msgs before a reply to
be treated as a single message."

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I–III, §V, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS, §XVII, §XVIII): No env
  vars, Israel-local timestamps, feature-branch workflow, integration tests as E2E, no
  monkey-patching, bounded-retry on external handshakes.
- **METHODOLOGY.md** (§I, II, VI, VIII, IX, X, XXI-style constitution boundary): Spec-first
  development, mandatory user stories, the 2026-08-18 "TDD" redefinition, Terminology Glossary,
  Technology Choices, Requirement IDs, explicit `runtime_constitution.md` boundary section for
  new behavior.

**Required Files**: `user-stories.md` ✅ · `spec.md` (this file) ✅ · `plan.md` ⏳ ·
`data-model.md` ⏳ · `contracts/` ⏳ · `research.md` ⏳ · `quickstart.md` ⏳ · `tasks.md` ⏳

---

## Clarifications

### Session 2026-08-30 (initial design conversation)

- Q: What is in scope — message coalescing, concurrency/interference, or multiple attachments per
  send? → A: **Text coalescing only.** Media (image/document/video/audio) is explicitly out of
  scope. A media message **breaks** a text burst and is handled on its existing path with no
  merge and no interrupt. Full media-burst handling (several deposit screenshots at once,
  image+caption bursts) is a **separate future decision**, not this feature.
- Q: Debounce window — how long do we wait for "more" before processing? → A: **No window.** This
  is not a "wait N seconds then process" design. Each message is processed immediately; a
  follow-up only matters if it arrives *before the reply to the earlier message has been sent*.
- Q: Polling behavior while a turn is being processed? → A: **Always polling.** A background
  producer continuously drains the incoming-message queue and never stops while a turn is in
  flight — that is what makes it possible to notice an interfering message at all.
- Q: How late can an interfering message still be merged? → A: **Any point until the reply is
  actually sent.** The instant the outbound reply succeeds, the mechanism resets for that chat and
  the next message is a brand-new turn.
- Q: When several messages are coalesced, how many replies and how much history? → A: **Only the
  last message gets a reply**, based on all combined text. Every earlier user message in the burst
  is still individually persisted to the conversation history (N user messages, one assistant
  reply).
- Q: What happens to an in-flight AI turn when an interfering message arrives? → A: **Discard the
  in-flight reply; merge the user text; regenerate one reply.** The single in-flight model call
  is allowed to return (it cannot be safely killed mid-request), but:
  - Any **DeniDin-local action** the returned response asked for (recording a ledger event,
    creating/modifying/deleting a reminder, running a query tool) is **NOT performed** — the local
    action loop stops.
  - Any **external invoicing action** the model already performed on its own (server-side, before
    returning) **cannot be un-done**; the system **detects what was done** and carries it into the
    merged follow-up turn as "already done" context, so the final single reply can report it
    truthfully ("I already created receipt #1234 before you said 'actually, cancel'").
  - The discarded turn's reply text is **never sent**.
  - Any pending-approval prompt the discarded turn would have created is **dropped** (nothing was
    executed, so there is nothing to approve).
- Q: Group chats — coalesce per-sender or per-chat? → A: **Per chat.** Any new message in a group,
  from anyone, merges with the in-flight turn for that chat. This matches DeniDin's existing model
  of one shared conversation history, one typing indicator, and one pending-approval slot per
  chat.
- Q: Feature flag? → A: **Yes.** `config.feature_flags.realistic_message_handling`, default
  `false`. When off, behavior is byte-for-byte the current one-reply-per-message serial behavior.
- Q: Concurrency-protection primitive? → A: **No `threading.Lock` without a further explicit human
  approval.** Follow the existing project precedent (background delivery/cleanup/reconciliation
  jobs all run lock-free against shared conversation state and document the accepted residual
  risk). Design to minimize shared mutable state rather than lock it. A one-way cross-thread flag
  (already used elsewhere in the codebase) is acceptable.

### Session 2026-08-30 (speckit.clarify)

- Q: When a media message arrives while a text turn is in flight, what happens to that in-flight
  text turn? → A: **The text turn continues.** Media is handled on its own path; the in-flight
  text turn is not discarded — its reply (based only on the text received so far) is still
  produced and sent. The user receives the text reply, then the media reply. (Resolves Open
  Question 1.)
- Q: How is the "already done" journal delivered to the merged follow-up turn's model call? → A:
  **Dedicated system-note field.** A new `AIRequest` field carries the structured journal; it is
  assembled into the model `instructions` **after** the per-call date line, keeping the
  constitution prefix byte-stable so OpenAI prompt caching still hits. Journal lines are built
  from structured side-effect records, never free model text. (Resolves Open Question 2.)
- Q: When should the inbound message be acknowledged to the upstream queue
  (`deleteNotification`)? → A: **Immediately on receipt.** The producer acknowledges as soon as it
  has read the notification and handed it to the intake coordinator — it no longer waits for the
  turn to finish. This also relieves redelivery pressure on the existing notification deduper.
  Accepted trade-off: a process crash between ack and turn completion loses that one message with
  no upstream redelivery — documented as residual risk in `research.md`. (Resolves Open
  Question 4.)
- Q: If an interfering message lands during the short "כן" approval-**execution** turn (which runs
  with no automatic retry after the past double-invoice incident), what happens? → A: **That turn
  is non-interruptible.** Approval-execution turns always run to completion and send their reply;
  interfering messages queue up and only start a fresh turn afterward. This is the safest choice
  against double-execution of a real invoicing action. The interfering messages are still
  coalesced among themselves into that next turn. (Resolves Open Question 5.)
- Q: Typing indicator on the merged turn? (resolved with documented default, not separately
  asked) → A: **Re-fire it** when a burst restarts the turn — cheap, ~20s window.
- Q: Worker-thread exception handling? (resolved with documented default, not separately asked) →
  A: **Mirror the current live-loop posture** — log the exception, sleep 5s, continue to the next
  work item; never exit the consumer.

## Terminology Glossary

- **Turn**: one full cycle of DeniDin processing an inbound message — understand it, optionally
  call tools, produce and send one reply (or deliberately stay silent).
- **Burst**: two or more text messages in the same chat where each later message arrives before
  the reply to the earlier one has been sent.
- **Coalescing / merging**: combining every text message in a burst into a single turn that
  produces one reply based on all of the combined text.
- **In-flight turn**: a turn that has started processing but has not yet sent its reply.
- **Interfering message**: a message that arrives while a turn for the same chat is in flight.
- **Discarded turn**: an in-flight turn that was interrupted by an interfering message; its reply
  is thrown away and replaced by the merged turn's reply.
- **Side effect**: a change the system made outside the conversation itself during a turn — an
  invoicing document created in the external system, or a ledger/reminder record written to local
  storage.
- **"Already done" journal**: the list of side effects a discarded turn completed before it was
  interrupted, carried into the merged turn so the model can account for them.
- **Reset**: clearing all burst/merge state for a chat, which happens the moment a reply is
  successfully sent (or the turn deliberately stays silent, or an error fallback is sent).
- **Feature flag OFF**: `config.feature_flags.realistic_message_handling = false` — the current
  strictly-serial, one-reply-per-message behavior, unchanged.

## Technology Choices

Detailed design (threading model, class seams, exact interruption points) is deferred to
`plan.md` / `research.md`. Constraints fixed now:

- **No new runtime dependency** is expected for this feature.
- **No `threading.Lock`/`RLock`/`Semaphore`/`queue.Queue`** without a separate explicit human
  approval (see Clarifications). A one-way cross-thread flag (`threading.Event`, or a plain bool
  in the `SessionCleanupThread` style) is permitted.
- The **replay/export player path** (`PlayerExportSource`) and the shared dispatch/handler code
  it runs through MUST remain synchronous and behaviorally unchanged — any producer/consumer or
  interruption machinery lives behind the **live** message source only.
- The turn-processing pipeline stays **single-threaded per chat** — at most one turn runs at a
  time for a given chat, preserving every existing "no parallel turns" assumption in session and
  approval handling.

## User Stories Reference

Authoritative user stories with full Given-When-Then acceptance criteria are in
**`user-stories.md`** (same directory). Quick reference:

- **US1 (P1)** — Benign additive burst: three quick messages that together form one request get
  one coherent reply.
- **US2 (P1)** — Feature flag OFF: identical burst produces today's three separate replies.
- **US3 (P2)** — Create-then-retract burst: a "do X" message followed immediately by "actually,
  don't" produces one reply, no half-done local action, and honest reporting of anything the
  external system already did.
- **US4 (P2)** — Media breaks the burst: an image sent mid-burst is answered on its own, and does
  not merge into or interrupt the text turn.
- **US5 (P3)** — Reset after reply: a message sent just after the reply lands starts a fresh turn,
  not a merge.
- **US6 (P3)** — Group chat, per-chat scope: a second person's message in a group merges with the
  in-flight turn.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Benign additive burst gets one coherent reply (Priority: P1)

A user sends "book a meeting", then "with Dana", then "tomorrow at 3" in quick succession, each
before the previous reply arrives. DeniDin replies once, having understood the full request.

**Why this priority**: This is the core value of the feature — the most common real-world burst
pattern, and the reason the feature exists.

**Independent Test**: Send three related text messages faster than the reply latency; verify
exactly one reply arrives and it reflects all three messages.

**Acceptance Scenarios**:

1. **Given** the feature flag is ON and no turn is in flight for a chat, **When** the user sends
   three text messages in quick succession (each before the prior reply is sent), **Then**
   DeniDin sends exactly one reply, based on the concatenation of all three messages in order.
2. **Given** such a burst, **When** the single reply is sent, **Then** the conversation history
   for that chat contains all three user messages as separate entries followed by exactly one
   assistant reply.
3. **Given** the first message's turn has already started calling the model, **When** the second
   message arrives, **Then** the first turn's reply is never sent to the user.

### User Story 2 - Feature flag OFF preserves today's behavior (Priority: P1)

With the flag disabled, the same burst produces three separate replies, exactly as today.

**Why this priority**: The feature must be safely disableable; the OFF path is the rollback and
must be provably identical to current behavior.

**Independent Test**: Disable the flag, send the same three-message burst, verify three separate
replies in message order.

**Acceptance Scenarios**:

1. **Given** the feature flag is OFF, **When** the user sends a three-message text burst, **Then**
   DeniDin sends three replies, one per message, in order — identical to current behavior.
2. **Given** the feature flag is OFF, **When** any message (text or media, 1:1 or group) is
   processed, **Then** the code path taken is the current one, with no burst/merge state created.

### User Story 3 - Create-then-retract burst is handled truthfully (Priority: P2)

A user sends "create a receipt for client X for 500 shekels", then immediately "actually, cancel
that" before the approval prompt returns. DeniDin sends one reply that reflects the retraction and
leaves no stale pending approval — and if the external system already created the document on its
own, the reply says so.

**Why this priority**: This is the "implications" half of the feature — without it, a burst could
leave half-completed actions or misrepresent what happened. High value but rarer than US1.

**Independent Test**: Send a document-creating request followed immediately by a retraction;
verify one final reply, no lingering pending approval, and — if the external system executed the
action server-side — an honest mention of it.

**Acceptance Scenarios**:

1. **Given** a turn that has proposed a local action (ledger/reminder) but not yet had it
   approved, **When** an interfering message arrives, **Then** the local action is not performed
   and no pending-approval prompt is left active for that chat.
2. **Given** a turn during which the external invoicing system already created a document
   server-side, **When** an interfering message arrives, **Then** the merged follow-up turn is
   given an "already done" note describing that document, and the single final reply reports it.
3. **Given** a discarded turn that had created a pending-approval prompt, **When** the merged turn
   completes, **Then** no approval prompt from the discarded turn can still be resolved by a later
   "yes"/"no" or button tap.
4. **Given** the merged turn's reply has been sent, **When** the user sends another message,
   **Then** the "already done" journal has been cleared and is not repeated.

### User Story 4 - A media message breaks the burst (Priority: P2)

While a text turn is in flight, the user sends an image. The image is processed on its own
existing path; it is not merged into the text turn and does not interrupt it.

**Why this priority**: Defines the scope boundary. Necessary for correctness but not the primary
value.

**Independent Test**: Start a slow text turn, send an image mid-turn; verify the text reply still
arrives (based only on the text) and the image gets its own separate reply.

**Acceptance Scenarios**:

1. **Given** a text turn is in flight for a chat, **When** a media message arrives for that chat,
   **Then** the media message is handled on its current media path and is not added to the text
   turn's combined text.
2. **Given** a text turn is in flight, **When** a media message arrives, **Then** the in-flight
   text turn is not discarded — its reply is still produced and sent (based only on the text
   messages).
3. **Given** the feature flag is ON, **When** a media message is the only message (no burst),
   **Then** it is processed exactly as today.

### User Story 5 - Reset after a reply starts a fresh turn (Priority: P3)

A message sent just after the previous reply landed is a new turn, not a continuation.

**Why this priority**: Defines the lifecycle boundary; low risk, easily verified.

**Acceptance Scenarios**:

1. **Given** a reply for a chat has just been successfully sent, **When** a new text message
   arrives, **Then** it starts a new turn and is not merged with the previous turn's content.
2. **Given** a turn that deliberately produced no reply, **When** a new message arrives, **Then**
   it also starts a fresh turn (the reset still happened).

### User Story 6 - Group chat merges per-chat (Priority: P3)

In a group, a message from a second person while a turn is in flight merges into that turn.

**Why this priority**: Consistency with the existing per-chat model; low incremental risk.

**Acceptance Scenarios**:

1. **Given** a turn is in flight for a group chat triggered by person A's message, **When** person
   B sends a text message in the same group before the reply is sent, **Then** B's message is
   merged into the same turn and the single reply accounts for both.
2. **Given** such a merged group turn, **When** the reply is sent, **Then** both A's and B's
   messages are persisted as separate user entries with one assistant reply.

### Edge Cases

- **Burst longer than the model's context budget**: the combined text is pruned to the role's
  token budget by the existing session-pruning logic; no new behavior.
- **Interfering message arrives in the microseconds between "reply generated" and "reply sent"**:
  treated as arriving before the send — the turn is discarded and merged. (If the send has
  already succeeded, it is a fresh turn.)
- **Interfering message during the "yes"-approval execution turn** (which runs with no retry after
  a prior double-charge incident): that turn is **non-interruptible** — it runs to completion and
  sends its reply. The interfering messages are held and coalesced into the next fresh turn.
- **The worker processing turns crashes on one turn**: it must log, sleep 5s, and continue
  processing later messages (mirroring the current live polling loop), never silently stop all
  message handling.
- **Rapid alternating text/media** (text, image, text, image): each media is its own turn; the
  text messages coalesce among themselves per the normal rule.
- **Process restart mid-burst**: in-memory burst state is lost. Messages already acknowledged to
  the upstream queue (ack-immediately, per clarify) are gone — not redelivered; messages not yet
  acknowledged are redelivered and handled as new messages. The lost-message window is the
  accepted residual risk of ack-immediately (documented in `research.md`).
- **Feature flag toggled while the app is running**: the flag is read once at the live entry
  point (process start). A toggle takes effect only on the next process restart, never
  mid-session.

## Requirements *(mandatory)*

### Functional Requirements

**Coalescing**

- **REQ-RMH-001**: When the feature flag is ON, the system MUST treat two or more text messages
  in the same chat, where each later one arrives before the reply to the earlier one has been
  sent, as a single turn.
- **REQ-RMH-002**: The merged turn MUST base its reply on the combined text of every message in
  the burst, concatenated in arrival order.
- **REQ-RMH-003**: The merged turn MUST produce exactly one reply, delivered as a reply to the
  last message of the burst.
- **REQ-RMH-004**: Every user message in a burst MUST be persisted individually to the
  conversation history; the merged turn MUST persist exactly one assistant reply.
- **REQ-RMH-005**: Coalescing scope MUST be per chat (`chat_id`), including group chats — a
  message from any participant merges with the in-flight turn for that chat.

**Interruption**

- **REQ-RMH-006**: When an interfering text message arrives, the system MUST stop the in-flight
  turn at the next safe point and MUST NOT send that turn's reply.
- **REQ-RMH-007**: The single in-flight model request MAY be allowed to return; the system MUST
  NOT attempt to kill it mid-request.
- **REQ-RMH-007a**: The "כן"/"לא" approval-**execution** turn (the one that runs with no
  automatic retry) MUST be non-interruptible: it always runs to completion and sends its reply.
  Text messages that arrive during it MUST be held and coalesced into the next fresh turn.
- **REQ-RMH-008**: After interruption, the system MUST NOT perform any DeniDin-local action the
  returned response requested (ledger capture, reminder create/modify/delete, ledger query).
- **REQ-RMH-009**: After interruption, the system MUST NOT create or leave active any
  pending-approval prompt (external-action approval or local-action approval) originating from the
  discarded turn.
- **REQ-RMH-010**: After interruption, the system MUST detect any external invoicing action the
  model executed server-side during the discarded turn and record it in the "already done"
  journal.
- **REQ-RMH-011**: The system MUST record in the "already done" journal any DeniDin-local side
  effect that was already durably written before the interruption (e.g. a ledger event file
  written mid-turn, or a reminder write already committed on a "yes"-execution turn).
- **REQ-RMH-012**: The interrupted turn's user message MUST still be persisted to history; no
  assistant reply for the discarded turn is persisted.

**Merged turn with journal**

- **REQ-RMH-013**: When a merged turn follows a discarded turn that had side effects, the system
  MUST make the "already done" journal available to the model via a **dedicated system-note
  field** on the request, assembled into the model instructions **after** the per-call date line
  (so the constitution prefix stays byte-stable for prompt caching). The journal MUST be built
  from structured side-effect records, not free model text.
- **REQ-RMH-014**: The model MUST be instructed (via `runtime_constitution.md`) to factor
  "already done" side effects into its single reply, report them to the user when relevant, and
  NOT re-attempt them.
- **REQ-RMH-015**: The "already done" journal for a chat MUST be cleared once the merged turn's
  reply has been successfully sent.

**Reset & lifecycle**

- **REQ-RMH-016**: All burst/merge/journal state for a chat MUST be cleared the moment a reply is
  successfully sent, OR the turn deliberately produces no reply, OR an error fallback message is
  sent.
- **REQ-RMH-017**: After a reset, the next message for that chat MUST start a fresh turn.
- **REQ-RMH-017a**: When a burst restarts a turn (a merged turn begins), the typing indicator
  MUST be re-fired for that chat.

**Media boundary**

- **REQ-RMH-018**: A media message (image/document/video/audio) MUST NOT be merged into a text
  burst.
- **REQ-RMH-019**: A media message arriving while a text turn is in flight MUST NOT discard or
  interrupt that text turn.
- **REQ-RMH-020**: A media message MUST be processed on its existing media path regardless of
  feature-flag state.

**Feature flag & safety**

- **REQ-RMH-021**: The behavior MUST be gated by `config.feature_flags.realistic_message_handling`
  (default `false`), read once at the live entry point (process start). When OFF, the
  message-processing code path MUST be byte-for-byte the current serial behavior, with no
  burst/merge state created.
- **REQ-RMH-021a**: When the feature flag is ON, the inbound notification MUST be acknowledged to
  the upstream queue immediately on receipt (as soon as the producer has read it and handed it to
  the intake coordinator), not after the turn completes. The resulting crash-window (an
  acknowledged message lost if the process dies before its turn finishes) MUST be documented as
  accepted residual risk in `research.md`.
- **REQ-RMH-022**: The replay/export player path MUST remain synchronous and behaviorally
  unchanged; interruption/coalescing machinery MUST NOT run on it.
- **REQ-RMH-023**: At most one turn MUST run at a time for a given chat.
- **REQ-RMH-024**: A failure while processing one turn MUST be logged and MUST NOT stop the
  processing of subsequent messages.
- **REQ-RMH-025**: The implementation MUST NOT introduce a `threading.Lock`/`RLock`/`Semaphore`/
  `queue.Queue` without separate explicit human approval; any residual concurrency risk that is
  accepted MUST be documented in `research.md`.

**Constitution boundary** (per METHODOLOGY.md's "every new tool-bearing / behavior feature needs
explicit constitution boundaries" rule)

- **REQ-RMH-026**: `config/runtime_constitution.md` MUST gain a section defining when the
  "interrupted / merged turn" context applies, that combined burst text is a single instruction,
  that a short trailing message still answers the most recent pending question in the same
  context, and that "already done" side effects must not be re-attempted.
- **REQ-RMH-027**: The existing tool-bearing sections of `runtime_constitution.md` (Ledger Event
  Recognition, Reminder Management, Invoice Management) MUST cross-reference the new section so an
  ambiguous merged turn in their context resolves correctly.

### Key Entities

- **Burst buffer** (per chat, in-memory, non-persistent): the ordered list of text messages
  received for a chat that have not yet been folded into a turn.
- **Active turn handle** (per chat, in-memory): a reference to the currently-running turn plus a
  one-way "interrupted" flag the producer can raise and the turn checks at safe points.
- **"Already done" journal** (per chat, in-memory, non-persistent): structured records of side
  effects completed by a discarded turn, consumed by the next merged turn (delivered via a
  dedicated request-level system-note field assembled after the date line) and cleared on its
  reply.
- **Feature flag** `feature_flags.realistic_message_handling` (config, boolean, default false).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the feature ON, a 3-message additive burst sent within the reply latency
  window produces exactly **one** reply that reflects all three messages (verified by acceptance
  test US1).
- **SC-002**: With the feature OFF, the identical burst produces exactly **three** replies in
  order — no observable behavior change from today (verified by acceptance test US2).
- **SC-003**: In a create-then-retract burst, **zero** stale pending approvals remain and **zero**
  un-asked-for local actions are performed; any external document the model created server-side is
  named in the final reply (verified by acceptance test US3).
- **SC-004**: A media message sent mid-burst always receives its own reply, and the concurrent
  text turn's reply is unaffected (verified by acceptance test US4).
- **SC-005**: Every burst message appears in the conversation history; the count of assistant
  replies for a burst is exactly one (verified by unit/integration tests).
- **SC-006**: A turn-processing failure is logged and the next inbound message is still processed
  (verified by unit test).
- **SC-007**: A burst arriving during a "כן"-approval execution turn never causes that turn to be
  discarded or its invoicing action to run twice; the burst is answered by one following turn
  (verified by integration test IT-2b).

## Open Questions — all resolved in `speckit.clarify` (Session 2026-08-30)

1. **Does a media message cancel an in-flight text turn?** → **RESOLVED: No.** The text turn
   continues; both replies are sent (text first, then media).
2. **Journal delivery mechanism** → **RESOLVED:** Dedicated system-note field on the request,
   assembled into instructions after the date line (prompt-cache-safe).
3. **Typing indicator on the merged turn** → **RESOLVED: Yes** — re-fire it when a burst restarts
   the turn.
4. **Acknowledgement timing** → **RESOLVED:** Acknowledge immediately on receipt (flag ON), for
   every message. Crash-window is accepted residual risk, documented in `research.md`.
5. **Interference during the "yes"-approval execution turn** → **RESOLVED:** That turn is
   non-interruptible — it always completes and sends its reply; interfering messages coalesce into
   the next fresh turn.
6. **Worker-thread exception handling** → **RESOLVED:** Mirror the live loop — log, sleep 5s,
   continue; never exit the consumer.
