# User Stories: WhatsApp Reply/Quote Reference Resolution (for Ledger Event Cancellations)

**Feature**: 032-whatsapp-reply-reference-resolution
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval until present.
**Status**: DRAFT — scaffolded 2026-07-30, pending `speckit.clarify` before `spec.md` can be
finalized. See spec.md's "Open Questions (blocking clarify)" section — several of this
document's acceptance scenarios below have unresolved dependencies flagged inline.

---

## Background (why this feature exists)

A real user request (2026-07-30): "למחוק"/"לבטל" ("delete"/"cancel") sent as a WhatsApp
**reply** (quote) to an earlier message that stated a fee agreement, meaning "cancel THAT
agreement." Investigated 2026-07-30 and confirmed **not supported today**:

- Green API's webhook does carry quote/reply data (`messageData.extendedTextMessageData.quotedMessage`,
  keyed by `stanzaId`) — typed in `src/models/green_api.py` but never read anywhere.
- `bugfix-008` deliberately flattens quoted/forwarded messages to plain body text (correct
  fix for that bug, at the cost of discarding reply linkage — a known, intentional trade-off
  at the time, not a defect of that fix).
- DeniDin doesn't capture Green API's own `idMessage` for any message today — its internal
  `message_id` is a freshly-generated UUID, unrelated to Green API's own ID scheme that
  `stanzaId` would reference. Even if `stanzaId` were captured, there's currently no way to
  resolve it back to one of DeniDin's own stored `Message` records.
- Feature 033 (Ledger Event Persistence) already gives every `LedgerEvent` a real `event_id`/
  `agreement_id`, and every `Message` a `ledger_event_ids` back-link — so once a WhatsApp
  reply can be resolved to the internal `Message` it quotes, resolving from there to the real
  `agreement_id`/`event_id` to cancel is straightforward (existing infrastructure).
- `capture_ledger_event`'s existing `replaces_hint` → `replaced_event_id` mechanism (Feature
  033, REQ-DATA-002) always writes the literal placeholder `"צריך למצוא"` ("need to find") —
  because DeniDin has never been able to resolve a hint to a real prior id. This feature is
  what would finally let that placeholder become a real resolved id, in the one case where
  resolution is actually possible: the user directly replying to the original message.

## User Story 1 — Cancelling an agreement by replying "לבטל"/"למחוק" to its original message (Priority: P1)

A godfather/admin previously sent a message that resulted in a captured fee-agreement event.
Later, they reply directly to that original WhatsApp message with "לבטל" or "למחוק". DeniDin
should recognize this as a cancellation of the specific agreement the replied-to message
created, and persist a cancellation event correctly linked to it — not a vague, unresolvable
`"צריך למצוא"` placeholder.

**Why this priority**: This is the concrete, real-life scenario that motivated the feature;
everything else here exists to make this one flow possible.

**Independent Test**: Capture a fee-agreement event from message A. Reply to message A (using
Green API's real reply/quote mechanism) with "לבטל". Verify a new `LedgerEvent` is persisted
with `event_subtype=ביטול` and `replaced_event_id` set to the REAL prior `event_id` (or
`agreement_id` — **open question, see spec.md**), not the `"צריך למצוא"` placeholder.

**Router/Integration Requirement** (partially known, needs `speckit.plan`):
- `WhatsAppHandler`/`WhatsAppMessage.from_notification` must capture `quotedMessage.stanzaId`
  from the webhook when present (currently discarded).
- Every message DeniDin stores (or at minimum, every message capable of being later
  referenced) must also carry Green API's own `idMessage`, so a future reply's `stanzaId` can
  be matched against it. **Open question**: does this mean storing `idMessage` on every
  `Message`, or only on ones that produced a ledger event? See spec.md.
- A resolution step, given a `stanzaId`, that finds the corresponding stored `Message` (by its
  Green API `idMessage`) and, via that `Message.ledger_event_ids`, the real captured
  `LedgerEvent`(s) to reference.
- This resolved reference needs to reach `capture_ledger_event`'s classification call somehow
  — **open question**: is it injected into the AI's prompt/instructions as context ("this
  message replies to a message that captured agreement X"), or resolved entirely in code
  after the AI just recognizes "this is a cancellation request" generically? See spec.md.

**Acceptance Scenarios**:

1. **Given** message A ("X - הצעת שכר טרחה: 9,000 ₪") was sent and captured a `LedgerEvent`
   with some `event_id`/`agreement_id`, **When** the user replies to message A (real WhatsApp
   quote/reply) with "לבטל", **Then** a new `LedgerEvent` is persisted with
   `event_subtype=ביטול`, `source_type=הסכם`, and a reference back to message A's captured
   event that is a REAL id, not the `"צריך למצוא"` placeholder.
2. **Given** the same scenario, **When** the cancellation event is inspected, **Then**
   `client_name` matches message A's client (resolved from the referenced agreement, not
   re-guessed from "לבטל" alone, which carries no client information itself).
3. **Given** a reply to a message that did NOT capture any ledger event (ordinary chatter),
   **When** the user replies "לבטל" to it, **Then** no cancellation event is captured (there
   is nothing to cancel) — **open question**: what, if anything, should DeniDin reply to the
   user in this case? See spec.md.
4. **Given** "לבטל"/"למחוק" sent WITHOUT being a reply to anything (no quote), **When**
   processed, **Then** behavior is UNCHANGED from today (out of scope for this feature —
   resolving a cancellation with no reply-context at all is a separate, harder problem, not
   addressed here).

---

## User Story 2 (tentative, may be dropped or merged into US1 at `speckit.clarify`) — Non-ledger replies are unaffected

Capturing `stanzaId`/`idMessage` is new plumbing that touches every message, not just
cancellation ones — this story exists to make sure ordinary reply usage (replying to a normal
conversational message, unrelated to any ledger event) doesn't regress.

**Why this priority**: Regression-prevention for existing behavior, not new capability.

**Independent Test**: Reply to an ordinary conversational message with unrelated new text;
verify DeniDin responds normally, with no ledger-event side effects.

**Acceptance Scenarios**:

1. **Given** an ordinary prior message with no captured ledger event, **When** the user
   replies to it with unrelated text, **Then** DeniDin's response is unaffected by the new
   `stanzaId`/`idMessage` plumbing — same behavior as before this feature.

---

## Explicitly Out of Scope (per user instruction, 2026-07-30)

- **Modification (`לעדכן`)** — "modify can be relaxed for now." Not covered by this feature;
  a future addition once cancellation is proven out.
- Resolving a cancellation/reference request that is NOT a direct WhatsApp reply (e.g. "בטל
  את ההסכם עם X" with no quote) — a fundamentally different, harder resolution problem
  (name/context matching against history) that this feature does not attempt.
