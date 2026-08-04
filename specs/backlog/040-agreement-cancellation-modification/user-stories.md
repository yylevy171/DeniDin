# User Stories: Agreement Cancellation & Modification via Reply Reference

**Feature**: 040-agreement-cancellation-modification
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval until present.
**Status**: DRAFT — split out of Feature 032 on 2026-08-04, pending `speckit.clarify`. See
spec.md's "Open Questions" section — several scenarios below have unresolved dependencies
flagged inline.

---

## Background (why this feature exists)

A real user request (2026-07-30): "למחוק"/"לבטל" ("delete"/"cancel") sent as a WhatsApp
**reply** (quote) to an earlier message that stated a fee agreement, meaning "cancel THAT
agreement." Feature 032 provides the underlying capability to resolve such a reply back to
the original message (and its `ledger_event_ids`, if any); this feature is what interprets
that resolved reference as a cancellation or modification request and acts on it.

- Feature 033 (Ledger Event Persistence) already gives every `LedgerEvent` a real `event_id`/
  `agreement_id`, and every `Message` a `ledger_event_ids` back-link — so once Feature 032
  resolves a reply to the internal `Message` it quotes, resolving from there to the real
  `agreement_id`/`event_id` to cancel/modify is straightforward (existing infrastructure).
- `capture_ledger_event`'s existing `replaces_hint` → `replaced_event_id` mechanism (Feature
  033, REQ-DATA-002) always writes the literal placeholder `"צריך למצוא"` ("need to find") —
  because DeniDin has never been able to resolve a hint to a real prior id. This feature is
  what finally lets that placeholder become a real resolved id, in the one case resolution is
  actually possible: the user directly replying to the original message.

## User Story 1 — Cancelling an agreement by replying "לבטל"/"למחוק" to its original message (Priority: P1)

A godfather/admin previously sent a message that resulted in a captured fee-agreement event.
Later, they reply directly to that original WhatsApp message with "לבטל" or "למחוק". DeniDin
should recognize this as a cancellation of the specific agreement the replied-to message
created (using Feature 032's resolved reference), and persist a cancellation event correctly
linked to it — not a vague, unresolvable `"צריך למצוא"` placeholder.

**Why this priority**: This is the concrete, real-life scenario that motivated the original
032 draft; everything else here exists to make this one flow possible.

**Independent Test**: Capture a fee-agreement event from message A. Reply to message A (using
Green API's real reply/quote mechanism) with "לבטל". Verify a new `LedgerEvent` is persisted
with `event_subtype=ביטול` and `replaced_event_id` set to the REAL prior `event_id` (resolved
Q4: specific `event_id`, not `agreement_id`), not the `"צריך למצוא"` placeholder.

**Router/Integration Requirement**:
- Consumes Feature 032's resolved reference (original message's content/metadata +
  `ledger_event_ids` if present) — does not itself do `stanzaId`/`idMessage` resolution.
- When the resolved reference has `ledger_event_ids`, that reference reaches
  `capture_ledger_event`'s classification call as injected prompt context ("this message
  replies to a message that captured agreement X"), consistent with Feature 032's Q2
  resolution (AI classifies, code never guesses semantics) and this codebase's existing
  pattern.
- No RBAC restriction beyond existing `capture_ledger_event` gating (godfather/admin) — Q6
  resolved 2026-08-04, no original-creator restriction.

**Acceptance Scenarios**:

1. **Given** message A ("X - הצעת שכר טרחה: 9,000 ₪") was sent and captured a `LedgerEvent`
   with some `event_id`/`agreement_id`, **When** the user replies to message A (real WhatsApp
   quote/reply) with "לבטל", **Then** a new `LedgerEvent` is persisted with
   `event_subtype=ביטול`, `source_type=הסכם`, and `replaced_event_id` set to message A's real
   `event_id`, not the `"צריך למצוא"` placeholder.
2. **Given** the same scenario, **When** the cancellation event is inspected, **Then**
   `client_name` matches message A's client (resolved from the referenced agreement, not
   re-guessed from "לבטל" alone, which carries no client information itself).
3. **Given** a reply to a message that resolves (per Feature 032) but has no
   `ledger_event_ids` (ordinary chatter, nothing to cancel), **When** the user replies "לבטל"
   to it, **Then** no cancellation event is captured — **open question (Q5)**: what, if
   anything, should DeniDin reply to the user in this case? See spec.md.
4. **Given** "לבטל"/"למחוק" sent WITHOUT being a reply to anything (no quote, so Feature 032
   has nothing to resolve), **When** processed, **Then** behavior is UNCHANGED from today
   (out of scope — resolving a cancellation with no reply-context at all is a separate,
   harder problem, not addressed here or by Feature 032).
5. **Open question (Q3)**: **Given** message A captured a MULTI-COMPONENT agreement (Feature
   033 US3 — multiple linked `LedgerEvent`s), **When** the user replies "לבטל" to message A,
   **Then** — undecided: cancel all components, or ask which one? See spec.md.

---

## User Story 2 — Modifying ("לעדכן") a previously captured agreement (Priority: P2)

A godfather/admin replies to a message that captured an agreement, with "לעדכן" (update) plus
new details (e.g. a new amount). DeniDin should recognize this as a modification of the
specific agreement the replied-to message created, using Feature 032's resolved reference.

**Why this priority**: Deferred in the original 032 draft ("modify can be relaxed for now")
but included here as a real, if lower-priority, story rather than dropped entirely.

**Independent Test**: Capture a fee-agreement event from message A. Reply to message A with
"לעדכן ל-10,000 ₪" (or similar). Verify a new `LedgerEvent` is persisted reflecting the
update, correctly linked back to message A's original event.

**Open questions (block this story's scenarios from being finalized)**:
- **Q7**: What exactly can be modified — amount only, or any field from the original capture?
  Full replace or partial patch?
- **Q8**: Does a modification produce its own `event_subtype` (e.g. `עדכון`), referencing
  `replaced_event_id` the same way cancellation does? Needs confirmation against real
  `Events.csv` convention.

**Acceptance Scenarios** (draft — pending Q7/Q8):

1. **Given** message A captured an agreement, **When** the user replies "לעדכן" with new
   details, **Then** a new `LedgerEvent` is persisted reflecting the update, with
   `replaced_event_id` pointing at message A's real `event_id` — **exact `event_subtype`/
   field semantics: open, see Q7/Q8**.

---

## User Story 3 — Reply-cancellation to a non-ledger message is a no-op (regression guard) (Priority: P2)

Replying "לבטל"/"למחוק" to a message that Feature 032 resolves, but which has no
`ledger_event_ids`, must not produce any spurious `LedgerEvent` or crash.

**Why this priority**: Regression-prevention — this feature must degrade gracefully when
there is nothing to act on, not just when there's nothing to resolve at all (that case is
Feature 032's US2).

**Independent Test**: Reply "לבטל" to an ordinary conversational message (no captured ledger
event); verify no `LedgerEvent` is created and DeniDin's response is otherwise normal.

**Acceptance Scenarios**:

1. **Given** an ordinary prior message with no captured ledger event, **When** the user
   replies to it with "לבטל"/"למחוק", **Then** no `LedgerEvent` side effects occur — same as
   Scenario 3 under US1, restated here as its own regression guard.

---

## Explicitly Out of Scope

- Resolving a cancellation/modification request that is NOT a direct WhatsApp reply (e.g.
  "בטל את ההסכם עם X" with no quote) — a fundamentally different, harder resolution problem
  (name/context matching against history) that neither this feature nor Feature 032 attempts.
