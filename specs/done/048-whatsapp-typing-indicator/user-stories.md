# User Stories: WhatsApp Typing Indicator While Processing

**Feature**: 048-whatsapp-typing-indicator
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec
approval until present.
**Status**: DONE — merged to master (2026-08-13). Single-call design (final, see spec.md Q1
for the reverted renewal-loop attempt). Media support (US4) added same day.

---

## Background (why this feature exists)

DeniDin currently gives no feedback in WhatsApp while it's working on a reply — nothing happens
visually between a user sending a message and the reply landing, which can be several seconds
for a plain text turn and much longer for tool-calling/vision-heavy turns. The request is for
DeniDin to trigger WhatsApp's native typing indicator while actively processing — and,
symmetrically, to stop the instant it's DeniDin's own message that's waiting on the user, not
the other way around.

## User Story 1 — Sender sees typing dots only while it is DeniDin's turn to respond (Priority: P1)

A client, godfather, or admin sends DeniDin a text (or contact-card) message. While DeniDin is
processing it, the sender's WhatsApp client shows the typing indicator. The moment DeniDin sends
*any* outbound message — a final reply, an interim clarification question, or a pending-approval
request mid-flow (e.g. during a Morning MCP invoice flow) — the indicator stops, because it is
now the user's turn: DeniDin is waiting on them for a reply, clarification, or approval, and must
not look like it's still composing something.

**Why this priority**: This is the entire ask — everything else here is a refinement or edge
case of this one behavior. The "DeniDin's turn only" framing is the key clarification that
resolves what would otherwise be ambiguous across multi-message exchanges (e.g. an approval
flow with several back-and-forth turns).

**Independent Test**: Send a real WhatsApp text message to DeniDin's number from a real device.
Observe (on the sending device) that the typing indicator appears shortly after sending and
disappears the moment any reply — including an interim one — arrives, never lingering into a
window where DeniDin is actually waiting on the user.

**Acceptance Scenarios**:

1. **Given** a client sends DeniDin a text message, **When** DeniDin begins processing the
   conversational turn (after RBAC/session resolution, before the OpenAI call), **Then** the
   sender's WhatsApp app shows the typing indicator.
2. **Given** the typing indicator is showing, **When** DeniDin sends its reply, **Then** the
   indicator stops — no further `sendTyping` call fires until the user's next inbound message.
3. **Given** a turn where DeniDin sends an interim message (e.g. a pending-approval request
   partway through a Morning MCP flow) rather than a final answer, **When** that interim message
   is sent, **Then** the typing indicator stops exactly the same as it would for a final reply —
   DeniDin does not appear to keep "typing" while it's actually waiting on the user's approval.
4. **Given** DeniDin has sent a pending-approval request and is waiting on the user, **When**
   the user replies "yes"/"no" (or any answer) to that approval, **Then** that reply is itself a
   new inbound conversational turn — routed through the same `_process_conversational_message`
   entry point as any other message — so the typing indicator appears again while DeniDin
   processes the approval and executes the approved action (e.g. the Morning MCP call), and
   stops the instant DeniDin sends its next message (e.g. a confirmation or error). No special
   handling is needed for this case; it falls out of the indicator firing on every inbound turn.
5. **Given** DeniDin's turn resolves to `[[NO_REPLY]]` (Feature 039 — no textual reply sent),
   **When** processing ends, **Then** no special "stop" handling is needed — the single
   fixed-duration `sendTyping` call (US3) simply isn't renewed, so the indicator lapses on its
   own shortly after.

## User Story 2 — Typing indicator does not fire for blocked users (Priority: P2)

A blocked user sends DeniDin a message. No typing indicator appears in their chat — consistent
with DeniDin already ignoring blocked users' messages outright.

**Why this priority**: A direct precedent from feature 045's read-receipt behavior (its Q4);
same reasoning applies here, not expected to need further debate.

**Independent Test**: Send a message from a number configured as blocked in a test/dev
environment's role config. Confirm no typing indicator appears on that device.

**Acceptance Scenarios**:

1. **Given** the sender's resolved role is `blocked`, **When** their message is received,
   **Then** no `sendTyping` call fires.

## User Story 3 — Single call only, no renewal (Priority: P2, final decision)

DeniDin sends exactly one `sendTyping(chatId, typingTime=20000)` call at the start of processing
a turn. There is no periodic resend for turns that run longer than 20 seconds — a permanent,
accepted v1 limitation, not an oversight.

**Why this priority**: A renewal loop (resend every 15s, capped at 180s) was built and
live-tested same day (2026-08-13) as a fix for the 20-second lapse, but surfaced a real,
unresolved bug of its own — at least one live test showed the renewer's first call delayed by
~20 seconds after starting, meaning the indicator wasn't showing for most of the turn anyway.
Root cause wasn't pinned down before the attempt was judged not worth the added complexity and
reverted. The single-call gap is the known, simpler, reliably-working tradeoff.

**Independent Test**: Trigger a real conversational turn, watched on a real device, and confirm
a single `sendTyping` call is made at the start of processing with no follow-up calls, regardless
of how long the turn actually takes.

**Acceptance Scenarios**:

1. **Given** DeniDin begins processing a conversational turn, **When** the turn starts, **Then**
   exactly one `sendTyping(chatId, typingTime=20000)` call is made — no resend, no renewal,
   regardless of how long the turn ultimately takes.
2. **Given** a turn takes longer than ~20 seconds, **When** the `typingTime` window elapses
   before the reply is ready, **Then** the indicator may lapse before the reply arrives — an
   accepted, permanent limitation, not a bug.

---

## User Story 4 — Typing dots also show while media is being processed (Priority: P1)

A client, godfather, or admin sends DeniDin an image, document, video, or audio file. While
`MediaHandler` is extracting/analyzing it — a step that can take a while (vision model calls,
multi-page PDF extraction) — the sender's WhatsApp client shows the typing indicator, same as
for a conversational turn.

**Why this priority**: Corrects a scope mistake (spec.md Q2) — media was originally excluded as
a default I (the assistant) set during the initial spec draft and never surfaced back for
explicit confirmation, unlike Q1/Q4. The user caught this live once images visibly had no
indicator, and the original request ("typing dots when processing") was never actually
text-only. Same priority as US1 — this is a correction to the core ask, not a lesser add-on.

**Independent Test**: Send a real image to DeniDin's number from a real device. Confirm the
typing indicator appears while it's being processed and disappears once the summary reply
arrives — same behavior as US1/US3, just via a separate call site
(`_process_media_message` in `denidin.py`, since `WhatsAppHandler` has no `bot`/API reference
to call `sendTyping` with directly).

**Acceptance Scenarios**:

1. **Given** a non-blocked sender sends an image/document/video/audio message, **When**
   `MediaHandler` begins processing it, **Then** the typing indicator appears, renewing every
   15s (US3's mechanism) until DeniDin sends its summary reply or an error message.
2. **Given** a blocked sender sends a media message, **When** it's received, **Then** no
   typing indicator fires — same precedent as US2.

---

## Explicitly Out of Scope

- Any change to feature 045's read-receipt (blue checkmark) behavior — a related but
  independent WhatsApp affordance using the same underlying client library. (Unlike the typing
  indicator, read-receipts already covered media messages from the start — `on_notification_
  received` fires pre-routing for every notification type.)
- The `typingType="recording"` audio-recording indicator — DeniDin doesn't send voice notes.
- Turns genuinely longer than 180 seconds — the indicator stops renewing at the cap (spec.md
  Q1), an accepted limit, not a bug.
