# Research: Gate Zero — Real Button Round-Trip

**Feature**: 047-whatsapp-interactive-approval-buttons
**Date**: 2026-08-14
**Method**: Real `sendInteractiveButtons` calls against the **dev** Green API instance
(`green_api_instance_id` from `config/config.dev.json`), sent to the real godfather test
number (1:1) and to `קבוצה נסיונית עם דנידין` ("Experimental group with DeniDin", the
project's existing test group), tapped live on real devices. `denidin-app-dev` was stopped for
the duration (its polling loop would otherwise have consumed each notification before these
scripts could) and one-off scripts polled `receiveNotification` directly. Raw captured
payloads:
- [`gate-zero-captured-notifications.json`](./gate-zero-captured-notifications.json) — 1:1
  send + first tap (4 notifications: 3 outgoing-status updates for our own sent message, plus
  the 1 incoming tap reply).
- [`gate-zero-group-captured-notifications.json`](./gate-zero-group-captured-notifications.json)
  — group send + tap (5 notifications, same shape).
- [`gate-zero-repeat-tap-captured-notification.json`](./gate-zero-repeat-tap-captured-notification.json)
  — a second, different-button tap on the already-resolved 1:1 message (item 5).

This satisfies CONSTITUTION's NO UNVERIFIED THIRD-PARTY ASSUMPTIONS rule for the items below —
nothing here is inferred from documentation, all of it is a directly observed payload.

## What was sent

```python
buttons = [
    {"type": "reply", "buttonId": "gate_zero_yes", "buttonText": "אישור"},
    {"type": "reply", "buttonId": "gate_zero_no", "buttonText": "ביטול"},
]
api.sending.sendInteractiveButtons(
    chatId=chat_id, header="Gate Zero test", body="...", buttons=buttons, footer="DeniDin dev",
)
```

Note: `sendInteractiveButtons` **requires** `"type": "reply"` on every button — omitting it is a
hard validation failure (`400`, `'buttons[0].type' is required`), confirmed live on the first
attempt before adding it.

## Findings, against the 6 questions Gate Zero posed

### 1. The exact `typeMessage` a tapped button produces
A tap arrives as its own top-level webhook: `typeWebhook: "incomingMessageReceived"`, with
`messageData.typeMessage: "interactiveButtonsResponse"`. This is a **new message type**, not
carried on the original `interactiveButtons` type — the router needs a new case for it (today it
would fall into the catch-all, `handle_unsupported_message_default`, same as any other
unrecognized type).

Sending itself also produces 3 additional `outgoingMessageStatus` webhooks (`sent` → `delivered`
→ `read`) that any new router branch must not misinterpret as a reply — they carry no
`messageData` at all.

### 2. Where the identifier lives, and whether the label is also carried
Both are present, in **separate fields**, confirmed distinct:
- `messageData.interactiveButtonsResponse.selectedId` — the identifier (`"gate_zero_yes"`),
  exactly what we sent as `buttonId`. **This is what to key on.**
- `messageData.interactiveButtonsResponse.selectedDisplayText` — the label (`"אישור"`), display
  text only.
- `messageData.interactiveButtonsResponse.selectedIndex` — positional index (`0`), also
  available if ever needed, but `selectedId` is the stable key.

### 3. Whether the reply is linked to the original message
Yes. **Two** independent pointers back to the original outbound `idMessage`
(`"3EB0C93530F6E687164133"`), both present on the reply:
- `messageData.interactiveButtonsResponse.stanzaId`
- `messageData.quotedMessage.stanzaId` (alongside a full echo of the original button set/labels
  in `quotedMessage.interactiveButtons`)

This means a tap **can** be bound to one specific pending approval (match on `stanzaId` ==
the `idMessage` returned when the buttons were sent), not just "whatever's currently pending in
this chat" — resolves the open question in Gate Zero item 3 in favor of the more precise design.

### 4. Behaviour in group chats
**Confirmed.** Sent to `120363410226011645@g.us` (the project's existing test group). Payload
shape is identical to 1:1 — same `interactiveButtonsResponse` structure, same `stanzaId`
linkage — with two differences to design around:
- `senderData.chatId` is the **group's** id, but `senderData.sender`/`senderName` correctly
  identify the **specific member who tapped** (not the group) — so per-tapper attribution is
  free, same as any other group message.
- No new information about *who else can see/tap* the buttons was gathered — WhatsApp's own
  group semantics presumably mean any member can tap, same as any member can type; nothing
  observed suggests buttons are restricted to whoever the message was "addressed to". Open
  question 3 in spec.md (should buttons even appear in groups) is a product decision, not
  something this round-trip resolves either way.

### 5. Behaviour on a stale/already-resolved button
**Confirmed.** A second tap — a *different* button (`gate_zero_no`) — on the same original 1:1
message, after the first tap had already been processed (by this script, i.e. "resolved"),
produced a completely ordinary second `interactiveButtonsResponse` notification, same
`stanzaId`, no error, no block, no WhatsApp-side indication the message was "already answered".
**WhatsApp/Green API imposes no restriction whatsoever on re-tapping** — buttons remain live
and tappable indefinitely, and every tap (first, second, or Nth, same or different button)
produces an identical, independent notification. This means the entire staleness/idempotency
guard — recognizing that a given `stanzaId` already has a resolved outcome and refusing to
act on a later tap — **must live entirely in our own application code**. WhatsApp will not do
any of this for us.

### 6. Whether buttons render on the real paid WhatsApp Business numbers this project uses
**Confirmed for dev.** The message rendered as native WhatsApp interactive buttons and was
tappable on a real device, real dev number, real Green API instance. Prod uses separate
infrastructure (own Green API instance/number, per CLAUDE.md's 2026-08-03 asymmetry note) and
was not tested here — no reason to expect divergence, but not itself confirmed.

## Gate Zero status: CLOSED (2026-08-14)

All 6 questions Gate Zero posed are now answered against real, captured payloads. `plan.md` may
proceed.

## Design implications carried forward from these findings

- The router needs a new case for `typeMessage == "interactiveButtonsResponse"` (currently falls
  into the unsupported-type catch-all) — separate from the existing `outgoingMessageStatus`
  webhooks, which carry no `messageData` and must not be mistaken for a reply.
- Bind a tap to a specific pending approval by matching
  `messageData.interactiveButtonsResponse.stanzaId` against the `idMessage` returned when the
  buttons were originally sent — never "whatever's currently pending in this chat".
- Key exclusively on `selectedId` (`buttonId`), never `selectedDisplayText` (the label) —
  confirmed genuinely distinct fields.
- The idempotency/staleness guard (US3) is 100% an application-level responsibility — nothing
  upstream prevents a second tap, on the same or a different button, on an already-resolved
  message.
- Group taps arrive with correct per-member attribution via `senderData.sender`, so RBAC/audit
  can identify the actual tapper same as any typed group message.
