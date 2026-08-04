# User Stories: WhatsApp Reply/Quote Reference Resolution

**Feature**: 032-whatsapp-reply-reference-resolution
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval until present.
**Status**: DRAFT — rescoped 2026-08-04 to general reply-resolution infrastructure only.
Agreement-specific cancellation/modification user stories moved to Feature 040 (see that
feature's `user-stories.md`).

---

## Background (why this feature exists)

A real user request (2026-07-30) — replying "לבטל"/"למחוק" to an earlier message that stated
a fee agreement, meaning "cancel that agreement" — surfaced that WhatsApp reply/quote data is
discarded entirely today:

- Green API's webhook does carry quote/reply data (`messageData.extendedTextMessageData.quotedMessage`,
  keyed by `stanzaId`) — typed in `src/models/green_api.py` but never read anywhere.
- `bugfix-008` deliberately flattens quoted/forwarded messages to plain body text (correct
  fix for that bug, at the cost of discarding reply linkage — a known, intentional trade-off
  at the time, not a defect of that fix).
- DeniDin doesn't capture Green API's own `idMessage` for any message today — its internal
  `message_id` is a freshly-generated UUID, unrelated to Green API's own ID scheme that
  `stanzaId` would reference. Even if `stanzaId` were captured, there's currently no way to
  resolve it back to one of DeniDin's own stored `Message` records.

That original cancellation use case motivated this work but is **not** this feature's scope —
this feature only builds the general capability (resolve a reply to the message it quotes);
what a caller does with a resolved reference (e.g. cancel an agreement) is Feature 040.

## User Story 1 — Resolve a WhatsApp reply to the internal message it quotes (Priority: P1)

Any user replies (real WhatsApp quote/reply) to any earlier message DeniDin sent or received.
DeniDin should recognize this as a reply, capture the quoted `stanzaId`, and resolve it back
to its own internally stored `Message` record for that earlier message — making that message's
content, sender, and timestamp (and, if present, its `ledger_event_ids`, passed through as-is
with no interpretation) available as context to whatever consumes the reply next.

**Why this priority**: This is the foundational capability everything else (Feature 040's
cancellation/modification flows, and any future reply-aware feature) depends on.

**Independent Test**: Send message A. Reply to message A (using Green API's real reply/quote
mechanism) with arbitrary new text. Verify the resulting `Message` record for the reply
carries a resolved reference to message A's stored `Message` (matched via `idMessage`/
`stanzaId`), independent of whether message A ever produced a ledger event.

**Router/Integration Requirement** (partially known, needs `speckit.plan`):
- `WhatsAppHandler`/`WhatsAppMessage.from_notification` must capture `quotedMessage.stanzaId`
  from the webhook when present (currently discarded).
- Every message DeniDin sends/stores must also carry Green API's own `idMessage`, so a future
  reply's `stanzaId` can be matched against it (Q1, resolved: every message, not just
  ledger-event-producing ones).
- A resolution step, given a `stanzaId`, that finds the corresponding stored `Message` (by its
  Green API `idMessage`) and surfaces its content/metadata (plus `ledger_event_ids` if
  present, unconditionally — this feature does not filter or interpret them).

**Acceptance Scenarios**:

1. **Given** message A was sent/received and stored with its `idMessage`, **When** a later
   message arrives as a real WhatsApp quote/reply to message A, **Then** the reply's stored
   `Message` record carries a resolved reference to message A (its content, sender,
   timestamp).
2. **Given** message A happens to have `ledger_event_ids` (it captured a ledger event),
   **When** a reply to message A is resolved, **Then** message A's `ledger_event_ids` are
   included in the resolved reference as pass-through data — this feature does not act on or
   interpret them (that's Feature 040's job).
3. **Given** message A has no `ledger_event_ids` (ordinary conversational message), **When** a
   reply to message A is resolved, **Then** resolution still succeeds — content/metadata only,
   no ledger data attached, and no error.
4. **Given** a reply whose `stanzaId` does not match any stored `Message` (e.g. message A
   predates this feature, or was never captured), **When** processed, **Then** resolution
   fails gracefully — no crash, and the reply is treated as an ordinary new message.

---

## User Story 2 — Non-reply messages are unaffected (regression guard) (Priority: P2)

Capturing `stanzaId`/`idMessage` is new plumbing that touches every message, not just replies
— this story exists to make sure ordinary (non-reply) message handling doesn't regress.

**Why this priority**: Regression-prevention for existing behavior, not new capability.

**Independent Test**: Send an ordinary message with no quote/reply; verify DeniDin's behavior
is unchanged from before this feature.

**Acceptance Scenarios**:

1. **Given** an ordinary message with no `quotedMessage`, **When** processed, **Then**
   DeniDin's behavior is identical to before this feature (no resolution attempted, no new
   side effects).

---

## Moved to Feature 040 (`specs/backlog/040-agreement-cancellation-modification/`)

The following, from this spec's original draft, are now Feature 040's user stories and are no
longer part of 032:

- Cancelling a fee agreement by replying "לבטל"/"למחוק" to the message that captured it.
- Modifying ("לעדכן") a previously captured agreement.
- `replaced_event_id` resolution to a real `event_id` (replacing the `"צריך למצוא"`
  placeholder).
- RBAC questions specific to who may cancel/modify an agreement via reply.
