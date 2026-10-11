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

### User Story 6 — Media does not merge or interrupt (P2)

1. **Given** text handling is under way, **When** an image arrives, **Then** it is processed on
   its existing media path, is not merged into text and does not interrupt it.

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
