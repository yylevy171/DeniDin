# User Stories: Realistic Message Handling — Multiple Interfering Messages

**Feature Branch**: `feature/067-realistic-message-handling`
**Related Spec**: `spec.md` (same directory)

---

## System flow (all stories)

```
Green API queue
  → [live source only] background producer: receive → read-receipt hook → acknowledge → hand raw body to intake coordinator
      → intake coordinator (per chat_id):
          - text, no in-flight turn         → new single-message work item, mark turn active
          - text, in-flight turn             → raise the turn's "interrupted" flag; append to the chat's burst buffer
          - text, buffer present, no turn    → append to buffer (consumer will fold it in)
          - media / non-text / button-tap    → own work item, no merge, does NOT interrupt an active text turn
  → single consumer worker (one at a time): pull work item → today's dispatch_notification → handler → ai_handler.get_response(cancel_check=...) → send_response
      - on cancel_check True at a round boundary: stop, build "already done" journal, return a cancelled result (no reply sent)
      - consumer stashes the journal as carryover[chat_id], then folds the burst buffer into ONE merged turn
  → on successful send (or deliberate no-reply, or error fallback sent): reset burst buffer + active turn + carryover for that chat
```

**Routing / dispatcher requirements**:

- The live message source (`GreenAPIMessageSource` / `DeniDinGreenAPIBot`) is the ONLY place the
  producer/consumer split and interruption machinery exist. `PlayerExportSource.start(dispatch)`
  and the shared `dispatch_notification` / handler code stay synchronous.
- `HANDLER_REGISTRY` in `denidin.py` MUST remain exactly the current 8 message types — the intake
  coordinator sits upstream of dispatch and does not add a message type. The immutable test
  `test_denidin_dispatch.py::TestHandlerRegistryCompleteness` MUST stay green untouched.
- `interactiveButtonsResponse` stays special-cased in `dispatch_notification` (not in the
  registry); the coordinator treats a button tap as a non-mergeable own work item.
- `ai_handler.get_response` gains one new optional parameter, `cancel_check: Callable[[], bool]`,
  defaulting to `lambda: False` so every existing caller (tests, player) is unaffected.
- The "already done" journal reaches the model via a new optional request-level system-note field
  (default empty), assembled into `instructions` AFTER the per-call date line — the constitution
  prefix stays byte-identical so prompt caching is unaffected. Every existing caller that omits it
  is unchanged.
- The "כן"/"לא"-approval execution turn is non-interruptible: `cancel_check` is NOT threaded into
  the approval-resolution path (`_resolve_pending_approval` / `_call_openai_approval_api`); a
  burst arriving during it is buffered and coalesced into the next fresh turn.
- Inbound notifications are acknowledged to the upstream queue immediately on receipt when the
  flag is ON (producer acks before handing to the coordinator), not after the turn.
- The feature flag `config.feature_flags.realistic_message_handling` is read once at the live
  entry point (`__main__`) to decide whether `run_forever()` runs the current single-loop body or
  the producer/consumer body. When OFF, no coordinator is constructed.

---

### User Story 1 - Benign additive burst gets one coherent reply (Priority: P1)

As a user of DeniDin, I want to send a request across several quick messages and get one sensible
reply, so I don't get three disjointed answers to what was really one question.

**Why this priority**: The most common real-world burst pattern and the entire reason the feature
exists.

**Independent Test**: With the flag ON, send "קבע פגישה", then "עם דנה", then "מחר ב-3" within a
couple of seconds; verify exactly one reply arrives and it addresses all three.

**Acceptance Scenarios**:

1. **Given** the feature flag is ON and no turn is in flight for chat C, **When** the user sends
   three text messages in C in quick succession, each before the previous reply is sent, **Then**
   DeniDin sends exactly one reply to C, based on all three messages concatenated in arrival
   order.
2. **Given** that burst, **When** the reply is sent, **Then** C's conversation history contains
   the three user messages as three separate entries, followed by exactly one assistant reply.
3. **Given** the first message's turn has already issued its model call, **When** the second
   message arrives, **Then** the first turn's generated reply is never sent to C.
4. **Given** the first turn's model call has not yet been issued when the second and third
   messages arrive, **When** the consumer picks up the work, **Then** only one model call is made
   and it contains all three messages.

---

### User Story 2 - Feature flag OFF preserves today's behavior (Priority: P1)

As the operator, I want to be able to turn this feature off and get exactly today's behavior, so
it is safely reversible.

**Why this priority**: The OFF path is the rollback and must be provably identical to current
behavior.

**Independent Test**: Set `feature_flags.realistic_message_handling = false`, send the same
three-message burst, verify three replies in order.

**Acceptance Scenarios**:

1. **Given** the feature flag is OFF, **When** the user sends a three-message text burst in chat
   C, **Then** DeniDin sends three replies, one per message, in message order.
2. **Given** the flag is OFF, **When** the app starts, **Then** no intake coordinator or consumer
   worker is constructed and `run_forever()` runs its current single-loop body.
3. **Given** the flag is OFF, **When** any inbound notification (text/media/button, 1:1/group) is
   handled, **Then** the observable outcome is identical to the pre-feature codebase.

---

### User Story 3 - Create-then-retract burst is handled truthfully (Priority: P2)

As a godfather/admin user, I want to be able to change my mind mid-request without DeniDin
half-doing the first thing or lying about what happened, so I can trust it with real invoicing
actions.

**Why this priority**: The "implications" half of the feature — prevents partial actions and
false reporting. High value, less frequent than US1.

**Independent Test**: Send "צור קבלה ללקוח X על 500 שקל", then "בעצם תבטל" before the approval
prompt returns; verify one final reply, no lingering pending approval, and honest reporting of any
document the external system created on its own.

**Acceptance Scenarios**:

1. **Given** an in-flight turn whose returned model response asks for a DeniDin-local action
   (record a ledger event / create a reminder), **When** an interfering message arrives before
   that action runs, **Then** the local action is not performed.
2. **Given** an in-flight turn that created (or would create) a pending-approval prompt, **When**
   an interfering message arrives, **Then** after the merged turn completes there is no pending
   approval from the discarded turn, and a later "כן"/"לא" or button tap cannot resolve one.
3. **Given** an in-flight turn during which the external invoicing system created a document
   server-side (the model called the tool itself), **When** an interfering message arrives,
   **Then** the merged follow-up turn receives an "already done" note naming that document, and
   the single final reply reports it to the user.
4. **Given** a merged turn that reported an "already done" side effect, **When** its reply is
   sent and the user sends a further message, **Then** the "already done" journal has been cleared
   and the side effect is not mentioned again unprompted.
5. **Given** an interfering message arrives during the "כן"/"לא"-approval execution turn (which
   runs with no automatic retry), **When** that turn is running, **Then** it runs to completion
   and sends its reply uninterrupted, and the interfering message(s) are held and coalesced into
   the next fresh turn (no journal needed — nothing was discarded).
6. **Given** the interrupted turn, **When** it is discarded, **Then** its triggering user message
   is still saved to history and no assistant reply for it is saved.

---

### User Story 4 - A media message breaks the burst (Priority: P2)

As a user, I want an image I send to always get looked at, even if I sent it right after some text
messages, so media is never silently swallowed into a text turn.

**Why this priority**: Defines the scope boundary; necessary for correctness.

**Independent Test**: Start a slow text turn, send an image mid-turn; verify the text reply
arrives (based only on the text) and the image gets its own separate reply.

**Acceptance Scenarios**:

1. **Given** a text turn is in flight for chat C, **When** a media message arrives for C, **Then**
   it is routed to the existing media handler and is not added to the text turn's combined text.
2. **Given** a text turn is in flight for C, **When** a media message arrives for C, **Then** the
   in-flight text turn is not discarded — its reply is still produced and sent, based only on the
   text messages.
3. **Given** the feature flag is ON, **When** a lone media message arrives (no burst in
   progress), **Then** it is handled exactly as today.
4. **Given** a media message and then a text message arrive while a text turn is in flight,
   **When** processing completes, **Then** the media message got its own reply and the text
   message merged into the text turn.

---

### User Story 5 - Reset after a reply starts a fresh turn (Priority: P3)

As a user, I want a message I send after getting a reply to be treated as a new question, so a
follow-up thought isn't glued onto the previous answer.

**Why this priority**: Lifecycle boundary; low risk, easily verified.

**Acceptance Scenarios**:

1. **Given** a reply for chat C has just been successfully sent, **When** a new text message
   arrives for C, **Then** it starts a new turn and is not merged with the previous turn's
   content or journal.
2. **Given** a turn that deliberately produced no reply (silent turn), **When** a new message
   arrives for C, **Then** the reset still happened and the new message starts a fresh turn.
3. **Given** a turn that ended in an error and sent the fallback error message, **When** a new
   message arrives, **Then** it starts a fresh turn.

---

### User Story 6 - Group chat merges per-chat (Priority: P3)

As a participant in a group with DeniDin, I want everyone's quick messages during one exchange to
be understood together, matching how the group already shares one conversation with DeniDin.

**Why this priority**: Consistency with the existing per-chat model; low incremental risk.

**Acceptance Scenarios**:

1. **Given** a turn is in flight for group chat G, triggered by person A's message, **When**
   person B sends a text message in G before the reply is sent, **Then** B's message is merged
   into the same turn and the single reply accounts for both A's and B's messages.
2. **Given** such a merged group turn, **When** the reply is sent, **Then** both A's and B's
   messages are persisted as separate user entries, followed by one assistant reply.
3. **Given** the merged group turn, **When** RBAC is resolved, **Then** the existing
   most-permissive-member resolution for the group is used, unchanged.

---

## Integration test requirements

- **IT-1 (US1/US2)**: Drive `initialize_app` with a fake message source that feeds a scripted
  three-message text burst and a fake OpenAI client whose first response is deliberately slow.
  Flag ON → assert exactly one outbound send containing all three messages, three user history
  entries, one assistant entry. Flag OFF → assert three outbound sends in order.
- **IT-2 (US3)**: Same harness; the fake OpenAI first response contains a completed server-side
  MCP call and a proposed local ledger action. Interfere before the local action runs. Assert:
  no ledger file written for the discarded turn, no pending approval remains, the merged turn's
  request carries the "already done" note in its system-note field (assembled after the date
  line, constitution prefix unchanged), one final send.
- **IT-2b (US3 scenario 5)**: A burst arrives during a "כן"-approval execution turn. Assert the
  approval turn completes and sends its own reply uninterrupted, and the burst messages are then
  processed as one following turn.
- **IT-3 (US4)**: Scripted burst of text, then a media notification, then text, while the first
  model response is slow. Assert the media notification went through the media handler and the
  two text messages coalesced into one text reply.
- **IT-4 (US5)**: Two messages separated by a completed send. Assert two independent turns, no
  carryover between them.
- **IT-5 (player contract)**: `test_message_source.py` — `PlayerExportSource.start(dispatch)`
  still calls `dispatch` once per notification synchronously in order, unchanged.
- **IT-6 (registry immutability)**: `test_denidin_dispatch.py::TestHandlerRegistryCompleteness`
  still passes with no edit.
