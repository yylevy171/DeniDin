# User Stories: Realistic Message Handling — Conversation Without "Turns"

**Feature Branch**: `feature/067-realistic-message-handling`
**Related Spec**: `spec.md` (same directory) — revised 2026-10-11 (Feature 090 folded in)

The earlier turn-based stories (discard-and-merge, reset after reply, feature-flag-OFF) are
**superseded**. There is no "turn", no "end of processing" and no feature flag.

---

## Model of operation (all stories)

```
WhatsApp message arrives → acknowledged and persisted at once, added to the chat's pending user messages
Whenever the model hands control back to the app (tool call, progress update, reaction,
recording, send_to_user, approval request, plain text), the app looks at:
   (A) what the model just sent        (B) pending user messages
and decides what is owed to the model and/or the user — merging A and B into the model's next input,
every user message carrying its timestamp and a before/after marker relative to the model's last output.
Nothing owed → nothing happens until the next WhatsApp message.
```

---

### User Story 1 — Additive burst is understood as one request (P1)

"book a meeting" → "with Dana" → "tomorrow at 3", sent quickly.

1. **Given** the model is working on message 1, **When** messages 2 and 3 arrive, **Then** they are
   persisted individually at once and handed to the model at its next hand-back.
2. **Given** that burst, **When** the model finally answers, **Then** the answer reflects all
   three messages.
3. **Given** the burst, **Then** history holds the three user messages individually, in order.

### User Story 2 — A long burst (P1)

The user sends ~10 messages in a row, very quickly.

1. **Given** message 1 arrives first, **Then** it is handed to the model immediately (no waiting).
2. **Given** several more arrive before the first hand-back, **When** the model hands back,
   **Then** the model's next input carries every message read since, in order.
3. **Given** the model's first output was based on message 1 alone, **Then** later input still
   reaches it; nothing is dropped.

### User Story 3 — "Do X" then "stop, don't do X" (P2)

1. **Given** the model proposes an approval-gated write for X and the user then writes "stop",
   **Then** the "stop" reaches the model at its next hand-back and the write never runs without
   the user's approval.
2. **Given** a write needs approval, **Then** nothing is created until the user approves.
3. **Given** the model's reply arrives while newer messages are waiting, **Then** the reply is
   sent as is, and the newer messages go to the model in its next input.

### User Story 4 — Something was already done (P2)

1. **Given** the model already performed an action server-side (e.g. a Morning document) before
   the correction arrived, **Then** its result is in the model's own chain and the final reply
   reports it truthfully and does not repeat it.

### User Story 5 — Timeline and confusion (P2)

1. **Given** user messages are handed to the model, **Then** each carries its timestamp and is
   marked as sent before or after the model's last output.
2. **Given** the sequence is genuinely confusing, **Then** the model may ask the user what to do
   next.

### User Story 6 — A single image fits in (P2)

1. **Given** nothing else is being handled, **When** an image arrives, **Then** it is handled at
   once, exactly as today.
2. **Given** the model is busy with a text request, **When** an image arrives, **Then** it is
   saved and acknowledged immediately, the model is told at its next hand-back that a file
   arrived (timestamp, caption), and the image is analyzed in its own exchange as soon as the
   current work is finished.
3. **Given** an image is being analyzed, **When** text arrives, **Then** the text is attached at
   the next hand-back like any other text.
4. **Given** several images in a row, **Then** they are handled one after another, as today
   (Feature 102 removes the wait).

### User Story 7 — Group chats, per chat (P3)

1. **Given** a group chat, **When** a second person writes while the model is working, **Then**
   their message joins that chat's stream and is handed over at the next hand-back.

### User Story 8 — Approval execution is protected (P3)

1. **Given** the user approved ("כן"/button) and the action is executing, **When** more messages
   arrive, **Then** the execution runs to completion once, its reply is sent, and the messages
   are handled afterwards.

### User Story 9 — Guards stay put (P3)

1. **Given** a pending approval, **When** unrelated messages arrive, **Then** a tap on its button
   is still honored; the stale-tap guard clears only when the approval is resolved, superseded or
   cancelled.
2. **Given** a chat idle longer than `capabilities_reset_minutes`, **Then** the idle reset still
   clears its loaded capabilities.
3. **Given** the model no longer needs a capability, **Then** it unloads it itself.

---

## Routing / dispatcher requirements

- The producer/hand-back machinery exists only behind the **live** message source;
  `PlayerExportSource` and the shared dispatch/handler code stay synchronous.
- `HANDLER_REGISTRY` stays exactly the current 8 message types.

---

## Acceptance Scenarios (`billed` / `expensive`) — DRAFT, awaiting human approval

*(METHODOLOGY §VI.a. Plain-language descriptions of what a real person does and sees. No test code
exists or will exist until the feature is code-complete. Each runs through the real webhook →
router → handler → backbone → OpenAI path; Morning scenarios use the real Morning sandbox via
MCP. Because replies are sent as they come back, scenarios assert on the **final state and on the
last answer**, not on an exact number of intermediate messages. Seeded state is wiped before and
after each test.)*

**A1 — Quick additive burst (`billed`) — US1, SC-001.**
The owner sends three short messages one right after another, e.g. "תפיק לי חשבונית", "ללקוח
דנה", "על 500 שקל", faster than DeniDin can answer the first. *They should see:* DeniDin ends up
with one coherent understanding — its final answer (e.g. the approval prompt) names Dana and
500 ₪, and never asks for something the later messages already said. All three user messages are
saved individually, in order.

**A2 — Long burst (`billed`) — US2, SC-002, SC-005.**
The owner sends ten short messages in a row very quickly (e.g. ten separate facts about one
invoice request). *They should see:* DeniDin starts answering after the first message without
waiting; nothing is lost — its final answer reflects every message (including the last one);
all ten are saved individually, in order, each with its timestamp.

**A3 — "Do X", then "stop, don't do X" (`billed`, Morning sandbox) — US3, SC-003.**
The owner asks for a receipt for a client, then immediately writes "עצור, אל תעשה את זה". *They
should see:* no document appears in Morning; DeniDin acknowledges the cancellation; if an
approval prompt was already shown, a later "כן" does not create anything unwanted.

**A4 — Message sent while an approved action is executing (`billed`, Morning sandbox) — US8,
US4, SC-004, SC-007.**
The owner approves a document ("כן") and, right away, sends "רגע, תבטל". *They should see:* the
approved document is created exactly once; DeniDin's reply states honestly that it was created
(with its number) and then deals with the cancel request (e.g. asks how to proceed); no second
document is ever created.

**A5 — Confusing sequence (`billed`) — US5.**
The owner sends "תשלח לדנה", then "לא, ליוסי", then "בעצם דנה". *They should see:* DeniDin either
settles correctly on Dana (using the timeline of the messages) or asks a short clarifying
question — it never silently picks the wrong person.

**A6 — Group chat, second person joins (`billed`) — US7.**
In a group, person A starts a request and person B adds a detail seconds later. *They should
see:* DeniDin's answer accounts for both messages; both are saved as separate user messages.

**A7 — Approval button still works after unrelated chatter (`billed`) — US9.**
DeniDin shows an approval prompt with buttons; the owner sends two unrelated messages; then taps
the button. *They should see:* the tap is honored (the action runs once); after the approval is
resolved, tapping the same button again does nothing.

**A8 — Image sent while a text request is being handled (`expensive` — vision call; needs its
own per-run approval) — US6.**
The owner sends a text request and, a moment later, an image. *They should see:* the text request
is answered normally; the image is then analyzed in its own exchange right after, and its content
is not mixed into the text request; nothing is lost or analyzed twice.

*Not covered by a `billed`/`expensive` scenario (existing or unit/integration coverage instead):*
idle capability reset (already tested), acknowledge-on-receipt, replay-player unchanged,
worker-failure continuation.
