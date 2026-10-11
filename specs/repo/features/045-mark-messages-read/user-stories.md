# User Stories: Mark Incoming Messages as Read (Blue Checkmarks)

**Feature**: 045-mark-messages-read
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec
approval until present.
**Status**: CLARIFIED (2026-08-07) — all blocking questions resolved, including a live-verified
confirmation that Green API's `readChat` produces real blue checkmarks. Ready for `plan.md`.

---

## Background (why this feature exists)

A real user request (2026-08-07): incoming WhatsApp messages sent to DeniDin's number never
show the sender their normal WhatsApp read-receipt feedback (blue double-checkmarks). The
requester wants DeniDin to actively mark messages as read so senders get that familiar
confirmation, the same as messaging a human.

## User Story 1 — Sender sees a read receipt after DeniDin processes their message (Priority: P1)

A client, godfather, or admin sends DeniDin a WhatsApp message. After DeniDin receives and
processes it, the sender's WhatsApp client shows blue checkmarks on that message, same as if
a human recipient had opened and read it.

**Why this priority**: This is the entire ask — everything else here is a refinement or edge
case of this one behavior.

**Independent Test**: Send a real WhatsApp text message to DeniDin's number from a real device.
Observe (on the sending device) whether the message's checkmarks turn blue immediately after
receipt. Already live-verified once during clarify (2026-08-07): a real `readChat` call against
DeniDin dev's Green API instance, targeting a specific real message by `idMessage`, produced a
visually-confirmed blue checkmark on the sender's device — this test should reproduce the same
result once implemented in the actual message flow.

**Acceptance Scenarios**:

1. **Given** a client sends DeniDin a text message, **When** the inbound webhook is received
   and parsed (fires immediately, before AI processing — Q2 resolved), **Then** the sender's
   WhatsApp app shows that specific message as read (blue checkmarks).
2. **Given** the read-receipt call is always scoped to the specific message's real `idMessage`
   (Q3 resolved — never omitted), **When** it fires, **Then** it does NOT mark any other
   message in the same chat as read, only the one just received.
3. **Given** the sender is a blocked user, **When** their message is received, **Then** no
   read-receipt call fires (Q4 resolved — consistent with DeniDin already ignoring blocked
   users' messages).

## User Story 2 — Read receipt still sent when DeniDin does not reply in text (Priority: P2)

DeniDin sometimes processes a message but sends no textual reply — e.g. the `[[NO_REPLY]]`
group-etiquette sentinel (Feature 039). This story asks whether the read receipt should still
fire in that case, independent of whether a reply is sent.

**Why this priority**: A real edge case given DeniDin's existing no-reply behavior, but
secondary to the core ask.

**Independent Test**: Trigger a message in a group chat that DeniDin's model judges should get
`[[NO_REPLY]]` (per `config/runtime_constitution.md`'s "Group Conversation Etiquette"). Confirm
whether the read receipt still appears on the sender's device despite no textual reply being
sent.

**Acceptance Scenarios**:

1. **Given** a message that resolves to `[[NO_REPLY]]` (no textual reply sent), **When**
   DeniDin has finished processing it, **Then** — **open question**: should the read receipt
   still fire? (Not yet resolved; likely "yes, since the message genuinely was processed" but
   needs explicit confirmation alongside Q2/Q4 in spec.md.)

---

## Explicitly Out of Scope

- Read receipts for DeniDin's own outbound messages (not requested).
- Typing indicators (a distinct, unrequested WhatsApp UI affordance).
